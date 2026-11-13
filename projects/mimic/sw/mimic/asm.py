"""Assembler and disassembler for Mimic programs.

A program file holds the instructions and the state machine configuration they need,
so one file is everything a host loads to run a protocol. See docs/isa.md for the syntax.

    .program uart_tx
    .side_set 1 opt
    .side_pins uo0
    .out_pins uo0 1
    .clkdiv 52.08
    .shift_out right autopull 8
        pull           side 1 [7]   ; idle high, wait for a byte
        set x, 7       side 0 [7]   ; start bit
    bit:
        out pins, 1
        jmp x--, bit   [6]

Usage: python -m mimic.asm file.mim [-o file.json] [--listing]
"""

from __future__ import annotations

import argparse
import ast
import json
import operator
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import isa


class AsmError(Exception):
    def __init__(self, msg: str, line: int = 0, path: str = "") -> None:
        loc = f"{path}:{line}: " if line else ""
        super().__init__(f"{loc}{msg}")


_BINOPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Div: operator.floordiv,
    ast.Mod: operator.mod,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
}


def evaluate(expr: str, symbols: dict[str, int]) -> int:
    """Integer expression with + - * / % << >> & | ^ ~ and symbols."""
    v = evaluate_num(expr, symbols)
    if v != int(v):
        raise ValueError(f"{expr!r} is not an integer")
    return int(v)


def evaluate_num(expr: str, symbols: dict[str, Any]) -> Any:
    """Like evaluate, but allows fractional values (for .clkdiv and its .define)."""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"bad expression {expr!r}") from e

    def ev(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in symbols:
                return symbols[node.id]
            try:
                return isa.pin_number(node.id)
            except ValueError:
                raise ValueError(f"unknown symbol {node.id!r}") from None
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            return _BINOPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp):
            v = ev(node.operand)
            if isinstance(node.op, ast.USub):
                return -v
            if isinstance(node.op, ast.Invert):
                return ~v
            if isinstance(node.op, ast.UAdd):
                return v
        raise ValueError(f"unsupported expression {expr!r}")

    return ev(tree)


@dataclass
class Config:
    """State machine configuration a program asks for; the loader turns it into registers."""

    clkdiv: float = 1.0
    in_base: int = 0
    out_base: int = 0
    out_count: int = 0
    set_base: int = 0
    set_count: int = 0
    side_base: int = 0
    in_right: bool = True
    out_right: bool = True
    autopush: bool = False
    autopull: bool = False
    push_thresh: int = 32
    pull_thresh: int = 32
    join_tx: bool = False
    join_rx: bool = False
    route: bool = False
    status_sel: int = 0
    status_n: int = 0
    crc_poly: int | None = None
    crc_init: int = 0
    crc_reflect: bool = False
    crc_feed_out: bool = False
    crc_feed_in: bool = False
    opendrain: list[int] = field(default_factory=list)
    pindirs_out: list[int] = field(default_factory=list)
    initial: dict[int, int] = field(default_factory=dict)
    x: int | None = None
    y: int | None = None


@dataclass
class Program:
    name: str
    instrs: list[int]
    origin: int = 0
    wrap_target: int = 0  # offsets within the program
    wrap: int = 0
    side_count: int = 0  # data bits
    side_opt: bool = False
    side_pindirs: bool = False
    config: Config = field(default_factory=Config)
    labels: dict[str, int] = field(default_factory=dict)
    source: list[str] = field(default_factory=list)

    def at(self, origin: int | None = None) -> list[int]:
        """Instructions relocated to `origin`: JMP targets move with the program."""
        base = self.origin if origin is None else origin
        out = []
        for w in self.instrs:
            if w >> 28 == isa.OP_JMP:
                w = (w & ~63) | ((w + base) & 63)
            out.append(w)
        return out

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "origin": self.origin,
            "instrs": [f"0x{w:08x}" for w in self.instrs],
            "wrap_target": self.wrap_target,
            "wrap": self.wrap,
            "side_count": self.side_count,
            "side_opt": self.side_opt,
            "side_pindirs": self.side_pindirs,
            "config": self.config.__dict__,
            "labels": self.labels,
        }


