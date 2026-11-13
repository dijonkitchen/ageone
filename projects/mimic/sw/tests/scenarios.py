"""Scenarios that run on the golden model (pytest) and on the RTL (cocotb, in lockstep).

Each scenario is an `async def (bench) -> None` that loads programs through the SPI host
port, drives peripherals, and asserts on what comes back. Register a scenario in ALL.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from mimic import assemble, isa
from mimic.bench import Bench

Scenario = Callable[[Bench], Awaitable[None]]
ALL: dict[str, Scenario] = {}


def scenario(fn: Scenario) -> Scenario:
    ALL[fn.__name__] = fn
    return fn


@scenario
async def chip_id(b: Bench) -> None:
    assert await b.read(isa.REG_ID) == [isa.CHIP_ID]
    await b.write(isa.REG_PADCTRL, 0xA5)
    assert await b.read(isa.REG_PADCTRL) == [0xA5]
    await b.write(isa.REG_PADCTRL, 0)


@scenario
async def blink(b: Bench) -> None:
    prog = assemble(
        """
        .set_pins uio0 2
        .pindirs uio0 uio1
            set pins, 1 [3]
            set pins, 2 [3]
        """
    )
    await b.load(prog, 0, start=True)
    seen = []
    for _ in range(16):
        await b.step()
        seen.append(b.uio_out & 3)
    assert b.uio_oe & 3 == 3
    # Each level holds for 4 cycles (1 + 3 delay).
    runs = "".join(str(v) for v in seen)
    assert "1111" in runs and "2222" in runs and "11111" not in runs, runs


@scenario
async def fifo_echo(b: Bench) -> None:
    prog = assemble(
        """
            pull
            mov isr, ~osr
            push
        """
    )
    await b.load(prog, 1, start=True)
    words = [0, 1, 0xDEADBEEF, 0x80000000, 0x12345678]
    await b.put(1, *words[:2])
    got = await b.get(1, 2)
    await b.put(1, *words[2:])
    got += await b.get(1, 3)
    assert got == [(~w) & isa.M32 for w in words], [hex(g) for g in got]


# ---------------------------------------------------------------------------
# Random differential tests: any bit pattern is a valid instruction, so random words,
# random configuration, random pin activity and random host traffic exercise every
# encoding. On the model they only check for crashes; under cocotb the lockstep compare
# holds the RTL to the model every cycle.
# ---------------------------------------------------------------------------

import random

from mimic.bench import Peripheral


class PinNoise(Peripheral):
    """Toggles board-driven pins at random: ui0-4 and uio0-7 (when the chip is not driving)."""

    def __init__(self, rng: random.Random, rate: float = 0.05) -> None:
        self.rng = rng
        self.rate = rate

    def tick(self, bench: Bench) -> None:
        for g in [*range(8), *range(16, 21)]:
            if self.rng.random() < self.rate:
                choice = self.rng.random()
                bench.drive(g, None if (choice < 0.3 and g < 8) else self.rng.getrandbits(1))


def random_instr(rng: random.Random) -> int:
    """A random instruction word, shaped so programs keep moving (most waits time out)."""
    op = rng.choices(range(16), weights=[7, 3, 6, 6, 4, 7, 2, 6, 5, 5, 1, 1, 1, 1, 1, 1])[0]
    junk = rng.getrandbits(20) if rng.random() < 0.3 else 0  # set unused bits sometimes
    sd = rng.getrandbits(8) if rng.random() < 0.1 else rng.getrandbits(2)
    r = rng.getrandbits
    if op == isa.OP_JMP:
        cond = rng.randrange(18) if rng.random() < 0.9 else rng.randrange(32)
        args = (cond << 15) | (r(1) << 14) | (r(5) << 9) | r(6) | (junk & (7 << 6))
    elif op == isa.OP_WAIT:
        src = rng.choice([0, 0, 1, 1, 2, 2, 3, rng.randrange(8)])
        tmo = int(rng.random() < 0.85)
        args = (r(1) << 19) | (src << 16) | (tmo << 15) | (r(1) << 14) | (r(5) << 9) | (junk & 0x1FF)
    elif op in (isa.OP_IN, isa.OP_OUT):
        args = (r(4) << 16) | (r(5) << 4) | r(4) | (junk & 0xFE00)
    elif op == isa.OP_PUSHPULL:
        args = (r(1) << 19) | (r(1) << 18) | (int(rng.random() < 0.5) << 17) | (junk & 0x1FFFF)
    elif op == isa.OP_IRQ:
        wait = int(rng.random() < 0.15)
        args = (r(1) << 19) | (wait << 18) | (r(1) << 14) | (r(3) << 9) | (junk & 0x31FF)
    elif op == isa.OP_SET:
        imm = r(4) if rng.random() < 0.7 else r(16)
        args = (r(4) << 16) | imm
    else:
        args = r(20)
    return (op << 28) | (sd << 20) | args


def random_config(rng: random.Random, sm: int) -> list[tuple[int, int]]:
    regs = [
        (isa.SM_CLKDIV, (rng.choice([1, 1, 1, 2, 3]) << 16) | (rng.choice([0, 0, 0x40, 0x80]) << 8)),
        (isa.SM_EXECCTRL, rng.getrandbits(28)),
        (isa.SM_SHIFTCTRL, rng.getrandbits(23) & ~(3 << 16) | (rng.choice([0, 0, 1, 2]) << 16)),
        (isa.SM_PINCTRL, rng.getrandbits(26)),
        (isa.SM_CRCCFG, rng.getrandbits(3)),
    ]
    return [(isa.sm_reg(sm, r), v) for r, v in regs]


async def random_isa(b: Bench, seed: int, cycles: int = 6000) -> None:
    rng = random.Random(seed)
    b.add(PinNoise(rng))
    words = [random_instr(rng) for _ in range(isa.IMEM_WORDS)]
    await b.write(isa.REG_IMEM, *words)
    if hasattr(b.dev, "check_every"):
        b.dev.check_every = 1  # compare SM registers with the model every cycle
    for sm in range(4):
        for addr, v in random_config(rng, sm):
            await b.write(addr, v)
        await b.exec(sm, isa.enc_set(isa.DST["x"], rng.randrange(64)))
        await b.exec(sm, isa.enc_jmp(0, rng.randrange(64)))
    await b.write(isa.REG_PADCTRL, rng.getrandbits(8))
    await b.write(isa.REG_CTRL, isa.pack_ctrl(enable=15, div_restart=15))
    end = b.cycle + cycles
    while b.cycle < end:
        r = rng.random()
        sm = rng.randrange(4)
        if r < 0.25:
            # Small and special values make equal operands and zeros likely.
            v = rng.choice([0, 1, 2, 3, isa.M32, 0x80000000, rng.getrandbits(32), rng.getrandbits(32)])
            await b.write(isa.sm_reg(sm, isa.SM_TXF), v, inc=False)
        elif r < 0.45:
            await b.read(isa.sm_reg(sm, isa.SM_RXF), rng.randint(1, 3), inc=False)
        elif r < 0.55:
            await b.write(isa.REG_IRQ if rng.random() < 0.5 else isa.REG_IRQ_FORCE, rng.getrandbits(8))
        elif r < 0.62:
            await b.read(isa.sm_reg(sm, rng.choice([isa.SM_INSTR, isa.SM_PC, isa.SM_X, isa.SM_Y, isa.SM_STAT])))
        elif r < 0.68:
            await b.read(rng.choice([isa.REG_FLEVEL, isa.REG_FDEBUG, isa.REG_PINS, isa.REG_PINOUT, isa.REG_PINOE]))
        elif r < 0.71:
            await b.exec(sm, random_instr(rng))
        elif r < 0.73:
            await b.exec(sm, isa.enc_jmp(0, rng.randrange(64)))  # unstick
        elif r < 0.77:
            addr, v = rng.choice(random_config(rng, sm))
            await b.write(addr, v)
        elif r < 0.80:
            await b.write(isa.REG_IMEM + rng.randrange(64), random_instr(rng))
        elif r < 0.83:
            ctrl = isa.pack_ctrl(
                enable=rng.getrandbits(4) | rng.getrandbits(4),
                restart=rng.getrandbits(4) & rng.getrandbits(4),
                div_restart=rng.getrandbits(4),
                step=rng.getrandbits(4),
                tx_clear=rng.getrandbits(4) & rng.getrandbits(4),
                rx_clear=rng.getrandbits(4) & rng.getrandbits(4),
            )
            await b.write(isa.REG_CTRL, ctrl)
        elif r < 0.85:
            await b.write(isa.REG_FDEBUG, rng.getrandbits(20))
        else:
            await b.step(rng.randint(1, 60))


def _random_scenario(seed: int) -> Scenario:
    async def run(b: Bench) -> None:
        await random_isa(b, seed)

    run.__name__ = f"random_isa_{seed}"
    return run


for _seed in range(6):
    ALL[f"random_isa_{_seed}"] = _random_scenario(_seed)


# ---------------------------------------------------------------------------
# UART
# ---------------------------------------------------------------------------

from mimic import periph, programs

UART_TX_PIN = 8  # uo0
UART_RX_PIN = 16  # ui0


@scenario
async def uart_tx(b: Bench) -> None:
    div = 2
    rx = b.add(periph.UartRx(UART_TX_PIN, bit=8 * div))
    await b.load(programs.load("uart_tx", TX=UART_TX_PIN, DIV=div), 0, start=True)
    data = b"Mimic\x00\xff\x55"
    await b.put(0, *data)
    await b.until(lambda: len(rx.data) == len(data), what="UART bytes")
    assert bytes(rx.data) == data and rx.framing_errors == 0, rx.data


@scenario
async def uart_rx(b: Bench) -> None:
    div = 6  # the host polls over SPI; keep the line slower than the host
    tx = b.add(periph.UartTx(UART_RX_PIN, bit=8 * div))
    await b.load(programs.load("uart_rx", RX=UART_RX_PIN, DIV=div), 2, start=True)
    data = b"\x00\xa5\xff\x01ok"
    tx.send(data)
    got = await b.get(2, len(data))
    assert bytes(got) == data, got
    # A framing error raises IRQ 2 (0 + SM2) and drops the byte; the next byte still arrives.
    tx.send(b"\x33", framing_error=True)
    await b.until(lambda: tx.idle, what="bad frame sent")
    await b.step(8 * div * 2)  # the line idles before the next frame, as after any break
    tx.send(b"\x44")
    got = await b.get(2, 1)
    assert got == [0x44], got
    assert (await b.read(isa.REG_IRQ))[0] & (1 << 2)


@scenario
async def uart_bridge(b: Bench) -> None:
    """UART RX on SM0 routed into UART TX on SM1 at a different baud: no host in the data path."""
    tx = b.add(periph.UartTx(UART_RX_PIN, bit=8 * 3))
    rx = b.add(periph.UartRx(UART_TX_PIN, bit=8 * 2.5))
    rx_prog = programs.load("uart_rx", RX=UART_RX_PIN, DIV=3)
    rx_prog.config.route = True
    await b.load(rx_prog, 0, origin=0)
    tx_prog = programs.load("uart_tx", TX=UART_TX_PIN)
    tx_prog.config.clkdiv = 2.5  # fractional divider
    await b.load(tx_prog, 1, origin=16)
    await b.start(0b11)
    data = b"bridge!"
    tx.send(data)
    await b.until(lambda: len(rx.data) == len(data), limit=20_000, what="bridged bytes")
    assert bytes(rx.data) == data, rx.data


# ---------------------------------------------------------------------------
# SPI, I2C, WS2812
# ---------------------------------------------------------------------------

from mimic import protocols

SPI_CS, SPI_MOSI, SPI_MISO, SPI_SCK = 0, 1, 2, 3  # uio0-3, the Pmod SPI layout


def _spi_ctrl(mode: int) -> Scenario:
    async def run(b: Bench) -> None:
        reply = bytes([0x5A, 0x01, 0xFE, 0x80])
        dev = b.add(periph.SpiTarget(SPI_SCK, SPI_MOSI, SPI_MISO, SPI_CS, mode=mode, reply=reply))
        prog = programs.load("spi_ctrl", CPOL=mode >> 1, CPHA=mode & 1, DIV=4)
        await b.load(prog, 3, start=True)
        data = bytes([0xA5, 0x3C, 0x00, 0xFF])
        for chunk in (data[:1], data[1:]):
            await b.put(3, *protocols.spi_words(chunk))
        got = await b.get(3, 4)
        await b.until(lambda: len(dev.transactions) == 2, what="CS deasserted")
        assert dev.transactions == [data[:1], data[1:]], dev.transactions
        assert bytes(got) == reply, [hex(g) for g in got]
        assert not b.contention

    run.__name__ = f"spi_ctrl_mode{mode}"
    return run


for _mode in range(4):
    ALL[f"spi_ctrl_mode{_mode}"] = _spi_ctrl(_mode)


@scenario
async def spi_target(b: Bench) -> None:
    ctl = b.add(periph.SpiController(SPI_SCK, SPI_MOSI, SPI_MISO, SPI_CS, half=10))
    await b.load(programs.load("spi_target"), 1, start=True)
    await b.put(1, 0xC3 << 24, 0x7E << 24)
    ctl.transfer(bytes([0x12, 0x34, 0x56]))
    await b.until(lambda: ctl.idle, what="SPI transfer")
    assert ctl.received == [bytes([0xC3, 0x7E, 0xFF])], ctl.received
    got = await b.get(1, 3)
    assert got == [0x12, 0x34, 0x56], got


async def _i2c(b: Bench, stretch: int) -> None:
    dev = b.add(periph.I2CTarget(scl=2, sda=3, addr=0x50, stretch=stretch))
    await b.load(programs.load("i2c", SCL=2, SDA=3, DIV=4), 0, start=True)
    # Write two bytes at register 0x10, then set the pointer back and read them.
    slots = protocols.i2c_write(0x50, bytes([0x10, 0xCA, 0xFE]))
    slots += protocols.i2c_write(0x50, bytes([0x10]), stop=False) + protocols.i2c_read(0x50, 2)
    results: list[int] = []
    for s in slots:
        await b.put(0, s)
        if (await b.levels(0))[1]:
            results += await b.get(0, (await b.levels(0))[1])
    results += await b.get(0, len(slots) - len(results))
    # Slots: 4 for the write, 2 to set the pointer, 1 address for the read, 2 data bytes.
    assert all(protocols.i2c_acked(r) for r in results[:7]), [hex(r) for r in results]
    assert [protocols.i2c_byte(r) for r in results[7:]] == [0xCA, 0xFE], [hex(r) for r in results]
    assert dev.mem[0x10:0x12] == b"\xca\xfe"
    await b.until(lambda: dev.log[-1] == "P", what="STOP")
    # A missing target does not ACK.
    await b.put(0, *protocols.i2c_write(0x23, b""))
    assert not protocols.i2c_acked((await b.get(0, 1))[0])
    assert not b.contention
    if stretch:
        assert dev.stretched > 0, "the target never held SCL low after the controller released it"


@scenario
async def i2c(b: Bench) -> None:
    await _i2c(b, stretch=0)


@scenario
async def i2c_stretch(b: Bench) -> None:
    await _i2c(b, stretch=40)


@scenario
async def ws2812(b: Bench) -> None:
    div = 2
    leds = b.add(periph.Ws2812(9, threshold=int(4.5 * div), reset=60 * div))
    await b.load(programs.load("ws2812", DOUT=9, DIV=div), 2, start=True)
    colors = [0xFF0000, 0x00FF00, 0x0000FF, 0x123456]
    await b.put(2, *[protocols.ws2812_word(c) for c in colors])
    await b.until(lambda: len(leds.frames) == 1, what="LED frame")
    assert leds.frames[0] == colors, [hex(c) for c in leds.frames[0]]


# ---------------------------------------------------------------------------
# 10BASE-T style Ethernet: Manchester, preamble and SFD, CRC-32 in hardware
# ---------------------------------------------------------------------------

import zlib

ETH_TXD = 10  # uo2
ETH_RXD = 17  # ui1


async def _eth_tx(b: Bench, div: int, payload: bytes, half: int = 3) -> None:
    rx = b.add(periph.ManchesterRx(ETH_TXD, bit=2 * half * div))
    await b.load(programs.load("eth_tx", TXD=ETH_TXD, DIV=div, HALF=half), 0, start=True)
    await b.put(0, *protocols.eth_tx_words(payload))
    await b.until(lambda: len(rx.frames) == 1, limit=50_000, what="Ethernet frame")
    frame = rx.frames[0]
    assert frame[:-4] == payload, frame.hex()
    assert frame[-4:] == protocols.eth_fcs(payload), (frame[-4:].hex(), protocols.eth_fcs(payload).hex())


@scenario
async def eth_tx_line_rate(b: Bench) -> None:
    """10 Mb/s at 60 MHz: 6 cycles a bit, a frame that fits the joined TX FIFO."""
    await _eth_tx(b, 1, bytes(range(0x30, 0x3C)))


@scenario
async def eth_tx(b: Bench) -> None:
    await _eth_tx(b, 2, b"Mimic sends Ethernet frames!", half=4)


async def _eth_rx(b: Bench, half: int, payload: bytes, bit_scale: float, phase: float) -> None:
    tx = b.add(periph.ManchesterTx(ETH_RXD, bit=2 * half * bit_scale, phase=phase))
    await b.load(programs.load("eth_rx", RXD=ETH_RXD, HALF=half), 1, start=True)
    frame = payload + protocols.eth_fcs(payload)
    tx.send(periph.manchester_frame_bits(frame))
    words: list[int] = []
    while True:
        n = (await b.levels(1))[1]
        if n:
            words += await b.read(isa.sm_reg(1, isa.SM_RXF), n, inc=False)
        elif (await b.read(isa.REG_IRQ))[0] & (1 << 1):
            break
    data, crc = protocols.eth_rx_frame(words)
    assert data == frame, (data.hex(), frame.hex())
    assert crc == protocols.ETH_RESIDUE, hex(crc)
    assert zlib.crc32(data) == 0x2144DF1C  # the same check, in software


@scenario
async def eth_rx_line_rate(b: Bench) -> None:
    """10 Mb/s with the transmitter 0.5% slow and out of phase with the chip's clock."""
    await _eth_rx(b, 3, b"\x01\x80\xc2\x00", bit_scale=1.005, phase=0.37)


