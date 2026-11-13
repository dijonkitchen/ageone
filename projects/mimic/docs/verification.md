# Verification

The question for a reprogrammable chip is not whether one protocol works but whether every
instruction does what the ISA says in every combination, so that programs nobody has written yet
will work. The verification is built around that.

```
            docs/isa.md (the specification)
              │                        │
              ▼                        ▼
   golden model (Python)  ◀── directed ISA tests: expected values computed from the spec
              │                         (Python arithmetic, published CRC check values,
              │                          cycle counts from the timing rules)
              │ lockstep: every output pin, every cycle; SM registers every 1-16 cycles
              ▼
         RTL (Verilog)  ◀── random programs (any 32-bit word is an instruction), random
              │              configuration, pin noise and host traffic
              │         ◀── protocol scenarios against device models written from each
              │              protocol's specification
              ▼
   gate-level netlist (same scenarios)    LibreLane / Tiny Tapeout precheck
```

## 1. A golden model that runs the same tests

[`sw/mimic/model.py`](../sw/mimic/model.py) is a cycle-accurate model of the whole chip at the
pin level: input synchronizers, the SPI host port bit by bit, the four state machines, FIFOs,
routing, IRQs, the latch memory's write latency. It is written the way the RTL is (compute all
next-state values from the current registers, then commit), so a difference between them is a
bug in one of them, never a modelling convention.

Every test is a *scenario* (`async def scenario(bench)`) that talks to the chip only through its
pins: it loads programs through the SPI port, drives peripherals, reads FIFOs. The same scenario
runs on three targets through one `Device` interface:

| Target | Runner | Time |
|---|---|---|
| Golden model | `pytest` (`make test`) | ~1.5 min for all |
| RTL, Icarus Verilog, model in lockstep | cocotb (`make rtl`) | ~12 min for all |
| Gate-level netlist (IHP cell models), model in lockstep | cocotb (`make gl`) | ~25 min for all |

In lockstep ([`test/test.py`](../test/test.py)) the RTL and the model take the same inputs every
cycle; any difference in `uo_out`, `uio_out` or `uio_oe` fails the test at that cycle with both
values, and the SMs' internal registers (PC, X, Y, ISR, OSR, CRC, POLY, shift counts, delay)
are compared through cocotb's hierarchy access every 16 cycles, every cycle in the random tests.

## 2. Directed tests from the specification

Lockstep only proves the RTL and the model agree. The directed tests ([`scenarios.py`](../sw/tests/scenarios.py),
`isa_*`) check the model (and so the RTL) against the specification, with expected values
computed independently:

- **ALU**: every operation on edge values (0, all ones, sign bit, shift counts above 31) against
  Python arithmetic, through both `ALU` and `ALUI`.
- **Shifts**: `IN` and `OUT` in both directions with counts 1, 3, 8, 17, 31, 32, checking the
  shifted value and what remains, and the `MOV` operations (invert, bit reverse, byte swap).
- **Conditions**: every `JMP` condition taken and not taken, including unsigned `X<Y` and the
  decrement of `X--`.
- **CRC unit**: three published check values from the string `123456789`: CRC-32 `0xCBF43926`
  (equal to `zlib.crc32`), CRC-16/CCITT-FALSE `0x29B1` (MSB-first, left-aligned) and the USB
  CRC16 `0xB4C8` (reflected).
- **Timing**: side-set with delay, a `WAIT` that times out (X + 1 ticks), and the fractional
  clock divider, measured in cycles on the pins against the timing rules in the ISA.
- **EXEC and IRQs**: `OUT EXEC` running a word from the FIFO; an IRQ handshake between two SMs.
- **Waits and pin priority**: an edge wait re-arms on every `WAIT`; side-set beats `SET` on the
  same pin; the higher-numbered SM wins a shared pin (added after the mutation test, below).

They drive a stopped SM through the debug path (`INSTR` writes and `X` reads over SPI), so the
same tests exercise the host port and the debugger.

## 3. Random differential tests

Any 32-bit word is a valid instruction (reserved opcodes are `NOP`s, unused bits are ignored), so
random words exercise every encoding, including the ones no assembler emits. Each random test:

- fills all 64 words with random instructions, shaped so programs keep moving (waits mostly time
  out, few IRQ waits, delays mostly short) and with random unused bits;
- gives each SM a random configuration (dividers with fractions, side-set, shift directions and
  thresholds, autopush/autopull, FIFO joins, routing, pin bases and counts, CRC modes) and
  open-drain pads;
