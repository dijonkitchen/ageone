# SPEC-2026-11-13-mimic: Mimic Protocol Emulator ASIC

An entry for Jane Street's [protocol emulator ASIC competition](https://blog.janestreet.com/protocol-emulator-asic-competition/): an open-source, general-purpose chip for bit-banging protocols, reprogrammable after fabrication, on the Tiny Tapeout IHP SG13CMOS5L shuttle (8x4 tiles, about 1.2 mm², 24 digital pins, one clock from the demo board's RP2350).
Entries are due 2027-01-18; about four are taped out in March 2027.
The judges weigh flexibility most (protocols the chip was not designed for), then protocols demonstrated, unique capabilities, the design and verification approach, and above all a clear write-up.

## Functional requirements

- **Engines**: several programmable state machines, PIO-like (single-cycle instructions, side-set, delays), with what PIO lacks for unknown protocols: arithmetic, CRCs, edge and timeout waits, immediates, open-drain pins, and ways for engines to cooperate without the host.
- **Program loading**: a documented host interface the demo board's RP2350 can drive, to load programs, configure and debug the engines, and move data, after reset and after reselection.
- **Toolchain**: an assembler, a loader that turns programs into host register writes, a MicroPython driver for the demo board, and example programs.
- **Protocols**: UART, SPI (modes 0-3, controller and target) and I2C (100 and 400 kHz, clock stretching) at least; stretch goals low-speed USB and 10 Mb/s Ethernet, doing as much line coding, CRC and clock recovery on chip as possible; more protocols the architecture was not built around.
- **Submission**: the Tiny Tapeout layout (`info.yaml`, `src/`, `test/`, `docs/info.md`), so the folder can become the public submission repository.

## Non-functional requirements

- Fits 8x4 tiles with room to place and route on five metal layers; one clock domain; 60 MHz target.
- Verified to a standard a judge can rerun: a golden model, tests from the ISA specification, random differential tests, protocol tests against independent device models, gate-level simulation, and a write-up of how and why.
- Everything runs from `make check` in the pinned environment; the hardening flow runs with Tiny Tapeout's tools.

## Out of scope

- Analog blocks, PLLs and SRAM macros (a later revision could use IHP's SRAM for program memory; see [the memory decision](../docs/decisions/2026-11-13-mimic-imem.md)).
- Physical-layer hardware for USB and Ethernet (transceivers, magnetics): the chip's I/O is 3.3 V digital, and the Pmods that would carry them are outside the chip.
- Creating the public submission repository and submitting: JC does that from this folder.

## Definition of done

1. RTL, golden model, assembler, loader, board driver, example programs, and documents (architecture, ISA, host port, protocols, verification, `docs/info.md`) are in `projects/mimic/`.
2. `make check` passes: ruff, mypy, every scenario on the model, and every scenario on the RTL in lockstep with the model.
3. Scenarios cover UART, SPI modes 0-3 (controller and target), I2C with clock stretching, low-speed USB receive and 10BASE-T transmit and receive at line rate, and at least three protocols beyond the competition's list.
4. Tiny Tapeout's flow hardens the design for `ihp-sg13cmos5l` at 8x4 tiles, and the write-up reports area, timing per corner, precheck, and gate-level results, including what does not pass.
5. Decision records cover the stack, the instruction memory, and the area trade-offs.
