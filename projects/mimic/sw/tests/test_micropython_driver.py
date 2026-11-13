"""The board driver (sw/micropython/mimic_tt.py) against the golden model, over a bit-level SPI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mimic import cli, isa
from mimic.model import Mimic as Model

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "micropython"))
import mimic_tt


class ModelSpi:
    """machine.SoftSPI and a CS pin, bit-banged into the model at 8 clock cycles per bit."""

    def __init__(self, model: Model) -> None:
        self.m = model
        self.csn = 1
        self.out = (0, 0, 0)

    def _clock(self, n: int, sck: int, mosi: int) -> None:
        for _ in range(n):
            ui = (self.csn << 5) | (sck << 6) | (mosi << 7)
            self.out = self.m.clock(ui, 0xFF)

    def value(self, v: int) -> None:  # the CS pin
        self.csn = v
        self._clock(4, 0, 0)

    def write_readinto(self, tx: bytes, rx: bytearray) -> None:
        for i, byte in enumerate(tx):
            r = 0
            for b in range(7, -1, -1):
                bit = byte >> b & 1
                self._clock(4, 0, bit)
                r = (r << 1) | (self.out[0] >> 7 & 1)
                self._clock(4, 1, bit)
            rx[i] = r


def test_driver_loads_and_runs_a_program(tmp_path: Path) -> None:
    out = tmp_path / "echo.json"
    src = tmp_path / "echo.mim"
    src.write_text("    pull\n    mov isr, ~osr\n    push\n")
    assert cli.main([str(src), "--sm", "2", "--start", "-o", str(out)]) == 0
    assert json.loads(out.read_text())["sm"] == 2

    model = Model()
    spi = ModelSpi(model)
    chip = mimic_tt.Mimic(spi=spi, cs=spi)
    assert chip.chip_id() == isa.CHIP_ID
    chip.play_file(str(out))
    chip.put(2, [0x12345678, 0])
    spi._clock(50, 0, 0)
    assert chip.levels(2) == (0, 2)
    assert chip.get(2) == [0xEDCBA987, 0xFFFFFFFF]
