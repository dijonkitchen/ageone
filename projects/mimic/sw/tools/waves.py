"""Draw docs/eth_tx_wave.svg: the Ethernet transmitter's pin at 10 Mb/s, from the golden model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "sw")]

from mimic import programs, protocols  # noqa: E402
from mimic.bench import Bench, run  # noqa: E402

PIN = 10  # uo2


async def capture(b: Bench) -> None:
    await b.load(programs.load("eth_tx", TXD=PIN), 0, start=True)
    trace: list[int] = []
    b.monitors.append(lambda bb: trace.append(bb.level(PIN)))
    await b.put(0, *protocols.eth_tx_words(b"\xa5\x0f\x33\xcc"))
    await b.step(1200)
    b.trace = trace  # type: ignore[attr-defined]


def svg(levels: list[int], bits: list[str], start: int) -> str:
    w, h, x0, y0 = 6, 30, 60, 30
    pts = []
    for i, lv in enumerate(levels):
        y = y0 + (0 if lv else h)
        pts += [f"{x0 + i * w},{y}", f"{x0 + (i + 1) * w},{y}"]
    width = x0 + len(levels) * w + 20
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 130" font-family="Helvetica, Arial, sans-serif" font-size="12">',
        f'<rect width="{width}" height="130" fill="#fff"/>',
        f'<text x="8" y="{y0 + 20}">TXD</text>',
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="#1f4e79" stroke-width="2"/>',
    ]
    for k, label in enumerate(bits):
        x = x0 + (k * 6) * w
        out.append(f'<line x1="{x}" y1="{y0 - 8}" x2="{x}" y2="{y0 + h + 8}" stroke="#bbb" stroke-dasharray="2,2"/>')
        out.append(f'<text x="{x + 3 * w}" y="{y0 + h + 24}" text-anchor="middle">{label}</text>')
    out.append(
        f'<text x="{x0}" y="122" fill="#555">One bit = 6 cycles at 60 MHz (10 Mb/s); first half the inverse, '
        f"second half the bit. Cycles {start}-{start + len(levels)} after load.</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    b = run(capture)
    trace: list[int] = b.trace  # type: ignore[attr-defined]
    first = trace.index(1) - 3  # the first rise is mid-bit: a Manchester 1 starts low, like idle
    # The preamble is 62 bits of 1 0, then SFD 1 1, then data: show 4 preamble bits, the SFD tail, 8 data bits.
    start = first + 6 * 58
    n_bits = 14
    labels = ["1", "0", "1", "0", "1", "1"] + [str((0xA5 >> i) & 1) for i in range(8)]
    Path(ROOT / "docs" / "eth_tx_wave.svg").write_text(svg(trace[start : start + 6 * n_bits], labels, start))


if __name__ == "__main__":
    main()
