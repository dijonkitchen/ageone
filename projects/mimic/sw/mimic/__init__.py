"""Mimic: toolchain and golden model for a reprogrammable protocol emulator ASIC."""

from .asm import Program, assemble, assemble_file, disassemble
from .model import Mimic

__all__ = ["Mimic", "Program", "assemble", "assemble_file", "disassemble"]
