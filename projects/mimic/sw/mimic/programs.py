"""Load the example programs in programs/ with pin and timing defines."""

from __future__ import annotations

from pathlib import Path

from . import isa
from .asm import Program, assemble_file

PROGRAMS = Path(__file__).resolve().parents[2] / "programs"


def load(name: str, **defines: int | str) -> Program:
    """Assemble programs/<name>.mim; pin defines may be names such as 'uio3'."""
    values = {k: isa.pin_number(v) if isinstance(v, str) else v for k, v in defines.items()}
    return assemble_file(PROGRAMS / f"{name}.mim", values)
