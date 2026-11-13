# Decision Record 2026-11-13: Mimic Instruction Memory

## Status timeline

2026-11-13: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Every state machine fetches an instruction every cycle (single-cycle instructions are the point), from a memory the host can rewrite after fabrication, as large as fits.

#### Non-functional

Passes the Tiny Tapeout flow and precheck without custom macros; one clock domain; static timing analysis can check every path.

### Nice to haves

#### Functional

Programs share the memory, so one SM can run a large program while others run small ones.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

#### Non-functional

## Decision

One shared memory of **64 words of 32 bits**, with four asynchronous read ports and one write port from the host.
Words are stored in **latches**, each word written through its own clock gate made of standard cells: a negative-level latch holds the write enable while `clk` is low, and an AND with `clk` opens the word's latches for the high half of a cycle.
`MIMIC_IMEM_FF` selects flip-flops instead, for FPGAs.

| Choice | Area (µm², IHP SG13CMOS5L, synthesized) |
|---|---|
| Flip-flops with enables, 64 words | 241,000 |
| Latches with clock gates, 64 words | 149,000 |
| of which the four 64:1 read multiplexers | about 100,000 |

### Choices and Tradeoffs/Risks

**Shared, not per-SM.** Four private memories of 16 words each would cost the same read ports and leave every program small; one shared memory lets the USB receiver use 64 words across two SMs while a UART needs four.

**32-bit words.** A 24-bit word would save about 40,000 µm², but would cost the 16-bit immediates (constants without the host), the per-instruction pin index, and room for later instructions. Each bit of width costs about 4,000 µm²; immediates pay for themselves in every program that needs a constant.

**64 words, not 32 or 48.** The read multiplexers, not the storage, dominate; 32 words would save about 80,000 µm². The Ethernet transmitter alone is 41 words and the USB receiver 64, so 64 is what makes the stretch goals possible.

**Latches, not an SRAM macro.** IHP's single-port SRAM macros are allowed and denser, but give one read per cycle; four SMs would need four macros (with very little of each used) or time-multiplexing that breaks single-cycle execution. Integrating a macro in the TT flow is also a risk this entry does not need. A later revision could hold programs in SRAM behind per-SM fetch buffers.

**Latch write timing.** A host write at cycle T lands in cycle T+2 (one later than flip-flops); the golden model models this so lockstep holds. Host writes are at least 32 SCK edges apart, so the write data register never changes while a gate is open.

**Static timing.** The clock gates are clock-derived, so STA times the latches' setup (half a cycle from the data register) and the gates' enable; the latch read paths are ordinary data paths into the SMs.

### Dependencies

### Interfaces

The `IMEM` registers at host addresses `0x00`-`0x3F` (write only).

## Key Results and retrospective feedback
