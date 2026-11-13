# Mimic instruction set

Each of Mimic's four state machines (SMs) runs 32-bit instructions from a shared 64-word memory.
An instruction takes one *tick* unless it stalls; then the SM idles for the instruction's delay.
A tick is one clock cycle, or fewer when the SM's clock divider slows it down.

This page is the reference: encodings, exact semantics, timing, and the assembler.
[`sw/mimic/isa.py`](../sw/mimic/isa.py) holds the same tables in code, the golden model
[`sw/mimic/model.py`](../sw/mimic/model.py) is the executable form of this page, and the RTL
[`src/mimic_sm.v`](../src/mimic_sm.v) is checked against both (see [verification](verification.md)).

## State

| Register | Bits | Notes |
|---|---|---|
| `PC` | 6 | Wraps from `WRAP_TOP` to `WRAP_BOTTOM` for free |
| `X`, `Y` | 32 | Scratch; `JMP` can test and decrement them, `ALU` can compute with them |
| `ISR` | 32 | Input shift register, with a count of the bits shifted in (0-32) |
| `OSR` | 32 | Output shift register, with a count of the bits shifted out (0-32; 32 is empty) |
| `CRC` | 32 | CRC or LFSR register, fed one bit per `IN` or `OUT` |
| `POLY` | 32 | The CRC polynomial |

Shared by all SMs: eight IRQ flags, and the 32-pin GPIO space.

## GPIO space

