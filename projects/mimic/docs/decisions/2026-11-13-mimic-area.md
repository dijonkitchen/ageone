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

The first synthesis was 711,000 µm². These changes brought it to about 510,000 µm² with every ISA feature kept (520,000 after the routing fix below):

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

**Hardening settings** (`src/config.json`), each found by a failed run:

- `SYNTH_STRATEGY` `AREA 0`, as above.
- `CLOCK_PERIOD` 16.6 ns (60 MHz), repaired at all three corners. Earlier the memory's gated
  clocks made timing analysis cost 5 GB per corner, which forced repair at the typical corner
  only, at 20 ns, with a zero setup margin for the latches' time borrowing; with the enables
  below, repair at every corner takes seven minutes in under 1 GB.
- `RUN_POST_GRT_DESIGN_REPAIR` and `RUN_POST_GRT_RESIZER_TIMING`: repair slew, capacitance and
  setup again after global routing, and `DESIGN_REPAIR_MAX_WIRE_LENGTH` /
  `GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH` 400 µm put repeaters on long wires. Placement's wire
  estimates miss the long wires: the first routed chip met 60 MHz at the typical corner but missed
  by 9.3 ns at the slow one, with 292 slew violations. The repairs cut those to 24, but the slow
  corner still misses by 9.6 ns after routing (setup closes on global routing's estimate, then a
  few nets that timing repair restructured route long; one is 2.4 mm from a single small gate).
- `SETUP_VIOLATION_CORNERS` typical and fast. LibreLane fails a flow with setup violations at any
  corner by default; Mimic is rated for 60 MHz at the typical corner, where the demo board runs
  it, and about 38 MHz at the slow corner, which sign-off still reports.
- `RUN_MAGIC_DRC` off: magic's DRC ran for over 90 minutes without finishing, and would push
  Tiny Tapeout's 6-hour GitHub job; the precheck runs IHP's own KLayout deck on the GDS.

**Routing.** The first layout did not route.
A project may route only on Metal2 to Metal4 (TopMetal1 belongs to the chip's power grid), so
Metal3 is its only horizontal layer, and on an 8x4 die, more than twice as wide as tall, most
long wires run horizontally.
The global router needed 128% of Metal3's capacity (84% of its raw tracks) against 61% of the two
vertical layers', and after two hours of overflow repair it still had not converged.
Lower placement density did not help at first: the placer's routability mode raised every target
from 52% to 60% back to about 67%, and Metal3 stayed at 108% before buffering.
The wiring came from the memory's read multiplexers: synthesis decoded each port's address into
64 word lines, and each line ran to its word's 32 bits wherever the placer put them.
Those 256 lines and their buffers were a third of the placed wiring.
These changes, each measured on the layout, followed:

- Each read port decodes in two levels: eight one-hot lines from the low three address bits
  pick a word in every group of eight, and eight lines from the high three bits pick the group.
  `(* keep *)` stops synthesis from flattening the levels back into word lines.
  The same function in 1,000 more cells (+9,000 µm²) cut the wiring by 19% and Metal3's
  demand from 108% to 86% before buffering.
- The memory's latches open on a one-cycle pulse from a flip-flop instead of 64 gated clocks.
  Each gated clock reached its word in all 32 bit columns, so clock tree synthesis built 64 trees
  across the memory: 600 of the chip's 860 clock buffers, which packed it to 100% local density
  (36 placement bins over 80%; none after). Clock tree synthesis went from 7 minutes and 4 to
  12 GB to 19 seconds and 340 MB.
- `PL_TARGET_DENSITY_PCT` 55 leaves room for the buffers the memory's select lines get after
  placement.
- `GRT_LAYER_ADJUSTMENTS` reserves 15% of Metal3 in global routing instead of 30% (Metal2 and
  Metal4 keep 30%), leaving the difference to the detailed router, which sees real tracks.
- `CTS_APPLY_NDR` `none`: the clock tree's double-spaced wires took Metal3 tracks, and while any
  overflow remained, the global router dropped them about ten nets at a time and reran 20 passes
  each time, for hours. A 60 MHz clock does not need them. `GRT_OVERFLOW_ITERS` 20 stops the
  passes that no longer help.

Global routing now takes two and a half minutes and leaves 0.7% overflow (5,200), against
111,000 and a run that never finished. The library's fanout limit (8) overrides a looser
`MAX_FANOUT_CONSTRAINT`, so the fanout buffers stay.

**Detailed routing** with four state machines still did not converge: 106,793 violations after
the first pass, mostly shorts on Metal2 (where every cell pin is reached) and Metal3, and about
12% fewer per 45-minute pass after that. Global routing's small overflow understated how hard
three thin layers are to wire at half the core in cells. With
[three state machines](2026-11-14-mimic-three-sms.md) (41% of the core after repair), global
routing has 79 overflow and detailed routing reaches zero violations in 21 passes.

### Choices and Tradeoffs/Risks

Two-word FIFOs make the host keep up sooner: at full rate a protocol that streams data needs the host's SPI port at 10 MHz (about 9 Mb/s). Joining a FIFO doubles one direction, and SM-to-SM routing keeps pipelines on chip.

Ring routing loses arbitrary fan-in (two SMs feeding one), which no example needed; it keeps each TX FIFO's write multiplexer at two inputs.

### Dependencies

### Interfaces

## Key Results and retrospective feedback

2026-11-14: with four state machines, synthesis 521,000 µm²; timing repaired for 60 MHz at every corner before routing (slow corner −0.16 ns); global routing converged and detailed routing did not.

2026-11-15: with three, synthesis 411,000 µm²; detailed routing at zero violations, zero antenna violations, LVS clean; 60 MHz met at the typical (+0.13 ns) and fast corners, about 38 MHz at the slow corner.
