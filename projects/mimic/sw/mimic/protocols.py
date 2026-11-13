"""Host-side helpers for the example programs' FIFO word formats (see programs/*.mim)."""

from __future__ import annotations

import zlib

# ---- spi_ctrl ---------------------------------------------------------------


def spi_words(data: bytes) -> list[int]:
    """TX FIFO words for one chip-select-framed transfer of `data`."""
    return [8 * len(data) - 1] + [b << 24 for b in data]


# ---- i2c --------------------------------------------------------------------

I2C_START = 1 << 31
I2C_STOP = 1 << 30


def i2c_slot(nine_bits: int, start: bool = False, stop: bool = False) -> int:
    return (I2C_START if start else 0) | (I2C_STOP if stop else 0) | ((nine_bits & 0x1FF) << 21)


def i2c_write(addr: int, data: bytes, stop: bool = True) -> list[int]:
    """Slots for START, address+W, the data bytes, and optionally STOP."""
    out = [i2c_slot((addr << 2) | 1, start=True)]  # (addr << 1 | W) << 1 | release for ACK
    for i, b in enumerate(data):
        out.append(i2c_slot((b << 1) | 1, stop=stop and i == len(data) - 1))
    if not data and stop:
        out[-1] |= I2C_STOP
    return out


def i2c_read(addr: int, count: int) -> list[int]:
    """Slots for (repeated) START, address+R, then `count` bytes ACKed but the last, then STOP."""
    out = [i2c_slot((((addr << 1) | 1) << 1) | 1, start=True)]
    for i in range(count):
        last = i == count - 1
        out.append(i2c_slot(0x1FE | int(last), stop=last))
    return out


def i2c_acked(result: int) -> bool:
    return result & 1 == 0


def i2c_byte(result: int) -> int:
    return (result >> 1) & 0xFF


# ---- ws2812 -----------------------------------------------------------------


def ws2812_word(grb: int) -> int:
    return (grb & 0xFFFFFF) << 8


# ---- eth_tx / eth_rx -----------------------------------------------------------

ETH_PREAMBLE = bytes([0x55] * 7 + [0xD5])
ETH_RESIDUE = 0xDEBB20E3  # CRC register after data and a good FCS (reflected, no final XOR)


def eth_fcs(data: bytes) -> bytes:
    return zlib.crc32(data).to_bytes(4, "little")


def eth_tx_words(data: bytes) -> list[int]:
    """TX FIFO words for eth_tx: header, then the data packed LSB first (the FCS is added on chip)."""
    padded = data + bytes(-len(data) % 4)
    return [8 * len(data) - 1] + [int.from_bytes(padded[i : i + 4], "little") for i in range(0, len(padded), 4)]


def eth_rx_frame(words: list[int]) -> tuple[bytes, int]:
    """Bytes eth_rx received (data then FCS) and its CRC register, from one frame's RX words."""
    *data_words, partial, crc, count = words
    k = count & 0x3F
    data = b"".join(w.to_bytes(4, "little") for w in data_words)
    if k:
        data += ((partial >> (32 - k)) & ((1 << k) - 1)).to_bytes((k + 7) // 8, "little")
    return data, crc


# ---- usb_ls_rx / usb_ls_rx_pkt -----------------------------------------------------

USB_CRC16_RESIDUE = 0xB001  # reflected form of the spec's 0x800D
USB_CRC5_RESIDUE = 0x06  # reflected form of the spec's 0b01100
USB_PID = {"OUT": 0x1, "IN": 0x9, "SETUP": 0xD, "DATA0": 0x3, "DATA1": 0xB, "ACK": 0x2, "NAK": 0xA}


# ---- pulse_capture -----------------------------------------------------------------


def pulses(words: list[int]) -> list[tuple[int, int]]:
    """(level, ticks) of each captured pulse: the level that lasted, and for how long."""
    return [(1 - (w & 1), (w >> 1) + 5) for w in words]  # + the 5 ticks the wait does not count


def nec_decode(pulse_list: list[tuple[int, int]], unit: float) -> tuple[int, int] | None:
    """(address, command) from the pulses of an NEC frame, or None if it does not check."""
    lows_highs = [p for p in pulse_list]
    i = next((k for k, (lv, n) in enumerate(lows_highs) if lv == 0 and n > 12 * unit), None)
    if i is None:
        return None
    bits = []
    for k in range(i + 3, i + 3 + 64, 2):  # skip the header burst and space, then each bit's space
        if k >= len(lows_highs):
            return None
        bits.append(1 if lows_highs[k][1] > 2 * unit else 0)
    data = [sum(bits[8 * j + b] << b for b in range(8)) for j in range(4)]
    if data[0] ^ data[1] != 0xFF or data[2] ^ data[3] != 0xFF:
        return None
    return data[0], data[2]