@scenario
async def eth_rx(b: Bench) -> None:
    await _eth_rx(b, 9, b"Mimic receives frames too", bit_scale=0.997, phase=0.71)


# ---------------------------------------------------------------------------
# Low-speed USB receive: two SMs chained by the FIFO route
# ---------------------------------------------------------------------------

USB_DM, USB_DP = 18, 19  # ui2, ui3


async def _usb_rx(b: Bench, bit_scale: float) -> None:
    host = b.add(periph.UsbLsHost(USB_DM, USB_DP, bit=40 * bit_scale))
    await b.load(programs.load("usb_ls_rx", DM=USB_DM), 2, origin=0)
    await b.load(programs.load("usb_ls_rx_pkt"), 3, origin=34)  # 34 + 30 = all 64 words
    await b.start(0b1100)
    pid = protocols.USB_PID
    packets = [
        (pid["SETUP"], b"", (0x00, 0)),
        (pid["DATA0"], bytes([0x80, 0x06, 0x00, 0x01, 0x00, 0x00, 0x40, 0x00]), None),
        (pid["IN"], b"", (0x15, 3)),
        (pid["DATA1"], bytes([0xFF] * 4 + [0x7F, 0x3F]), None),  # long runs of 1s: bit stuffing
    ]
    for p, payload, token in packets:
        host.send(periph.usb_bits(p, payload, token))
        words: list[int] = []
        start = b.cycle
        while True:
            assert b.cycle - start < 40_000, f"packet not received; words so far {[hex(w) for w in words]}"
            n = (await b.levels(3))[1]
            if n:
                words += await b.read(isa.sm_reg(3, isa.SM_RXF), n, inc=False)
            elif (await b.read(isa.REG_IRQ))[0] & (1 << 3):
                await b.write(isa.REG_IRQ, 1 << 3)
                break
        got, crc = protocols.eth_rx_frame(words)  # the same layout
        pid_byte = p | ((~p & 0xF) << 4)
        assert got[0] == pid_byte, (hex(got[0]), hex(pid_byte))
        if token is None:
            assert got[1:-2] == payload, got.hex()
            assert crc == protocols.USB_CRC16_RESIDUE, hex(crc)
        else:
            assert crc == protocols.USB_CRC5_RESIDUE, hex(crc)
    assert not b.contention