- runs all four SMs together while random pins toggle and the host does random things: FIFO
  writes (biased toward 0, 1 and all ones so equal operands happen), FIFO reads, IRQ set and
  clear, debug reads, forced instructions, configuration and instruction-memory writes while the
  SMs run, single steps, restarts, FIFO clears.

Eight seeds run in the suite, about 35,000 cycles each, with registers compared every cycle.
A coverage count on the model showed the first generator spent most ticks stalled on edge waits,
IRQ waits and FIFOs, and that two `JMP` conditions never ran: each seed had only 64 static
instructions. The generator now rewrites eight-word blocks of the memory while the SMs run,
rarely uses long delays or blocking `PUSH`/`PULL`, and enables autopush and autopull a third of
the time. Over the eight seeds (279,000 cycles):

| Opcode | Executed | Stalled ticks |
|---|---|---|
| `JMP` | 7,560 | |
| `WAIT` | 603 | 22,809 |
| `IN` | 2,120 | 12,846 |
| `OUT` | 1,901 | 19,545 |
| `PUSH`/`PULL` | 1,526 | 45,591 |
| `MOV` | 2,984 | |
| `IRQ` | 901 | 4,183 |
| `SET` | 1,391 | |
| `ALU`/`ALUI` | 2,230 | |
| reserved | 1,452 | |

Every `JMP` condition (and undefined ones), every defined `IN` source, every `OUT` and `SET`
destination, all eight ALU operations, and all four `WAIT` sources ran; 49 of the 256 `MOV`
destination and source pairs did. Waits that end without a timeout, rare here, are the
protocols' bread and butter (section 4).

### Do the tests catch bugs?

[`sw/tools/mutate.py`](../sw/tools/mutate.py) plants one bug at a time in the golden model and
runs the lockstep suite (random and directed tests) against the RTL; a bug the suite misses is a
gap in the tests.

| Mutant (one line of the model changed) | First run | After the fix |
|---|---|---|
| `xor` computes `or` | caught | |
| `x==y` false when both are 0 | caught (missed by an earlier generator, until FIFO data favoured 0, 1 and all ones) | |
| `x<y` reads the wrong carry bit | caught | |
| ISR count saturates at 31 | caught | |
| autopull waits for one bit too many | caught | |
| `wait rise` forgets to re-arm on a new WAIT | **survived** | caught |
| `OUT`/`SET` beats side-set on the same pin | **survived** | caught |
| reflected CRC feeds back the wrong bit | caught | |
| `irq rel` subtracts the SM number | caught | |
| a FIFO holds one word too many | caught | |
| `OUT EXEC`'s delay not ignored | caught | |
| byte swap computes bit reverse | caught | |

The two survivors were real gaps: random programs almost never put two edge waits in a row with
the line held at the new level, or side-set and a `SET` on the same pin in one instruction.
The directed test `isa_wait_and_pins` now covers both (and SM priority), and catches both mutants.

## 4. Protocols against independent device models

Each program in [`programs/`](../programs) is tested against a model of the other end written
from that protocol's specification, not from the program ([`periph.py`](../sw/mimic/periph.py)):

| Scenario | Checks |
|---|---|
| `uart_tx`, `uart_rx`, `uart_bridge` | Bytes and framing; a framing error raises the IRQ and the receiver recovers; RX routed into TX at another baud with a fractional divider |
| `spi_ctrl_mode0`-`3` | All four modes against a target that shifts on the opposite edge; chip select framing |
| `spi_target` | Against a controller; replies from the FIFO and the `0xFF` default |
| `i2c`, `i2c_stretch` | Against an EEPROM-like target: writes, repeated START and reads, ACK/NACK, an absent address, and a target that stretches every clock (checked to have stretched) |
| `i2c_loopback` | The I2C controller on one SM writing to the I2C target on another, over board wires: ACKs, data, STOP, an address nobody answers |
| `jtag` | Against an IEEE 1149.1 TAP model (all 16 states, IR, IDCODE, BYPASS): IDCODE read, an IR scan, BYPASS's one-bit delay |
| `ws2812` | Pulse widths decoded by a WS2812 model |
| `eth_tx`, `eth_tx_line_rate` | A Manchester decoder recovers the frame; FCS compared with `zlib.crc32`; at 10 Mb/s (6 cycles a bit) and slower |
| `eth_rx`, `eth_rx_line_rate` | Frames from a Manchester encoder with its clock 0.3-0.5% off and its phase unrelated to the chip's; data and CRC residue checked |
| `usb_ls_rx`, `_fast_host`, `_slow_host` | Tokens and data packets from a USB host model (NRZI, bit stuffing, CRC5/CRC16 computed per the USB spec) at 1.5 Mb/s with the clock 0 and ±1.5% off |
| `ps2_rx` | Scan codes from a keyboard model, including a bad parity bit |
| `nec_ir` | An NEC remote frame captured as pulse widths and decoded on the host |
| `pwm_capture_loopback` | PWM on an internal pin measured by pulse capture on another SM, exact to the cycle |

