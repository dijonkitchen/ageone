"""A board around the chip: pins, peripherals, and the RP2350's SPI host, cycle by cycle.

The bench drives any `Device` (the golden model here, the RTL under cocotb in test/),
so every protocol scenario runs unchanged on both. Peripheral models (mimic.periph) see
pin levels after each clock edge and set what they drive for the next one.

GPIO numbering is the chip's: 0-7 uio, 8-14 uo, 16-23 ui (21-23 carry the host port).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol

from . import host, isa
from .asm import Program
from .model import Mimic


class Device(Protocol):
    async def clock(self, ui_in: int, uio_in: int) -> tuple[int, int, int]: ...


class ModelDevice:
    def __init__(self, model: Mimic | None = None) -> None:
        self.model = model or Mimic()

    async def clock(self, ui_in: int, uio_in: int) -> tuple[int, int, int]:
        return self.model.clock(ui_in, uio_in)


class Peripheral:
    """Something on the board. `tick` runs once per cycle after the clock edge."""

    def tick(self, bench: Bench) -> None:
        raise NotImplementedError


HOST_CSN, HOST_SCK, HOST_MOSI = 5, 6, 7  # ui bits
HOST_MISO = 7  # uo bit


class Bench:
    def __init__(self, dev: Device, sck_period: int = 8, pullup: int = 0xFF) -> None:
        if sck_period < 6 or sck_period % 2:
            raise ValueError("SCK period must be an even number of cycles, at least 6")
        self.dev = dev
        self.sck_period = sck_period
        self.pullup = pullup  # uio pins with a pull-up (others float low)
        self.periphs: list[Peripheral] = []
        self.drives: dict[int, int] = {}  # external drivers: GPIO -> level (uio pins are wired-AND)
        self.host_bits = 1 << HOST_CSN  # CS_N idle high
        self.uo = 0
        self.uio_out = 0
        self.uio_oe = 0
        self.cycle = 0
        self.contention: list[tuple[int, int]] = []  # (cycle, gpio) where chip and board fought
        self.loader = host.Loader()
        self.monitors: list[Callable[[Bench], None]] = []
        self.join_tx: dict[int, bool] = {}

    # ---- pins ---------------------------------------------------------------
    def add(self, p: Peripheral) -> Peripheral:
        self.periphs.append(p)
        return p

    def drive(self, gpio: int, level: int | None) -> None:
        """Drive a uio (0-7) or ui (16-20) pin from the board; None releases it."""
        if level is None:
            self.drives.pop(gpio, None)
        else:
            self.drives[gpio] = level & 1

    def _uio_bus(self) -> int:
        v = 0
        for i in range(8):
            if self.uio_oe >> i & 1:
                bit = self.uio_out >> i & 1
            elif i in self.drives:
                bit = self.drives[i]
            else:
                bit = self.pullup >> i & 1
            v |= bit << i
        return v

    def level(self, gpio: int) -> int:
        """The level a board device sees on a GPIO now."""
        if gpio < 8:
            return self._uio_bus() >> gpio & 1
        if gpio < 16:
            return self.uo >> (gpio - 8) & 1
        if gpio < 24:
            return self._ui() >> (gpio - 16) & 1
        raise ValueError(f"GPIO {gpio} is internal")

    def _ui(self) -> int:
        v = self.host_bits
        for g, lv in self.drives.items():
            if 16 <= g < 24 and (g - 16) not in (HOST_CSN, HOST_SCK, HOST_MOSI):
                v |= lv << (g - 16)
        return v

    # ---- time ---------------------------------------------------------------
    async def step(self, n: int = 1) -> None:
        for _ in range(n):
            for i in range(8):
                if self.uio_oe >> i & 1 and i in self.drives and self.drives[i] != (self.uio_out >> i & 1):
                    self.contention.append((self.cycle, i))
            self.uo, self.uio_out, self.uio_oe = await self.dev.clock(self._ui(), self._uio_bus())
            self.cycle += 1
            for p in self.periphs:
                p.tick(self)
            for m in self.monitors:
                m(self)

    async def until(self, cond: Callable[[], bool], limit: int = 100_000, what: str = "condition") -> int:
        start = self.cycle
        while not cond():
            if self.cycle - start >= limit:
                raise TimeoutError(f"{what} not met in {limit} cycles")
            await self.step()
        return self.cycle - start

    # ---- host SPI -----------------------------------------------------------
    def _set_host(self, csn: int, sck: int, mosi: int) -> None:
        self.host_bits = (csn << HOST_CSN) | (sck << HOST_SCK) | (mosi << HOST_MOSI)

    async def spi(self, tx: bytes) -> bytes:
        """One SPI mode-0 transfer with CS_N low throughout; returns the bytes read on MISO."""
        h = self.sck_period // 2
        self._set_host(0, 0, 0)
        await self.step(h)
        rx = bytearray()
        for byte in tx:
            r = 0
            for b in range(7, -1, -1):
                self._set_host(0, 0, byte >> b & 1)
                await self.step(h)
                r = (r << 1) | (self.uo >> HOST_MISO & 1)  # sampled on the rising edge
                self._set_host(0, 1, byte >> b & 1)
                await self.step(h)
            rx.append(r)
        self._set_host(0, 0, 0)
        await self.step(h)
        self._set_host(1, 0, 0)
        await self.step(4)
        return bytes(rx)

    async def run(self, ops: list[host.Op]) -> list[list[int]]:
        results = []
        for op in ops:
            rx = await self.spi(host.frame(op))
            if op.is_read:
                results.append(host.parse_read(rx, op.count))
        return results

    async def write(self, addr: int, *words: int, inc: bool = True) -> None:
        await self.run([host.write(addr, *words, inc=inc)])

    async def read(self, addr: int, count: int = 1, inc: bool = True) -> list[int]:
        return (await self.run([host.read(addr, count, inc)]))[0]

    async def load(self, prog: Program, sm: int, origin: int | None = None, start: bool = False) -> None:
        self.join_tx[sm] = prog.config.join_tx
        await self.run(self.loader.load(prog, sm, origin, start))

    async def start(self, mask: int) -> None:
        await self.run(self.loader.start(mask))

    async def stop(self, mask: int) -> None:
        await self.run(self.loader.stop(mask))

    async def put(self, sm: int, *words: int) -> None:
        """Write words to an SM's TX FIFO, as many per SPI frame as there is room for."""
        todo = list(words)
        while todo:
            room = self.tx_capacity(sm) - (await self.levels(sm))[0]
            if room <= 0:
                await self.step(16)
                continue
            await self.write(isa.sm_reg(sm, isa.SM_TXF), *todo[:room], inc=False)
            todo = todo[room:]

    def tx_capacity(self, sm: int) -> int:
        return isa.FIFO_DEPTH * 2 if self.join_tx.get(sm) else isa.FIFO_DEPTH

    async def get(self, sm: int, count: int = 1, limit: int = 200_000) -> list[int]:
        """Read `count` words from an SM's RX FIFO, waiting for each."""
        out: list[int] = []
        start = self.cycle
        while len(out) < count:
            _, rx = await self.levels(sm)
            if rx:
                out += await self.read(isa.sm_reg(sm, isa.SM_RXF), min(rx, count - len(out)), inc=False)
            elif self.cycle - start > limit:
                raise TimeoutError(f"SM{sm} RX: got {len(out)} of {count} words")
            else:
                await self.step(16)
        return out

    async def levels(self, sm: int) -> tuple[int, int]:
        v = (await self.read(isa.REG_FLEVEL))[0] >> (8 * sm)
        return v & 15, (v >> 4) & 15

    async def exec(self, sm: int, instr: int) -> None:
        await self.run([host.force(sm, instr)])

    async def peek(self, sm: int, src: str) -> int:
        """Read an SM register through X: force `mov x, src`, read X (X is clobbered)."""
        await self.exec(sm, isa.enc_mov(isa.DST["x"], isa.SRC[src]))
        return (await self.read(isa.sm_reg(sm, isa.SM_X)))[0]


def run(coro_fn: Callable[[Bench], Awaitable[None]], bench: Bench | None = None) -> Bench:
    """Run a scenario on the golden model (pytest uses this)."""
    b = bench or Bench(ModelDevice())
    asyncio.run(_run(coro_fn, b))
    return b


async def _run(coro_fn: Callable[[Bench], Awaitable[None]], b: Bench) -> None:
    await coro_fn(b)