@scenario
async def usb_ls_rx(b: Bench) -> None:
    await _usb_rx(b, 1.0)


@scenario
async def usb_ls_rx_fast_host(b: Bench) -> None:
    """The host's clock 1.5% fast, the limit low-speed USB allows."""
    await _usb_rx(b, 1 / 1.015)


@scenario
async def usb_ls_rx_slow_host(b: Bench) -> None:
    await _usb_rx(b, 1.015)


# ---------------------------------------------------------------------------
# Protocols Mimic was not built around: PS/2, NEC infrared via pulse capture, PWM
# ---------------------------------------------------------------------------


@scenario
async def ps2_rx(b: Bench) -> None:
    kbd = b.add(periph.Ps2Device(clk=5, data=4, half=30))
    await b.load(programs.load("ps2_rx", DATA=4, CLK=5), 0, start=True)
    codes = bytes([0x1C, 0xF0, 0x1C, 0x5A])  # 'a' make, break, Enter
    kbd.send(codes)
    kbd.send(b"\x29", bad_parity=True)
    words = await b.get(0, 5)
    assert bytes(w & 0xFF for w in words) == codes + b"\x29", [hex(w) for w in words]
    assert [w >> 9 & 1 for w in words] == [1, 1, 1, 1, 0], [hex(w) for w in words]


