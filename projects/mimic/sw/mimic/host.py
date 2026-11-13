"""Host side of the Mimic SPI port: frames, the program loader, and a driver.

Everything the host does is a list of register operations (`Op`), so the same loader runs
over a real SPI bus (`Host`, e.g. on the demo board's RP2350), the cocotb testbench, and
the golden model (`mimic.bench`).

Frame (SPI mode 0, MSB first, CS_N low for the whole frame):
    write: [0x80 | INC<<6] [addr] then 4 bytes per word
    read:  [0x00 | INC<<6] [addr] [dummy] then 4 bytes per word on MISO
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import isa
from .asm import Program


@dataclass(frozen=True)
class Op:
    """A host register access: write `words` to `addr`, or read `count` words from it."""

    addr: int
    words: tuple[int, ...] = ()
    count: int = 0
    inc: bool = True

    @property
    def is_read(self) -> bool:
        return self.count > 0


def write(addr: int, *words: int, inc: bool = True) -> Op:
    return Op(addr, tuple(w & isa.M32 for w in words), 0, inc)


def read(addr: int, count: int = 1, inc: bool = True) -> Op:
    return Op(addr, (), count, inc)


def frame(op: Op) -> bytes:
    """Bytes the host sends for `op` (for a read, the MISO bytes after the 3-byte header are data)."""
    cmd = (0x80 if not op.is_read else 0x00) | (0x40 if op.inc else 0x00)
    if op.is_read:
        return bytes([cmd, op.addr & 0xFF, 0]) + bytes(4 * op.count)
    return bytes([cmd, op.addr & 0xFF]) + b"".join(w.to_bytes(4, "big") for w in op.words)


def parse_read(rx: bytes, count: int) -> list[int]:
    data = rx[3 : 3 + 4 * count]
    return [int.from_bytes(data[4 * i : 4 * i + 4], "big") for i in range(count)]


def force(sm: int, instr: int) -> Op:
    """Run `instr` on state machine `sm` on the next cycle, enabled or not."""
    return write(isa.sm_reg(sm, isa.SM_INSTR), instr)


class Loader:
    """Builds the register writes that load and configure programs.

    It keeps a shadow of the chip-wide registers it shares between programs (CTRL enables,
    PADCTRL open-drain bits), so loading one state machine never disturbs the others.
    """

    def __init__(self) -> None:
        self.enabled = 0
        self.opendrain = 0

    def ctrl(self, **pulses: int) -> Op:
        return write(isa.REG_CTRL, isa.pack_ctrl(enable=self.enabled, **pulses))

    def load(self, prog: Program, sm: int, origin: int | None = None, start: bool = False) -> list[Op]:
        """Ops that stop `sm`, load `prog` at `origin`, configure `sm` for it, and leave it at the entry."""
        o = prog.origin if origin is None else origin
        if o + len(prog.instrs) > isa.IMEM_WORDS:
            raise ValueError(f"{prog.name}: {len(prog.instrs)} instructions at {o} overflow the memory")
        cfg = prog.config
        bit = 1 << sm
        ops: list[Op] = []
        self.enabled &= ~bit
        ops.append(self.ctrl())
        ops.append(write(isa.REG_IMEM + o, *prog.at(o)))
        ops.append(write(isa.sm_reg(sm, isa.SM_CLKDIV), isa.pack_clkdiv(cfg.clkdiv)))
        execctrl = isa.pack_execctrl(
            wrap_bottom=o + prog.wrap_target,
            wrap_top=o + prog.wrap,
            side_base=cfg.side_base,
            side_count=prog.side_count + int(prog.side_opt),
            side_en=prog.side_opt,
            side_pindirs=prog.side_pindirs,
            status_sel=cfg.status_sel,
            status_n=cfg.status_n,
        )
        ops.append(write(isa.sm_reg(sm, isa.SM_EXECCTRL), execctrl))
        shiftctrl = isa.pack_shiftctrl(
            in_right=cfg.in_right,
            out_right=cfg.out_right,
            autopush=cfg.autopush,
            autopull=cfg.autopull,
            push_thresh=cfg.push_thresh,
            pull_thresh=cfg.pull_thresh,
            join_tx=cfg.join_tx,
            join_rx=cfg.join_rx,
            route=cfg.route,
        )
        # No join while we pass setup values through the TX FIFO; the real value goes last.
        ops.append(write(isa.sm_reg(sm, isa.SM_SHIFTCTRL), shiftctrl & ~(3 << 16)))
        ops.append(
            write(isa.sm_reg(sm, isa.SM_CRCCFG), isa.pack_crccfg(cfg.crc_reflect, cfg.crc_feed_out, cfg.crc_feed_in))
        )
        ops.append(self.ctrl(tx_clear=bit, rx_clear=bit))

        # Values the program expects in registers, passed through the TX FIFO.
        def via_osr(dst: str, value: int) -> list[Op]:
            return [
                write(isa.sm_reg(sm, isa.SM_TXF), value),
                force(sm, isa.enc_pull(block=False)),
                force(sm, isa.enc_mov(isa.DST[dst], isa.SRC["osr"])),
            ]

        if cfg.crc_poly is not None:
            ops += via_osr("poly", cfg.crc_poly)
            ops += via_osr("crc", cfg.crc_init)
        if cfg.x is not None:
            ops += via_osr("x", cfg.x)
        if cfg.y is not None:
            ops += via_osr("y", cfg.y)

        # Initial pin levels and directions, one pin at a time through SET.
        pinctrl = isa.pack_pinctrl(cfg.out_base, cfg.out_count, cfg.set_base, cfg.set_count, cfg.in_base)
        for p, v in sorted(cfg.initial.items()):
            ops.append(write(isa.sm_reg(sm, isa.SM_PINCTRL), isa.pack_pinctrl(set_base=p, set_count=1)))
            ops.append(force(sm, isa.enc_set(isa.DST["pins"], v)))
        for p in sorted(set(cfg.pindirs_out)):
            ops.append(write(isa.sm_reg(sm, isa.SM_PINCTRL), isa.pack_pinctrl(set_base=p, set_count=1)))
            ops.append(force(sm, isa.enc_set(isa.DST["pindirs"], 1)))
        ops.append(write(isa.sm_reg(sm, isa.SM_PINCTRL), pinctrl))

        if cfg.opendrain:
            for p in cfg.opendrain:
                if p > 7:
                    raise ValueError(f"{prog.name}: only GPIO 0-7 (uio) can be open-drain, not {p}")
                self.opendrain |= 1 << p
            ops.append(write(isa.REG_PADCTRL, self.opendrain))

        ops.append(write(isa.sm_reg(sm, isa.SM_SHIFTCTRL), shiftctrl))
        ops.append(self.ctrl(restart=bit, div_restart=bit, tx_clear=bit, rx_clear=bit))
        ops.append(force(sm, isa.enc_jmp(0, o)))
        if start:
            ops += self.start(bit)
        return ops

    def start(self, mask: int) -> list[Op]:
        """Enable the SMs in `mask` together, with their clock dividers in phase."""
        self.enabled |= mask
        return [self.ctrl(div_restart=mask)]

    def stop(self, mask: int) -> list[Op]:
        self.enabled &= ~mask
        return [self.ctrl()]


Transport = Callable[[bytes], bytes]


class Host:
    """Synchronous driver over any full-duplex SPI transfer function (CS low for one call)."""

    def __init__(self, xfer: Transport) -> None:
        self.xfer = xfer
        self.loader = Loader()

    def run(self, ops: list[Op]) -> list[list[int]]:
        results = []
        for op in ops:
            rx = self.xfer(frame(op))
            if op.is_read:
                results.append(parse_read(rx, op.count))
        return results

    def write(self, addr: int, *words: int, inc: bool = True) -> None:
        self.run([write(addr, *words, inc=inc)])

    def read(self, addr: int, count: int = 1, inc: bool = True) -> list[int]:
        return self.run([read(addr, count, inc)])[0]

    def chip_id(self) -> int:
        return self.read(isa.REG_ID)[0]

    def load(self, prog: Program, sm: int, origin: int | None = None, start: bool = False) -> None:
        self.run(self.loader.load(prog, sm, origin, start))

    def start(self, mask: int) -> None:
        self.run(self.loader.start(mask))

    def stop(self, mask: int) -> None:
        self.run(self.loader.stop(mask))

    def put(self, sm: int, *words: int) -> None:
        """Write words to an SM's TX FIFO (check `levels` first: a full FIFO drops them)."""
        self.write(isa.sm_reg(sm, isa.SM_TXF), *words, inc=False)

    def get(self, sm: int, count: int = 1) -> list[int]:
        return self.read(isa.sm_reg(sm, isa.SM_RXF), count, inc=False)

    def levels(self, sm: int) -> tuple[int, int]:
        """(TX level, RX level) of an SM's FIFOs."""
        v = self.read(isa.REG_FLEVEL)[0] >> (8 * sm)
        return v & 15, (v >> 4) & 15

    def exec(self, sm: int, instr: int) -> None:
        self.run([force(sm, instr)])
