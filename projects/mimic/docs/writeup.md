# Mimic: a protocol emulator you can teach new protocols

*An entry for Jane Street's protocol emulator ASIC competition, on Tiny Tapeout's IHP
SG13CMOS5L shuttle.*

## The idea

A protocol emulator earns its keep on the protocols nobody planned for. So rather than
hard-wiring UART, SPI and I2C and adding a programmable escape hatch, Mimic is only the escape
hatch: four small processors built for bit-banging, and nothing else that knows what a protocol
is. UART, SPI, I2C, Ethernet and USB are all programs.

The RP2040's PIO shows how good such processors can be: every instruction takes one cycle, sets
pins as a side effect, and delays for free, so waveforms are exact by construction. Mimic starts
there. Then it adds what PIO programs most often work around, because those workarounds are
where protocols PIO was not designed for fail:

- **Arithmetic** (`ALU`: add, sub, and, or, xor, shifts, rotate; `X<Y`): counters, checksums,
  computed delays, without the host.
- **A CRC unit** per state machine, any polynomial up to 32 bits, fed by bits as `IN` and `OUT`
  shift them: Ethernet's CRC-32, USB's CRC5 and CRC16, parity, scramblers, at no cost in
  instructions.
- **Waits that know about time**: `wait rise`, `wait fall`, `wait change`, and a timeout that
  counts down in X while waiting. One instruction is an edge detector and a timer, which is what
  clock recovery needs.
- **Constants in instructions** (16-bit immediates), **any pin** in `JMP`, **open-drain**
  pins, **internal pins** between state machines, and **FIFO routing** so state machines form
  pipelines.

The [architecture](architecture.md) explains the design and its costs; the
[instruction set](isa.md) is the reference.

## What it runs

Fifteen programs, each tested against an independent model of the device at the other end:

- The required three: UART (any baud, framing errors, a UART-to-UART bridge with no host),
  SPI (all four modes, controller and target), I2C (controller with clock stretching and
  repeated START, and a target, tested against each other on one chip).
- Both stretch goals, at line rate: **10BASE-T Ethernet** transmit and receive at 10 Mb/s
  (Manchester, preamble and SFD, CRC-32 computed and checked on chip, clock recovery tolerating
  0.5% frequency error), and **low-speed USB** receive at 1.5 Mb/s (NRZI, clock recovery within
  USB's ±1.5%, bit unstuffing, SYNC and end-of-packet detection, CRC5 or CRC16 chosen from the
  PID), split across two state machines chained by a FIFO.
- More from the competition's list and beyond: JTAG, PS/2 (parity from a one-bit CRC), WS2812
  LEDs, NEC infrared (decoded from a four-instruction pulse-width capture), PWM measured on an
  internal pin.

[Protocols](protocols.md) shows how each works, and what does not fit.

## How we know it works

The chip has to run programs nobody has written yet, so the verification targets the
instruction set, not the examples ([verification](verification.md)):

1. A cycle-accurate **golden model** of the whole chip in Python, including the SPI port bit by
   bit, runs every test in lockstep with the RTL: every output pin every cycle, every state
   machine register every cycle in the random tests.
2. **Directed tests from the specification**: expected values computed independently (Python
   arithmetic, published CRC check values like CRC-32's `0xCBF43926`, cycle counts from the
   timing rules).
3. **Random programs**: any 32-bit word is an instruction, so random words, random configuration,
   pin noise and host traffic exercise every encoding; coverage counts show every `JMP` condition,
   `IN` source, `OUT` destination and ALU operation run.
4. **Mutation testing** measures the suite: bugs planted in the model one at a time, each of
   which the lockstep tests must catch.
5. **Protocol models** written from each protocol's specification, including off-frequency
   transmitters with random phase.
6. **Gate-level simulation** of the hardened netlist, in lockstep with the same model.

One set of `async` test scenarios runs on all three targets: the model (pytest), the RTL and
the netlist (cocotb).

## The silicon

HARDENING_SUMMARY

## Reprogramming it

The demo board's RP2350 drives an SPI port (four pins) that loads programs, configures the
state machines, moves data, and debugs: force any instruction into a stopped state machine,
single-step, read its registers. On a PC, `mimic-load` turns a program into register writes;
a 100-line MicroPython driver plays them on the board ([host port](host.md)).

Adding a protocol is writing a `.mim` file, which carries its own pin, shift, FIFO and CRC
settings, testing it on the model against a model of the device, and loading it.

## How it was built

The design, RTL, toolchain, programs, tests and documents were written by Claude, Anthropic's AI
model, as a coding agent: it chose the architecture, ran the simulators and the LibreLane flow,
and changed the design on what they said. Several decisions came straight from measurements:
the first synthesis was 0.71 mm² and became 0.51 mm² with every feature kept
([area decision](decisions/2026-11-13-mimic-area.md)); the default synthesis strategy doubled
the area with buffers; the slow corner's critical path ran through the adder into the pins until
pin writes got their own multiplexer. The verification is built so its conclusions rest on the
specification and on independent models, not on trusting whoever wrote the RTL.

## Limits and next steps

- 64 words of program memory is the binding limit: a complete USB device does not fit. An IHP
  SRAM macro behind per-SM fetch buffers could hold several times more.
- FIFOs of two words each way make the host keep up early; streaming at 10 Mb/s needs the host's
  SPI port near its 10 MHz limit.
- Nothing here has met silicon yet.