@scenario
async def nec_ir(b: Bench) -> None:
    """Pulse capture turns an NEC remote frame into durations; host software decodes them."""
    unit = 500  # cycles per 562.5 us: 67 times faster than at 60 MHz, slow enough for the test's host
    b.drive(20, 1)  # the receiver idles high
    await b.load(programs.load("pulse_capture", PIN=20), 1, start=True)
    b.add(periph.PulseTrain(20, periph.nec_pulses(0x04, 0x08, unit)))
    words: list[int] = []
    start = b.cycle
    while len(words) < 67:
        assert b.cycle - start < 150_000, f"{len(words)} pulses captured"
        n = (await b.levels(1))[1]
        words += await b.read(isa.sm_reg(1, isa.SM_RXF), n, inc=False) if n else []
        if not n:
            await b.step(50)
    got = protocols.nec_decode(protocols.pulses(words), unit)
    assert got == (0x04, 0x08), (got, protocols.pulses(words)[:8])


@scenario
async def pwm_capture_loopback(b: Bench) -> None:
    """PWM on internal pin v0 (GPIO 24), measured by pulse capture on the same internal pin."""
    await b.load(programs.load("pwm", OUT="v0", DIV=40), 0, origin=0)
    await b.load(programs.load("pulse_capture", PIN="v0"), 1, origin=16)
    await b.start(0b11)
    period, duty = 20, 6
    await b.put(0, (period << 16) | duty)
    words = await b.get(1, 10)
    widths = protocols.pulses(words)[2:]  # skip the start-up pulses
    highs = {n for lv, n in widths if lv == 1}
    lows = {n for lv, n in widths if lv == 0}
    assert len(highs) == 1 and len(lows) == 1, widths  # every period identical
    high, low = highs.pop(), lows.pop()
    # 3 ticks a count; high for duty+1 counts plus the 7-tick reload, low for the rest.
    assert (high, low) == (40 * (3 * (duty + 1) + 7), 40 * 3 * (period - duty)), (high, low)


