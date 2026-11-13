"""Mimic instruction set and register map: the one place encodings are defined.

The assembler, the golden model, the host driver, and the docs (docs/isa.md) all follow
these tables. The RTL (src/mimic_sm.v) implements the same encodings and is checked
against the model.
"""

from __future__ import annotations

M32 = 0xFFFF_FFFF
IMEM_WORDS = 64
NUM_SM = 4
FIFO_DEPTH = 2
CHIP_ID = 0x4D494D31  # "MIM1"

# Opcodes, bits [31:28].
OP_JMP = 0x0
OP_WAIT = 0x1
OP_IN = 0x2
OP_OUT = 0x3
OP_PUSHPULL = 0x4
OP_MOV = 0x5
OP_IRQ = 0x6
OP_SET = 0x7
OP_ALU = 0x8
OP_ALUI = 0x9

# Sources for IN, MOV and ALU, bits [3:0].
SRC = {
    "pins": 0,
    "x": 1,
    "y": 2,
    "null": 3,
    "status": 4,
    "isr": 5,
    "osr": 6,
    "crc": 7,
    "irq": 8,
}

# Destinations for OUT, MOV and SET, bits [19:16].
DST = {
    "pins": 0,
    "x": 1,
    "y": 2,
    "null": 3,
    "pindirs": 4,
    "pc": 5,
    "isr": 6,
    "osr": 7,
    "exec": 8,
    "crc": 9,
    "poly": 10,
}

# JMP conditions, bits [19:15].
COND = {
    "always": 0,
    "!x": 1,
    "x--": 2,
    "!y": 3,
    "y--": 4,
    "x!=y": 5,
    "x==y": 6,
    "x<y": 7,
    "pin": 8,
    "!pin": 9,
    "!osre": 10,
    "osre": 11,
    "!txe": 12,
    "txe": 13,
    "x0": 14,
    "!x0": 15,
    "irq": 16,
    "!irq": 17,
}
PIN_CONDS = {COND["pin"], COND["!pin"]}
IRQ_CONDS = {COND["irq"], COND["!irq"]}

# WAIT sources, bits [18:16].
WAIT_LEVEL = 0
WAIT_EDGE = 1
WAIT_CHANGE = 2
WAIT_IRQ = 3

# ALU operations, bits [18:16].
ALU = {"add": 0, "sub": 1, "and": 2, "or": 3, "xor": 4, "shl": 5, "shr": 6, "rol": 7}

# MOV operations, bits [15:14].
MOVOP = {"": 0, "!": 1, "~": 1, "::": 2, "><": 3}

# Pin names: GPIO numbers in the 32-pin space.
PIN_GROUPS = {"uio": 0, "uo": 8, "ui": 16, "v": 24}

# Host register map (word addresses).
REG_IMEM = 0x00
REG_ID = 0x40
REG_CTRL = 0x41
REG_FLEVEL = 0x42
REG_FDEBUG = 0x43
REG_IRQ = 0x44
REG_IRQ_FORCE = 0x45
REG_PADCTRL = 0x46
REG_PINS = 0x47
REG_PINOUT = 0x48
REG_PINOE = 0x49

SM_BASE = 0x80
SM_STRIDE = 0x10
SM_TXF = 0x0
SM_RXF = 0x1
SM_CLKDIV = 0x2
SM_EXECCTRL = 0x3
SM_SHIFTCTRL = 0x4
SM_PINCTRL = 0x5
SM_CRCCFG = 0x6
SM_INSTR = 0x7
SM_PC = 0x8
SM_X = 0x9
SM_Y = 0xA
SM_STAT = 0xF


def sm_reg(sm: int, reg: int) -> int:
    """Host address of register `reg` of state machine `sm`."""
    return SM_BASE + SM_STRIDE * sm + reg


def pin_number(name: str | int) -> int:
    """GPIO number of a pin name such as 'uio3', 'uo1', 'ui7', 'v0', 'gpio12', or a number."""
    if isinstance(name, int):
        n = name
    else:
        s = name.strip().lower()
        if s.isdigit():
            n = int(s)
        elif s.startswith("gpio") and s[4:].isdigit():
            n = int(s[4:])
        else:
            for prefix in sorted(PIN_GROUPS, key=len, reverse=True):
                if s.startswith(prefix) and s[len(prefix) :].isdigit():
                    idx = int(s[len(prefix) :])
                    if idx > 7:
                        raise ValueError(f"pin {name!r}: index above 7")
                    n = PIN_GROUPS[prefix] + idx
                    break
            else:
                raise ValueError(f"unknown pin {name!r}")
    if not 0 <= n < 32:
        raise ValueError(f"pin {name!r} outside 0-31")
    return n


# ---------------------------------------------------------------------------
# Instruction encoders
# ---------------------------------------------------------------------------


def _word(op: int, args: int, sd: int = 0) -> int:
    assert 0 <= op < 16 and 0 <= sd < 256 and 0 <= args < (1 << 20)
    return (op << 28) | (sd << 20) | args


