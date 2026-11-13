"""Cycle-accurate golden model of the Mimic chip, at the Tiny Tapeout pin level.

`Mimic.clock(ui_in, uio_in)` advances one rising edge of clk, exactly as the RTL does,
including the input synchronizers and the SPI host port, and returns the outputs after
that edge. Tests run the same scenarios on this model and on the RTL, and the lockstep
tests compare the two every cycle.

The model is written as the RTL's next-state functions: compute everything from the
current registers, then commit. Keep it that way: it is the reference the RTL is held to.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import isa
from .isa import M32


def rotl(v: int, s: int) -> int:
    s &= 31
    return ((v << s) | (v >> (32 - s))) & M32 if s else v


def lomask(k: int) -> int:
    """Low k bits set, k in 0..32."""
    return M32 if k >= 32 else (1 << k) - 1


def bitrev(v: int) -> int:
    return int(f"{v:032b}"[::-1], 2)


def byteswap(v: int) -> int:
    return int.from_bytes(v.to_bytes(4, "big"), "little")


def crc_step(c: int, p: int, b: int, refl: bool) -> int:
    if refl:
        fb = (c & 1) ^ b
        return (c >> 1) ^ (p if fb else 0)
    fb = (c >> 31) ^ b
    return ((c << 1) & M32) ^ (p if fb else 0)


class Fifo:
    """A state machine's TX and RX FIFOs sharing 2*DEPTH words (src/mimic_fifo.v)."""

    def __init__(self, depth: int = isa.FIFO_DEPTH) -> None:
        self.depth = depth
        self.mem = [0] * (2 * depth)
        self.tx_rp = self.tx_wp = self.tx_cnt = 0
        self.rx_rp = self.rx_wp = self.rx_cnt = 0
        self.join_tx_q = self.join_rx_q = False

    def caps(self, join_tx: bool, join_rx: bool) -> tuple[int, int, int]:
        d = self.depth
        tx_cap = 2 * d if join_tx else (0 if join_rx else d)
        rx_cap = 2 * d if join_rx else (0 if join_tx else d)
        rx_base = 0 if join_rx else d
        return tx_cap, rx_cap, rx_base

    def view(self, join_tx: bool, join_rx: bool) -> dict[str, int | bool]:
        tx_cap, rx_cap, rx_base = self.caps(join_tx, join_rx)
        n = 2 * self.depth
        return {
            "tx_empty": self.tx_cnt == 0,
            "rx_empty": self.rx_cnt == 0,
            "tx_full": self.tx_cnt >= tx_cap,
            "rx_full": self.rx_cnt >= rx_cap,
            "tx_level": self.tx_cnt,
            "rx_level": self.rx_cnt,
            "tx_head": self.mem[self.tx_rp % n],
            "rx_head": self.mem[(rx_base + self.rx_rp) % n],
        }

    def _inc(self, p: int, joined: bool) -> int:
        n = 2 * self.depth
        return (p + 1) % n if joined else (p + 1) % self.depth

    def commit(
        self,
        join_tx: bool,
        join_rx: bool,
        clr_tx: bool,
        clr_rx: bool,
        tx_wr: bool,
        tx_wdata: int,
        tx_rd: bool,
        rx_wr: bool,
        rx_wdata: int,
        rx_rd: bool,
    ) -> None:
        v = self.view(join_tx, join_rx)
        _, _, rx_base = self.caps(join_tx, join_rx)
        n = 2 * self.depth
        do_tx_wr = tx_wr and not v["tx_full"]
        do_tx_rd = tx_rd and not v["tx_empty"]
        do_rx_wr = rx_wr and not v["rx_full"]
        do_rx_rd = rx_rd and not v["rx_empty"]
        tx_widx = self.tx_wp % n
        rx_widx = (rx_base + self.rx_wp) % n
        if do_tx_wr:
            self.mem[tx_widx] = tx_wdata
        if do_rx_wr and not (do_tx_wr and tx_widx == rx_widx):
            self.mem[rx_widx] = rx_wdata
        rejoin = join_tx != self.join_tx_q or join_rx != self.join_rx_q
        self.join_tx_q, self.join_rx_q = join_tx, join_rx
        if clr_tx or rejoin:
            self.tx_rp = self.tx_wp = self.tx_cnt = 0
        else:
            if do_tx_wr:
                self.tx_wp = self._inc(self.tx_wp, join_tx)
            if do_tx_rd:
                self.tx_rp = self._inc(self.tx_rp, join_tx)
            self.tx_cnt = (self.tx_cnt + int(do_tx_wr) - int(do_tx_rd)) & 7
        if clr_rx or rejoin:
            self.rx_rp = self.rx_wp = self.rx_cnt = 0
        else:
            if do_rx_wr:
                self.rx_wp = self._inc(self.rx_wp, join_rx)
            if do_rx_rd:
                self.rx_rp = self._inc(self.rx_rp, join_rx)
            self.rx_cnt = (self.rx_cnt + int(do_rx_wr) - int(do_rx_rd)) & 7