# ---------------------------------------------------------------------------
# Directed ISA tests: expected values come from the spec (docs/isa.md), computed here
# independently of the model, and the host drives a stopped SM through INSTR (debug).
# ---------------------------------------------------------------------------

M32 = isa.M32
SM_DBG = 3


async def _set(b: Bench, sm: int, dst: str, value: int) -> None:
    """Load a 32-bit value into an SM register through the TX FIFO."""
    await b.write(isa.sm_reg(sm, isa.SM_TXF), value, inc=False)
    await b.exec(sm, isa.enc_pull(block=False))
    await b.exec(sm, isa.enc_mov(isa.DST[dst], isa.SRC["osr"]))


async def _x(b: Bench, sm: int) -> int:
    return (await b.read(isa.sm_reg(sm, isa.SM_X)))[0]


@scenario
async def isa_alu(b: Bench) -> None:
    def ref(op: str, a: int, c: int) -> int:
        k = c & 31
        return {
            "add": (a + c) & M32,
            "sub": (a - c) & M32,
            "and": a & c,
            "or": a | c,
            "xor": a ^ c,
            "shl": (a << k) & M32,
            "shr": a >> k,
            "rol": ((a << k) | (a >> (32 - k))) & M32 if k else a,
        }[op]

    pairs = [(0x12345678, 0x0F0F0F0F), (0xFFFFFFFF, 1), (5, 37), (0x80000001, 0x1F)]
    for a, c in pairs:
        for op in isa.ALU:
            await _set(b, SM_DBG, "x", a)
            await _set(b, SM_DBG, "y", c)
            await b.exec(SM_DBG, isa.enc_alu(False, isa.ALU[op], isa.SRC["y"]))
            assert await _x(b, SM_DBG) == ref(op, a, c), (op, hex(a), hex(c))
    # The immediate form, writing Y.
    await _set(b, SM_DBG, "y", 1000)
    await b.exec(SM_DBG, isa.enc_alui(True, isa.ALU["sub"], 1001))
    assert (await b.read(isa.sm_reg(SM_DBG, isa.SM_Y)))[0] == M32