| GPIO | Pad | Direction |
|---|---|---|
| 0-7 | `uio[7:0]` | Bidirectional; each pin optionally open-drain (`PADCTRL`) |
| 8-14 | `uo[6:0]` | Output (GPIO 15 has no pad: `uo[7]` is the host port's MISO) |
| 16-23 | `ui[7:0]` | Input (`ui[5..7]` also carry the host port) |
| 24-31 | internal | Outputs that read back as inputs: wires between SMs |

Inputs pass through a two-flip-flop synchronizer, so an SM sees a pad two cycles after it changes.
Outputs are registered: an instruction's pin write reaches the pad on the next cycle.
When several SMs write a pin in the same cycle the highest-numbered SM wins,
and within one SM side-set wins over `OUT`, `MOV` or `SET`.

In open-drain mode a `uio` pin's output value controls its enable: writing 0 drives the pad low,
writing 1 releases it, and reading the pin returns the level on the wire.
I2C, 1-Wire, PS/2 and similar buses need nothing else.

## Instruction word

```
 31    28 27            20 19                                   0
+--------+----------------+--------------------------------------+
| opcode | side-set/delay |              arguments               |
+--------+----------------+--------------------------------------+
```

The 8-bit side-set/delay field is split per SM by `SIDE_COUNT` (0-8, including the enable bit
when `SIDE_EN`): the top `SIDE_COUNT` bits are side-set, the rest are delay (0-255 with no
side-set, 0-31 with three side-set bits).
With `SIDE_EN` the topmost bit enables the side-set for that instruction.
Side-set writes `SIDE_COUNT - SIDE_EN` pins starting at `SIDE_BASE` (or their directions,
with `SIDE_PINDIRS`), on every tick the instruction issues, including ticks it stalls.

| Opcode | Mnemonic | Arguments |
|---|---|---|
| `0` | `JMP` | `[19:15]` condition, `[14]` absolute pin, `[13:9]` pin, `[5:0]` address |
| `1` | `WAIT` | `[19]` polarity, `[18:16]` source, `[15]` timeout, `[14]` absolute pin (or IRQ relative), `[13:9]` pin (or `[11:9]` IRQ) |
| `2` | `IN` | `[8:4]` bit count (0 means 32), `[3:0]` source |
| `3` | `OUT` | `[19:16]` destination, `[8:4]` bit count (0 means 32) |
| `4` | `PUSH`/`PULL` | `[19]` 0 push, 1 pull; `[18]` if full/if empty; `[17]` block |
| `5` | `MOV` | `[19:16]` destination, `[15:14]` operation, `[3:0]` source |
| `6` | `IRQ` | `[19]` clear, `[18]` wait, `[14]` relative, `[11:9]` index |
| `7` | `SET` | `[19:16]` destination, `[15:0]` value |
| `8` | `ALU` | `[19]` writes Y (else X), `[18:16]` operation, `[3:0]` source |
| `9` | `ALUI` | `[19]` writes Y (else X), `[18:16]` operation, `[15:0]` value |
| `A`-`F` | | Reserved: executes as `NOP` (side-set and delay still apply) |

Unused argument bits are ignored.

### Sources (`IN`, `MOV`, `ALU`)

| Code | Name | Value |
|---|---|---|
| 0 | `PINS` | GPIO rotated so bit 0 is `IN_BASE` |
| 1 | `X` | |
| 2 | `Y` | |
| 3 | `NULL` | 0 |
| 4 | `STATUS` | All ones if the TX (or, with `STATUS_SEL`, RX) FIFO level is below `STATUS_N`, else 0 |
| 5 | `ISR` | |
| 6 | `OSR` | |
| 7 | `CRC` | |
| 8 | `IRQ` | The eight IRQ flags in bits 7:0 |
| 9 | `COUNT` | Bits 5:0 the ISR count, bits 13:8 the OSR count |
| 10-15 | | 0 |

### Destinations (`OUT`, `MOV`, `SET`)

| Code | Name | Effect |
|---|---|---|
| 0 | `PINS` | Pin levels: `OUT`/`MOV` from `OUT_BASE` for `OUT_COUNT` pins, `SET` from `SET_BASE` for `SET_COUNT` |
| 1 | `X` | |
| 2 | `Y` | |
| 3 | `NULL` | Nothing |
| 4 | `PINDIRS` | Pin directions, mapped like `PINS` (only GPIO 0-7 have them) |
| 5 | `PC` | Jump to the value's bits 5:0 |
| 6 | `ISR` | `ISR` = value; the count becomes the bit count for `OUT`, 0 otherwise |
| 7 | `OSR` | `OSR` = value, count 0 (full); `OUT` to `OSR` does nothing |
| 8 | `EXEC` | Run the value as the next instruction (this instruction's delay is ignored) |
| 9 | `CRC` | |
| 10 | `POLY` | |
| 11-15 | | Nothing |

## Instructions

### `JMP cond, address`

Jumps to `address` (absolute; the loader relocates it with the program) if the condition holds.

| Code | Condition | Holds when |
|---|---|---|
| 0 | (always) | |
| 1 | `!X` | X = 0 |
| 2 | `X--` | X ≠ 0; X is decremented either way |
| 3 | `!Y` | Y = 0 |
| 4 | `Y--` | Y ≠ 0; Y is decremented either way |
| 5 | `X!=Y` | |
| 6 | `X==Y` | |
| 7 | `X<Y` | Unsigned |
| 8 | `PIN n` | The pin is 1: `IN_BASE + n`, or GPIO `n` when absolute (`gpio n` in assembly) |
| 9 | `!PIN n` | The pin is 0 |
| 10 | `!OSRE` | OSR count < pull threshold |
| 11 | `OSRE` | OSR count ≥ pull threshold |
| 12 | `!TXE` | The TX FIFO holds data |
| 13 | `TXE` | The TX FIFO is empty |
| 14 | `X0` | X bit 0 is 1 |
| 15 | `!X0` | X bit 0 is 0 |
| 16 | `IRQ n` | IRQ flag `n` is set (with `rel`, `n` is offset by the SM number as for `IRQ`) |
| 17 | `!IRQ n` | IRQ flag `n` is clear |
| 18-31 | | Never |

### `WAIT polarity source index [timeout]`

Stalls until the condition holds.

| Code | Source | Holds when |
|---|---|---|
| 0 | level (`wait 1 pin 3`) | The pin equals the polarity |
| 1 | edge (`wait rise pin 3`, `wait fall pin 3`) | The pin equals the polarity after the wait has seen it at the other level |
| 2 | change (`wait change pin 3`) | The pin differs from its level on the wait's first tick |
| 3 | IRQ (`wait 1 irq 2`) | The flag equals the polarity; with polarity 1 the wait clears it |
| 4-7 | | At once |

Pins are relative to `IN_BASE`, or absolute GPIO numbers with `gpio` (bit 14).
The edge and change sources compare against what the SM saw on its own ticks, so a pulse
shorter than a tick can be missed when the clock divider is above 1.

With **timeout** (bit 15) X counts the ticks: each tick the condition does not hold, if X is 0
the wait ends, else X is decremented. A timed-out wait leaves X at 0 and lasts X + 1 ticks.
`jmp !x` after the wait tells a timeout from the condition.
Because X counts down while the wait waits, `X` afterwards also measures how long it took:
[pulse capture](../programs/pulse_capture.mim) is four instructions for this reason.

### `IN source, count`

Shifts `count` bits (1-32) of the source into ISR; right shift puts them in at bit 31, left
shift at bit 0. The ISR count increases by `count`, saturating at 32.
With autopush, when the count reaches the push threshold the new ISR value is pushed and ISR
cleared in the same tick; if the destination FIFO is full the `IN` stalls instead.
With `CRC_FEED_IN`, the CRC unit takes bit 0 of the shifted-in bits.

### `OUT destination, count`

Shifts `count` bits out of OSR (right shift: from bit 0; left shift: from bit 31) and writes them,
zero-extended, to the destination. The OSR count increases by `count`, saturating at 32.
With autopull, if the OSR count has reached the pull threshold the `OUT` first refills OSR from
the TX FIFO in the same tick (count 0), or stalls while the FIFO is empty.
With `CRC_FEED_OUT`, the CRC unit takes bit 0 of the shifted-out bits (the bit that goes
to the first pin).

### `PUSH [iffull] [block|noblock]`

Pushes ISR to the RX FIFO (or, with `ROUTE`, to the next SM's TX FIFO) and clears ISR.
`iffull` does nothing unless the ISR count has reached the push threshold.
A blocking push stalls while the destination is full; a non-blocking push to a full
destination drops the word, clears ISR and sets an `FDEBUG` flag.

### `PULL [ifempty] [block|noblock]`

Moves the next TX FIFO word into OSR (count 0).
`ifempty` does nothing unless the OSR count has reached the pull threshold.
A blocking pull stalls while the FIFO is empty; a non-blocking pull from an empty FIFO copies X.

### `MOV destination, [op]source`

| Op | Syntax | Value |
|---|---|---|
| 0 | `mov x, y` | The source |
| 1 | `mov x, !y` or `~y` | Inverted |
| 2 | `mov x, ::y` | Bit-reversed |
| 3 | `mov x, ><y` | Byte-swapped |

### `IRQ [set|wait|clear] index [rel]`

Sets (or clears) IRQ flag `index`. With `wait` it sets the flag and stalls until something
clears it. With `rel` the SM number is added to the index's two low bits, so one program can
signal per SM. The host can read, set and clear the flags.

### `SET destination, value`

Writes a 16-bit value (zero-extended). Pin writes use `SET_BASE` and `SET_COUNT`.

### `ALU` and `ALUI`: `op x|y, source|value`

`X` or `Y` = itself `op` the operand (a source, or a 16-bit immediate). Shifts use the operand's
bits 4:0.

| Code | Op | Result |
|---|---|---|
| 0 | `add` | a + b |
| 1 | `sub` | a − b |
| 2 | `and` | a & b |
| 3 | `or` | a \| b |
| 4 | `xor` | a ^ b |
| 5 | `shl` | a << b |
| 6 | `shr` | a >> b (logical) |
| 7 | `rol` | a rotated left by b |

32-bit constants take three instructions: `set x, hi`, `shl x, 16`, `or x, lo`.

## The CRC unit

Each SM has a CRC (or LFSR) register and polynomial. For each fed bit `b`:

- MSB-first (`CRC_REFLECT` = 0, polynomial left-aligned):
  `f = CRC[31] ^ b; CRC = (CRC << 1) ^ (f ? POLY : 0)`.
- LSB-first (`CRC_REFLECT` = 1, polynomial bit-reversed and right-aligned):
  `f = CRC[0] ^ b; CRC = (CRC >> 1) ^ (f ? POLY : 0)`.

Any width from 1 to 32 bits works without a width setting: align the polynomial and the initial
value, and the unused bits stay 0. `CRC_FEED_OUT` and `CRC_FEED_IN` feed it from `OUT` and `IN`;
`MOV`/`SET` to `CRC` and `POLY` set it up, and `MOV` from `CRC` reads it.

| Use | `.crc` setting | Check |
|---|---|---|
| CRC-32 (Ethernet, zlib) | `0xEDB88320 reflect`, init all ones | `CRC ^ 0xFFFFFFFF` = `zlib.crc32` |
| CRC-16/CCITT | `0x10210000`, init `0xFFFF0000` | result in bits 31:16 |
| USB CRC16 | `0xA001 reflect`, init `0xFFFF` | residue `0xB001` |
| USB CRC5 | `0x14 reflect`, init `0x1F` | residue `0x06` |
| Parity | `1 reflect` | bit 0 is the parity of the fed bits |

The directed tests check these against published check values.

## Timing

An instruction issues on a tick. It completes in that tick unless it stalls (`WAIT` not met,
`IRQ wait`, a blocking `PUSH`/`PULL` or autopush/autopull that cannot proceed); a stalled
instruction retries on every tick, re-applying its side-set. After it completes the SM idles for
the delay, then fetches the next instruction. So a non-stalling instruction with delay `d` takes
exactly `1 + d` ticks, and loops built from them are cycle-exact.

- Pin writes reach the pads one cycle after the tick; pad inputs reach the SMs two cycles after they
  change. An SM that reacts to an input and answers on an output therefore takes at least
  4 cycles: 2 in, the tick, 1 out.
- The clock divider gives a tick every `INT + FRAC/256` cycles on average (`INT` 1-65535,
  `INT` 0 counts as 1). Restarting dividers together keeps SMs in phase.

## Configuration registers

Per SM, written by the host (see [host port](host.md)):

| Register | Fields |
|---|---|
| `CLKDIV` | `[31:16]` INT, `[15:8]` FRAC |
| `EXECCTRL` | `[5:0]` WRAP_BOTTOM, `[11:6]` WRAP_TOP, `[16:12]` SIDE_BASE, `[20:17]` SIDE_COUNT, `[21]` SIDE_EN, `[22]` SIDE_PINDIRS, `[23]` STATUS_SEL, `[27:24]` STATUS_N |
| `SHIFTCTRL` | `[0]` IN_RIGHT, `[1]` OUT_RIGHT, `[2]` AUTOPUSH, `[3]` AUTOPULL, `[8:4]` PUSH_THRESH, `[13:9]` PULL_THRESH (0 means 32), `[16]` FJOIN_TX, `[17]` FJOIN_RX, `[20]` ROUTE |
| `PINCTRL` | `[4:0]` OUT_BASE, `[10:5]` OUT_COUNT, `[15:11]` SET_BASE, `[20:16]` SET_COUNT, `[25:21]` IN_BASE |
| `CRCCFG` | `[0]` CRC_REFLECT, `[1]` CRC_FEED_OUT, `[2]` CRC_FEED_IN |

After reset: `CLKDIV` 1, `WRAP_TOP` 63, shifts to the right, thresholds 32, everything else 0.

FIFOs hold two words each way; `FJOIN_TX` or `FJOIN_RX` gives one direction all four (and
empties both). With `ROUTE`, pushes go to the TX FIFO of the next SM in the ring
SM0 → SM1 → SM2 → SM3 → SM0, so SMs form pipelines without the host.

## Assembler

`mimic-asm program.mim [-D NAME=VALUE] [--listing] [-o out.json]` assembles a program;
`mimic-load program.mim --sm N [--origin A] [--start] -o ops.json` turns it into the register
writes that load it. The syntax follows the RP2040's `pioasm` where the instructions overlap.

```
; comments start with ; or //
.program uart_tx          ; name
.define TX uo0            ; a symbol; -D TX=uio1 overrides it
.side_set 1 opt           ; side-set bits, optional enable, [pindirs]
.side_pins TX             ; SIDE_BASE
.out_pins TX 1            ; OUT_BASE, OUT_COUNT
.set_pins CS 1            ; SET_BASE, SET_COUNT
.in_pins RX               ; IN_BASE
.clkdiv 52.08             ; clock divider, fractions allowed
.shift_in right autopush 8   ; direction, autopush, threshold
.shift_out left 8            ; direction, threshold without autopull
.fifo tx                  ; join the FIFOs (tx or rx)
.route                    ; pushes go to the next SM
.status rx 2              ; STATUS: RX level below 2
.crc 0xEDB88320 reflect out in init 0xFFFFFFFF
.opendrain SDA SCL        ; open-drain pads (uio only)
.pindirs SCK MOSI         ; pins to make outputs at load
.initial CS=1 SCK=0       ; their first levels
.x 0xFFFFFFFF             ; initial X (and .y)
.origin 0                 ; default load address
.wrap_target / .wrap      ; the free loop
label:
    out pins, 1   side 0 [7]   ; instruction, side-set value, delay
```

Pins are numbers (0-31), names (`uio0`-`uio7`, `uo0`-`uo6`, `ui0`-`ui7`, `v0`-`v7` for the
internal pins, `gpio12`), or symbols. Values are integer expressions (`+ - * / % << >> & | ^ ~`)
of numbers, symbols and labels. `nop` is `mov y, y`; `word EXPR` emits a raw instruction.

| Assembly | Encodes |
|---|---|
| `jmp x--, loop` | conditions as in the table: `!x x-- !y y-- x!=y x==y x<y pin N !pin N gpio N !gpio N !osre osre !txe txe x0 !x0 irq N [rel] !irq N [rel]` |
| `wait 1 pin 0`, `wait 0 gpio uio3`, `wait rise pin 1`, `wait fall gpio 5`, `wait change pin 0`, `wait 1 irq 2 rel`, ... `timeout` | `WAIT` |
| `in pins, 8`, `out pindirs, 2`, `out exec, 32` | `IN`, `OUT` |
| `push`, `push iffull noblock`, `pull ifempty` | `PUSH`, `PULL` |
| `mov isr, ~crc`, `mov x, ::osr`, `mov osr, ><x` | `MOV` |
| `irq 3`, `irq wait 0 rel`, `irq clear 2` | `IRQ` |
| `set pindirs, 3`, `set x, 1000` | `SET` |
| `add x, 1`, `sub y, x`, `xor x, isr`, `shr y, 25` | `ALU`, `ALUI` |
