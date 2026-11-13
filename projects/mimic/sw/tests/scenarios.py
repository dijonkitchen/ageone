"""Scenarios that run on the golden model (pytest) and on the RTL (cocotb, in lockstep).

Each scenario is an `async def (bench) -> None` that loads programs through the SPI host
port, drives peripherals, and asserts on what comes back. Register a scenario in ALL.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from mimic import assemble, isa
from mimic.bench import Bench

Scenario = Callable[[Bench], Awaitable[None]]
ALL: dict[str, Scenario] = {}


def scenario(fn: Scenario) -> Scenario:
    ALL[fn.__name__] = fn
    return fn


@scenario
async def chip_id(b: Bench) -> None:
    assert await b.read(isa.REG_ID) == [isa.CHIP_ID]
    await b.write(isa.REG_PADCTRL, 0xA5)
    assert await b.read(isa.REG_PADCTRL) == [0xA5]
    await b.write(isa.REG_PADCTRL, 0)


@scenario
async def blink(b: Bench) -> None:
    prog = assemble(
        """
        .set_pins uio0 2
        .pindirs uio0 uio1
            set pins, 1 [3]
            set pins, 2 [3]
        """
    )
    await b.load(prog, 0, start=True)
    seen = []
    for _ in range(16):
        await b.step()
        seen.append(b.uio_out & 3)
    assert b.uio_oe & 3 == 3
    # Each level holds for 4 cycles (1 + 3 delay).
    runs = "".join(str(v) for v in seen)
    assert "1111" in runs and "2222" in runs and "11111" not in runs, runs


@scenario
async def fifo_echo(b: Bench) -> None:
    prog = assemble(
        """
            pull
            mov isr, ~osr
            push
        """
    )
    await b.load(prog, 1, start=True)
    words = [0, 1, 0xDEADBEEF, 0x80000000, 0x12345678]
    await b.put(1, *words[:2])
    got = await b.get(1, 2)
    await b.put(1, *words[2:])
    got += await b.get(1, 3)
    assert got == [(~w) & isa.M32 for w in words], [hex(g) for g in got]


# ---------------------------------------------------------------------------
# Random differential tests: any bit pattern is a valid instruction, so random words,
# random configuration, random pin activity and random host traffic exercise every
# encoding. On the model they only check for crashes; under cocotb the lockstep compare
# holds the RTL to the model every cycle.
# ---------------------------------------------------------------------------

import random  # noqa: E402

from mimic.bench import Peripheral  # noqa: E402


class PinNoise(Peripheral):
    """Toggles board-driven pins at random: ui0-4 and uio0-7 (when the chip is not driving)."""

    def __init__(self, rng: random.Random, rate: float = 0.05) -> None:
        self.rng = rng
        self.rate = rate

    def tick(self, bench: Bench) -> None:
        for g in [*range(8), *range(16, 21)]:
            if self.rng.random() < self.rate:
                choice = self.rng.random()
                bench.drive(g, None if (choice < 0.3 and g < 8) else self.rng.getrandbits(1))


def random_instr(rng: random.Random) -> int:
    """A random instruction word, shaped so programs keep moving (most waits time out)."""
    op = rng.choices(range(16), weights=[7, 3, 6, 6, 4, 7, 2, 6, 5, 5, 1, 1, 1, 1, 1, 1])[0]
    junk = rng.getrandbits(20) if rng.random() < 0.3 else 0  # set unused bits sometimes
    sd = rng.getrandbits(8) if rng.random() < 0.1 else rng.getrandbits(2)
    r = rng.getrandbits
    if op == isa.OP_JMP:
        cond = rng.randrange(18) if rng.random() < 0.9 else rng.randrange(32)
        args = (cond << 15) | (r(1) << 14) | (r(5) << 9) | r(6) | (junk & (7 << 6))
    elif op == isa.OP_WAIT:
        src = rng.choice([0, 0, 1, 1, 2, 2, 3, rng.randrange(8)])
        tmo = int(rng.random() < 0.85)
        args = (r(1) << 19) | (src << 16) | (tmo << 15) | (r(1) << 14) | (r(5) << 9) | (junk & 0x1FF)
    elif op in (isa.OP_IN, isa.OP_OUT):
        args = (r(4) << 16) | (r(5) << 4) | r(4) | (junk & 0xFE00)
    elif op == isa.OP_PUSHPULL:
        args = (r(1) << 19) | (r(1) << 18) | (int(rng.random() < 0.5) << 17) | (junk & 0x1FFFF)
    elif op == isa.OP_IRQ:
        wait = int(rng.random() < 0.15)
        args = (r(1) << 19) | (wait << 18) | (r(1) << 14) | (r(3) << 9) | (junk & 0x31FF)
    elif op == isa.OP_SET:
        imm = r(4) if rng.random() < 0.7 else r(16)
        args = (r(4) << 16) | imm
    else:
        args = r(20)
    return (op << 28) | (sd << 20) | args


def random_config(rng: random.Random, sm: int) -> list[tuple[int, int]]:
    regs = [
        (isa.SM_CLKDIV, (rng.choice([1, 1, 1, 2, 3]) << 16) | (rng.choice([0, 0, 0x40, 0x80]) << 8)),
        (isa.SM_EXECCTRL, rng.getrandbits(28)),
        (isa.SM_SHIFTCTRL, rng.getrandbits(23) & ~(3 << 16) | (rng.choice([0, 0, 1, 2]) << 16)),
        (isa.SM_PINCTRL, rng.getrandbits(26)),
        (isa.SM_CRCCFG, rng.getrandbits(3)),
    ]
    return [(isa.sm_reg(sm, r), v) for r, v in regs]


async def random_isa(b: Bench, seed: int, cycles: int = 6000) -> None:
    rng = random.Random(seed)
    b.add(PinNoise(rng))
    words = [random_instr(rng) for _ in range(isa.IMEM_WORDS)]
    await b.write(isa.REG_IMEM, *words)
    if hasattr(b.dev, "check_every"):
        b.dev.check_every = 1  # compare SM registers with the model every cycle
    for sm in range(4):
        for addr, v in random_config(rng, sm):
            await b.write(addr, v)
        await b.exec(sm, isa.enc_set(isa.DST["x"], rng.randrange(64)))
        await b.exec(sm, isa.enc_jmp(0, rng.randrange(64)))
    await b.write(isa.REG_PADCTRL, rng.getrandbits(8))
    await b.write(isa.REG_CTRL, isa.pack_ctrl(enable=15, div_restart=15))
    end = b.cycle + cycles
    while b.cycle < end:
        r = rng.random()
        sm = rng.randrange(4)
        if r < 0.25:
            # Small and special values make equal operands and zeros likely.
            v = rng.choice([0, 1, 2, 3, isa.M32, 0x80000000, rng.getrandbits(32), rng.getrandbits(32)])
            await b.write(isa.sm_reg(sm, isa.SM_TXF), v, inc=False)
        elif r < 0.45:
            await b.read(isa.sm_reg(sm, isa.SM_RXF), rng.randint(1, 3), inc=False)
        elif r < 0.55:
            await b.write(isa.REG_IRQ if rng.random() < 0.5 else isa.REG_IRQ_FORCE, rng.getrandbits(8))
        elif r < 0.62:
            await b.read(isa.sm_reg(sm, rng.choice([isa.SM_INSTR, isa.SM_PC, isa.SM_X, isa.SM_Y, isa.SM_STAT])))
        elif r < 0.68:
            await b.read(rng.choice([isa.REG_FLEVEL, isa.REG_FDEBUG, isa.REG_PINS, isa.REG_PINOUT, isa.REG_PINOE]))
        elif r < 0.71:
            await b.exec(sm, random_instr(rng))
        elif r < 0.73:
            await b.exec(sm, isa.enc_jmp(0, rng.randrange(64)))  # unstick
        elif r < 0.77:
            addr, v = rng.choice(random_config(rng, sm))
            await b.write(addr, v)
        elif r < 0.80:
            await b.write(isa.REG_IMEM + rng.randrange(64), random_instr(rng))
        elif r < 0.83:
            ctrl = isa.pack_ctrl(
                enable=rng.getrandbits(4) | rng.getrandbits(4),
                restart=rng.getrandbits(4) & rng.getrandbits(4),
                div_restart=rng.getrandbits(4),
                step=rng.getrandbits(4),
                tx_clear=rng.getrandbits(4) & rng.getrandbits(4),
                rx_clear=rng.getrandbits(4) & rng.getrandbits(4),
            )
            await b.write(isa.REG_CTRL, ctrl)
        elif r < 0.85:
            await b.write(isa.REG_FDEBUG, rng.getrandbits(20))
        else:
            await b.step(rng.randint(1, 60))


def _random_scenario(seed: int) -> Scenario:
    async def run(b: Bench) -> None:
        await random_isa(b, seed)

    run.__name__ = f"random_isa_{seed}"
    return run


for _seed in range(6):
    ALL[f"random_isa_{_seed}"] = _random_scenario(_seed)


# ---------------------------------------------------------------------------
# UART
# ---------------------------------------------------------------------------

from mimic import periph, programs  # noqa: E402

UART_TX_PIN = 8  # uo0
UART_RX_PIN = 16  # ui0


@scenario
async def uart_tx(b: Bench) -> None:
    div = 2
    rx = b.add(periph.UartRx(UART_TX_PIN, bit=8 * div))
    await b.load(programs.load("uart_tx", TX=UART_TX_PIN, DIV=div), 0, start=True)
    data = b"Mimic\x00\xff\x55"
    await b.put(0, *data)
    await b.until(lambda: len(rx.data) == len(data), what="UART bytes")
    assert bytes(rx.data) == data and rx.framing_errors == 0, rx.data


@scenario
async def uart_rx(b: Bench) -> None:
    div = 6  # the host polls over SPI; keep the line slower than the host
    tx = b.add(periph.UartTx(UART_RX_PIN, bit=8 * div))
    await b.load(programs.load("uart_rx", RX=UART_RX_PIN, DIV=div), 2, start=True)
    data = b"\x00\xa5\xff\x01ok"
    tx.send(data)
    got = await b.get(2, len(data))
    assert bytes(got) == data, got
    # A framing error raises IRQ 2 (0 + SM2) and drops the byte; the next byte still arrives.
    tx.send(b"\x33", framing_error=True)
    await b.until(lambda: tx.idle, what="bad frame sent")
    await b.step(8 * div * 2)  # the line idles before the next frame, as after any break
    tx.send(b"\x44")
    got = await b.get(2, 1)
    assert got == [0x44], got
    assert (await b.read(isa.REG_IRQ))[0] & (1 << 2)


@scenario
async def uart_bridge(b: Bench) -> None:
    """UART RX on SM0 routed into UART TX on SM1 at a different baud: no host in the data path."""
    tx = b.add(periph.UartTx(UART_RX_PIN, bit=8 * 3))
    rx = b.add(periph.UartRx(UART_TX_PIN, bit=8 * 2.5))
    rx_prog = programs.load("uart_rx", RX=UART_RX_PIN, DIV=3)
    rx_prog.config.route = True
    await b.load(rx_prog, 0, origin=0)
    tx_prog = programs.load("uart_tx", TX=UART_TX_PIN)
    tx_prog.config.clkdiv = 2.5  # fractional divider
    await b.load(tx_prog, 1, origin=16)
    await b.start(0b11)
    data = b"bridge!"
    tx.send(data)
    await b.until(lambda: len(rx.data) == len(data), limit=20_000, what="bridged bytes")
    assert bytes(rx.data) == data, rx.data


# ---------------------------------------------------------------------------
# SPI, I2C, WS2812
# ---------------------------------------------------------------------------

from mimic import protocols  # noqa: E402

SPI_CS, SPI_MOSI, SPI_MISO, SPI_SCK = 0, 1, 2, 3  # uio0-3, the Pmod SPI layout


def _spi_ctrl(mode: int) -> Scenario:
    async def run(b: Bench) -> None:
        reply = bytes([0x5A, 0x01, 0xFE, 0x80])
        dev = b.add(periph.SpiTarget(SPI_SCK, SPI_MOSI, SPI_MISO, SPI_CS, mode=mode, reply=reply))
        prog = programs.load("spi_ctrl", CPOL=mode >> 1, CPHA=mode & 1, DIV=4)
        await b.load(prog, 3, start=True)
        data = bytes([0xA5, 0x3C, 0x00, 0xFF])
        for chunk in (data[:1], data[1:]):
            await b.put(3, *protocols.spi_words(chunk))
        got = await b.get(3, 4)
        await b.until(lambda: len(dev.transactions) == 2, what="CS deasserted")
        assert dev.transactions == [data[:1], data[1:]], dev.transactions
        assert bytes(got) == reply, [hex(g) for g in got]
        assert not b.contention

    run.__name__ = f"spi_ctrl_mode{mode}"
    return run


for _mode in range(4):
    ALL[f"spi_ctrl_mode{_mode}"] = _spi_ctrl(_mode)


@scenario
async def spi_target(b: Bench) -> None:
    ctl = b.add(periph.SpiController(SPI_SCK, SPI_MOSI, SPI_MISO, SPI_CS, half=10))
    await b.load(programs.load("spi_target"), 1, start=True)
    await b.put(1, 0xC3 << 24, 0x7E << 24)
    ctl.transfer(bytes([0x12, 0x34, 0x56]))
    await b.until(lambda: ctl.idle, what="SPI transfer")
    assert ctl.received == [bytes([0xC3, 0x7E, 0xFF])], ctl.received
    got = await b.get(1, 3)
    assert got == [0x12, 0x34, 0x56], got


async def _i2c(b: Bench, stretch: int) -> None:
    dev = b.add(periph.I2CTarget(scl=2, sda=3, addr=0x50, stretch=stretch))
    await b.load(programs.load("i2c", SCL=2, SDA=3, DIV=4), 0, start=True)
    # Write two bytes at register 0x10, then set the pointer back and read them.
    slots = protocols.i2c_write(0x50, bytes([0x10, 0xCA, 0xFE]))
    slots += protocols.i2c_write(0x50, bytes([0x10]), stop=False) + protocols.i2c_read(0x50, 2)
    results: list[int] = []
    for s in slots:
        await b.put(0, s)
        if (await b.levels(0))[1]:
            results += await b.get(0, (await b.levels(0))[1])
    results += await b.get(0, len(slots) - len(results))
    # Slots: 4 for the write, 2 to set the pointer, 1 address for the read, 2 data bytes.
    assert all(protocols.i2c_acked(r) for r in results[:7]), [hex(r) for r in results]
    assert [protocols.i2c_byte(r) for r in results[7:]] == [0xCA, 0xFE], [hex(r) for r in results]
    assert dev.mem[0x10:0x12] == b"\xca\xfe"
    await b.until(lambda: dev.log[-1] == "P", what="STOP")
    # A missing target does not ACK.
    await b.put(0, *protocols.i2c_write(0x23, b""))
    assert not protocols.i2c_acked((await b.get(0, 1))[0])
    assert not b.contention
    if stretch:
        assert dev.stretched > 0, "the target never held SCL low after the controller released it"


@scenario
async def i2c(b: Bench) -> None:
    await _i2c(b, stretch=0)


@scenario
async def i2c_stretch(b: Bench) -> None:
    await _i2c(b, stretch=40)


@scenario
async def ws2812(b: Bench) -> None:
    div = 2
    leds = b.add(periph.Ws2812(9, threshold=int(4.5 * div), reset=60 * div))
    await b.load(programs.load("ws2812", DOUT=9, DIV=div), 2, start=True)
    colors = [0xFF0000, 0x00FF00, 0x0000FF, 0x123456]
    await b.put(2, *[protocols.ws2812_word(c) for c in colors])
    await b.until(lambda: len(leds.frames) == 1, what="LED frame")
    assert leds.frames[0] == colors, [hex(c) for c in leds.frames[0]]