@scenario
async def isa_shifts(b: Bench) -> None:
    word, src = 0x8D2C_6B4F, 0x1234_5679
    for right in (True, False):
        await b.write(isa.sm_reg(SM_DBG, isa.SM_SHIFTCTRL), isa.pack_shiftctrl(in_right=right, out_right=right))
        for n in (1, 3, 8, 17, 31, 32):
            mask = (1 << n) - 1
            # OUT: the n bits that leave OSR first, and what remains.
            await _set(b, SM_DBG, "osr", word)
            await b.exec(SM_DBG, isa.enc_out(isa.DST["x"], n))
            want = word & mask if right else word >> (32 - n)
            assert await _x(b, SM_DBG) == want, ("out", right, n)
            await b.exec(SM_DBG, isa.enc_mov(isa.DST["x"], isa.SRC["osr"]))
            rest = (word >> n if right else (word << n) & M32) if n < 32 else 0
            assert await _x(b, SM_DBG) == rest, ("osr", right, n)
            # IN: n bits of Y enter ISR.
            await _set(b, SM_DBG, "isr", word)
            await _set(b, SM_DBG, "y", src)
            await b.exec(SM_DBG, isa.enc_in(isa.SRC["y"], n))
            await b.exec(SM_DBG, isa.enc_mov(isa.DST["x"], isa.SRC["isr"]))
            if right:
                want = ((word >> n) | ((src & mask) << (32 - n))) & M32 if n < 32 else src
            else:
                want = ((word << n) | (src & mask)) & M32 if n < 32 else src
            assert await _x(b, SM_DBG) == want, ("in", right, n)
    # MOV operations: invert, bit reverse, byte swap.
    for op, want in ((1, ~word & M32), (2, int(f"{word:032b}"[::-1], 2)), (3, 0x4F6B_2C8D)):
        await _set(b, SM_DBG, "y", word)
        await b.exec(SM_DBG, isa.enc_mov(isa.DST["x"], isa.SRC["y"], op))
        assert await _x(b, SM_DBG) == want, ("mov", op)


