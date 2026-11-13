# Host port

A host (the demo board's RP2350, or anything with SPI) loads programs, configures and debugs the
state machines, and moves data through the FIFOs over an SPI target port.

| Signal | Pin | |
|---|---|---|
| `CS_N` | `ui[5]` | Low for a whole frame |
| `SCK` | `ui[6]` | Mode 0 (idle low, MOSI sampled on the rising edge) |
| `MOSI` | `ui[7]` | MSB first |
| `MISO` | `uo[7]` | Changes after rising edges; valid for the next one |

The port oversamples SCK, CS_N and MOSI through the same synchronizers as every other input,
so it needs no second clock domain: SCK may run up to clk/4 for writes and clk/6 for reads
(10 MHz at 60 MHz). The three pins also read as GPIO 21-23, so a program could watch the host.

## Frames

```
write:  CS_N low, [1 INC 000000] [ADDR] [w0 b31..b24] [w0 b23..b16] ... [wN b7..b0], CS_N high
read:   CS_N low, [0 INC 000000] [ADDR] [dummy] then 4 bytes per word on MISO, CS_N high
```

Each 32-bit word is written to `ADDR` as its last bit arrives; with `INC` the address then
increments. A read fetches the word at the start of each 4-byte slot and pops a FIFO only when
the slot's last bit has been clocked out, so an aborted read loses nothing. A frame can carry any
number of words; a partial word at `CS_N` high is dropped.

## Register map

Word addresses.

| Address | Name | Access | |
|---|---|---|---|
| `0x00`-`0x3F` | `IMEM` | W | Instruction memory (write only) |
| `0x40` | `ID` | R | `0x4D494D31` ("MIM1") |
| `0x41` | `CTRL` | RW | `[3:0]` SM enable; write-1 pulses: `[7:4]` restart, `[11:8]` clock-divider restart, `[15:12]` single step, `[19:16]` clear TX FIFO, `[23:20]` clear RX FIFO |
| `0x42` | `FLEVEL` | R | Per SM n: `[8n+3:8n]` TX level, `[8n+7:8n+4]` RX level |
| `0x43` | `FDEBUG` | R/W1C | Sticky per SM: `[3:0]` push dropped (full), `[7:4]` host write dropped (TX full), `[11:8]` host read of an empty RX FIFO, `[15:12]` stalled on an empty TX FIFO, `[19:16]` stalled on a full push destination |
| `0x44` | `IRQ` | R/W1C | `[7:0]` IRQ flags |
| `0x45` | `IRQ_FORCE` | W1S | Set IRQ flags |
| `0x46` | `PADCTRL` | RW | `[7:0]` open-drain mode for GPIO 0-7 |
| `0x47` | `PINS` | R | What the SMs see on GPIO 0-31 |
| `0x48` | `PINOUT` | R | The output levels of GPIO 0-31 |
| `0x49` | `PINOE` | R | `[7:0]` output enables of GPIO 0-7 |
| `0x80 + 0x10n` | SM n block | | |

State machine block (`n` = 0-3, base `0x80 + 0x10n`):

| Offset | Name | Access | |
|---|---|---|---|
| `0x0` | `TXF` | W | Push to the TX FIFO (dropped, with an `FDEBUG` flag, when full) |
| `0x1` | `RXF` | R | Pop from the RX FIFO (0, with an `FDEBUG` flag, when empty) |
| `0x2` | `CLKDIV` | W | See [ISA](isa.md#configuration-registers) |
| `0x3` | `EXECCTRL` | W | |
| `0x4` | `SHIFTCTRL` | W | |
| `0x5` | `PINCTRL` | W | |
| `0x6` | `CRCCFG` | W | |
| `0x7` | `INSTR` | RW | Write: run this instruction on the next cycle, enabled or not. Read: the current instruction |
| `0x8` | `PC` | R | |
| `0x9` | `X` | R | |
| `0xA` | `Y` | R | |
| `0xF` | `SMSTAT` | R | `[5:0]` ISR count, `[13:8]` OSR count, `[23:16]` delay left, `[24]` stalled, `[25]` an instruction is pending from `INSTR` or `EXEC`, `[26]` in a `WAIT`, `[27]` in an `IRQ wait` |

Configuration registers are write-only (the host knows what it wrote); this saved a 32-bit read
mux per register per SM. Any other register reads through X: force `mov x, isr`, read `X`.

## Debugging

`INSTR` and the `CTRL` step bits make a debugger: stop an SM, force instructions (any
instruction, including `jmp` to set the PC, `pull` and `mov` to set registers), single-step,
and read `PC`, `X`, `Y`, `SMSTAT`, `PINS` and `FDEBUG`. A forced instruction runs even if the SM
is disabled or in a delay; if it stalls it stays pending until it completes. The tests use this
path to check every instruction against its specification.

## Loading a program

[`Loader`](../sw/mimic/host.py) turns an assembled program into register writes:

1. Clear the SM's enable bit (the others stay as they are).
2. Write the instructions to `IMEM` at the program's origin (a burst with `INC`).
3. Write `CLKDIV`, `EXECCTRL` (wrap points relocated), `SHIFTCTRL` without FIFO joins,
   and `CRCCFG`; clear the SM's FIFOs.
4. Pass initial values (`.crc`, `.x`, `.y`) through the TX FIFO with forced `pull` and `mov`.
5. Set initial pin levels and directions with forced `set` instructions, one pin at a time.
6. Write `PINCTRL`, `PADCTRL`, and the final `SHIFTCTRL`; restart the SM and its clock divider.
7. Force `jmp origin`. Optionally enable the SM.

`start(mask)` enables several SMs in one `CTRL` write with their dividers restarted, so they run
in phase.

## On the demo board

`mimic-load` writes those operations to JSON on the PC; the MicroPython driver
[`sw/micropython/mimic_tt.py`](../sw/micropython/mimic_tt.py) plays them through a SoftSPI on
the board's host-port pins (RP2350 GPIO 17-19 and 37 on the current demo board, read from the
Tiny Tapeout SDK's pin map):

```sh
mimic-load programs/uart_tx.mim --sm 0 -D TX=uo4 --start -o uart_tx.json   # on the PC
mpremote cp sw/micropython/mimic_tt.py uart_tx.json :
```

```python
from ttboard.demoboard import DemoBoard
import mimic_tt

tt = DemoBoard.get()
tt.shuttle.tt_um_dijonkitchen_mimic.enable()
tt.clock_project_PWM(60_000_000)
tt.reset_project(True)
tt.reset_project(False)

chip = mimic_tt.Mimic()
assert chip.chip_id() == mimic_tt.CHIP_ID
chip.play_file("uart_tx.json")
chip.put(0, b"hi")  # uart_tx takes one byte per word; uo4 is the board's USB-UART RX
```

The driver is tested in CPython against the golden model through a bit-level SPI
([`test_micropython_driver.py`](../sw/tests/test_micropython_driver.py)); it has not run on
silicon, which does not exist yet.

## Throughput

At SCK = 10 MHz a burst moves 32 bits per 3.2 µs plus a 2-3 byte header, about 9 Mb/s of payload.
That is plenty for UART, SPI, I2C, PS/2, infrared or low-speed USB. Ethernet at 10 Mb/s runs at
line rate on the chip, but a frame longer than the FIFOs needs the host to keep pace with it; the
tests send and receive short frames at line rate and longer ones at lower rates.
