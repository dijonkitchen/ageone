## How it works

Mimic is a protocol emulator: four small programmable state machines that bit-bang serial protocols with cycle-exact timing, reprogrammed over SPI after fabrication.
Each state machine runs 32-bit instructions from a shared 64-word memory: `JMP`, `WAIT` (levels, edges, changes, IRQs, with a timeout), `IN`/`OUT` shifts with autopush and autopull, `PUSH`/`PULL`, `MOV`, `IRQ`, `SET` with 16-bit immediates, and an `ALU`.
Every instruction can also set up to 8 pins (side-set) and delay up to 255 ticks.
Each state machine has a CRC/LFSR unit (any polynomial up to 32 bits) fed by its shifts, two FIFOs to the host, and can route its pushes to the next state machine.
The 24 pins and 8 internal pins form one GPIO space that every state machine can use; the bidirectional pins can be open-drain.

Example programs cover UART, SPI (modes 0-3, controller and target), I2C (controller with clock stretching, and target), JTAG, WS2812, 10BASE-T Manchester transmit and receive with CRC-32 at 10 Mb/s, low-speed USB receive (NRZI, bit stuffing, CRC5/CRC16), PS/2, infrared remotes, and PWM.

Full documentation: [architecture](architecture.md), [instruction set](isa.md), [host port](host.md), [protocols](protocols.md), [verification](verification.md).

## How to test

Clock the design at 60 MHz (10 Mb/s Ethernet needs it; everything else works slower) and reset it.
The RP2350 talks to the host port: `ui[5]` CS_N, `ui[6]` SCK, `ui[7]` MOSI, `uo[7]` MISO, SPI mode 0, SCK at most clk/6.
Read register `0x40`: it returns `0x4D494D31` ("MIM1").

On a PC, `mimic-load programs/uart_tx.mim --sm 0 -D TX=uo4 --start -o uart_tx.json` turns a program into register writes.
Copy `sw/micropython/mimic_tt.py` and the JSON to the board, then:

```python
import mimic_tt

chip = mimic_tt.Mimic()
chip.play_file("uart_tx.json")
chip.put(0, b"hi")  # appears on the demo board's USB serial port
```

## External hardware

Whatever the protocol needs, on the Pmod headers: an SPI or I2C device on `uio`, a WS2812 strip, a PS/2 keyboard (with level shifting), an infrared receiver.
Low-speed USB and 10BASE-T need line interfaces (USB series resistors and pull-ups, an Ethernet transformer and drivers) that are not part of the chip.
