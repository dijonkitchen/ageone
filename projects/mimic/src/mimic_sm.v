/*
 * Mimic state machine: one of four programmable bit-banging engines.
 *
 * Every instruction takes one tick unless it stalls (WAIT, a full or empty FIFO,
 * IRQ WAIT), then the SM idles for the instruction's delay. Side-set pins are
 * written on every tick an instruction issues, stalled or not.
 *
 * See docs/isa.md for the instruction set this module implements and
 * sw/mimic/model.py for the Python golden model it is checked against.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module mimic_sm #(
    parameter [1:0] SM_ID = 2'd0
) (
    input  wire        clk,
    input  wire        rst_n,

    // Control from the host (CTRL register); restart, div_restart, step are one-cycle pulses.
    input  wire        enable,
    input  wire        restart,
    input  wire        div_restart,
    input  wire        step,

    // Configuration and debug registers of this SM (16 words, see docs/host.md).
    input  wire        cfg_we,
    input  wire [3:0]  cfg_addr,
    input  wire [31:0] cfg_wdata,
    output reg  [31:0] cfg_rdata,

    // Shared instruction memory read port.
    output wire [5:0]  imem_addr,
    input  wire [31:0] imem_data,

    // GPIO space: 0-7 uio, 8-15 uo, 16-23 ui, 24-31 internal.
    input  wire [31:0] pins_in,
    output wire [31:0] pin_mask,   // which pin output levels this SM writes this cycle
    output wire [31:0] pin_val,
    output wire [31:0] dir_mask,   // which pin directions this SM writes this cycle
    output wire [31:0] dir_val,

    // Shared IRQ flags.
    input  wire [7:0]  irq_in,
    output wire [7:0]  irq_set,
    output wire [7:0]  irq_clr,

    // TX FIFO (host or another SM to this SM).
    input  wire        tx_empty,
    input  wire [31:0] tx_head,
    input  wire [3:0]  tx_level,
    output wire        tx_pop,

    // Push path: to this SM's RX FIFO, or routed to another SM's TX FIFO.
    input  wire        push_full,  // destination full, or lost arbitration this cycle
    input  wire [3:0]  rx_level,
    output wire        push_req,
    output wire [31:0] push_data,
    output wire        push_drop,  // non-blocking push found the destination full

    // Debug events (FDEBUG): stalled on an empty TX FIFO or a full push destination.
    output wire        tx_stall,
    output wire        rx_stall,

    // Configuration the top level needs.
    output wire        fjoin_tx,
    output wire        fjoin_rx,
    output wire        route_en  // pushes go to the next SM's TX FIFO
);

  // ---------------------------------------------------------------------------
  // Opcodes, sources and destinations
  // ---------------------------------------------------------------------------
  localparam [3:0] OP_JMP = 4'h0, OP_WAIT = 4'h1, OP_IN = 4'h2, OP_OUT = 4'h3,
                   OP_PP  = 4'h4, OP_MOV  = 4'h5, OP_IRQ = 4'h6, OP_SET = 4'h7,
                   OP_ALU = 4'h8, OP_ALUI = 4'h9;

  localparam [3:0] SRC_PINS = 4'd0, SRC_X = 4'd1, SRC_Y = 4'd2, SRC_STATUS = 4'd4,
                   SRC_ISR  = 4'd5, SRC_OSR = 4'd6, SRC_CRC = 4'd7, SRC_IRQ = 4'd8;

  localparam [3:0] DST_PINS = 4'd0, DST_X = 4'd1, DST_Y = 4'd2, DST_PINDIRS = 4'd4,
                   DST_PC   = 4'd5, DST_ISR = 4'd6, DST_OSR = 4'd7, DST_EXEC = 4'd8,
                   DST_CRC  = 4'd9, DST_POLY = 4'd10;

  localparam [2:0] ALU_ADD = 3'd0, ALU_SUB = 3'd1, ALU_AND = 3'd2, ALU_OR = 3'd3,
                   ALU_XOR = 3'd4, ALU_SHL = 3'd5, ALU_SHR = 3'd6, ALU_ROL = 3'd7;

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  // Rotate left by 0-31 as a five-level mux tree.
  function [31:0] rotl;
    input [31:0] v;
    input [4:0] s;
    reg [31:0] t;
    begin
      t = v;
      if (s[0]) t = {t[30:0], t[31]};
      if (s[1]) t = {t[29:0], t[31:30]};
      if (s[2]) t = {t[27:0], t[31:28]};
      if (s[3]) t = {t[23:0], t[31:24]};
      if (s[4]) t = {t[15:0], t[31:16]};
      rotl = t;
    end
  endfunction

  // Low k bits set, k in 0..32.
  function [31:0] lomask;
    input [5:0] k;
    integer i;
    begin
      for (i = 0; i < 32; i = i + 1) lomask[i] = (i < k);
    end
  endfunction

  function [31:0] bitrev;
    input [31:0] v;
    integer i;
    begin
      for (i = 0; i < 32; i = i + 1) bitrev[i] = v[31-i];
    end
  endfunction

  // ---------------------------------------------------------------------------
  // Configuration registers
  // ---------------------------------------------------------------------------
  reg [15:0] div_int;
  reg [7:0]  div_frac;
  // EXECCTRL
  reg [5:0]  wrap_bot, wrap_top;
  reg [4:0]  side_base;
  reg [3:0]  side_count;
  reg        side_en, side_pindirs, status_sel;
  reg [3:0]  status_n;
  // SHIFTCTRL
  reg        in_right, out_right, autopush, autopull;
  reg [4:0]  push_thr, pull_thr;
  reg        fjoin_tx_r, fjoin_rx_r, route_en_r;
  // PINCTRL
  reg [4:0]  out_base;
  reg [5:0]  out_count;
  reg [4:0]  set_base;
  reg [4:0]  set_count;
  reg [4:0]  in_base;
  // CRCCFG
  reg        crc_reflect, crc_feed_out, crc_feed_in;

  assign fjoin_tx = fjoin_tx_r;
  assign fjoin_rx = fjoin_rx_r;
  assign route_en = route_en_r;


  // ---------------------------------------------------------------------------
  // Architectural state
  // ---------------------------------------------------------------------------
  reg [5:0]  pc;
  reg [31:0] x, y, isr, osr, crc, poly, exec_reg;
  reg [5:0]  isr_cnt, osr_cnt;
  reg [7:0]  delay_cnt;
  reg        exec_pending;
  reg        wait_active, wait_ref, irq_waiting;
  reg        force_tick;
  reg        last_stall;
  reg [15:0] div_cnt;
  reg [7:0]  div_acc;

  // ---------------------------------------------------------------------------
  // Clock divider: a tick every INT + FRAC/256 cycles on average.
  // ---------------------------------------------------------------------------
  wire        div_pulse = (div_cnt == 16'd0);
  wire [8:0]  frac_sum  = {1'b0, div_acc} + {1'b0, div_frac};
  wire [15:0] int_eff   = (div_int == 16'd0) ? 16'd1 : div_int;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      div_cnt <= 16'd0;
      div_acc <= 8'd0;
    end else if (div_restart) begin
      div_cnt <= 16'd0;
      div_acc <= 8'd0;
    end else if (enable) begin
      if (div_pulse) begin
        div_cnt <= int_eff - 16'd1 + {15'd0, frac_sum[8]};
        div_acc <= frac_sum[7:0];
      end else begin
        div_cnt <= div_cnt - 16'd1;
      end
    end
  end

  wire tick       = (enable & div_pulse) | step | force_tick;
  wire in_delay   = (delay_cnt != 8'd0) & ~force_tick;
  wire exec_cycle = tick & ~in_delay;

  // ---------------------------------------------------------------------------
  // Fetch and decode
  // ---------------------------------------------------------------------------
  assign imem_addr = pc;
  wire [31:0] ins = exec_pending ? exec_reg : imem_data;

  wire [3:0]  op     = ins[31:28];
  wire [7:0]  sd     = ins[27:20];
  wire [3:0]  dst    = ins[19:16];
  wire [3:0]  srcsel = ins[3:0];
  wire [4:0]  cnt5   = ins[8:4];
  wire [5:0]  n      = (cnt5 == 5'd0) ? 6'd32 : {1'b0, cnt5};
  wire [15:0] imm16  = ins[15:0];

  // Side-set and delay share the 8-bit SD field: side-set takes the top side_count bits
  // (the topmost is an enable when side_en), delay the rest.
  wire [3:0] side_cnt_eff = (side_count > 4'd8) ? 4'd8 : side_count;
  wire [3:0] sbits        = (side_cnt_eff == 4'd0) ? 4'd0 : side_cnt_eff - {3'd0, side_en};
  wire [7:0] sd_top       = sd >> (4'd8 - side_cnt_eff);
  wire [7:0] side_data    = sd_top & ~(8'hff << sbits);
  wire [7:0] delay_val    = sd & ~(8'hff << (4'd8 - side_cnt_eff));
  wire       side_active  = (sbits != 4'd0) & (~side_en | sd[7]);

  wire [5:0] push_thr_eff = (push_thr == 5'd0) ? 6'd32 : {1'b0, push_thr};
  wire [5:0] pull_thr_eff = (pull_thr == 5'd0) ? 6'd32 : {1'b0, pull_thr};

  // Pins relative to IN_BASE: bit 0 is GPIO[in_base].
  wire [31:0] pins_rel = rotl(pins_in, ~in_base + 5'd1);

  // The one pin a JMP or WAIT tests: [14] absolute, [13:9] index.
  wire [4:0]  pin_idx = ins[14] ? ins[13:9] : (in_base + ins[13:9]);
  wire        sel_pin = pins_in[pin_idx];

  // IRQ index for WAIT, IRQ and JMP: [11:9], with [14] REL adding the SM number to the low two bits.
  wire [2:0]  irq_idx = ins[14] ? {ins[11], ins[10:9] + SM_ID} : ins[11:9];
  wire        irq_bit = irq_in[irq_idx];
  wire [7:0]  irq_one = 8'd1 << irq_idx;

  wire [3:0]  status_lvl = status_sel ? rx_level : tx_level;
  wire [31:0] status_val = (status_lvl < status_n) ? 32'hffffffff : 32'd0;

  reg [31:0] srcv;
  always @(*) begin
    case (srcsel)
      SRC_PINS:   srcv = pins_rel;
      SRC_X:      srcv = x;
      SRC_Y:      srcv = y;
      SRC_STATUS: srcv = status_val;
      SRC_ISR:    srcv = isr;
      SRC_OSR:    srcv = osr;
      SRC_CRC:    srcv = crc;
      SRC_IRQ:    srcv = {24'd0, irq_in};
      default:    srcv = 32'd0;
    endcase
  end

  reg [31:0] movv;
  always @(*) begin
    case (ins[15:14])
      2'd0: movv = srcv;
      2'd1: movv = ~srcv;
      2'd2: movv = bitrev(srcv);
      default: movv = {srcv[7:0], srcv[15:8], srcv[23:16], srcv[31:24]};
    endcase
  end

  // ---------------------------------------------------------------------------
  // Shared datapath: one adder and one rotator, used by whichever instruction issues.
  // ---------------------------------------------------------------------------
  wire [4:0]  cond   = ins[19:15];
  wire [2:0]  aluop  = ins[18:16];
  wire        is_alu = (op == OP_ALU) | (op == OP_ALUI);
  wire [31:0] alu_a  = (is_alu & ins[19]) | ((op == OP_JMP) & (cond == 5'd4)) ? y : x;
  wire [31:0] alu_b  = (op == OP_ALUI) ? {16'd0, imm16} : srcv;
  wire [31:0] add_b  = is_alu ? alu_b : (((op == OP_JMP) & (cond == 5'd7)) ? y : 32'd1);
  wire        add_sub = ~(is_alu & (aluop == ALU_ADD));
  wire [32:0] sum    = {1'b0, alu_a} + {1'b0, add_sub ? ~add_b : add_b} + {32'd0, add_sub};
  wire        x_lt_y = ~sum[32];  // borrow out of x - y

  wire        do_autopull = autopull & (osr_cnt >= pull_thr_eff);
  wire [31:0] osr_src     = do_autopull ? tx_head : osr;

  // Shift amount for the masks: IN/OUT use their count, ALU shifts use B[4:0].
  wire [5:0]  sh_n   = is_alu ? {1'b0, alu_b[4:0]} : n;
  wire [31:0] m_lo   = lomask(sh_n);
  wire [31:0] m_hi   = lomask(6'd32 - sh_n);  // low 32-n bits

  wire [31:0] in_merge = (isr & ~m_lo) | (srcv & m_lo);
  reg  [31:0] rot_in;
  reg  [4:0]  rot_amt;
  always @(*) begin
    rot_in  = x;
    rot_amt = sh_n[4:0];
    case (op)
      OP_IN:  begin rot_in = in_right ? in_merge : isr; rot_amt = in_right ? (5'd0 - n[4:0]) : n[4:0]; end
      OP_OUT: begin rot_in = osr_src; rot_amt = out_right ? (5'd0 - n[4:0]) : n[4:0]; end
      default: begin
        rot_in  = alu_a;
        rot_amt = (aluop == ALU_SHR) ? (5'd0 - alu_b[4:0]) : alu_b[4:0];
      end
    endcase
  end
  wire [31:0] rot_out = rotl(rot_in, rot_amt);

  wire [31:0] isr_new  = in_right ? rot_out : ((rot_out & ~m_lo) | (srcv & m_lo));
  wire [6:0]  isr_sum  = {1'b0, isr_cnt} + {1'b0, n};
  wire [5:0]  isr_cntn = (isr_sum > 7'd32) ? 6'd32 : isr_sum[5:0];
  wire [31:0] out_data = out_right ? (osr_src & m_lo) : (rot_out & m_lo);
  wire [31:0] osr_new  = out_right ? (rot_out & m_hi) : (rot_out & ~m_lo);
  wire [6:0]  osr_sum  = {1'b0, (do_autopull ? 6'd0 : osr_cnt)} + {1'b0, n};
  wire [5:0]  osr_cntn = (osr_sum > 7'd32) ? 6'd32 : osr_sum[5:0];

  reg [31:0] alu_res;
  always @(*) begin
    case (aluop)
      ALU_ADD, ALU_SUB: alu_res = sum[31:0];
      ALU_AND: alu_res = alu_a & alu_b;
      ALU_OR:  alu_res = alu_a | alu_b;
      ALU_XOR: alu_res = alu_a ^ alu_b;
      ALU_SHL: alu_res = rot_out & ~m_lo;
      ALU_SHR: alu_res = rot_out & m_hi;
      ALU_ROL: alu_res = rot_out;
      default: alu_res = rot_out;
    endcase
  end

  // CRC/LFSR step on one bit: left-aligned MSB-first, or right-aligned reflected.
  function [31:0] crc_step;
    input [31:0] c;
    input [31:0] p;
    input b;
    input refl;
    reg fb;
    begin
      fb = refl ? (c[0] ^ b) : (c[31] ^ b);
      crc_step = (refl ? {1'b0, c[31:1]} : {c[30:0], 1'b0}) ^ (fb ? p : 32'd0);
    end
  endfunction

  // ---------------------------------------------------------------------------
  // Execute
  // ---------------------------------------------------------------------------
  reg        stall, jump, wb_en, wb_set, exec_req, crc_feed, crc_bit;
  reg [5:0]  jump_tgt;
  reg [3:0]  wb_dst;
  reg [31:0] wb_val;
  reg [5:0]  wb_cnt;
  reg [31:0] x_n, y_n, isr_n, osr_n, crc_n, poly_n, exec_val;
  reg [5:0]  isr_cnt_n, osr_cnt_n;
  reg        push_req_c, push_drop_c, pull_req_c, tx_stall_c, rx_stall_c;
  reg [31:0] push_data_c;
  reg [7:0]  irq_set_c, irq_clr_c;
  reg        wait_active_n, wait_ref_n, irq_waiting_n;
  reg        main_pins, main_dirs;
  reg        met, ref_c, take;

  always @(*) begin
    stall = 1'b0;  jump = 1'b0;  jump_tgt = ins[5:0];
    wb_en = 1'b0;  wb_set = 1'b0;  wb_dst = dst;  wb_val = 32'd0;  wb_cnt = 6'd0;
    exec_req = 1'b0;  exec_val = 32'd0;
    crc_feed = 1'b0;  crc_bit = 1'b0;
    x_n = x;  y_n = y;  isr_n = isr;  osr_n = osr;  crc_n = crc;  poly_n = poly;
    isr_cnt_n = isr_cnt;  osr_cnt_n = osr_cnt;
    push_req_c = 1'b0;  push_drop_c = 1'b0;  push_data_c = isr;  pull_req_c = 1'b0;
    tx_stall_c = 1'b0;  rx_stall_c = 1'b0;
    irq_set_c = 8'd0;  irq_clr_c = 8'd0;
    wait_active_n = 1'b0;  wait_ref_n = wait_ref;  irq_waiting_n = 1'b0;
    main_pins = 1'b0;  main_dirs = 1'b0;
    met = 1'b0;  ref_c = 1'b0;  take = 1'b0;

    case (op)
      OP_JMP: begin
        case (cond)
          5'd0:  take = 1'b1;
          5'd1:  take = (x == 32'd0);
          5'd2:  begin take = (x != 32'd0); x_n = sum[31:0]; end
          5'd3:  take = (y == 32'd0);
          5'd4:  begin take = (y != 32'd0); y_n = sum[31:0]; end
          5'd5:  take = (x != y);
          5'd6:  take = (x == y);
          5'd7:  take = x_lt_y;
          5'd8:  take = sel_pin;
          5'd9:  take = ~sel_pin;
          5'd10: take = (osr_cnt < pull_thr_eff);
          5'd11: take = (osr_cnt >= pull_thr_eff);
          5'd12: take = ~tx_empty;
          5'd13: take = tx_empty;
          5'd14: take = x[0];
          5'd15: take = ~x[0];
          5'd16: take = irq_bit;
          5'd17: take = ~irq_bit;
          default: take = 1'b0;
        endcase
        jump = take;
      end

      OP_WAIT: begin
        case (ins[18:16])
          3'd0: met = (sel_pin == ins[19]);
          3'd1: begin  // edge to POL: needs a !POL sample during this wait first
            ref_c = wait_active ? (wait_ref | (sel_pin != ins[19])) : (sel_pin != ins[19]);
            met   = wait_active & wait_ref & (sel_pin == ins[19]);
          end
          3'd2: begin  // any change from the level at the first cycle
            ref_c = wait_active ? wait_ref : sel_pin;
            met   = wait_active & (sel_pin != wait_ref);
          end
          3'd3: begin
            met = (irq_bit == ins[19]);
            if (met & ins[19]) irq_clr_c = irq_one;
          end
          default: met = 1'b1;
        endcase
        if (!met && !(ins[15] && x == 32'd0)) begin
          stall = 1'b1;
          wait_active_n = 1'b1;
          wait_ref_n = ref_c;
          if (ins[15]) x_n = sum[31:0];
        end
      end

      OP_IN: begin
        if (autopush && isr_cntn >= push_thr_eff) begin
          push_req_c  = 1'b1;
          push_data_c = isr_new;
          if (push_full) begin
            stall = 1'b1;
            rx_stall_c = 1'b1;
          end else begin
            isr_n = 32'd0;
            isr_cnt_n = 6'd0;
          end
        end else begin
          isr_n = isr_new;
          isr_cnt_n = isr_cntn;
        end
        crc_feed = crc_feed_in & ~stall;
        crc_bit  = srcv[0];
      end

      OP_OUT: begin
        if (do_autopull && tx_empty) begin
          stall = 1'b1;
          tx_stall_c = 1'b1;
        end else begin
          pull_req_c = do_autopull;
          osr_n = osr_new;
          osr_cnt_n = osr_cntn;
          wb_en = 1'b1;
          wb_val = out_data;
          wb_cnt = n;
          crc_feed = crc_feed_out;
          crc_bit = out_data[0];
        end
      end

      OP_PP: begin
        if (!ins[19]) begin  // PUSH
          if (!(ins[18] && isr_cnt < push_thr_eff)) begin
            push_req_c = 1'b1;
            if (push_full && ins[17]) begin
              stall = 1'b1;
              rx_stall_c = 1'b1;
            end else begin
              push_drop_c = push_full;
              isr_n = 32'd0;
              isr_cnt_n = 6'd0;
            end
          end
        end else begin  // PULL
          if (!(ins[18] && osr_cnt < pull_thr_eff)) begin
            if (tx_empty) begin
              if (ins[17]) begin
                stall = 1'b1;
                tx_stall_c = 1'b1;
              end else begin
                osr_n = x;
                osr_cnt_n = 6'd0;
              end
            end else begin
              pull_req_c = 1'b1;
              osr_n = tx_head;
              osr_cnt_n = 6'd0;
            end
          end
        end
      end

      OP_MOV: begin
        wb_en = 1'b1;
        wb_val = movv;
      end

      OP_IRQ: begin
        if (ins[19]) begin
          irq_clr_c = irq_one;
        end else if (!ins[18]) begin
          irq_set_c = irq_one;
        end else if (!irq_waiting) begin
          irq_set_c = irq_one;
          stall = 1'b1;
          irq_waiting_n = 1'b1;
        end else if (irq_bit) begin
          stall = 1'b1;
          irq_waiting_n = 1'b1;
        end
      end

      OP_SET: begin
        wb_en = 1'b1;
        wb_set = 1'b1;
        wb_val = {16'd0, imm16};
      end

      OP_ALU, OP_ALUI: begin
        wb_en = 1'b1;
        wb_dst = ins[19] ? DST_Y : DST_X;
        wb_val = alu_res;
      end

      default: ;  // reserved opcodes are NOPs
    endcase

    if (crc_feed) crc_n = crc_step(crc, poly, crc_bit, crc_reflect);

    if (wb_en) begin
      case (wb_dst)
        DST_PINS:    main_pins = 1'b1;
        DST_X:       x_n = wb_val;
        DST_Y:       y_n = wb_val;
        DST_PINDIRS: main_dirs = 1'b1;
        DST_PC:      begin jump = 1'b1; jump_tgt = wb_val[5:0]; end
        DST_ISR:     begin isr_n = wb_val; isr_cnt_n = wb_cnt; end
        DST_OSR:     if (op != OP_OUT) begin osr_n = wb_val; osr_cnt_n = 6'd0; end
        DST_EXEC:    begin exec_req = 1'b1; exec_val = wb_val; end
        DST_CRC:     crc_n = wb_val;
        DST_POLY:    poly_n = wb_val;
        default: ;
      endcase
    end
  end

  // ---------------------------------------------------------------------------
  // Pin writes: side-set wins over OUT/MOV/SET on the same pin.
  // ---------------------------------------------------------------------------
  wire [4:0]  main_base  = wb_set ? set_base : out_base;
  wire [5:0]  main_count = wb_set ? {1'b0, set_count} : out_count;
  wire [31:0] main_vrot  = rotl(wb_val, main_base);
  wire [31:0] main_mrot  = rotl(lomask(main_count), main_base);
  wire [31:0] side_vrot  = rotl({24'd0, side_data}, side_base);
  wire [31:0] side_mrot  = rotl(lomask({2'd0, sbits}), side_base);

  wire        side_go  = exec_cycle & side_active;
  wire [31:0] sp_mask  = (side_go & ~side_pindirs) ? side_mrot : 32'd0;
  wire [31:0] sd_mask  = (side_go &  side_pindirs) ? side_mrot : 32'd0;
  wire [31:0] mp_mask  = (exec_cycle & ~stall & main_pins) ? main_mrot : 32'd0;
  wire [31:0] md_mask  = (exec_cycle & ~stall & main_dirs) ? main_mrot : 32'd0;

  assign pin_mask = sp_mask | mp_mask;
  assign pin_val  = (sp_mask & side_vrot) | (~sp_mask & main_vrot);
  assign dir_mask = sd_mask | md_mask;
  assign dir_val  = (sd_mask & side_vrot) | (~sd_mask & main_vrot);

  assign irq_set   = exec_cycle ? irq_set_c : 8'd0;
  assign irq_clr   = exec_cycle ? irq_clr_c : 8'd0;
  assign tx_pop    = exec_cycle & pull_req_c & ~tx_empty;
  assign push_req  = exec_cycle & push_req_c;
  assign push_data = push_data_c;
  assign push_drop = exec_cycle & push_drop_c;
  assign tx_stall  = exec_cycle & tx_stall_c;
  assign rx_stall  = exec_cycle & rx_stall_c;

  wire [5:0] pc_inc = (pc == wrap_top) ? wrap_bot : pc + 6'd1;

  // ---------------------------------------------------------------------------
  // State update
  // ---------------------------------------------------------------------------
  wire force_wr = cfg_we & (cfg_addr == 4'h7);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      pc <= 6'd0;
      x <= 32'd0; y <= 32'd0; isr <= 32'd0; osr <= 32'd0;
      crc <= 32'd0; poly <= 32'd0; exec_reg <= 32'd0;
      isr_cnt <= 6'd0; osr_cnt <= 6'd32;
      delay_cnt <= 8'd0;
      exec_pending <= 1'b0; wait_active <= 1'b0; wait_ref <= 1'b0; irq_waiting <= 1'b0;
      force_tick <= 1'b0; last_stall <= 1'b0;
    end else begin
      force_tick <= 1'b0;
      if (restart) begin
        isr <= 32'd0; osr <= 32'd0; isr_cnt <= 6'd0; osr_cnt <= 6'd32;
        delay_cnt <= 8'd0;
        exec_pending <= 1'b0; wait_active <= 1'b0; irq_waiting <= 1'b0; last_stall <= 1'b0;
      end else if (exec_cycle) begin
        x <= x_n; y <= y_n; isr <= isr_n; osr <= osr_n; crc <= crc_n; poly <= poly_n;
        isr_cnt <= isr_cnt_n; osr_cnt <= osr_cnt_n;
        wait_active <= wait_active_n; wait_ref <= wait_ref_n; irq_waiting <= irq_waiting_n;
        last_stall <= stall;
        if (!stall) begin
          pc <= jump ? jump_tgt : (exec_pending ? pc : pc_inc);
          delay_cnt <= exec_req ? 8'd0 : delay_val;
          exec_pending <= exec_req;
          if (exec_req) exec_reg <= exec_val;
        end
      end else if (tick) begin
        delay_cnt <= delay_cnt - 8'd1;
      end
      // A host INSTR write replaces any pending instruction and runs it on the next cycle.
      if (force_wr) begin
        exec_reg <= cfg_wdata;
        exec_pending <= 1'b1;
        force_tick <= 1'b1;
        wait_active <= 1'b0;
        irq_waiting <= 1'b0;
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Configuration writes and debug reads
  // ---------------------------------------------------------------------------
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      div_int <= 16'd1; div_frac <= 8'd0;
      wrap_bot <= 6'd0; wrap_top <= 6'd63;
      side_base <= 5'd0; side_count <= 4'd0; side_en <= 1'b0; side_pindirs <= 1'b0;
      status_sel <= 1'b0; status_n <= 4'd0;
      in_right <= 1'b1; out_right <= 1'b1; autopush <= 1'b0; autopull <= 1'b0;
      push_thr <= 5'd0; pull_thr <= 5'd0;
      fjoin_tx_r <= 1'b0; fjoin_rx_r <= 1'b0; route_en_r <= 1'b0;
      out_base <= 5'd0; out_count <= 6'd0; set_base <= 5'd0; set_count <= 5'd0; in_base <= 5'd0;
      crc_reflect <= 1'b0; crc_feed_out <= 1'b0; crc_feed_in <= 1'b0;
    end else if (cfg_we) begin
      case (cfg_addr)
        4'h2: begin div_int <= cfg_wdata[31:16]; div_frac <= cfg_wdata[15:8]; end
        4'h3: begin
          wrap_bot <= cfg_wdata[5:0];  wrap_top <= cfg_wdata[11:6];
          side_base <= cfg_wdata[16:12]; side_count <= cfg_wdata[20:17];
          side_en <= cfg_wdata[21]; side_pindirs <= cfg_wdata[22];
          status_sel <= cfg_wdata[23]; status_n <= cfg_wdata[27:24];
        end
        4'h4: begin
          in_right <= cfg_wdata[0]; out_right <= cfg_wdata[1];
          autopush <= cfg_wdata[2]; autopull <= cfg_wdata[3];
          push_thr <= cfg_wdata[8:4]; pull_thr <= cfg_wdata[13:9];
          fjoin_tx_r <= cfg_wdata[16]; fjoin_rx_r <= cfg_wdata[17];
          route_en_r <= cfg_wdata[20];
        end
        4'h5: begin
          out_base <= cfg_wdata[4:0]; out_count <= cfg_wdata[10:5];
          set_base <= cfg_wdata[15:11]; set_count <= cfg_wdata[20:16];
          in_base <= cfg_wdata[25:21];
        end
        4'h6: begin
          crc_reflect <= cfg_wdata[0]; crc_feed_out <= cfg_wdata[1]; crc_feed_in <= cfg_wdata[2];
        end
        default: ;
      endcase
    end
  end

  wire [31:0] smstat = {4'd0, irq_waiting, wait_active, exec_pending, last_stall,
                        delay_cnt, 2'd0, osr_cnt, 2'd0, isr_cnt};

  // Debug reads; anything else (ISR, OSR, CRC, ...) is read by forcing a MOV into X.
  always @(*) begin
    case (cfg_addr)
      4'h7: cfg_rdata = ins;
      4'h8: cfg_rdata = {26'd0, pc};
      4'h9: cfg_rdata = x;
      4'hA: cfg_rdata = y;
      4'hF: cfg_rdata = smstat;
      default: cfg_rdata = 32'd0;
    endcase
  end

endmodule
