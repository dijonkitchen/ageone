# mimic

Mimic, a reprogrammable protocol emulator ASIC for Jane Street's Tiny Tapeout competition: four programmable state machines in 8x4 IHP SG13CMOS5L tiles, with a Python toolchain, golden model and tests.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-11-13-mimic.md): what to build and the definition of done.
- [README](README.md): what it is and how to run everything.
- [ISA](docs/isa.md): the specification the RTL and the model are held to.
- Decisions: [stack](docs/decisions/2026-11-13-mimic-stack.md), [instruction memory](docs/decisions/2026-11-13-mimic-imem.md), [area and timing](docs/decisions/2026-11-13-mimic-area.md).

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: ruff, mypy, Verilator lint, every scenario on the golden model, and every scenario on the RTL in lockstep with the model (about 12 minutes); CI runs it whenever this folder changes.
- `make test` (model only, about 2 minutes), `make rtl`, `make gl` (gate-level, after hardening).
- `cd test && make COCOTB_TEST_FILTER=test_uart` runs some RTL scenarios; the filter is a regex, but `|` breaks the cocotb Makefile, so use character classes.
- `make fix`: apply lint and format fixes.

## Rules

- The ISA in `docs/isa.md`, `sw/mimic/isa.py`, `sw/mimic/model.py` and `src/mimic_sm.v` change together: the lockstep tests fail on any difference, so update the model in the same change as the RTL.
- Every new program gets a scenario against an independent model of the other end (`sw/mimic/periph.py`), written from the protocol's specification, not from the program.
- A test host is slower than the chip; when a streaming scenario fails, check `FDEBUG`'s stall bits before blaming the program.
- Keep the folder in Tiny Tapeout's layout (`info.yaml`, `src/`, `test/`, `docs/info.md`): it becomes the submission repository. Hardening needs it as a git root, so harden a copy (see the README).
- Commit the lockfile (`uv.lock`) with any dependency change.
