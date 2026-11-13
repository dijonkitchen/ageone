# SPDX-License-Identifier: Apache-2.0
"""cocotb tests: every scenario in sw/tests/scenarios.py, run on the RTL (or gate-level netlist).

Each scenario drives the chip through mimic.bench, the same board model the pytest suite
runs on the golden model. By default the golden model also runs in lockstep and every
output pin is compared every cycle (LOCKSTEP=0 turns that off, e.g. for speed).
On the RTL, the state machines' registers are compared with the model's too.
"""

from __future__ import annotations

import os

import cocotb
import scenarios
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge
from mimic.bench import Bench
from mimic.model import Mimic

GATES = os.environ.get("GATES") == "yes"
LOCKSTEP = os.environ.get("LOCKSTEP", "1") != "0"


def _int(sig) -> int:
    v = sig.value
    if not v.is_resolvable:
        raise AssertionError(f"{sig._name} is {v} (X or Z)")
    return int(v)


class RtlDevice:
    def __init__(self, dut) -> None:
        self.dut = dut

    async def clock(self, ui_in: int, uio_in: int) -> tuple[int, int, int]:
        self.dut.ui_in.value = ui_in
        self.dut.uio_in.value = uio_in
        await RisingEdge(self.dut.clk)
        await FallingEdge(self.dut.clk)
        return _int(self.dut.uo_out), _int(self.dut.uio_out), _int(self.dut.uio_oe)


SM_REGS = ("pc", "x", "y", "isr", "osr", "crc", "poly", "isr_cnt", "osr_cnt", "delay_cnt")


class Lockstep:
    """The RTL and the golden model side by side; any difference fails the test."""

    def __init__(self, dut) -> None:
        self.rtl = RtlDevice(dut)
        self.model = Mimic()
        self.dut = dut
        self.cycle = 0
        self.check_every = 16  # scenarios may lower this to compare registers more often
        self.cores = [dut.user_project.sm[i].core for i in range(4)] if not GATES else []

    async def clock(self, ui_in: int, uio_in: int) -> tuple[int, int, int]:
        got = await self.rtl.clock(ui_in, uio_in)
        want = self.model.clock(ui_in, uio_in)
        self.cycle += 1
        if got != want:
            names = ("uo_out", "uio_out", "uio_oe")
            diff = ", ".join(f"{n} rtl={g:02x} model={w:02x}" for n, g, w in zip(names, got, want) if g != w)
            raise AssertionError(f"cycle {self.cycle}: {diff}")
        if not GATES and self.cycle % self.check_every == 0:
            self.compare_state()
        return got

    def compare_state(self) -> None:
        for i, sm in enumerate(self.model.sms):
            core = self.cores[i]
            for r in SM_REGS:
                rtl = _int(getattr(core, r))
                ref = getattr(sm, r)
                if rtl != ref:
                    raise AssertionError(f"cycle {self.cycle}: SM{i}.{r} rtl={rtl:#x} model={ref:#x}")


async def make_bench(dut) -> Bench:
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.ena.value = 1
    dut.ui_in.value = 1 << 5  # host CS_N idle high
    dut.uio_in.value = 0xFF
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    dev = Lockstep(dut) if LOCKSTEP else RtlDevice(dut)
    bench = Bench(dev)
    if GATES:
        # The instruction memory's latches power up unknown; in a netlist that X can reach
        # outputs through the read multiplexers, so clear the memory first (the model sees it too).
        await bench.write(0x00, *([0] * 64))
    return bench


def _make_test(name: str, fn):
    async def run(dut) -> None:
        bench = await make_bench(dut)
        await fn(bench)
        dut._log.info(f"{name}: {bench.cycle} cycles")

    run.__name__ = run.__qualname__ = f"test_{name}"
    return cocotb.test(timeout_time=None)(run)


for _name, _fn in scenarios.ALL.items():
    globals()[f"test_{_name}"] = _make_test(_name, _fn)