@dataclass
class SMOut:
    """What one state machine drives during a cycle (combinational outputs)."""

    pin_mask: int = 0
    pin_val: int = 0
    dir_mask: int = 0
    dir_val: int = 0
    irq_set: int = 0
    irq_clr: int = 0
    tx_pop: bool = False
    push_req: bool = False
    push_data: int = 0
    push_drop: bool = False
    tx_stall: bool = False
    rx_stall: bool = False


@dataclass
class SM:
    """One state machine: configuration, architectural state, and its next-state function."""

    sm_id: int
    # CLKDIV
    div_int: int = 1
    div_frac: int = 0
    # EXECCTRL
    wrap_bot: int = 0
    wrap_top: int = 63
    side_base: int = 0
    side_count: int = 0
    side_en: bool = False
    side_pindirs: bool = False
    status_sel: int = 0
    status_n: int = 0
    # SHIFTCTRL
    in_right: bool = True
    out_right: bool = True
    autopush: bool = False
    autopull: bool = False
    push_thr: int = 0
    pull_thr: int = 0
    fjoin_tx: bool = False
    fjoin_rx: bool = False
    route_en: bool = False
    # PINCTRL
    out_base: int = 0
    out_count: int = 0
    set_base: int = 0
    set_count: int = 0
    in_base: int = 0
    # CRCCFG
    crc_reflect: bool = False
    crc_feed_out: bool = False
    crc_feed_in: bool = False
    # state
    pc: int = 0
    x: int = 0
    y: int = 0
    isr: int = 0
    osr: int = 0
    crc: int = 0
    poly: int = 0
    exec_reg: int = 0
    isr_cnt: int = 0
    osr_cnt: int = 32
    delay_cnt: int = 0
    exec_pending: bool = False
    wait_active: bool = False
    wait_ref: bool = False
    irq_waiting: bool = False
    force_tick: bool = False
    last_stall: bool = False
    div_cnt: int = 0
    div_acc: int = 0
    # set by evaluate() for commit()
    _next: dict[str, int | bool] = field(default_factory=dict, repr=False)

    # ---- configuration ----------------------------------------------------
    def cfg_write(self, reg: int, d: int) -> None:
        if reg == isa.SM_CLKDIV:
            self.div_int, self.div_frac = d >> 16, (d >> 8) & 0xFF
        elif reg == isa.SM_EXECCTRL:
            self.wrap_bot, self.wrap_top = d & 63, (d >> 6) & 63
            self.side_base, self.side_count = (d >> 12) & 31, (d >> 17) & 15
            self.side_en, self.side_pindirs = bool(d >> 21 & 1), bool(d >> 22 & 1)
            self.status_sel, self.status_n = (d >> 23) & 1, (d >> 24) & 15
        elif reg == isa.SM_SHIFTCTRL:
            self.in_right, self.out_right = bool(d & 1), bool(d >> 1 & 1)
            self.autopush, self.autopull = bool(d >> 2 & 1), bool(d >> 3 & 1)
            self.push_thr, self.pull_thr = (d >> 4) & 31, (d >> 9) & 31
            self.fjoin_tx, self.fjoin_rx = bool(d >> 16 & 1), bool(d >> 17 & 1)
            self.route_en = bool(d >> 20 & 1)
        elif reg == isa.SM_PINCTRL:
            self.out_base, self.out_count = d & 31, (d >> 5) & 63
            self.set_base, self.set_count = (d >> 11) & 31, (d >> 16) & 31
            self.in_base = (d >> 21) & 31
        elif reg == isa.SM_CRCCFG:
            self.crc_reflect, self.crc_feed_out, self.crc_feed_in = bool(d & 1), bool(d >> 1 & 1), bool(d >> 2 & 1)

    def ins(self, imem: list[int]) -> int:
        return self.exec_reg if self.exec_pending else imem[self.pc]

    def cfg_read(self, reg: int, imem: list[int]) -> int:
        if reg == isa.SM_INSTR:
            return self.ins(imem)
        if reg == isa.SM_PC:
            return self.pc
        if reg == isa.SM_X:
            return self.x
        if reg == isa.SM_Y:
            return self.y
        if reg == isa.SM_STAT:
            return (
                self.isr_cnt
                | (self.osr_cnt << 8)
                | (self.delay_cnt << 16)
                | (int(self.last_stall) << 24)
                | (int(self.exec_pending) << 25)
                | (int(self.wait_active) << 26)
                | (int(self.irq_waiting) << 27)
            )
        return 0

    def div_pulse(self) -> bool:
        return self.div_cnt == 0

    # ---- one cycle --------------------------------------------------------
    def evaluate(
        self,
        imem: list[int],
        pins_in: int,
        irq_in: int,
        fifo: dict[str, int | bool],
        push_full: bool,
        enable: bool,
        step: bool,
    ) -> SMOut:
        """Combinational outputs for this cycle; stores next state for commit()."""
        o = SMOut()
        tick = (enable and self.div_pulse()) or step or self.force_tick
        in_delay = self.delay_cnt != 0 and not self.force_tick
        exec_cycle = tick and not in_delay

        ins = self.ins(imem)
        op = ins >> 28
        sd = (ins >> 20) & 0xFF
        dst = (ins >> 16) & 15
        srcsel = ins & 15
        cnt5 = (ins >> 4) & 31
        n = 32 if cnt5 == 0 else cnt5
        imm16 = ins & 0xFFFF

        side_cnt_eff = min(self.side_count, 8)
        sbits = 0 if side_cnt_eff == 0 else side_cnt_eff - int(self.side_en)
        sd_top = sd >> (8 - side_cnt_eff)
        side_data = sd_top & ((1 << sbits) - 1)
        delay_val = sd & ((1 << (8 - side_cnt_eff)) - 1)
        side_active = sbits != 0 and (not self.side_en or bool(sd >> 7 & 1))

        push_thr = 32 if self.push_thr == 0 else self.push_thr
        pull_thr = 32 if self.pull_thr == 0 else self.pull_thr

        pins_rel = rotl(pins_in, (-self.in_base) & 31)
        pin_idx = ((ins >> 9) & 31) if (ins >> 14) & 1 else (self.in_base + ((ins >> 9) & 31)) & 31
        sel_pin = (pins_in >> pin_idx) & 1
        if (ins >> 14) & 1:
            irq_idx = (((ins >> 11) & 1) << 2) | ((((ins >> 9) & 3) + self.sm_id) & 3)
        else:
            irq_idx = (ins >> 9) & 7
        irq_bit = (irq_in >> irq_idx) & 1
        irq_one = 1 << irq_idx

        tx_empty = bool(fifo["tx_empty"])
        tx_head = int(fifo["tx_head"])
        status_lvl = int(fifo["rx_level"]) if self.status_sel else int(fifo["tx_level"])
        status_val = M32 if status_lvl < self.status_n else 0

        srcv = {
            0: pins_rel,
            1: self.x,
            2: self.y,
            4: status_val,
            5: self.isr,
            6: self.osr,
            7: self.crc,
            8: irq_in,
            9: self.isr_cnt | (self.osr_cnt << 8),
        }.get(srcsel, 0)
        movop = (ins >> 14) & 3
        movv = [srcv, (~srcv) & M32, bitrev(srcv), byteswap(srcv)][movop]

        # Shared adder.
        cond = (ins >> 15) & 31
        aluop = (ins >> 16) & 7
        is_alu = op in (isa.OP_ALU, isa.OP_ALUI)
        use_y = (is_alu and bool(ins >> 19 & 1)) or (op == isa.OP_JMP and cond == 4)
        alu_a = self.y if use_y else self.x
        alu_b = imm16 if op == isa.OP_ALUI else srcv
        if is_alu:
            add_b = alu_b
        elif op == isa.OP_JMP and cond == 7:
            add_b = self.y
        else:
            add_b = 1
        add_sub = not (is_alu and aluop == 0)
        s33 = alu_a + ((~add_b & M32) if add_sub else add_b) + int(add_sub)
        sum32 = s33 & M32
        x_lt_y = not (s33 >> 32)

        do_autopull = self.autopull and self.osr_cnt >= pull_thr
        osr_src = tx_head if do_autopull else self.osr

        sh_n = (alu_b & 31) if is_alu else n
        m_lo = lomask(sh_n)
        m_hi = lomask(32 - sh_n)
        in_merge = (self.isr & ~m_lo & M32) | (srcv & m_lo)
        if op == isa.OP_IN:
            rot_in = in_merge if self.in_right else self.isr
            rot_amt = (-n) & 31 if self.in_right else n & 31
        elif op == isa.OP_OUT:
            rot_in = osr_src
            rot_amt = (-n) & 31 if self.out_right else n & 31
        else:
            rot_in = alu_a
            rot_amt = (-(alu_b & 31)) & 31 if aluop == 6 else alu_b & 31
        rot_out = rotl(rot_in, rot_amt)

        isr_new = rot_out if self.in_right else (rot_out & ~m_lo & M32) | (srcv & m_lo)
        isr_cntn = min(self.isr_cnt + n, 32)
        out_data = (osr_src & m_lo) if self.out_right else (rot_out & m_lo)
        osr_new = (rot_out & m_hi) if self.out_right else (rot_out & ~m_lo & M32)
        osr_cntn = min((0 if do_autopull else self.osr_cnt) + n, 32)

        alu_res = {
            0: sum32,
            1: sum32,
            2: alu_a & alu_b,
            3: alu_a | alu_b,
            4: alu_a ^ alu_b,
            5: rot_out & ~m_lo & M32,
            6: rot_out & m_hi,
            7: rot_out,
        }[aluop]

        # Execute.
        stall = jump = wb_en = wb_set = exec_req = crc_feed = False
        crc_bit = 0
        jump_tgt = ins & 63
        wb_dst, wb_val, wb_cnt = dst, 0, 0
        exec_val = 0
        x_n, y_n, isr_n, osr_n, crc_n, poly_n = self.x, self.y, self.isr, self.osr, self.crc, self.poly
        isr_cnt_n, osr_cnt_n = self.isr_cnt, self.osr_cnt
        push_req = push_drop = pull_req = tx_stall = rx_stall = False
        push_data = self.isr
        irq_set = irq_clr = 0
        wait_active_n, wait_ref_n, irq_waiting_n = False, self.wait_ref, False
        main_pins = main_dirs = False

        if op == isa.OP_JMP:
            take = False
            if cond == 0:
                take = True
            elif cond == 1:
                take = self.x == 0
            elif cond == 2:
                take = self.x != 0
                x_n = sum32
            elif cond == 3:
                take = self.y == 0
            elif cond == 4:
                take = self.y != 0
                y_n = sum32
            elif cond == 5:
                take = self.x != self.y
            elif cond == 6:
                take = self.x == self.y
            elif cond == 7:
                take = x_lt_y
            elif cond == 8:
                take = bool(sel_pin)
            elif cond == 9:
                take = not sel_pin
            elif cond == 10:
                take = self.osr_cnt < pull_thr
            elif cond == 11:
                take = self.osr_cnt >= pull_thr
            elif cond == 12:
                take = not tx_empty
            elif cond == 13:
                take = tx_empty
            elif cond == 14:
                take = bool(self.x & 1)
            elif cond == 15:
                take = not (self.x & 1)
            elif cond == 16:
                take = bool(irq_bit)
            elif cond == 17:
                take = not irq_bit
            jump = take
        elif op == isa.OP_WAIT:
            pol = (ins >> 19) & 1
            wsrc = (ins >> 16) & 7
            ref_c = False
            if wsrc == isa.WAIT_LEVEL:
                met = sel_pin == pol
            elif wsrc == isa.WAIT_EDGE:
                ref_c = (self.wait_ref or sel_pin != pol) if self.wait_active else sel_pin != pol
                met = self.wait_active and self.wait_ref and sel_pin == pol
            elif wsrc == isa.WAIT_CHANGE:
                ref_c = self.wait_ref if self.wait_active else bool(sel_pin)
                met = self.wait_active and sel_pin != int(self.wait_ref)
            elif wsrc == isa.WAIT_IRQ:
                met = irq_bit == pol
                if met and pol:
                    irq_clr = irq_one
            else:
                met = True
            timeout = bool(ins >> 15 & 1)
            if not met and not (timeout and self.x == 0):
                stall = True
                wait_active_n = True
                wait_ref_n = ref_c
                if timeout:
                    x_n = sum32
        elif op == isa.OP_IN:
            if self.autopush and isr_cntn >= push_thr:
                push_req = True
                push_data = isr_new
                if push_full:
                    stall = rx_stall = True
                else:
                    isr_n, isr_cnt_n = 0, 0
            else:
                isr_n, isr_cnt_n = isr_new, isr_cntn
            crc_feed = self.crc_feed_in and not stall
            crc_bit = srcv & 1
        elif op == isa.OP_OUT:
            if do_autopull and tx_empty:
                stall = tx_stall = True
            else:
                pull_req = do_autopull
                osr_n, osr_cnt_n = osr_new, osr_cntn
                wb_en, wb_val, wb_cnt = True, out_data, n
                crc_feed = self.crc_feed_out
                crc_bit = out_data & 1
        elif op == isa.OP_PUSHPULL:
            iff = bool(ins >> 18 & 1)
            blk = bool(ins >> 17 & 1)
            if not (ins >> 19 & 1):  # PUSH
                if not (iff and self.isr_cnt < push_thr):
                    push_req = True
                    if push_full and blk:
                        stall = rx_stall = True
                    else:
                        push_drop = push_full
                        isr_n, isr_cnt_n = 0, 0
            else:  # PULL
                if not (iff and self.osr_cnt < pull_thr):
                    if tx_empty:
                        if blk:
                            stall = tx_stall = True
                        else:
                            osr_n, osr_cnt_n = self.x, 0
                    else:
                        pull_req = True
                        osr_n, osr_cnt_n = tx_head, 0
        elif op == isa.OP_MOV:
            wb_en, wb_val = True, movv
        elif op == isa.OP_IRQ:
            if ins >> 19 & 1:
                irq_clr = irq_one
            elif not (ins >> 18 & 1):
                irq_set = irq_one
            elif not self.irq_waiting:
                irq_set = irq_one
                stall = irq_waiting_n = True
            elif irq_bit:
                stall = irq_waiting_n = True
        elif op == isa.OP_SET:
            wb_en, wb_set, wb_val = True, True, imm16
        elif op in (isa.OP_ALU, isa.OP_ALUI):
            wb_en = True
            wb_dst = isa.DST["y"] if ins >> 19 & 1 else isa.DST["x"]
            wb_val = alu_res

        if crc_feed:
            crc_n = crc_step(self.crc, self.poly, crc_bit, self.crc_reflect)

        if wb_en:
            if wb_dst == 0:
                main_pins = True
            elif wb_dst == 1:
                x_n = wb_val
            elif wb_dst == 2:
                y_n = wb_val
            elif wb_dst == 4:
                main_dirs = True
            elif wb_dst == 5:
                jump, jump_tgt = True, wb_val & 63
            elif wb_dst == 6:
                isr_n, isr_cnt_n = wb_val, wb_cnt
            elif wb_dst == 7:
                if op != isa.OP_OUT:
                    osr_n, osr_cnt_n = wb_val, 0
            elif wb_dst == 8:
                exec_req, exec_val = True, wb_val
            elif wb_dst == 9:
                crc_n = wb_val
            elif wb_dst == 10:
                poly_n = wb_val

        # Pins.
        main_base = self.set_base if wb_set else self.out_base
        main_count = self.set_count if wb_set else self.out_count
        main_vrot = rotl(wb_val, main_base)
        main_mrot = rotl(lomask(main_count), main_base)
        side_vrot = rotl(side_data, self.side_base)
        side_mrot = rotl(lomask(sbits), self.side_base)
        side_go = exec_cycle and side_active
        sp_mask = side_mrot if side_go and not self.side_pindirs else 0
        sdir_mask = side_mrot if side_go and self.side_pindirs else 0
        mp_mask = main_mrot if exec_cycle and not stall and main_pins else 0
        md_mask = main_mrot if exec_cycle and not stall and main_dirs else 0
        o.pin_mask = sp_mask | mp_mask
        o.pin_val = (sp_mask & side_vrot) | (~sp_mask & M32 & main_vrot)
        o.dir_mask = sdir_mask | md_mask
        o.dir_val = (sdir_mask & side_vrot) | (~sdir_mask & M32 & main_vrot)

        if exec_cycle:
            o.irq_set, o.irq_clr = irq_set, irq_clr
            o.tx_pop = pull_req and not tx_empty
            o.push_req = push_req
            o.push_drop = push_drop
            o.tx_stall, o.rx_stall = tx_stall, rx_stall
        o.push_data = push_data

        pc_inc = self.wrap_bot if self.pc == self.wrap_top else (self.pc + 1) & 63
        self._next = {
            "tick": tick,
            "exec_cycle": exec_cycle,
            "stall": stall,
            "x": x_n,
            "y": y_n,
            "isr": isr_n,
            "osr": osr_n,
            "crc": crc_n,
            "poly": poly_n,
            "isr_cnt": isr_cnt_n,
            "osr_cnt": osr_cnt_n,
            "wait_active": wait_active_n,
            "wait_ref": wait_ref_n,
            "irq_waiting": irq_waiting_n,
            "pc": jump_tgt if jump else (self.pc if self.exec_pending else pc_inc),
            "delay": 0 if exec_req else delay_val,
            "exec_req": exec_req,
            "exec_val": exec_val,
        }
        return o

    def commit(
        self, enable: bool, restart: bool, div_restart: bool, force: int | None, cfg: tuple[int, int] | None
    ) -> None:
        nx = self._next
        # Clock divider.
        if div_restart:
            self.div_cnt = self.div_acc = 0
        elif enable:
            if self.div_cnt == 0:
                fs = self.div_acc + self.div_frac
                int_eff = self.div_int if self.div_int else 1
                self.div_cnt = (int_eff - 1 + (fs >> 8)) & 0xFFFF
                self.div_acc = fs & 0xFF
            else:
                self.div_cnt -= 1
        # State.
        force_tick = self.force_tick
        self.force_tick = False
        if restart:
            self.isr = self.osr = 0
            self.isr_cnt, self.osr_cnt = 0, 32
            self.delay_cnt = 0
            self.exec_pending = self.wait_active = self.irq_waiting = self.last_stall = False
        elif nx["exec_cycle"]:
            self.x, self.y, self.isr, self.osr = int(nx["x"]), int(nx["y"]), int(nx["isr"]), int(nx["osr"])
            self.crc, self.poly = int(nx["crc"]), int(nx["poly"])
            self.isr_cnt, self.osr_cnt = int(nx["isr_cnt"]), int(nx["osr_cnt"])
            self.wait_active = bool(nx["wait_active"])
            self.wait_ref = bool(nx["wait_ref"])
            self.irq_waiting = bool(nx["irq_waiting"])
            self.last_stall = bool(nx["stall"])
            if not nx["stall"]:
                self.pc = int(nx["pc"])
                self.delay_cnt = int(nx["delay"])
                self.exec_pending = bool(nx["exec_req"])
                if nx["exec_req"]:
                    self.exec_reg = int(nx["exec_val"])
        elif nx["tick"]:
            self.delay_cnt -= 1
        del force_tick
        if force is not None:
            self.exec_reg = force
            self.exec_pending = True
            self.force_tick = True
            self.wait_active = False
            self.irq_waiting = False
        if cfg is not None:
            self.cfg_write(*cfg)


