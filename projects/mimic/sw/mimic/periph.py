"""Cycle-level models of the devices on the other end of each protocol.

They are written from the protocol specifications, independently of the Mimic programs
they test, and run on the bench (mimic.bench) against the model or the RTL alike.
Times are in clock cycles. Pins are GPIO numbers (uio 0-7, uo 8-14, ui 16-20).
"""

from __future__ import annotations

from collections import deque
from typing import ClassVar

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
                if self._state == "read" and sda == 1:  # NACK from the controller: stop sending
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
                    [
                        sum(b << (23 - i) for i, b in enumerate(self.bits[j : j + 24]))
                        for j in range(0, len(self.bits), 24)
                    ]
                )
                self.bits = []
        self._prev = lv


class ManchesterTx(Peripheral):
    """Drives IEEE 802.3 Manchester frames (preamble, SFD, data, FCS) onto a pin.

    `bit` is cycles per bit (fractional values model a transmitter clock that is off
    frequency), `phase` delays the first edge by a fraction of a cycle's worth of time.
    The line idles low; each frame ends with a high idle pulse of `tail` bits.
    """

    def __init__(self, pin: int, bit: float, phase: float = 0.0, tail: float = 2.5) -> None:
        self.pin, self.bit, self.phase, self.tail = pin, bit, phase, tail
        self.frames: deque[list[int]] = deque()
        self._levels: list[tuple[float, int]] = []  # (end time, level) of each half-bit
        self._t = 0.0
        self._i = 0

    def send(self, frame_bits: list[int]) -> None:
        self.frames.append(frame_bits)

    @property
    def idle(self) -> bool:
        return not self.frames and not self._levels

    def tick(self, bench: Bench) -> None:
        if not self._levels:
            bench.drive(self.pin, 0)
            if not self.frames:
                return
            bits = self.frames.popleft()
            half = self.bit / 2
            t = self.phase
            levels = []
            for b in bits:
                first, second = (0, 1) if b else (1, 0)
                levels += [(t + half, first), (t + 2 * half, second)]
                t += 2 * half
            levels.append((t + self.tail * self.bit, 1))
            levels.append((t + self.tail * self.bit + 1, 0))
            self._levels, self._t, self._i = levels, 0.0, 0
        self._t += 1
        while self._i < len(self._levels) and self._t > self._levels[self._i][0]:
            self._i += 1
        if self._i >= len(self._levels):
            self._levels = []
            bench.drive(self.pin, 0)
            return
        bench.drive(self.pin, self._levels[self._i][1])


class ManchesterRx(Peripheral):
    """Records a pin and decodes IEEE 802.3 Manchester frames from its transitions."""

    def __init__(self, pin: int, bit: float) -> None:
        self.pin, self.bit = pin, bit
        self.frames: list[bytes] = []
        self._edges: list[tuple[int, int]] = []  # (cycle, new level)
        self._prev = 0
        self._cycle = 0

    def tick(self, bench: Bench) -> None:
        lv = bench.level(self.pin)
        self._cycle += 1
        if lv != self._prev:
            self._edges.append((self._cycle, lv))
        elif self._edges and self._cycle - self._edges[-1][0] > 4 * self.bit:
            self._decode()
            self._edges = []
        self._prev = lv

    def _decode(self) -> None:
        edges = self._edges
        bits = []
        i = 0
        while i < len(edges):
            t, lv = edges[i]
            bits.append(lv)  # level after a mid-bit transition
            j = i + 1
            while j < len(edges) and edges[j][0] < t + 0.75 * self.bit:
                j += 1
            if j >= len(edges) or edges[j][0] > t + 1.25 * self.bit:
                break
            i = j
        # Strip the preamble: data starts after the first "1 1".
        for k in range(1, len(bits)):
            if bits[k] == 1 and bits[k - 1] == 1:
                data_bits = bits[k + 1 :]
                break
        else:
            return
        n = len(data_bits) // 8
        self.frames.append(bytes(sum(data_bits[8 * j + b] << b for b in range(8)) for j in range(n)))


def manchester_frame_bits(data_with_fcs: bytes) -> list[int]:
    """Preamble, SFD and the given bytes as bits in transmit order (LSB first)."""
    frame = bytes([0x55] * 7 + [0xD5]) + data_with_fcs
    return [(byte >> i) & 1 for byte in frame for i in range(8)]


def usb_crc5(bits: list[int]) -> list[int]:
    """USB token CRC5 bits as transmitted (inverted remainder, MSb first), from the spec."""
    rem = 0x1F
    for b in bits:
        fb = ((rem >> 4) & 1) ^ b
        rem = ((rem << 1) & 0x1F) ^ (0x05 if fb else 0)
    rem ^= 0x1F
    return [(rem >> (4 - i)) & 1 for i in range(5)]


