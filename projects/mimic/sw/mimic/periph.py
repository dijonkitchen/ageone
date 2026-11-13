"""Cycle-level models of the devices on the other end of each protocol.

They are written from the protocol specifications, independently of the Mimic programs
they test, and run on the bench (mimic.bench) against the model or the RTL alike.
Times are in clock cycles. Pins are GPIO numbers (uio 0-7, uo 8-14, ui 16-20).
"""

from __future__ import annotations

from collections import deque

from .bench import Bench, Peripheral


class UartRx(Peripheral):
    """Receives 8N1 frames on `pin` at `bit` cycles per bit."""

    def __init__(self, pin: int, bit: float) -> None:
        self.pin, self.bit = pin, bit
        self.data: list[int] = []
        self.framing_errors = 0
        self._t: float | None = None  # cycles since the start edge
        self._prev = 0  # a start bit needs an idle-high line first
        self._samples: list[int] = []

    def tick(self, bench: Bench) -> None:
        lv = bench.level(self.pin)
        if self._t is None:
            if self._prev == 1 and lv == 0:
                self._t = 0.0
                self._samples = []
        else:
            self._t += 1
            k = len(self._samples)
            if self._t >= (k + 0.5) * self.bit:
                self._samples.append(lv)
                if len(self._samples) == 10:
                    start, *bits, stop = self._samples
                    if start != 0 or stop != 1:
                        self.framing_errors += 1
                    else:
                        self.data.append(sum(b << i for i, b in enumerate(bits[:8])))
                    self._t = None
        self._prev = lv


