# Decision Record 2026-11-13: Mimic Area and Timing Trade-offs

## Status timeline

2026-11-13: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Four full-featured state machines with a 64-word memory in 8x4 tiles (1.22 mm²), on IHP SG13CMOS5L's five metal layers (three thin routing layers: Metal2-4, with TopMetal1 for power), at 60 MHz, which 10 Mb/s Manchester needs (6 cycles a bit).

#### Non-functional

Placement density below about 50%, because the design is mostly multiplexers and the process has few routing layers.

### Nice to haves

#### Functional

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Cutting features that make the chip flexible (the competition's first criterion) to save area that is not needed.

#### Non-functional

## Decision

The first synthesis was 711,000 µm². These changes brought it to about 510,000 µm² with every ISA feature kept:

| Change | Saved (µm²) |
|---|---|
| Latch instruction memory ([decision](2026-11-13-mimic-imem.md)) | 92,000 |
| FIFOs of 2+2 words, joinable to 4, instead of 4+4 | 53,000 |
| Debug reads only for PC, X, Y, SMSTAT and the instruction (others through `mov x, ...`) | 10,000 |
| Routing only to the next SM in a ring, not any SM | 7,000 |
| One adder and one rotator per SM shared by all instructions | (designed in) |

**Synthesis strategy `AREA 0`.** LibreLane's default for this PDK, `DELAY 4`, produced 1.25 mm² for the same RTL: 38,000 buffers on high-fanout multiplexer selects, and even I/O pad cells used as buffers. `AREA 0` maps for area and leaves buffering to the placer's resizer, which buffers only what timing needs.

**Timing.** Measured feature costs per SM were small and spread out (CRC unit 7,400 µm², side-set 5,100, pin rotators 6,700, `pins` rotation 3,400, EXEC 3,200, fractional divider 2,300), so timing came from restructuring, not removing features:

- Pin writes have their own value multiplexer: sharing the write-back value with the ALU put the adder on every pin path, the slow corner's worst path.
- The adder is a Kogge-Stone tree (5 levels) instead of a ripple chain (32), for 2,000 µm².

### Choices and Tradeoffs/Risks

Two-word FIFOs make the host keep up sooner: at full rate a protocol that streams data needs the host's SPI port at 10 MHz (about 9 Mb/s). Joining a FIFO doubles one direction, and SM-to-SM routing keeps pipelines on chip.

Ring routing loses arbitrary fan-in (two SMs feeding one), which no example needed; it keeps each TX FIFO's write multiplexer at two inputs.

### Dependencies

### Interfaces

## Key Results and retrospective feedback
