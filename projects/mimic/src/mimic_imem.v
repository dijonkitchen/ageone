/*
 * Shared instruction memory: 64 x 32-bit words, one write port (host) and four
 * asynchronous read ports (one per state machine), so every SM fetches every cycle.
 *
 * Words are stored in latches behind a per-word clock gate, less than half the area of
 * flip-flops with enables. Define MIMIC_IMEM_FF for plain flip-flops instead (for FPGAs,
 * where latches and gated clocks are a poor fit); writes then land one cycle sooner.
 * See docs/decisions/2026-11-13-mimic-imem.md.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module mimic_imem (
    input  wire        clk,
    input  wire        we,
    input  wire [5:0]  waddr,
    input  wire [31:0] wdata,
    input  wire [5:0]  raddr0,
    input  wire [5:0]  raddr1,
    input  wire [5:0]  raddr2,
    input  wire [5:0]  raddr3,
    output wire [31:0] rdata0,
    output wire [31:0] rdata1,
    output wire [31:0] rdata2,
    output wire [31:0] rdata3
);

`ifndef MIMIC_IMEM_FF
  // Each word is 32 latches behind its own clock gate, a negative latch holding the enable
  // and an AND with clk (the structure of an integrated clock gate). A host write at cycle T
  // opens word waddr's latches for the high half of cycle T+2, capturing wdata_q, which holds
  // still because host writes are at least 32 SCK edges apart.
  reg [31:0] wdata_q;
  reg        we_q;
  reg [5:0]  waddr_q;
  always @(posedge clk) begin
    we_q <= we;
    waddr_q <= waddr;
    if (we) wdata_q <= wdata;
  end
  wire [31:0] mem [0:63];
  /* verilator lint_off LATCH */
  genvar g;
  generate
    for (g = 0; g < 64; g = g + 1) begin : word
      reg        en_l;
      reg [31:0] q;
      wire       en = we_q & (waddr_q == g);
      always @(*) if (!clk) en_l = en;
      wire gclk = clk & en_l;
      always @(*) if (gclk) q = wdata_q;
      assign mem[g] = q;
    end
  endgenerate
  /* verilator lint_on LATCH */
`else
  reg [31:0] mem [0:63];
  always @(posedge clk) begin
    if (we) mem[waddr] <= wdata;
  end
`endif

  // Each read port selects in two levels: eight one-hot lines from raddr[2:0] pick a word in
  // every group of eight, then eight lines from raddr[5:3] pick the group. The kept nets stop
  // synthesis from flattening this into 64 word lines per port, each running to all 32 bits:
  // those 256 lines were a third of the placed wiring and made the chip unroutable on its one
  // horizontal routing layer (see docs/decisions/2026-11-13-mimic-area.md).
  wire [5:0]  raddr [0:3];
  wire [31:0] rdata [0:3];
  assign raddr[0] = raddr0;
  assign raddr[1] = raddr1;
  assign raddr[2] = raddr2;
  assign raddr[3] = raddr3;
  genvar p, k, b;
  generate
    for (p = 0; p < 4; p = p + 1) begin : port
      (* keep *) wire [7:0] lo = 8'd1 << raddr[p][2:0];
      (* keep *) wire [7:0] hi = 8'd1 << raddr[p][5:3];
      for (b = 0; b < 32; b = b + 1) begin : column
        wire [7:0] grp;
        for (k = 0; k < 8; k = k + 1) begin : group
          (* keep *) wire sel = |(lo & {mem[8*k+7][b], mem[8*k+6][b], mem[8*k+5][b], mem[8*k+4][b],
                                      mem[8*k+3][b], mem[8*k+2][b], mem[8*k+1][b], mem[8*k][b]});
          assign grp[k] = sel;
        end
        assign rdata[p][b] = |(hi & grp);
      end
    end
  endgenerate
  assign rdata0 = rdata[0];
  assign rdata1 = rdata[1];
  assign rdata2 = rdata[2];
  assign rdata3 = rdata[3];

endmodule
