# Decision Record 2026-11-14: Three State Machines

## Status timeline

2026-11-14: Accepted by JC, from Claude's options after four-SM layouts did not route

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A chip that routes on the three layers a project may use on IHP SG13CMOS5L (Metal2 to Metal4),
keeping every per-SM feature and the 64-word memory.

#### Non-functional

### Nice to haves

#### Functional

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

#### Non-functional

A hierarchical flow (the memory as its own hardened block) on a shuttle whose tooling is new.

## Decision

**Three state machines instead of four**, each with every feature: ALU, CRC unit, side-set, edge
and timeout waits, FIFOs, routing. The memory keeps 64 words and gets three read ports.

With four, every step of Tiny Tapeout's flow up to detailed routing completed after the changes
in the [area and timing decision](2026-11-13-mimic-area.md), but detailed routing did not
converge: about 100,000 conflicts after two passes, falling 12% a pass.
The fourth SM and its FIFOs were about a fifth of the cells, and its read port a quarter of the
memory's read logic.

The register map keeps room for four: SM3's bits in `CTRL`, `FLEVEL` and `FDEBUG` read 0, and
its block (`0xB0`-`0xBF`) reads 0 and ignores writes, so software and a later four-SM revision
share one map. The ring routes SM2 → SM0 → SM1 → SM2.

### Choices and Tradeoffs/Risks

- **Floorplanning the memory** as a hardened block in the middle of the die would keep four SMs
  by splitting their instruction buses both ways, but needs a hierarchical flow, with no
  guarantee the rest routes.
- **Narrower SMs** (without the CRC unit, side-set or pin rotators) would keep four but drop the
  features that make Mimic more than PIO.
- **Three SMs** lose concurrency: three protocols at once instead of four, or one two-SM pipeline
  (USB receive, a UART baud converter) and one more. No example uses more than two SMs at once.

### Dependencies

### Interfaces

The host's register map is unchanged; `isa.NUM_SM` is 3.

## Key Results and retrospective feedback

2026-11-15: synthesis 29,572 cells and 410,952 µm² (from 38,503 and 521,151); 41% of the core after
timing repair (from 52%); global routing 79 overflow (from 5,210); detailed routing reaches zero
violations (four SMs: about 100,000 after two), in 19 passes and 69 minutes in the final run.
Every scenario passes on the model, the RTL and the routed netlist.