@scenario
async def isa_jmp(b: Bench) -> None:
    cases = [  # (cond, x, y, taken)
        ("always", 0, 0, True),
        ("!x", 0, 5, True),
        ("!x", 1, 5, False),
        ("x--", 0, 0, False),
        ("x--", 7, 0, True),
        ("!y", 3, 0, True),
        ("y--", 0, 1, True),
        ("x!=y", 4, 4, False),
        ("x!=y", 4, 5, True),
        ("x==y", 0, 0, True),
        ("x<y", 3, 4, True),
        ("x<y", 4, 4, False),
        ("x<y", 0xFFFFFFFF, 1, False),  # unsigned
        ("x0", 6, 0, False),
        ("!x0", 6, 0, True),
    ]
    for cond, x, y, taken in cases:
        await _set(b, SM_DBG, "x", x)
        await _set(b, SM_DBG, "y", y)
        await b.exec(SM_DBG, isa.enc_jmp(0, 10))
        await b.exec(SM_DBG, isa.enc_jmp(isa.COND[cond], 40))
        pc = (await b.read(isa.sm_reg(SM_DBG, isa.SM_PC)))[0]
        # A forced instruction does not advance the PC; a taken jump moves it.
        assert pc == (40 if taken else 10), (cond, x, y, pc)
        if cond == "x--":
            assert await _x(b, SM_DBG) == (x - 1) & M32


async def _crc_of(b: Bench, data: bytes, poly: int, init: int, reflect: bool) -> int:
    """Feed `data` bit by bit through OUT (LSB first if reflect, else MSB first); return CRC."""
    prog = assemble(
        f"""
        .crc {poly} {"reflect" if reflect else ""} out init {init}
        .shift_out {"right" if reflect else "left"} autopull 8
        .fifo tx
            out null, 1
        """
    )
    await b.load(prog, 2, start=True)
    await b.put(2, *[(c if reflect else c << 24) for c in data])
    await b.step(64)
    while (await b.levels(2))[0]:
        await b.step(64)
    await b.step(32)
    await b.stop(1 << 2)
    return await b.peek(2, "crc")


@scenario
async def isa_crc(b: Bench) -> None:
    check = b"123456789"
    # CRC-32 (Ethernet): reflected, init all ones, final XOR all ones.
    crc = await _crc_of(b, check, 0xEDB88320, M32, reflect=True)
    assert crc ^ M32 == zlib.crc32(check) == 0xCBF43926, hex(crc)
    # CRC-16/CCITT-FALSE: MSB first, left-aligned in the register: check value 0x29B1.
    crc = await _crc_of(b, check, 0x1021 << 16, 0xFFFF << 16, reflect=False)
    assert crc >> 16 == 0x29B1, hex(crc)
    # CRC-16/USB data CRC (the program uses the reflected form): check value 0xB4C8.
    crc = await _crc_of(b, check, 0xA001, 0xFFFF, reflect=True)
    assert crc ^ 0xFFFF == 0xB4C8, hex(crc)


