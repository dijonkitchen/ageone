"""Host-side helpers for the example programs' FIFO word formats (see programs/*.mim)."""

from __future__ import annotations

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