class HostPort:
    """SPI target state machine (src/mimic_host.v)."""

    PH_CMD, PH_ADDR, PH_DUMMY, PH_WDATA, PH_RDATA = range(5)

    def __init__(self) -> None:
        self.sck_q = 0
        self.phase = self.PH_CMD
        self.bitcnt = 0
        self.sh_in = 0
        self.sh_out = 0
        self.cmd_w = 0
        self.cmd_inc = 0
        self.load_pend = False
        self.bus_addr = 0
        self.miso = 0

    def strobes(self, sck: int, csn: int, mosi: int) -> tuple[bool, int, bool]:
        """(bus_we, bus_wdata, bus_rd_done) this cycle."""
        sck_rise = bool(sck and not self.sck_q and not csn)
        last32 = self.bitcnt == 31
        wdata = ((self.sh_in << 1) | mosi) & M32
        we = sck_rise and self.phase == self.PH_WDATA and last32
        rd = sck_rise and self.phase == self.PH_RDATA and last32
        return we, wdata, rd

    def commit(self, sck: int, csn: int, mosi: int, rdata: int) -> None:
        sck_rise = bool(sck and not self.sck_q and not csn)
        self.sck_q = sck
        if csn:
            self.phase = self.PH_CMD
            self.bitcnt = 0
            self.load_pend = False
            self.miso = 0
            return
        sh_out_old = self.sh_out
        if self.load_pend:
            self.sh_out = rdata
            self.miso = rdata >> 31
            self.load_pend = False
        if not sck_rise:
            return
        sh_in_old = self.sh_in
        self.sh_in = ((sh_in_old << 1) | mosi) & 0x7FFF_FFFF
        last8 = self.bitcnt == 7
        last32 = self.bitcnt == 31
        self.bitcnt = (self.bitcnt + 1) & 31
        if self.phase == self.PH_CMD:
            if last8:
                self.cmd_w = (sh_in_old >> 6) & 1
                self.cmd_inc = (sh_in_old >> 5) & 1
                self.phase = self.PH_ADDR
                self.bitcnt = 0
        elif self.phase == self.PH_ADDR:
            if last8:
                self.bus_addr = ((sh_in_old << 1) | mosi) & 0xFF
                self.phase = self.PH_WDATA if self.cmd_w else self.PH_DUMMY
                self.bitcnt = 0
        elif self.phase == self.PH_DUMMY:
            if last8:
                self.phase = self.PH_RDATA
                self.bitcnt = 0
                self.load_pend = True
        elif self.phase == self.PH_WDATA:
            if last32:
                self.bitcnt = 0
                if self.cmd_inc:
                    self.bus_addr = (self.bus_addr + 1) & 0xFF
        elif self.phase == self.PH_RDATA:
            if last32:
                self.bitcnt = 0
                self.load_pend = True
                if self.cmd_inc:
                    self.bus_addr = (self.bus_addr + 1) & 0xFF
            else:
                self.sh_out = (sh_out_old << 1) & M32
                self.miso = (sh_out_old >> 30) & 1