async def _pulse_width(b: Bench, pin: int, src: str, setup: list[tuple[int, int]] | None = None) -> list[int]:
    """Load `src`, run it, and return the lengths of the high pulses seen on `pin`."""
    widths: list[int] = []
    state = {"prev": 0, "start": 0}

    def watch(bb: Bench) -> None:
        lv = bb.level(pin)
        if lv and not state["prev"]:
            state["start"] = bb.cycle
        if not lv and state["prev"]:
            widths.append(bb.cycle - state["start"])
        state["prev"] = lv

    await b.load(assemble(src), 0)
    for addr, v in setup or []:
        await b.write(addr, v)
    b.monitors.append(watch)
    await b.start(1)
    await b.step(400)
    await b.stop(1)
    b.monitors.remove(watch)
    return widths


@scenario
async def isa_timing(b: Bench) -> None:
    # Side-set and delay: high for 1+5 ticks, low for 1+2.
    widths = await _pulse_width(
        b,
        9,
        """
        .side_set 1
        .side_pins uo1
            nop side 1 [5]
            nop side 0 [2]
        """,
    )
    assert set(widths[1:]) == {6}, widths
    # A WAIT that times out takes X + 1 ticks; set + set + wait(11) + set = high for 13.
    widths = await _pulse_width(
        b,
        9,
        """
        .set_pins uo1 1
            set pins, 1
            set x, 10
            wait 1 gpio ui4 timeout
            set pins, 0 [20]
        """,
    )
    assert set(widths[1:]) == {13}, widths
    # The clock divider: 2.5 cycles a tick on average, so the 6-tick high pulse lasts 15.
    widths = await _pulse_width(
        b,
        9,
        """
        .side_set 1
        .side_pins uo1
        .clkdiv 2.5
            nop side 1 [5]
            nop side 0 [5]
        """,
    )
    assert set(widths[1:]) <= {15} and widths, widths


@scenario
async def isa_exec_irq(b: Bench) -> None:
    # OUT EXEC runs a word from the FIFO as the next instruction.
    prog = assemble(
        """
            pull
            out exec, 32
            push
        """
    )
    await b.load(prog, 0, start=True)
    await b.put(0, isa.enc_mov(isa.DST["isr"], isa.SRC["osr"]))  # runs as the next instruction
    # ...then `push` sends ISR = OSR (empty after the OUT: 0)...
    assert await b.get(0, 1) == [0]
    # IRQ handshake: SM2 raises flag 5 and waits until it is cleared; SM1 waits for the flag,
    # which clears it, so both go on.
    waiter = assemble("    wait 1 irq 5\n    set x, 77\nend:\n    jmp end\n")
    setter = assemble("    irq wait 5\n    set x, 88\nend:\n    jmp end\n")
    await b.load(waiter, 1, origin=8)
    await b.load(setter, 2, origin=16)
    await b.write(isa.REG_IRQ, 0xFF)
    await b.start(0b110)
    await b.step(100)
    assert await _x(b, 1) == 77 and await _x(b, 2) == 88
    assert (await b.read(isa.REG_IRQ))[0] == 0


@scenario
async def i2c_loopback(b: Bench) -> None:
    """The I2C controller on SM0 writes to the I2C target on SM1 over wires on the board."""
    b.add(periph.Wire((2, 6), (3, 7)))
    await b.load(programs.load("i2c", SCL=2, SDA=3, DIV=8), 0, origin=0)
    await b.load(programs.load("i2c_target", SCL=6, SDA=7, ADDR=0x42), 1, origin=22)
    await b.start(0b11)
    data = bytes([0x5A, 0x00, 0xFF])
    slots = protocols.i2c_write(0x42, data) + protocols.i2c_write(0x17, b"\x99")
    results: list[int] = []
    for slot in slots:
        await b.put(0, slot)
        results += await b.get(0, 1)
    assert [protocols.i2c_acked(r) for r in results] == [True] * 4 + [False, False], [hex(r) for r in results]
    got = await b.get(1, 4)
    assert got == [*data, 0x100], [hex(g) for g in got]