_COND_ALIASES = {"!txe": "!txe", "txne": "!txe"}


class Assembler:
    def __init__(self, path: str = "<string>") -> None:
        self.path = path

    def err(self, msg: str, line: int) -> AsmError:
        return AsmError(msg, line, self.path)

    def assemble(self, text: str, defines: dict[str, int] | None = None) -> Program:
        lines = text.splitlines()
        symbols: dict[str, int] = dict(defines or {})
        self.fixed = set(symbols)
        labels: dict[str, int] = {}
        body: list[tuple[int, str]] = []
        prog = Program(name=Path(self.path).stem, instrs=[], source=lines)
        wrap_target: int | None = None
        wrap: int | None = None

        # Pass 1: directives, labels, and instruction lines.
        for lineno, raw in enumerate(lines, 1):
            line = re.split(r";|//", raw, maxsplit=1)[0].strip()
            if not line:
                continue
            while True:
                m = re.match(r"^([A-Za-z_]\w*)\s*:(?!:)\s*(.*)$", line)
                if not m:
                    break
                if m.group(1) in labels:
                    raise self.err(f"label {m.group(1)!r} defined twice", lineno)
                labels[m.group(1)] = len(body)
                line = m.group(2).strip()
            if not line:
                continue
            if line.startswith("."):
                parts = line.split()
                d, args = parts[0].lower(), parts[1:]
                try:
                    if d == ".wrap_target":
                        wrap_target = len(body)
                    elif d == ".wrap":
                        wrap = len(body) - 1
                    else:
                        self.directive(d, args, prog, symbols)
                except (ValueError, IndexError) as e:
                    raise self.err(f"{d}: {e}", lineno) from None
                continue
            body.append((lineno, line))

        if not body:
            raise AsmError("program has no instructions", 0, self.path)
        if len(body) > isa.IMEM_WORDS:
            raise AsmError(f"program has {len(body)} instructions; the memory holds {isa.IMEM_WORDS}", 0, self.path)
        prog.labels = labels
        symbols.update(labels)
        prog.wrap_target = wrap_target if wrap_target is not None else 0
        prog.wrap = wrap if wrap is not None else len(body) - 1

        for lineno, line in body:
            try:
                prog.instrs.append(self.instruction(line, prog, symbols))
            except ValueError as e:
                raise self.err(str(e), lineno) from None
        return prog

    # ---- directives ---------------------------------------------------------
    def directive(self, d: str, args: list[str], prog: Program, symbols: dict[str, int]) -> None:
        cfg = prog.config

        def num(s: str) -> int:
            return evaluate(s, symbols)

        def pin(s: str) -> int:
            return num(s) & 31  # numbers, .define symbols, or names like uio3

        if d == ".program":
            prog.name = args[0]
        elif d == ".origin":
            prog.origin = num(args[0]) & 63
        elif d == ".define":
            if args[0] not in self.fixed:  # a caller's define (-D) wins over the file's default
                symbols[args[0]] = evaluate_num(" ".join(args[1:]), symbols)
        elif d == ".word":
            raise ValueError(".word must be written as an instruction line: word EXPR")
        elif d == ".side_set":
            prog.side_count = num(args[0])
            flags = {a.lower() for a in args[1:]}
            prog.side_opt = "opt" in flags
            prog.side_pindirs = "pindirs" in flags
            if prog.side_count + int(prog.side_opt) > 8:
                raise ValueError("side-set uses at most 8 bits including opt")
        elif d == ".clkdiv":
            cfg.clkdiv = float(evaluate_num(" ".join(args), symbols))
        elif d == ".in_pins":
            cfg.in_base = pin(args[0])
        elif d == ".out_pins":
            cfg.out_base, cfg.out_count = pin(args[0]), num(args[1])
        elif d == ".set_pins":
            cfg.set_base, cfg.set_count = pin(args[0]), num(args[1])
        elif d == ".side_pins":
            cfg.side_base = pin(args[0])
        elif d in (".shift_in", ".shift_out"):
            # .shift_in|.shift_out left|right [autopush|autopull] [threshold]
            right = args[0].lower() == "right"
            if args[0].lower() not in ("left", "right"):
                raise ValueError("direction must be left or right")
            rest = args[1:]
            auto = bool(rest) and rest[0].lower() in ("autopush", "autopull")
            if auto:
                rest = rest[1:]
            thresh = num(rest[0]) if rest else 32
            if d == ".shift_in":
                cfg.in_right, cfg.autopush, cfg.push_thresh = right, auto, thresh
            else:
                cfg.out_right, cfg.autopull, cfg.pull_thresh = right, auto, thresh
        elif d == ".fifo":
            mode = args[0].lower()
            cfg.join_tx, cfg.join_rx = mode == "tx", mode == "rx"
        elif d == ".route":
            cfg.route = True
        elif d == ".status":
            cfg.status_sel = 1 if args[0].lower() == "rx" else 0
            cfg.status_n = num(args[1])
        elif d == ".crc":
            cfg.crc_poly = num(args[0]) & isa.M32
            rest = [a.lower() for a in args[1:]]
            cfg.crc_reflect = "reflect" in rest
            cfg.crc_feed_out = "out" in rest
            cfg.crc_feed_in = "in" in rest
            if "init" in rest:
                cfg.crc_init = num(args[1 + rest.index("init") + 1]) & isa.M32
        elif d == ".opendrain":
            cfg.opendrain += [pin(a) for a in args]
        elif d == ".pindirs":
            cfg.pindirs_out += [pin(a) for a in args]
        elif d == ".initial":
            for a in args:
                k, v = a.split("=")
                cfg.initial[pin(k)] = num(v) & 1
        elif d == ".x":
            cfg.x = num(args[0]) & isa.M32
        elif d == ".y":
            cfg.y = num(args[0]) & isa.M32
        else:
            raise ValueError(f"unknown directive {d}")

    # ---- instructions -------------------------------------------------------
    def instruction(self, line: str, prog: Program, symbols: dict[str, int]) -> int:
        delay = 0
        side: int | None = None
        m = re.search(r"\[([^\]]+)\]\s*$", line)
        if m:
            delay = evaluate(m.group(1), symbols)
            line = line[: m.start()].strip()
        m = re.search(r"\bside\s+(.+)$", line)
        if m:
            side = evaluate(m.group(1), symbols)
            line = line[: m.start()].strip()

        sd = self.sd_field(prog, side, delay)
        mnem, _, rest = line.partition(" ")
        mnem = mnem.lower()
        rest = rest.strip()
        ops = [o.strip() for o in rest.split(",")] if rest else []

        def src(name: str) -> int:
            if name.lower() not in isa.SRC:
                raise ValueError(f"unknown source {name!r}")
            return isa.SRC[name.lower()]

        def dst(name: str) -> int:
            if name.lower() not in isa.DST:
                raise ValueError(f"unknown destination {name!r}")
            return isa.DST[name.lower()]

        def count(s: str) -> int:
            c = evaluate(s, symbols)
            if not 1 <= c <= 32:
                raise ValueError(f"bit count {c} outside 1-32")
            return c & 31

        if mnem == "nop":
            return isa.enc_mov(isa.DST["y"], isa.SRC["y"], sd=sd)
        if mnem == "word":
            return evaluate(rest, symbols) & isa.M32
        if mnem == "jmp":
            return self.jmp(ops, symbols, sd)
        if mnem == "wait":
            return self.wait(rest, symbols, sd)
        if mnem == "in":
            return isa.enc_in(src(ops[0]), count(ops[1]), sd)
        if mnem == "out":
            return isa.enc_out(dst(ops[0]), count(ops[1]), sd)
        if mnem in ("push", "pull"):
            words = rest.lower().split()
            for w in words:
                if w not in ("iffull", "ifempty", "block", "noblock"):
                    raise ValueError(f"unknown {mnem} option {w!r}")
            cond = ("iffull" in words) if mnem == "push" else ("ifempty" in words)
            block = "noblock" not in words
            return isa.enc_push(cond, block, sd) if mnem == "push" else isa.enc_pull(cond, block, sd)
        if mnem == "mov":
            s = ops[1].replace(" ", "")
            op = 0
            for sym in ("::", "><", "!", "~"):
                if s.startswith(sym):
                    op, s = isa.MOVOP[sym], s[len(sym) :]
                    break
            return isa.enc_mov(dst(ops[0]), src(s), op, sd)
        if mnem == "irq":
            words = rest.split()
            rel = "rel" in [w.lower() for w in words]
            words = [w for w in words if w.lower() != "rel"]
            mode = "set"
            if words and words[0].lower() in ("set", "nowait", "wait", "clear"):
                mode = words.pop(0).lower()
            if len(words) != 1:
                raise ValueError("irq needs one flag number")
            n = evaluate(words[0], symbols)
            return isa.enc_irq(n, clear=mode == "clear", wait=mode == "wait", rel=rel, sd=sd)
        if mnem == "set":
            v = evaluate(ops[1], symbols)
            if not 0 <= v <= 0xFFFF:
                raise ValueError(f"set value {v} outside 0-65535")
            return isa.enc_set(dst(ops[0]), v, sd)
        if mnem in isa.ALU:
            d = ops[0].lower()
            if d not in ("x", "y"):
                raise ValueError(f"{mnem} writes x or y, not {ops[0]!r}")
            if ops[1].lower() in isa.SRC:
                return isa.enc_alu(d == "y", isa.ALU[mnem], isa.SRC[ops[1].lower()], sd)
            v = evaluate(ops[1], symbols)
            if not 0 <= v <= 0xFFFF:
                raise ValueError(f"{mnem} immediate {v} outside 0-65535")
            return isa.enc_alui(d == "y", isa.ALU[mnem], v, sd)
        raise ValueError(f"unknown instruction {mnem!r}")

    def sd_field(self, prog: Program, side: int | None, delay: int) -> int:
        n = prog.side_count + int(prog.side_opt)
        if side is None:
            if prog.side_count and not prog.side_opt:
                raise ValueError("side-set is mandatory (declare .side_set N opt to make it optional)")
            side_bits = 0
        else:
            if prog.side_count == 0:
                raise ValueError("side used without .side_set")
            if not 0 <= side < (1 << prog.side_count):
                raise ValueError(f"side value {side} does not fit {prog.side_count} bits")
            side_bits = side | ((1 << prog.side_count) if prog.side_opt else 0)
        max_delay = (1 << (8 - n)) - 1
        if not 0 <= delay <= max_delay:
            raise ValueError(f"delay {delay} outside 0-{max_delay}")
        return (side_bits << (8 - n)) | delay if n else delay

    def jmp(self, ops: list[str], symbols: dict[str, int], sd: int) -> int:
        if len(ops) == 1:
            return isa.enc_jmp(0, evaluate(ops[0], symbols), sd=sd)
        cond_s, target = ops[0].strip(), ops[1]
        addr = evaluate(target, symbols)
        words = cond_s.split()
        head = words[0].lower()
        head = _COND_ALIASES.get(head, head)
        absolute = False
        pin = 0
        if head in ("pin", "!pin", "gpio", "!gpio"):
            absolute = head.endswith("gpio")
            cond = isa.COND["!pin" if head.startswith("!") else "pin"]
            if len(words) > 1:
                pin = evaluate(" ".join(words[1:]), symbols) & 31
        elif head in ("irq", "!irq"):
            cond = isa.COND[head]
            rel = "rel" in [w.lower() for w in words[1:]]
            nums = [w for w in words[1:] if w.lower() != "rel"]
            # The IRQ index lives in [11:9] (the low pin-field bits), REL in the absolute bit.
            pin = evaluate(nums[0], symbols) if nums else 0
            return isa.enc_jmp(cond, addr, pin=pin & 7, absolute=rel, sd=sd)
        else:
            key = cond_s.replace(" ", "").lower()
            key = _COND_ALIASES.get(key, key)
            if key not in isa.COND:
                raise ValueError(f"unknown jmp condition {cond_s!r}")
            cond = isa.COND[key]
        return isa.enc_jmp(cond, addr, pin=pin, absolute=absolute, sd=sd)

    def wait(self, rest: str, symbols: dict[str, int], sd: int) -> int:
        words = rest.replace(",", " ").split()
        timeout = "timeout" in [w.lower() for w in words]
        rel = "rel" in [w.lower() for w in words]
        words = [w for w in words if w.lower() not in ("timeout", "rel")]
        words[:2] = [w.lower() for w in words[:2]]
        if len(words) < 3 and not (len(words) == 2 and words[0] in ("rise", "fall", "change")):
            raise ValueError("wait POL SRC INDEX (or wait rise|fall|change SRC INDEX)")
        kind = words[0]
        if kind in ("0", "1"):
            pol, src_kind = int(kind), words[1]
            idx_s = words[2] if len(words) > 2 else "0"
            if src_kind == "irq":
                return isa.enc_wait(pol, isa.WAIT_IRQ, evaluate(idx_s, symbols) & 7, absolute=rel, timeout=timeout, sd=sd)
            src = isa.WAIT_LEVEL
        elif kind in ("rise", "fall", "change"):
            pol = 1 if kind == "rise" else 0
            src_kind = words[1]
            idx_s = words[2] if len(words) > 2 else "0"
            src = isa.WAIT_CHANGE if kind == "change" else isa.WAIT_EDGE
        else:
            raise ValueError(f"wait: unknown polarity or kind {kind!r}")
        if src_kind == "pin":
            return isa.enc_wait(pol, src, evaluate(idx_s, symbols) & 31, False, timeout, sd)
        if src_kind == "gpio":
            return isa.enc_wait(pol, src, evaluate(idx_s, symbols) & 31, True, timeout, sd)
        raise ValueError(f"wait source must be pin, gpio or irq, not {src_kind!r}")