class Mimic:
    """The whole chip. `clock()` is one rising edge of clk."""

    def __init__(self, imem_latch: bool = True) -> None:
        # The latch memory makes a host write visible one cycle later than flip-flops would.
        self.imem_delay = 2 if imem_latch else 1
        self.reset()

    def reset(self) -> None:
        self.imem = [0] * isa.IMEM_WORDS
        self.imem_pipe: tuple[int, int] | None = None
        self.sms = [SM(i) for i in range(isa.NUM_SM)]
        self.fifos = [Fifo() for _ in range(isa.NUM_SM)]
        self.host = HostPort()
        self.ui_s1 = self.ui_s2 = self.uio_s1 = self.uio_s2 = 0
        self.sm_en = 0
        self.p_restart = self.p_divrst = self.p_step = self.p_txclr = self.p_rxclr = 0
        self.irq = 0
        self.od_en = 0
        self.fdebug = 0
        self.pin_out = 0
        self.pin_oe = 0
        self.cycle = 0

    # ---- pins -------------------------------------------------------------
    def pins_in(self) -> int:
        return (self.pin_out & 0xFF00_0000) | (self.ui_s2 << 16) | (self.pin_out & 0x0000_FF00) | self.uio_s2

    def outputs(self) -> tuple[int, int, int]:
        uo = (self.host.miso << 7) | ((self.pin_out >> 8) & 0x7F)
        uio_out = self.pin_out & 0xFF & ~self.od_en
        uio_oe = ((~self.pin_out & 0xFF) & self.od_en) | (self.pin_oe & ~self.od_en & 0xFF)
        return uo, uio_out, uio_oe

    # ---- register reads (combinational, as bus_rdata) ----------------------
    def _views(self) -> list[dict[str, int | bool]]:
        return [f.view(s.fjoin_tx, s.fjoin_rx) for f, s in zip(self.fifos, self.sms, strict=True)]

    def bus_read(self, addr: int) -> int:
        views = self._views()
        if (addr >> 4) == 0x4:
            reg = addr & 15
            if reg == 0:
                return isa.CHIP_ID
            if reg == 1:
                return self.sm_en
            if reg == 2:
                v = 0
                for i, fv in enumerate(views):
                    v |= (int(fv["tx_level"]) | (int(fv["rx_level"]) << 4)) << (8 * i)
                return v
            if reg == 3:
                return self.fdebug
            if reg == 4:
                return self.irq
            if reg == 6:
                return self.od_en
            if reg == 7:
                return self.pins_in()
            if reg == 8:
                return self.pin_out
            if reg == 9:
                return self.pin_oe
            return 0
        if (addr >> 6) == 0b10:
            n, reg = (addr >> 4) & 3, addr & 15
            if reg == isa.SM_RXF:
                return 0 if views[n]["rx_empty"] else int(views[n]["rx_head"])
            return self.sms[n].cfg_read(reg, self.imem)
        return 0

    # ---- one clock edge -----------------------------------------------------
    def clock(self, ui_in: int, uio_in: int) -> tuple[int, int, int]:
        sck, csn, mosi = (self.ui_s2 >> 6) & 1, (self.ui_s2 >> 5) & 1, (self.ui_s2 >> 7) & 1
        bus_we, bus_wdata, bus_rd_done = self.host.strobes(sck, csn, mosi)
        addr = self.host.bus_addr
        a_imem = (addr >> 6) == 0
        a_glob = (addr >> 4) == 0x4
        a_sm = (addr >> 6) == 0b10
        a_smn, a_reg = (addr >> 4) & 3, addr & 15
        g_we = bus_we and a_glob

        pins_in = self.pins_in()
        views = self._views()
        host_tx_wr = [bus_we and a_sm and a_smn == i and a_reg == isa.SM_TXF for i in range(4)]

        # Push requests do not depend on push_full; evaluate once to get them, then for real.
        pre = [
            sm.evaluate(
                self.imem, pins_in, self.irq, views[i], False, bool(self.sm_en >> i & 1), bool(self.p_step >> i & 1)
            )
            for i, sm in enumerate(self.sms)
        ]
        push_full = []
        for i, sm in enumerate(self.sms):
            if sm.route_en:
                j = (i + 1) % 4
                push_full.append(bool(views[j]["tx_full"]) or host_tx_wr[j])
            else:
                push_full.append(bool(views[i]["rx_full"]))
        outs = [
            sm.evaluate(
                self.imem,
                pins_in,
                self.irq,
                views[i],
                push_full[i],
                bool(self.sm_en >> i & 1),
                bool(self.p_step >> i & 1),
            )
            for i, sm in enumerate(self.sms)
        ]
        for a, b in zip(pre, outs, strict=True):
            assert a.push_req == b.push_req and a.push_data == b.push_data

        # FIFOs.
        rx_rd = [bus_rd_done and a_sm and a_smn == i and a_reg == isa.SM_RXF for i in range(4)]
        tx_wr, tx_wdata = [], []
        for i in range(4):
            p = (i + 3) % 4
            routed = self.sms[p].route_en and outs[p].push_req and not push_full[p]
            tx_wr.append(host_tx_wr[i] or routed)
            tx_wdata.append(bus_wdata if host_tx_wr[i] else outs[p].push_data)
        rx_wr = [outs[i].push_req and not self.sms[i].route_en and not views[i]["rx_full"] for i in range(4)]

        # FDEBUG.
        host_tx_drop = [host_tx_wr[i] and bool(views[i]["tx_full"]) for i in range(4)]
        host_rx_under = [rx_rd[i] and bool(views[i]["rx_empty"]) for i in range(4)]

        def bits(lst: list[bool]) -> int:
            return sum(int(b) << k for k, b in enumerate(lst))

        fdebug_set = (
            bits([o.push_drop for o in outs])
            | (bits(host_tx_drop) << 4)
            | (bits(host_rx_under) << 8)
            | (bits([o.tx_stall for o in outs]) << 12)
            | (bits([o.rx_stall for o in outs]) << 16)
        )

        # Pins: highest SM wins.
        pin_out_n, pin_oe_n = self.pin_out, self.pin_oe
        for o in outs:
            pin_out_n = (pin_out_n & ~o.pin_mask & M32) | (o.pin_val & o.pin_mask)
            dm = o.dir_mask & 0xFF
            pin_oe_n = (pin_oe_n & ~dm & 0xFF) | (o.dir_val & dm)

        irq_set_all = 0
        irq_clr_all = 0
        for o in outs:
            irq_set_all |= o.irq_set
            irq_clr_all |= o.irq_clr
        if g_we and a_reg == 5:
            irq_set_all |= bus_wdata & 0xFF
        if g_we and a_reg == 4:
            irq_clr_all |= bus_wdata & 0xFF

        rdata = self.bus_read(addr)
        imem_write = (addr & 63, bus_wdata) if (bus_we and a_imem) else None

        # ---- commit ----
        old_en, old_restart, old_divrst = self.sm_en, self.p_restart, self.p_divrst
        old_txclr, old_rxclr = self.p_txclr, self.p_rxclr
        joins = [(sm.fjoin_tx, sm.fjoin_rx) for sm in self.sms]  # before any SHIFTCTRL write lands
        for i, sm in enumerate(self.sms):
            cfg_we = bus_we and a_sm and a_smn == i
            force = bus_wdata if (cfg_we and a_reg == isa.SM_INSTR) else None
            cfg = (a_reg, bus_wdata) if cfg_we else None
            sm.commit(bool(old_en >> i & 1), bool(old_restart >> i & 1), bool(old_divrst >> i & 1), force, cfg)
        for i, f in enumerate(self.fifos):
            f.commit(
                joins[i][0],
                joins[i][1],
                bool(old_txclr >> i & 1),
                bool(old_rxclr >> i & 1),
                tx_wr[i],
                tx_wdata[i],
                outs[i].tx_pop,
                rx_wr[i],
                outs[i].push_data,
                rx_rd[i],
            )
        self.p_restart = self.p_divrst = self.p_step = self.p_txclr = self.p_rxclr = 0
        if g_we and a_reg == 1:
            self.sm_en = bus_wdata & 15
            self.p_restart = (bus_wdata >> 4) & 15
            self.p_divrst = (bus_wdata >> 8) & 15
            self.p_step = (bus_wdata >> 12) & 15
            self.p_txclr = (bus_wdata >> 16) & 15
            self.p_rxclr = (bus_wdata >> 20) & 15
        if g_we and a_reg == 6:
            self.od_en = bus_wdata & 0xFF
        self.pin_out, self.pin_oe = pin_out_n, pin_oe_n
        self.irq = (self.irq & ~irq_clr_all & 0xFF) | irq_set_all
        fd_clr = (bus_wdata & 0xFFFFF) if (g_we and a_reg == 3) else 0
        self.fdebug = (self.fdebug & ~fd_clr & 0xFFFFF) | fdebug_set

        # A host write to the instruction memory is visible after this edge (flip-flops) or
        # after the next one (latches: the word's gate opens in the cycle after next).
        if self.imem_delay == 1:
            landed = imem_write
        else:
            landed, self.imem_pipe = self.imem_pipe, imem_write
        if landed is not None:
            self.imem[landed[0]] = landed[1]

        self.host.commit(sck, csn, mosi, rdata)
        self.ui_s2, self.ui_s1 = self.ui_s1, ui_in & 0xFF
        self.uio_s2, self.uio_s1 = self.uio_s1, uio_in & 0xFF
        self.cycle += 1
        return self.outputs()