Several of these found real problems in programs and in the tests themselves, which the
scenarios now guard: a receiver model that took the reset-low line for a start bit, test hosts
too slow for their FIFOs (now flagged by `FDEBUG`'s stall bits), and an Ethernet receiver whose
sample point drifted when slowed with the clock divider (now slowed with ticks per bit instead).

## 5. Lint, synthesis and gate level

- Verilator `--lint-only -Wall` is clean (latches in the instruction memory are intended and
  marked).
- Yosys synthesis for IHP SG13CMOS5L is checked for area at every architectural change; see
  [architecture](architecture.md#area-and-timing) for the numbers and the choices they drove.
- **Gate level.** The scenarios run on the synthesized netlist with IHP's cell models, in lockstep
  with the golden model (pins every cycle), at about 13,000 cycles a second: all 41 pass on the synthesized netlist.
  The cell models feed their flip-flops from nets that `$setuphold` timing checks drive;
  Icarus Verilog does not run timing checks, so those nets stayed undriven and every flip-flop
  read X. `test/Makefile` builds a copy of the models that uses the inputs directly (the
  checks' delays are zero, so the copy is functionally exact).

## Hardening

Tiny Tapeout's flow (LibreLane 3.1.0.dev4, IHP SG13CMOS5L, 8x4 tiles: 1724 x 711 µm) on this
design, with the settings in `src/config.json` and the [area and timing decision](decisions/2026-11-13-mimic-area.md):

| Stage | Result |
|---|---|
| Synthesis (Yosys, `AREA 0`) | 37,492 cells, 511,881 µm²: 2,344 flip-flops, 2,048 memory latches, 64 clock-gate latches |
| Placement | 42% utilization, 50% after buffering |
| Clock tree | 865 clock buffers; the 64 memory-word clock gates are leaves of the tree |
| Timing repair (typical corner) | No setup violations at 20 ns; 1,631 hold buffers, then hold slack +0.10 ns |
| After repair | 46,677 cells, 618,721 µm², 51% utilization |
| Static timing at 60 MHz (16.6 ns), before layout | Typical corner met; slow corner (1.08 V, 125 °C) −1.10 ns |
ROUTING_RESULTS

Three things only a real flow shows, each now a setting with a comment in `src/config.json`:

- The default delay-oriented synthesis buffered every multiplexer select (38,000 buffers) and even
  used I/O pad cells as buffers: 1.25 mm², more than the die. Area-oriented mapping halves it.
- The memory latches time-borrow, which static timing reports as slack exactly 0; with the
  resizer's default 0.05 ns margin, all 2,048 of them counted as violations.
- OpenROAD's timing analysis of the design takes about 5 GB per corner; repairing against three
  corners exhausted the 16 GB machine (twice taking the whole container down), so repair runs at
  the typical corner, where the chip will run, and sign-off still reports all three.

## Running it

```sh
make test     # model: assembler, driver, every scenario (pytest)
make rtl      # RTL in lockstep with the model (cocotb, Icarus Verilog)
make gl       # gate-level netlist (after hardening; see test/Makefile)
make lint     # ruff, mypy --strict, verilator -Wall
uv run python sw/tools/mutate.py
```

## Tools and AI

The RTL, model, assembler, programs, tests and documents were written with Claude (Anthropic's
AI model) working as a coding agent in this repository: it designed the architecture, wrote the
code, ran the simulators and the LibreLane flow, and iterated on what they reported. The
verification was designed so its conclusions do not rest on trusting the author, human or AI:
the expected values come from the specification and from published standards, the device models
are written from protocol specifications, and the mutation test measures what the suite catches.
Tools: Icarus Verilog 12, cocotb 2.0, Verilator 5, Yosys, LibreLane 3.1 (OpenROAD, Magic,
KLayout, Netgen) with the IHP Open PDK, Python 3.12.
