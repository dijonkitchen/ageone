"""mimic-load: assemble a program and write the register operations that load it.

    mimic-load programs/uart_tx.mim --sm 0 --origin 0 -D TX=uo0 --start -o uart_tx.json

The JSON holds {"program", "sm", "origin", "ops": [[addr, [words], inc], ...]}; the board
driver (sw/micropython/mimic_tt.py) plays it with Mimic.play_file().
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import asm, isa
from .host import Loader


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mimic-load", description=__doc__.split("\n\n")[0])
    ap.add_argument("source")
    ap.add_argument("--sm", type=int, default=0, help="state machine 0-3")
    ap.add_argument("--origin", type=int, help="load address (default: the program's .origin)")
    ap.add_argument("--start", action="store_true", help="enable the SM after loading")
    ap.add_argument("-D", action="append", default=[], metavar="NAME=VALUE", help="define (pins by name)")
    ap.add_argument("-o", "--output", help="JSON file (default: stdout)")
    args = ap.parse_args(argv)

    defines: dict[str, int] = {}
    for d in args.D:
        k, v = d.split("=", 1)
        try:
            defines[k] = isa.pin_number(v)
        except ValueError:
            defines[k] = asm.evaluate(v, {})
    try:
        prog = asm.assemble_file(args.source, defines)
    except asm.AsmError as e:
        print(e, file=sys.stderr)
        return 1
    ops = Loader().load(prog, args.sm, args.origin, start=args.start)
    doc = {
        "program": prog.name,
        "sm": args.sm,
        "origin": prog.origin if args.origin is None else args.origin,
        "ops": [[op.addr, list(op.words), op.inc] for op in ops],
    }
    text = json.dumps(doc) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
