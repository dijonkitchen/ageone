# Mimic

A reprogrammable protocol emulator ASIC for [Tiny Tapeout](https://tinytapeout.com) on IHP's
130 nm SG13CMOS5L process, entered in Jane Street's
[protocol emulator ASIC competition](https://blog.janestreet.com/protocol-emulator-asic-competition/).

Four programmable state machines bit-bang serial protocols with cycle-exact timing from a shared
64-word program memory, which the demo board's RP2350 loads over SPI. The design starts from the
RP2040's PIO and adds what PIO programs most often have to work around: an ALU, a CRC unit per
state machine, edge and timeout waits, 16-bit immediates, open-drain pins, internal pins, and
FIFO routing between state machines. Those let the chip do the protocol work itself: CRC-32 for
Ethernet, NRZI, bit stuffing and CRC5/CRC16 for USB, clock recovery for both.

| | |
|---|---|
| Process, area | IHP SG13CMOS5L, 8x4 Tiny Tapeout tiles (1.22 mm²), about 520,000 µm² of cells |
| Clock | 60 MHz (one clock domain) |
| State machines | 4, each with X, Y, ISR, OSR, CRC/LFSR, clock divider, 2+2-word FIFOs |
| Program memory | 64 x 32-bit instructions, shared |
| Pins | 8 bidirectional (open-drain capable), 7 outputs, 5 inputs, 8 internal; the host port uses 4 |
| Host | SPI target, mode 0, up to 10 MHz; load, configure, debug, data |

## Protocols

| Protocol | Program |
|---|---|
| UART TX and RX, any baud, framing errors; RX routed into TX as a baud converter | [`uart_tx`](programs/uart_tx.mim), [`uart_rx`](programs/uart_rx.mim) |
| SPI controller, modes 0-3; SPI target | [`spi_ctrl`](programs/spi_ctrl.mim), [`spi_target`](programs/spi_target.mim) |
| I2C controller, 100/400 kHz, clock stretching, repeated START; I2C target | [`i2c`](programs/i2c.mim), [`i2c_target`](programs/i2c_target.mim) |
| 10BASE-T Ethernet TX and RX at 10 Mb/s: Manchester, preamble, CRC-32 | [`eth_tx`](programs/eth_tx.mim), [`eth_rx`](programs/eth_rx.mim) |
| Low-speed USB receive at 1.5 Mb/s: NRZI, clock recovery, unstuffing, CRC5/CRC16 | [`usb_ls_rx`](programs/usb_ls_rx.mim) + [`usb_ls_rx_pkt`](programs/usb_ls_rx_pkt.mim) |
| JTAG; WS2812 LEDs; PS/2 keyboards; NEC infrared; PWM | [`jtag`](programs/jtag.mim), [`ws2812`](programs/ws2812.mim), [`ps2_rx`](programs/ps2_rx.mim), [`pulse_capture`](programs/pulse_capture.mim), [`pwm`](programs/pwm.mim) |

[Protocols](docs/protocols.md) explains how each works and how to add one.

## Documents

- **[Write-up](docs/writeup.md)**: the entry in one read; start here.
- [Architecture](docs/architecture.md): the design, what it adds to PIO and why, area and timing.
- [Instruction set](docs/isa.md): the reference, including the assembler.
- [Host port](docs/host.md): SPI frames, registers, loading, the debugger, the demo board.
- [Protocols](docs/protocols.md): the example programs and their techniques.
- [Verification](docs/verification.md): golden model in lockstep, tests from the spec, random
  programs, mutation testing, protocol models, gate level, hardening results.
- [Decisions](docs/decisions/): the stack, the instruction memory, area and timing.
- [Datasheet page](docs/info.md) for Tiny Tapeout.

## Layout

```
info.yaml, src/, test/, docs/info.md   Tiny Tapeout's project layout
src/                RTL: project.v (top), mimic_sm.v, mimic_imem.v, mimic_fifo.v, mimic_host.v
programs/           example programs (.mim)
sw/mimic/           isa, asm (mimic-asm), model, host (loader), cli (mimic-load), bench, periph, protocols
sw/micropython/     the demo board driver
sw/tests/           scenarios (shared by pytest and cocotb) and unit tests
sw/tools/mutate.py  mutation testing of the verification
test/               cocotb testbench (RTL and gate level)
```

## Running

Inside the root `make shell` (Python, uv, Icarus Verilog):

```sh
make test                      # every scenario on the golden model (pytest)
make rtl                       # every scenario on the RTL, in lockstep with the model (cocotb)
make check                     # lint, types, and both
uv run mimic-asm programs/i2c.mim --listing
uv run mimic-load programs/uart_tx.mim --sm 0 -D TX=uo4 --start -o uart_tx.json
```

### Hardening

Tiny Tapeout's tools need the project at the root of a git repository. Copy this folder into one
(as the submission repository will be), add [tt-support-tools](https://github.com/TinyTapeout/tt-support-tools)
as `tt/`, and with Docker:

```sh
pip install -r tt/requirements.txt librelane==3.1.0.dev4
export PDK_ROOT=~/ttsetup/pdk PDK=ihp-sg13cmos5l
./tt/tt_tool.py --pdk $PDK --create-user-config
./tt/tt_tool.py --pdk $PDK --harden
./tt/tt_tool.py --pdk $PDK --print-stats
cp runs/wokwi/final/nl/tt_um_dijonkitchen_mimic.nl.v test/gate_level_netlist.v && make gl
```

Behind a TLS-intercepting proxy, fetch the PDK on the host first
(`ciel enable --pdk-root $PDK_ROOT --pdk-family ihp-sg13 <version>` with `SSL_CERT_FILE` set);
the container then finds it. The repository's GitHub Actions (`.github/workflows/`, from the
Tiny Tapeout template) run the same flow, the tests, and precheck.

## Status

Simulation and hardening only: the chip has not been fabricated. See the
[verification write-up](docs/verification.md) for what has and has not been shown.
