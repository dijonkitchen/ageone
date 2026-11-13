/*
 * Shared instruction memory: 64 x 32-bit words, one write port (host) and four
 * asynchronous read ports (one per state machine), so every SM fetches every cycle.
 *
 * MIMIC_IMEM_LATCH (set in info.yaml's build and the tests) stores words in latches behind a
 * per-word clock gate, less than half the area of flip-flops with enables; without it the
 * memory is plain flip-flops. See docs/decisions/2026-11-13-mimic-imem.md.
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

`ifdef MIMIC_IMEM_LATCH
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

  assign rdata0 = mem[raddr0];
  assign rdata1 = mem[raddr1];
  assign rdata2 = mem[raddr2];
  assign rdata3 = mem[raddr3];

endmodule
