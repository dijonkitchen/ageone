"""Mimic host driver for the Tiny Tapeout demo board (MicroPython on the RP2350).

The PC turns programs into register writes with `mimic-load` (sw/mimic/cli.py); copy the
JSON to the board and play it:

    from ttboard.demoboard import DemoBoard
    tt = DemoBoard.get()
    tt.shuttle.tt_um_dijonkitchen_mimic.enable()
    tt.clock_project_PWM(60_000_000)
    tt.reset_project(True); tt.reset_project(False)

    import mimic_tt
    chip = mimic_tt.Mimic()
    assert chip.chip_id() == mimic_tt.CHIP_ID
    chip.play_file("uart_tx.json")      # load and start
    chip.put(0, b"hello")                # one byte per word for uart_tx

The host port is an SPI target (mode 0) on ui_in[5] CS_N, ui_in[6] SCK, ui_in[7] MOSI and
uo_out[7] MISO; SCK must stay below clk/6. Frames are documented in docs/host.md.
"""

try:
    import machine  # MicroPython
except ImportError:  # CPython, for tests against the model
    machine = None

CHIP_ID = 0x4D494D31
REG_ID = 0x40
REG_FLEVEL = 0x42
SM_BASE = 0x80
SM_STRIDE = 0x10
SM_TXF = 0x0
SM_RXF = 0x1


def _board_pins():
    """GPIO numbers of the host port on this demo board, from the Tiny Tapeout SDK's map."""
    from ttboard.pins.gpio_map import GPIOMap

    return GPIOMap.UI_IN5, GPIOMap.UI_IN6, GPIOMap.UI_IN7, GPIOMap.UO_OUT7


class Mimic:
    def __init__(self, spi=None, cs=None, baudrate=1_000_000):
        """Use `spi` and `cs` (a Pin) if given, else a SoftSPI on the demo board's host-port pins."""
        if spi is None:
            cs_n, sck, mosi, miso = _board_pins()
            cs = machine.Pin(cs_n, machine.Pin.OUT, value=1)
            spi = machine.SoftSPI(
                baudrate=baudrate,
                polarity=0,
                phase=0,
                sck=machine.Pin(sck),
                mosi=machine.Pin(mosi),
                miso=machine.Pin(miso),
            )
        self.spi = spi
        self.cs = cs
        self.cs.value(1)

    # ---- frames -------------------------------------------------------------
    def _xfer(self, tx):
        rx = bytearray(len(tx))
        self.cs.value(0)
        self.spi.write_readinto(tx, rx)
        self.cs.value(1)
        return rx

    def write(self, addr, words, inc=True):
        buf = bytearray([0xC0 if inc else 0x80, addr & 0xFF])
        for w in words:
            buf += bytes([(w >> 24) & 0xFF, (w >> 16) & 0xFF, (w >> 8) & 0xFF, w & 0xFF])
        self._xfer(buf)

    def read(self, addr, count=1, inc=True):
        rx = self._xfer(bytearray([0x40 if inc else 0x00, addr & 0xFF, 0]) + bytearray(4 * count))
        return [
            (rx[3 + 4 * i] << 24) | (rx[4 + 4 * i] << 16) | (rx[5 + 4 * i] << 8) | rx[6 + 4 * i] for i in range(count)
        ]

    # ---- helpers ------------------------------------------------------------
    def chip_id(self):
        return self.read(REG_ID)[0]

    def play(self, ops):
        """Run register writes from mimic-load: a list of [addr, [words], inc]."""
        for addr, words, inc in ops:
            self.write(addr, words, inc)

    def play_file(self, path):
        import json

        with open(path) as f:
            self.play(json.load(f)["ops"])

    def levels(self, sm):
        """(TX level, RX level) of a state machine's FIFOs."""
        v = self.read(REG_FLEVEL)[0] >> (8 * sm)
        return v & 15, (v >> 4) & 15

    def put(self, sm, words):
        """Write words to a TX FIFO; the chip drops words that do not fit, so check levels first."""
        self.write(SM_BASE + SM_STRIDE * sm + SM_TXF, list(words), inc=False)

    def get(self, sm, count=None):
        """Read the words waiting in an RX FIFO (or exactly `count`, which must be waiting)."""
        n = self.levels(sm)[1] if count is None else count
        return self.read(SM_BASE + SM_STRIDE * sm + SM_RXF, n, inc=False) if n else []
