# Decision Record 2026-11-13: Mimic Stack

## Status timeline

2026-11-13: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-11-13-mimic.md) that a Tiny Tapeout judge can rerun: RTL the TT flow hardens, tests the TT template's GitHub Actions run, and a toolchain that runs on a PC and on the demo board's MicroPython.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.

### Nice to haves

#### Functional

One set of tests for the golden model, the RTL and the gate-level netlist.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

A hardware construction language or simulator the TT template does not already run.

#### Non-functional

## Decision

- **RTL: Verilog-2005**, synthesized by Yosys in LibreLane, the TT template's default.
  Hardcaml (Jane Street's own) or Amaranth would generate the same Verilog with more tooling for judges to install.
- **Tests: cocotb 2.0 on Icarus Verilog**, the TT template's test setup, so the template's `test` and `gl_test` actions run them unchanged.
- **Golden model, assembler, loader: Python 3.12 with uv**, the repo's Python stack (ruff, mypy strict, pytest).
  Tests are `async` scenarios that run on the model under pytest and on the RTL under cocotb through one `Device` interface, with the model in lockstep.
- **Board driver: MicroPython** on the RP2350, through the Tiny Tapeout SDK's pin map; the PC turns programs into register writes so the board needs no assembler.
- **Hardening: LibreLane 3.1 through Tiny Tapeout's `tt_tool.py`**, run locally in Docker with the IHP Open PDK; the project folder copies into a standalone repository for TT's GitHub Actions.
- **Environment**: `devenv.nix` adds Icarus Verilog for `make rtl` in CI; Verilator lints when present.

### Choices and Tradeoffs/Risks

Python for the model over SystemVerilog or C++: slower (about 3,000 lockstep cycles a second with the RTL), but the same language as cocotb, so the model runs inside the testbench with no foreign interface, and tests are short.

Lockstep at the pins rather than transaction-level scoreboards: any difference anywhere shows up at the first cycle it reaches a pin or a compared register, and the model doubles as the reference for program writers.

### Dependencies

Docker and about 10 GB of disk for local hardening; the PDK version is the one LibreLane 3.1.0.dev4 pins.

### Interfaces

`make check` (CI), `make rtl`, `make gl`; `mimic-asm`, `mimic-load`; `sw/micropython/mimic_tt.py`.

## Key Results and retrospective feedback
