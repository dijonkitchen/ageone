/*
 * A state machine's TX and RX FIFOs, sharing 2*DEPTH words of storage.
 *
 * Normally each FIFO owns DEPTH words. JOIN_TX gives all 2*DEPTH words to TX (RX then has
 * no room), JOIN_RX gives them to RX. Changing either join bit empties both FIFOs.
 *
 * TX: written by the host or by a routed SM push, read by this SM (PULL, autopull).
 * RX: written by this SM (PUSH, autopush), read by the host.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module mimic_fifo #(
    parameter DEPTH = 4  // words per direction; must be a power of two
) (
    input  wire        clk,
    input  wire        rst_n,

    input  wire        join_tx,
    input  wire        join_rx,
    input  wire        clr_tx,
    input  wire        clr_rx,

    input  wire        tx_wr,
    input  wire [31:0] tx_wdata,
    input  wire        tx_rd,
    output wire [31:0] tx_head,
    output wire        tx_empty,
    output wire        tx_full,
    output wire [3:0]  tx_level,

    input  wire        rx_wr,
    input  wire [31:0] rx_wdata,
    input  wire        rx_rd,
    output wire [31:0] rx_head,
    output wire        rx_empty,
    output wire        rx_full,
    output wire [3:0]  rx_level
);

  localparam AW = $clog2(2 * DEPTH);  // index into all storage
  localparam [AW-1:0] RX_BASE = DEPTH;  // RX region starts here unless RX is joined

  reg [31:0] mem [0:2*DEPTH-1];

  reg [AW-1:0] tx_rp, tx_wp, rx_rp, rx_wp;  // pointers relative to each FIFO's region
  reg [AW:0]   tx_cnt, rx_cnt;
  reg          join_tx_q, join_rx_q;

  wire [AW:0] tx_cap = join_tx ? (2 * DEPTH) : (join_rx ? 0 : DEPTH);
  wire [AW:0] rx_cap = join_rx ? (2 * DEPTH) : (join_tx ? 0 : DEPTH);
  wire [AW-1:0] rx_base = join_rx ? {AW{1'b0}} : RX_BASE;

  assign tx_empty = (tx_cnt == 0);
  assign rx_empty = (rx_cnt == 0);
  assign tx_full  = (tx_cnt >= tx_cap);
  assign rx_full  = (rx_cnt >= rx_cap);
  /* verilator lint_off WIDTHEXPAND */
  assign tx_level = tx_cnt;  // zero-extended to 4 bits
  assign rx_level = rx_cnt;
  /* verilator lint_on WIDTHEXPAND */

  wire do_tx_wr = tx_wr & ~tx_full;
  wire do_tx_rd = tx_rd & ~tx_empty;
  wire do_rx_wr = rx_wr & ~rx_full;
  wire do_rx_rd = rx_rd & ~rx_empty;

  // Pointer increment that wraps at the FIFO's capacity (DEPTH or 2*DEPTH).
  function [AW-1:0] inc;
    input [AW-1:0] p;
    input joined;
    begin
      if (joined) inc = p + 1'b1;
      else inc = {1'b0, p[AW-2:0] + 1'b1};
    end
  endfunction

  wire [AW-1:0] tx_widx = tx_wp;
  wire [AW-1:0] rx_widx = rx_base + rx_wp;

  assign tx_head = mem[tx_rp];
  assign rx_head = mem[rx_base + rx_rp];

  integer i;
  always @(posedge clk) begin
    for (i = 0; i < 2 * DEPTH; i = i + 1) begin
      if (do_tx_wr && tx_widx == i[AW-1:0]) mem[i] <= tx_wdata;
      else if (do_rx_wr && rx_widx == i[AW-1:0]) mem[i] <= rx_wdata;
    end
  end

  wire rejoin = (join_tx != join_tx_q) | (join_rx != join_rx_q);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      tx_rp <= 0; tx_wp <= 0; tx_cnt <= 0;
      rx_rp <= 0; rx_wp <= 0; rx_cnt <= 0;
      join_tx_q <= 1'b0; join_rx_q <= 1'b0;
    end else begin
      join_tx_q <= join_tx;
      join_rx_q <= join_rx;
      if (clr_tx | rejoin) begin
        tx_rp <= 0; tx_wp <= 0; tx_cnt <= 0;
      end else begin
        if (do_tx_wr) tx_wp <= inc(tx_wp, join_tx);
        if (do_tx_rd) tx_rp <= inc(tx_rp, join_tx);
        tx_cnt <= tx_cnt + {{AW{1'b0}}, do_tx_wr} - {{AW{1'b0}}, do_tx_rd};
      end
      if (clr_rx | rejoin) begin
        rx_rp <= 0; rx_wp <= 0; rx_cnt <= 0;
      end else begin
        if (do_rx_wr) rx_wp <= inc(rx_wp, join_rx);
        if (do_rx_rd) rx_rp <= inc(rx_rp, join_rx);
        rx_cnt <= rx_cnt + {{AW{1'b0}}, do_rx_wr} - {{AW{1'b0}}, do_rx_rd};
      end
    end
  end

endmodule