class UartTx(Peripheral):
    """Sends bytes as 8N1 frames on `pin` (a ui or uio pin) at `bit` cycles per bit."""

    def __init__(self, pin: int, bit: float, gap: int = 0) -> None:
        self.pin, self.bit, self.gap = pin, bit, gap
        self.queue: deque[int] = deque()
        self._bits: list[int] = []
        self._t = 0.0
        self.started = False

    def send(self, data: bytes, framing_error: bool = False) -> None:
        for byte in data:
            self.queue.append(byte | (0x100 if framing_error else 0))

    @property
    def idle(self) -> bool:
        return not self.queue and not self._bits

    def tick(self, bench: Bench) -> None:
        if not self.started:
            bench.drive(self.pin, 1)
            self.started = True
        if not self._bits:
            if not self.queue:
                return
            v = self.queue.popleft()
            stop = 0 if v & 0x100 else 1
            self._bits = [0] + [(v >> i) & 1 for i in range(8)] + [stop] + [1] * self.gap
            self._t = 0.0
        idx = int(self._t // self.bit)
        if idx >= len(self._bits):
            self._bits = []
            bench.drive(self.pin, 1)
            return
        bench.drive(self.pin, self._bits[idx])
        self._t += 1


class SpiTarget(Peripheral):
    """An SPI target (mode 0-3) that records MOSI and answers with `reply` bytes, MSB first."""

    def __init__(self, sck: int, mosi: int, miso: int, cs: int, mode: int = 0, reply: bytes = b"") -> None:
        self.sck, self.mosi, self.miso, self.cs = sck, mosi, miso, cs
        self.cpol, self.cpha = mode >> 1 & 1, mode & 1
        self.reply = deque(reply)
        self.received: list[int] = []  # bytes, across all transactions
        self.transactions: list[bytes] = []
        self._cur = bytearray()
        self._prev_sck = self.cpol
        self._prev_cs = 1
        self._in = 0
        self._nbits = 0
        self._out = 0
        self._out_bits = 0

    def _next_byte(self) -> None:
        self._out = self.reply.popleft() if self.reply else 0xFF
        self._out_bits = 8

    def _present(self, bench: Bench) -> None:
        if self._out_bits == 0:
            self._next_byte()
        bench.drive(self.miso, self._out >> 7 & 1)

    def tick(self, bench: Bench) -> None:
        cs = bench.level(self.cs)
        sck = bench.level(self.sck)
        if cs == 1:
            if self._prev_cs == 0 and self._cur:
                self.transactions.append(bytes(self._cur))
                self._cur = bytearray()
            bench.drive(self.miso, None)
            self._nbits = 0
            self._out_bits = 0
        else:
            if self._prev_cs == 1 and not self.cpha:
                self._present(bench)  # CPHA=0: first bit valid as soon as CS falls
            leading = sck != self._prev_sck and sck != self.cpol
            trailing = sck != self._prev_sck and sck == self.cpol
            sample_edge = leading if not self.cpha else trailing
            shift_edge = trailing if not self.cpha else leading
            if shift_edge:
                if self.cpha:
                    self._present(bench)
                else:
                    self._out = (self._out << 1) & 0xFF
                    self._out_bits -= 1
                    self._present(bench)
            if sample_edge:
                self._in = (self._in << 1) | bench.level(self.mosi)
                self._nbits += 1
                if self.cpha:
                    self._out = (self._out << 1) & 0xFF
                    self._out_bits -= 1
                if self._nbits == 8:
                    self.received.append(self._in)
                    self._cur.append(self._in)
                    self._in = 0
                    self._nbits = 0
        self._prev_sck = sck
        self._prev_cs = cs


class SpiController(Peripheral):
    """An SPI controller, mode 0, for testing Mimic as a target: exchanges `data` when started."""

    def __init__(self, sck: int, mosi: int, miso: int, cs: int, half: int) -> None:
        self.sck, self.mosi, self.miso, self.cs, self.half = sck, mosi, miso, cs, half
        self.queue: deque[bytes] = deque()
        self.received: list[bytes] = []
        self._bits: list[int] = []
        self._rx: list[int] = []
        self._t = 0
        self._phase = "idle"

    def transfer(self, data: bytes) -> None:
        self.queue.append(data)

    @property
    def idle(self) -> bool:
        return self._phase == "idle" and not self.queue

    def tick(self, bench: Bench) -> None:
        h = self.half
        if self._phase == "idle":
            bench.drive(self.cs, 1)
            bench.drive(self.sck, 0)
            bench.drive(self.mosi, 0)
            if self.queue:
                data = self.queue.popleft()
                self._bits = [(b >> (7 - i)) & 1 for b in data for i in range(8)]
                self._rx = []
                self._t = 0
                self._phase = "setup"
            return
        self._t += 1
        if self._phase == "setup":
            bench.drive(self.cs, 0)
            if self._t >= 4 * h:
                self._t = 0
                self._phase = "bits"
            return
        if self._phase == "bits":
            i, sub = divmod(self._t - 1, 2 * h)
            if i >= len(self._bits):
                bench.drive(self.sck, 0)
                if self._t >= len(self._bits) * 2 * h + 4 * h:
                    out = bytes(
                        sum(b << (7 - k) for k, b in enumerate(self._rx[j : j + 8])) for j in range(0, len(self._rx), 8)
                    )
                    self.received.append(out)
                    bench.drive(self.cs, 1)
                    self._phase = "idle"
                return
            if sub == 0:
                bench.drive(self.mosi, self._bits[i])
                bench.drive(self.sck, 0)
            elif sub == h:
                bench.drive(self.sck, 1)
                self._rx.append(bench.level(self.miso))


class I2CTarget(Peripheral):
    """An I2C EEPROM-like target: write [reg, data...], read from reg. Open-drain on SDA/SCL.

    `stretch` holds SCL low for that many cycles after every falling edge of SCL while the
    target is addressed, to test clock stretching; `stretched` counts the cycles it held
    SCL low after the controller had released it.
    """

    def __init__(self, scl: int, sda: int, addr: int = 0x50, size: int = 256, stretch: int = 0) -> None:
        self.scl, self.sda, self.addr = scl, sda, addr
        self.mem = bytearray(size)
        self.ptr = 0
        self.stretch = stretch
        self.log: list[str] = []
        self._prev_scl = 1
        self._prev_sda = 1
        self._state = "idle"
        self._shift = 0
        self._nbits = 0
        self._reading = False
        self._first = True
        self._drive_sda: int | None = None
        self._stretch_left = 0
        self._tx = 0
        self._ack_pending = False
        self.stretched = 0

    def tick(self, bench: Bench) -> None:
        scl = bench.level(self.scl)
        sda = bench.level(self.sda)
        rise = scl and not self._prev_scl
        fall = not scl and self._prev_scl
        if scl and self._prev_scl and sda != self._prev_sda:
            if sda == 0:  # START or repeated START
                self.log.append("S")
                self._state = "addr"
                self._shift = self._nbits = 0
                self._drive_sda = None
            else:  # STOP
                self.log.append("P")
                self._state = "idle"
                self._drive_sda = None
        elif rise and self._state in ("addr", "write", "read"):
            if self._nbits < 8:
                self._shift = (self._shift << 1) | sda
                self._nbits += 1
            else:  # 9th clock: ACK bit
                if self._state == "read":
                    if sda == 1:  # NACK from controller: stop sending
                        self._state = "nack"
                self._nbits = 9
        elif fall and self._state in ("addr", "write", "read", "nack"):
            if self._nbits == 8 and self._state != "read":
                byte = self._shift
                ack = True
                if self._state == "addr":
                    if byte >> 1 != self.addr:
                        ack = False
                        self._state = "ignore"
                    else:
                        self._reading = bool(byte & 1)
                        self._first = True
                        self.log.append(f"A{byte:02x}")
                else:
                    if self._first:
                        self.ptr = byte % len(self.mem)
                        self._first = False
                    else:
                        self.mem[self.ptr] = byte
                        self.ptr = (self.ptr + 1) % len(self.mem)
                    self.log.append(f"W{byte:02x}")
                self._drive_sda = 0 if ack else None
                self._ack_pending = True
            elif self._nbits == 8 and self._state == "read":
                self._drive_sda = None  # release for the controller's ACK
            elif self._nbits == 9:
                self._ack_pending = False
                self._drive_sda = None
                if self._state == "addr":
                    self._state = "read" if self._reading else "write"
                if self._state == "read":
                    self._tx = self.mem[self.ptr]
                    self.log.append(f"R{self._tx:02x}")
                    self.ptr = (self.ptr + 1) % len(self.mem)
                    self._drive_sda = self._tx >> 7 & 1
                self._shift = self._nbits = 0
                if self._state == "nack":
                    self._state = "idle"
            elif self._state == "read" and self._nbits < 8:
                self._drive_sda = self._tx >> (7 - self._nbits) & 1
        if fall and self.stretch and self._state in ("write", "read", "addr"):
            self._stretch_left = self.stretch
        sda_drive = None if self._drive_sda in (None, 1) else 0
        bench.drive(self.sda, sda_drive)
        if self._stretch_left:
            self._stretch_left -= 1
            bench.drive(self.scl, 0)
            if not (bench.uio_oe >> self.scl & 1):
                self.stretched += 1
        else:
            bench.drive(self.scl, None)
        self._prev_scl = scl
        self._prev_sda = sda


class Ws2812(Peripheral):
    """Decodes WS2812 bits from high-pulse widths; a low longer than `reset` latches a frame."""

    def __init__(self, pin: int, threshold: int, reset: int) -> None:
        self.pin, self.threshold, self.reset = pin, threshold, reset
        self.bits: list[int] = []
        self.frames: list[list[int]] = []
        self._prev = 0
        self._high = 0
        self._low = 0

    def tick(self, bench: Bench) -> None:
        lv = bench.level(self.pin)
        if lv:
            self._high += 1
            self._low = 0
        else:
            if self._prev:
                self.bits.append(1 if self._high > self.threshold else 0)
                self._high = 0
            self._low += 1
            if self._low == self.reset and self.bits:
                self.frames.append(
                    [sum(b << (23 - i) for i, b in enumerate(self.bits[j : j + 24])) for j in range(0, len(self.bits), 24)]
                )
                self.bits = []
        self._prev = lv