def usb_crc16(data: bytes) -> list[int]:
    """USB data CRC16 bits as transmitted (inverted remainder, MSb first), from the spec."""
    rem = 0xFFFF
    for byte in data:
        for i in range(8):
            fb = ((rem >> 15) & 1) ^ ((byte >> i) & 1)
            rem = ((rem << 1) & 0xFFFF) ^ (0x8005 if fb else 0)
    rem ^= 0xFFFF
    return [(rem >> (15 - i)) & 1 for i in range(16)]


def usb_bits(pid: int, payload: bytes = b"", token: tuple[int, int] | None = None) -> list[int]:
    """Bits of a packet after SYNC, LSB first, with its CRC: a token (addr, endp) or data."""
    pid_byte = (pid & 0xF) | ((~pid & 0xF) << 4)
    bits = [(pid_byte >> i) & 1 for i in range(8)]
    if token is not None:
        addr, endp = token
        field = [(addr >> i) & 1 for i in range(7)] + [(endp >> i) & 1 for i in range(4)]
        bits += field + usb_crc5(field)
    elif pid & 0b11 == 0b11:  # data packets carry a CRC16
        bits += [(b >> i) & 1 for b in payload for i in range(8)] + usb_crc16(payload)
    return bits


class UsbLsHost(Peripheral):
    """Drives low-speed USB packets (as a host would) on D- and D+: NRZI, bit stuffing, EOP.

    `bit` is cycles per bit; low-speed allows a 1.5% frequency error, which `bit` can model.
    """

    J = (0, 1)  # (D+, D-) for low speed
    K = (1, 0)

    def __init__(self, dm: int, dp: int, bit: float) -> None:
        self.dm, self.dp, self.bit = dm, dp, bit
        self.queue: deque[list[int]] = deque()
        self._levels: list[tuple[int, int]] = []
        self._t = 0.0
        self.started = False

    def send(self, bits: list[int]) -> None:
        self.queue.append(bits)

    @property
    def idle(self) -> bool:
        return not self.queue and not self._levels

    def _line(self, bits: list[int]) -> list[tuple[int, int]]:
        stuffed: list[int] = []
        ones = 0
        for b in [0, 0, 0, 0, 0, 0, 0, 1] + bits:  # SYNC, then the packet
            stuffed.append(b)
            ones = ones + 1 if b else 0
            if ones == 6:
                stuffed.append(0)
                ones = 0
        state = self.J
        out = []
        for b in stuffed:
            if b == 0:
                state = self.K if state == self.J else self.J
            out.append(state)
        return out + [(0, 0), (0, 0), self.J]  # EOP: two bits of SE0, then J

    def _drive(self, bench: Bench, lv: tuple[int, int]) -> None:
        bench.drive(self.dp, lv[0])
        bench.drive(self.dm, lv[1])

    def tick(self, bench: Bench) -> None:
        if not self._levels:
            self._drive(bench, self.J)
            if not self.queue:
                return
            self._levels = self._line(self.queue.popleft())
            self._t = 0.0
        idx = int(self._t // self.bit)
        if idx >= len(self._levels):
            self._levels = []
            self._drive(bench, self.J)
            return
        self._drive(bench, self._levels[idx])
        self._t += 1


class Ps2Device(Peripheral):
    """A PS/2 keyboard sending scan codes: it drives CLK and DATA open-drain, `half` cycles a phase."""

    def __init__(self, clk: int, data: int, half: int) -> None:
        self.clk, self.data, self.half = clk, data, half
        self.queue: deque[tuple[int, bool]] = deque()
        self._bits: list[int] = []
        self._t = 0

    def send(self, codes: bytes, bad_parity: bool = False) -> None:
        for c in codes:
            self.queue.append((c, bad_parity))

    @property
    def idle(self) -> bool:
        return not self.queue and not self._bits

    def tick(self, bench: Bench) -> None:
        if not self._bits:
            bench.drive(self.clk, None)
            bench.drive(self.data, None)
            if not self.queue:
                return
            code, bad = self.queue.popleft()
            parity = 1 ^ (code.bit_count() & 1) ^ int(bad)  # odd parity
            self._bits = [0] + [(code >> i) & 1 for i in range(8)] + [parity, 1]
            self._t = 0
        # Each bit: DATA set while CLK is high, then CLK low (the host samples), then high.
        bit, phase = divmod(self._t, 2 * self.half)
        if bit >= len(self._bits):
            self._bits = []
            return
        bench.drive(self.data, None if self._bits[bit] else 0)
        bench.drive(self.clk, 0 if phase >= self.half else None)
        self._t += 1


class PulseTrain(Peripheral):
    """Drives a pin through a list of (level, cycles) pulses, then holds the last level."""

    def __init__(self, pin: int, pulses: list[tuple[int, int]], idle: int = 1) -> None:
        self.pin, self.pulses, self.idle_level = pin, deque(pulses), idle
        self._left = 0
        self._level = idle

    def tick(self, bench: Bench) -> None:
        if self._left == 0 and self.pulses:
            self._level, self._left = self.pulses.popleft()
        if self._left:
            self._left -= 1
        bench.drive(self.pin, self._level)


def nec_pulses(addr: int, cmd: int, unit: int) -> list[tuple[int, int]]:
    """An NEC infrared remote frame as receiver output (active low), `unit` cycles per 562.5 us."""
    out = [(0, 16 * unit), (1, 8 * unit)]  # 9 ms burst, 4.5 ms space
    for byte in (addr, addr ^ 0xFF, cmd, cmd ^ 0xFF):
        for i in range(8):
            out += [(0, unit), (1, (3 if byte >> i & 1 else 1) * unit)]
    return out + [(0, unit), (1, 10 * unit)]


class Wire(Peripheral):
    """Board wires joining pairs of uio pins into open-drain buses with a pull-up (wired-AND)."""

    def __init__(self, *pairs: tuple[int, int]) -> None:
        self.pairs = pairs

    def tick(self, bench: Bench) -> None:
        for a, b in self.pairs:
            low = any(bench.uio_oe >> p & 1 and not bench.uio_out >> p & 1 for p in (a, b))
            for p in (a, b):
                bench.drive(p, 0 if low else None)


class JtagTap(Peripheral):
    """An IEEE 1149.1 TAP: the 16-state controller, a 4-bit IR, IDCODE (0b0001), BYPASS (0b1111).

    TMS and TDI are sampled on rising TCK; TDO changes on falling TCK (the LSB of the shift
    register in Shift-IR/Shift-DR, else held).
    """

    NEXT: ClassVar[dict[str, tuple[str, str]]] = {  # state: (next if TMS=0, next if TMS=1)
        "reset": ("idle", "reset"),
        "idle": ("idle", "select_dr"),
        "select_dr": ("capture_dr", "select_ir"),
        "capture_dr": ("shift_dr", "exit1_dr"),
        "shift_dr": ("shift_dr", "exit1_dr"),
        "exit1_dr": ("pause_dr", "update_dr"),
        "pause_dr": ("pause_dr", "exit2_dr"),
        "exit2_dr": ("shift_dr", "update_dr"),
        "update_dr": ("idle", "select_dr"),
        "select_ir": ("capture_ir", "reset"),
        "capture_ir": ("shift_ir", "exit1_ir"),
        "shift_ir": ("shift_ir", "exit1_ir"),
        "exit1_ir": ("pause_ir", "update_ir"),
        "pause_ir": ("pause_ir", "exit2_ir"),
        "exit2_ir": ("shift_ir", "update_ir"),
        "update_ir": ("idle", "select_dr"),
    }

    def __init__(self, tck: int, tms: int, tdi: int, tdo: int, idcode: int) -> None:
        self.tck, self.tms, self.tdi, self.tdo = tck, tms, tdi, tdo
        self.idcode = idcode
        self.state = "reset"
        self.ir = 0b0001  # IDCODE after reset
        self.shift = 0
        self.width = 0
        self._prev = 0
        self._out = 0

    def tick(self, bench: Bench) -> None:
        tck = bench.level(self.tck)
        if tck and not self._prev:  # rising: sample, then move
            tms, tdi = bench.level(self.tms), bench.level(self.tdi)
            st = self.state
            if st in ("shift_dr", "shift_ir"):
                self.shift = (self.shift >> 1) | (tdi << (self.width - 1))
            nxt = self.NEXT[st][tms]
            if nxt == "reset":
                self.ir = 0b0001
            elif nxt == "capture_ir":
                self.shift, self.width = 0b0101, 4  # IR capture value ends in 01, as 1149.1 requires
            elif nxt == "capture_dr":
                if self.ir == 0b0001:
                    self.shift, self.width = self.idcode, 32
                else:
                    self.shift, self.width = 0, 1  # BYPASS
            elif nxt == "update_ir":
                self.ir = self.shift & 0xF
            self.state = nxt
        elif self._prev and not tck and self.state in ("shift_dr", "shift_ir"):  # falling: TDO
            self._out = self.shift & 1
        bench.drive(self.tdo, self._out)
        self._prev = tck
