"""Mutation test of the verification: does the RTL-vs-model lockstep catch a planted bug?

Each mutant changes one line of the golden model; the lockstep cocotb suite (random programs
and the directed ISA tests) then runs the RTL against the broken model and must fail. A
mutant that survives marks behaviour the tests do not reach.

    uv run python sw/tools/mutate.py            # all mutants
    uv run python sw/tools/mutate.py alu_xor    # one
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "sw" / "mimic" / "model.py"

MUTANTS = {
    "alu_xor": ("            4: alu_a ^ alu_b,", "            4: alu_a | alu_b,"),
    "jmp_x_eq_y": (
        "                take = self.x == self.y\n",
        "                take = self.x == self.y and self.y != 0\n",
    ),
    "jmp_x_lt_y": ("        x_lt_y = not (s33 >> 32)", "        x_lt_y = not (s33 >> 31)"),
    "isr_count_saturation": (
        "        isr_cntn = min(self.isr_cnt + n, 32)",
        "        isr_cntn = min(self.isr_cnt + n, 31)",
    ),
    "autopull_threshold": (
        "        do_autopull = self.autopull and self.osr_cnt >= pull_thr",
        "        do_autopull = self.autopull and self.osr_cnt > pull_thr",
    ),
    "wait_edge_arming": (
        "                met = self.wait_active and self.wait_ref and sel_pin == pol",
        "                met = self.wait_ref and sel_pin == pol",
    ),
    "side_set_priority": (
        "        o.pin_val = (sp_mask & side_vrot) | (~sp_mask & M32 & main_vrot)",
        "        o.pin_val = (mp_mask & main_vrot) | (~mp_mask & M32 & side_vrot)",
    ),
    "crc_reflect_feedback": ("        fb = (c & 1) ^ b\n", "        fb = (c >> 1 & 1) ^ b\n"),
    "irq_rel_index": (
        "            irq_idx = (((ins >> 11) & 1) << 2) | ((((ins >> 9) & 3) + self.sm_id) & 3)",
        "            irq_idx = (((ins >> 11) & 1) << 2) | ((((ins >> 9) & 3) - self.sm_id) & 3)",
    ),
    "fifo_full": ('            "tx_full": self.tx_cnt >= tx_cap,', '            "tx_full": self.tx_cnt > tx_cap,'),
    "delay_after_exec": ('            "delay": 0 if exec_req else delay_val,', '            "delay": delay_val,'),
    "movop_byteswap": (
        "        movv = [srcv, (~srcv) & M32, bitrev(srcv), byteswap(srcv)][movop]",
        "        movv = [srcv, (~srcv) & M32, bitrev(srcv), bitrev(srcv)][movop]",
    ),
}

FILTER = "test_[ri][as][na_]"  # random_isa_* and isa_* (the cocotb Makefile cannot take "|")


def make(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PATH=f"{ROOT / '.venv' / 'bin'}:{os.environ['PATH']}")
    return subprocess.run(
        ["make", "-s", *args], cwd=ROOT / "test", env=env, capture_output=True, text=True, check=False
    )


def summary(res: subprocess.CompletedProcess[str]) -> str:
    """The cocotb summary line (TESTS=.. PASS=.. FAIL=..); a run without one did not run."""
    lines = [line for line in (res.stdout + res.stderr).splitlines() if "TESTS=" in line]
    if not lines:
        raise RuntimeError(f"the suite did not run:\n{res.stdout[-2000:]}{res.stderr[-2000:]}")
    return lines[-1]


def run(name: str) -> bool:
    """True if the suite caught the mutant."""
    old, new = MUTANTS[name]
    source = MODEL.read_text()
    assert source.count(old) == 1, f"{name}: pattern not found exactly once"
    backup = MODEL.with_suffix(".py.orig")
    shutil.copy(MODEL, backup)
    try:
        MODEL.write_text(source.replace(old, new))
        make("clean")
        caught = "FAIL=0" not in summary(make(f"COCOTB_TEST_FILTER={FILTER}"))
    finally:
        shutil.move(backup, MODEL)
    return caught


def main(names: list[str]) -> int:
    backup = MODEL.with_suffix(".py.orig")
    if backup.exists():  # an interrupted run left a mutant in place
        shutil.move(backup, MODEL)
    # The unmutated suite must pass, or a "caught" mutant means nothing.
    make("clean")
    baseline = summary(make(f"COCOTB_TEST_FILTER={FILTER}"))
    if "FAIL=0" not in baseline:
        print(f"the suite fails without mutants: {baseline}")
        return 1
    results = {}
    for n in names or MUTANTS:
        results[n] = run(n)
        print(f"{n:24s} {'caught' if results[n] else 'SURVIVED'}", flush=True)
    print(f"{sum(results.values())}/{len(results)} mutants caught")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