def assemble(text: str, path: str = "<string>", defines: dict[str, int] | None = None) -> Program:
    return Assembler(path).assemble(text, defines)


def assemble_file(path: str | Path, defines: dict[str, int] | None = None) -> Program:
    p = Path(path)
    return Assembler(str(p)).assemble(p.read_text(), defines)


# ---------------------------------------------------------------------------
# Disassembler
# ---------------------------------------------------------------------------

_SRC_N = {v: k for k, v in isa.SRC.items()}
_DST_N = {v: k for k, v in isa.DST.items()}
_COND_N = {v: k for k, v in isa.COND.items()}
_ALU_N = {v: k for k, v in isa.ALU.items()}


def disassemble(w: int, side_count: int = 0, side_opt: bool = False) -> str:
    op = w >> 28
    sd = (w >> 20) & 0xFF
    n = side_count + int(side_opt)
    delay = sd & ((1 << (8 - n)) - 1)
    suffix = ""
    if n:
        top = sd >> (8 - n)
        if not side_opt or top >> side_count & 1:
            suffix += f" side {top & ((1 << side_count) - 1)}"
    if delay:
        suffix += f" [{delay}]"
    cnt = ((w >> 4) & 31) or 32
    if op == isa.OP_JMP:
        cond = (w >> 15) & 31
        addr = w & 63
        if cond == 0:
            text = f"jmp {addr}"
        elif cond in isa.PIN_CONDS:
            kind = "gpio" if w >> 14 & 1 else "pin"
            neg = "!" if cond == isa.COND["!pin"] else ""
            text = f"jmp {neg}{kind} {(w >> 9) & 31}, {addr}"
        elif cond in isa.IRQ_CONDS:
            text = f"jmp {_COND_N[cond]} {(w >> 9) & 7}{' rel' if w >> 14 & 1 else ''}, {addr}"
        else:
            text = f"jmp {_COND_N.get(cond, f'?{cond}')}, {addr}"
    elif op == isa.OP_WAIT:
        pol, src, idx = (w >> 19) & 1, (w >> 16) & 7, (w >> 9) & 31
        kind = "gpio" if w >> 14 & 1 else "pin"
        tmo = " timeout" if w >> 15 & 1 else ""
        if src == isa.WAIT_IRQ:
            text = f"wait {pol} irq {idx & 7}{' rel' if w >> 14 & 1 else ''}{tmo}"
        elif src == isa.WAIT_EDGE:
            text = f"wait {'rise' if pol else 'fall'} {kind} {idx}{tmo}"
        elif src == isa.WAIT_CHANGE:
            text = f"wait change {kind} {idx}{tmo}"
        else:
            text = f"wait {pol} {kind} {idx}{tmo}"
    elif op == isa.OP_IN:
        text = f"in {_SRC_N.get(w & 15, '?')}, {cnt}"
    elif op == isa.OP_OUT:
        text = f"out {_DST_N.get((w >> 16) & 15, '?')}, {cnt}"
    elif op == isa.OP_PUSHPULL:
        pull = w >> 19 & 1
        opts = (" ifempty" if pull else " iffull") if w >> 18 & 1 else ""
        opts += "" if w >> 17 & 1 else " noblock"
        text = ("pull" if pull else "push") + opts
    elif op == isa.OP_MOV:
        mop = ["", "!", "::", "><"][(w >> 14) & 3]
        text = f"mov {_DST_N.get((w >> 16) & 15, '?')}, {mop}{_SRC_N.get(w & 15, '?')}"
    elif op == isa.OP_IRQ:
        mode = "clear" if w >> 19 & 1 else ("wait" if w >> 18 & 1 else "set")
        text = f"irq {mode} {(w >> 9) & 7}{' rel' if w >> 14 & 1 else ''}"
    elif op == isa.OP_SET:
        text = f"set {_DST_N.get((w >> 16) & 15, '?')}, {w & 0xFFFF}"
    elif op in (isa.OP_ALU, isa.OP_ALUI):
        d = "y" if w >> 19 & 1 else "x"
        operand = str(w & 0xFFFF) if op == isa.OP_ALUI else _SRC_N.get(w & 15, "?")
        text = f"{_ALU_N[(w >> 16) & 7]} {d}, {operand}"
    else:
        text = f"word 0x{w:08x}"
    return text + suffix


def listing(prog: Program) -> str:
    out = []
    for i, w in enumerate(prog.at()):
        mark = ">" if i == prog.wrap_target else (" " if i != prog.wrap else "<")
        out.append(f"{prog.origin + i:2d}{mark} {w:08x}  {disassemble(w, prog.side_count, prog.side_opt)}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mimic-asm", description="Assemble a Mimic program.")
    ap.add_argument("source")
    ap.add_argument("-o", "--output", help="write JSON for the loader")
    ap.add_argument("--listing", action="store_true", help="print a listing")
    ap.add_argument("-D", action="append", default=[], metavar="NAME=VALUE", help="define a symbol")
    args = ap.parse_args(argv)
    defines = {k: evaluate(v, {}) for k, v in (d.split("=", 1) for d in args.D)}
    try:
        prog = assemble_file(args.source, defines)
    except AsmError as e:
        print(e, file=sys.stderr)
        return 1
    if args.output:
        Path(args.output).write_text(json.dumps(prog.to_json(), indent=2) + "\n")
    if args.listing or not args.output:
        print(listing(prog))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
