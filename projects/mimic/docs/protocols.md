# Protocols

Fourteen programs in [`programs/`](../programs), each tested on the golden model and on the RTL
against an independent model of the device at the other end ([`periph.py`](../sw/mimic/periph.py)),
written from the protocol's specification. Each program's comments explain its timing.

| Program | Words | Protocol | Highlights |
|---|---|---|---|
| [`uart_tx`](../programs/uart_tx.mim) | 4 | UART 8N1 transmit | Side-set start and stop bits; any baud through the fractional divider |
| [`uart_rx`](../programs/uart_rx.mim) | 12 | UART 8N1 receive | Samples mid-bit; framing errors raise an IRQ and resynchronize |
| [`spi_ctrl`](../programs/spi_ctrl.mim) | 7 | SPI controller, modes 0-3 | One program, `CPOL`/`CPHA` as defines; the program frames chip select from a header word |
| [`spi_target`](../programs/spi_target.mim) | 11 | SPI target, mode 0 | Replies from the TX FIFO, `0xFF` when the host has queued none (`pull ifempty noblock` from X); CS resynchronizes |
| [`i2c`](../programs/i2c.mim) | 22 | I2C controller | Open-drain pins; clock stretching; START, repeated START, STOP, ACK/NACK as a nine-bit slot per FIFO word |
| [`i2c_target`](../programs/i2c_target.mim) | 36 | I2C target (writes) | Address match with `x!=y`; ACK on open-drain SDA; STOP and repeated START detected mid-byte; tested against the `i2c` controller on another SM |
| [`ws2812`](../programs/ws2812.mim) | 4 | WS2812 LEDs | 800 kHz from a 7.5 divider |
| [`eth_tx`](../programs/eth_tx.mim) | 41 | 10BASE-T transmit | Manchester at 6 cycles a bit (10 Mb/s at 60 MHz); preamble, SFD; the CRC unit computes the FCS as bits go out |
| [`eth_rx`](../programs/eth_rx.mim) | 19 | 10BASE-T receive | Clock recovery from transitions; SFD search; CRC-32 check; end of frame by timeout |
| [`usb_ls_rx`](../programs/usb_ls_rx.mim) | 34 | Low-speed USB, line layer | NRZI with clock recovery, bit unstuffing, SYNC, SE0 end of packet; routes bytes to the next SM |
| [`usb_ls_rx_pkt`](../programs/usb_ls_rx_pkt.mim) | 30 | Low-speed USB, packet layer | Chooses CRC5 or CRC16 from the PID and checks it in hardware |
| [`ps2_rx`](../programs/ps2_rx.mim) | 10 | PS/2 keyboard | Device-clocked; odd parity checked by a 1-bit CRC |
| [`pulse_capture`](../programs/pulse_capture.mim) | 5 | Pulse widths | One `wait change ... timeout` is edge detector and timer; decodes NEC infrared in host software |
| [`pwm`](../programs/pwm.mim) | 12 | PWM | Period and duty from one FIFO word with the ALU; repeats the last setting |

Every program fits beside others in the 64-word memory, and several run at once: the tests run
UART RX into UART TX (16 words), the I2C controller and target together (58), Ethernet TX and
RX together (60), and the USB receiver's two SMs (all 64).

## Techniques

**Cycle-exact waveforms.** As on PIO, an instruction takes exactly `1 + delay` ticks, side-set
changes pins in the same tick as the instruction's work, and `.wrap` loops back for free. The
Ethernet transmitter counts every tick: each half bit is three, and the program interleaves
fetching the next bit (`out y, 1`), branching on it and counting down in the slots between level
changes.

**Clock recovery.** Receivers without a clock line re-time themselves on transitions:
`wait change pin 0 timeout` ends at a transition, or at the timeout (X reaches 0) when there was
none. The USB receiver opens a window of one bit centred on each expected transition: a
transition is a 0 and re-times the receiver, none is a 1. The Ethernet receiver waits out the
half-bit after each mid-bit transition, so boundary transitions never confuse it. Both tolerate
the clock errors the standards allow (tested at ±1.5% for USB and 0.5% for Ethernet, with the
transmitter's phase unrelated to the chip clock).

**CRCs as bits pass.** With `.crc POLY reflect out`, every `OUT` feeds its first bit to the CRC
unit, so a serial transmitter computes its CRC for free, and `mov osr, ~crc` sends it. Receivers
feed `IN`; checking a frame is comparing the register with the standard's residue. The same unit
is a parity checker (polynomial 1) for PS/2, and could be a scrambler or PRBS generator.

**Pipelines of SMs.** `.route` sends an SM's pushes to the next SM. The USB receiver's line layer
(NRZI, unstuffing, end of packet) needs every tick of a bit time for the line, so the CRC check
and byte packing run on the next SM. A UART receiver routed into a UART transmitter converts
baud rates with no host involved.

**Internal pins.** GPIO 24-31 exist only inside the chip. The PWM test drives `v0` from one SM
and measures it with pulse capture on another: a self-test with no wiring, and a way for one SM
to clock or gate another.

**Leaving the rest to the host.** Not everything belongs on the chip. Pulse capture reports the
length of every level with one-tick resolution and the host decodes NEC infrared from that; the
same five words would serve any pulse-width protocol (RC servos, DShot, Manchester at unknown
rates, unknown remotes).

## Throughput and the host

Every protocol runs at its full rate on the chip (10 Mb/s Manchester needs 60 MHz, 6 cycles a
bit). What the host can stream is a separate limit: about 9 Mb/s over a 10 MHz SPI port. The
tests' host is slower than a real one relative to the chip, so tests that stream long transfers
run the line slower (`HALF` for Ethernet, the divider for UART) or keep transfers short; the
programs themselves are unchanged.

## Adding a protocol

1. Write `programs/<name>.mim`: the instructions plus the `.pins`, `.shift`, `.crc` and other
   directives it needs, so the file is all a host loads.
2. Run it on the model with a peripheral model of the other end
   ([`periph.py`](../sw/mimic/periph.py)) as a scenario in
   [`scenarios.py`](../sw/tests/scenarios.py); `make test` runs it on the model and `make rtl`
   on the RTL in lockstep.
3. `mimic-load programs/<name>.mim --sm N --start -o name.json` and play it on the board.