def enc_jmp(cond: int, addr: int, pin: int = 0, absolute: bool = False, sd: int = 0) -> int:
    return _word(OP_JMP, (cond << 15) | (int(absolute) << 14) | ((pin & 31) << 9) | (addr & 63), sd)


def enc_wait(
    pol: int, src: int, index: int, absolute: bool = False, timeout: bool = False, sd: int = 0
) -> int:
    args = (pol << 19) | (src << 16) | (int(timeout) << 15) | (int(absolute) << 14) | ((index & 31) << 9)
    return _word(OP_WAIT, args, sd)


def enc_in(src: int, count: int, sd: int = 0) -> int:
    return _word(OP_IN, ((count & 31) << 4) | src, sd)


def enc_out(dst: int, count: int, sd: int = 0) -> int:
    return _word(OP_OUT, (dst << 16) | ((count & 31) << 4), sd)


def enc_push(iffull: bool = False, block: bool = True, sd: int = 0) -> int:
    return _word(OP_PUSHPULL, (int(iffull) << 18) | (int(block) << 17), sd)


def enc_pull(ifempty: bool = False, block: bool = True, sd: int = 0) -> int:
    return _word(OP_PUSHPULL, (1 << 19) | (int(ifempty) << 18) | (int(block) << 17), sd)


def enc_mov(dst: int, src: int, op: int = 0, sd: int = 0) -> int:
    return _word(OP_MOV, (dst << 16) | (op << 14) | src, sd)


def enc_irq(index: int, clear: bool = False, wait: bool = False, rel: bool = False, sd: int = 0) -> int:
    args = (int(clear) << 19) | (int(wait) << 18) | (int(rel) << 14) | ((index & 7) << 9)
    return _word(OP_IRQ, args, sd)


def enc_set(dst: int, value: int, sd: int = 0) -> int:
    return _word(OP_SET, (dst << 16) | (value & 0xFFFF), sd)


def enc_alu(dst_y: bool, op: int, src: int, sd: int = 0) -> int:
    return _word(OP_ALU, (int(dst_y) << 19) | (op << 16) | src, sd)


def enc_alui(dst_y: bool, op: int, imm: int, sd: int = 0) -> int:
    return _word(OP_ALUI, (int(dst_y) << 19) | (op << 16) | (imm & 0xFFFF), sd)


NOP = enc_mov(DST["y"], SRC["y"])


# ---------------------------------------------------------------------------
# State machine configuration registers
# ---------------------------------------------------------------------------


def pack_clkdiv(div: float) -> int:
    """CLKDIV for an average of `div` cycles per tick (1.0 to 65535.996)."""
    if not 1.0 <= div < 65536.0:
        raise ValueError(f"clock divider {div} outside 1..65535")
    whole = int(div)
    frac = int(round((div - whole) * 256))
    if frac == 256:
        whole, frac = whole + 1, 0
    return (whole << 16) | (frac << 8)


def pack_execctrl(
    wrap_bottom: int = 0,
    wrap_top: int = 63,
    side_base: int = 0,
    side_count: int = 0,
    side_en: bool = False,
    side_pindirs: bool = False,
    status_sel: int = 0,
    status_n: int = 0,
) -> int:
    return (
        (wrap_bottom & 63)
        | ((wrap_top & 63) << 6)
        | ((side_base & 31) << 12)
        | ((side_count & 15) << 17)
        | (int(side_en) << 21)
        | (int(side_pindirs) << 22)
        | ((status_sel & 1) << 23)
        | ((status_n & 15) << 24)
    )


def pack_shiftctrl(
    in_right: bool = True,
    out_right: bool = True,
    autopush: bool = False,
    autopull: bool = False,
    push_thresh: int = 32,
    pull_thresh: int = 32,
    join_tx: bool = False,
    join_rx: bool = False,
    route: bool = False,
) -> int:
    return (
        int(in_right)
        | (int(out_right) << 1)
        | (int(autopush) << 2)
        | (int(autopull) << 3)
        | ((push_thresh & 31) << 4)
        | ((pull_thresh & 31) << 9)
        | (int(join_tx) << 16)
        | (int(join_rx) << 17)
        | (int(route) << 20)
    )


def pack_pinctrl(
    out_base: int = 0, out_count: int = 0, set_base: int = 0, set_count: int = 0, in_base: int = 0
) -> int:
    return (
        (out_base & 31)
        | ((out_count & 63) << 5)
        | ((set_base & 31) << 11)
        | ((set_count & 31) << 16)
        | ((in_base & 31) << 21)
    )


def pack_crccfg(reflect: bool = False, feed_out: bool = False, feed_in: bool = False) -> int:
    return int(reflect) | (int(feed_out) << 1) | (int(feed_in) << 2)


def pack_ctrl(
    enable: int = 0, restart: int = 0, div_restart: int = 0, step: int = 0, tx_clear: int = 0, rx_clear: int = 0
) -> int:
    """CTRL value; each argument is a 4-bit mask of state machines."""
    return (
        (enable & 15)
        | ((restart & 15) << 4)
        | ((div_restart & 15) << 8)
        | ((step & 15) << 12)
        | ((tx_clear & 15) << 16)
        | ((rx_clear & 15) << 20)
    )
