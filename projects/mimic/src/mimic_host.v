/*
 * Host port: an SPI target (mode 0, MSB first) that turns frames into 32-bit register
 * accesses. SCK, CS_N and MOSI arrive already synchronized to clk, so SCK must be at most
 * clk/4 for writes and clk/6 for reads (MISO changes two to four cycles after a rising edge).
 *
 * Frame:  CS_N low, CMD byte, ADDR byte, then
 *         write: 4-byte words, each written to ADDR when its 32nd bit arrives;
 *         read:  one dummy byte, then 4-byte words on MISO.
 * CMD:    bit 7 WRITE, bit 6 INC (ADDR += 1 after each word), bits 5:0 zero.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module mimic_host (
    input  wire        clk,
    input  wire        rst_n,

    input  wire        sck,   // synchronized
    input  wire        csn,   // synchronized
    input  wire        mosi,  // synchronized
    output reg         miso,

    output reg  [7:0]  bus_addr,
    output wire [31:0] bus_wdata,
    output wire        bus_we,       // write bus_wdata to bus_addr this cycle
    output wire        bus_rd_done,  // a read of bus_addr finished this cycle (FIFO pop)
    input  wire [31:0] bus_rdata     // value at bus_addr, sampled at the start of each word
);

  localparam [2:0] PH_CMD = 3'd0, PH_ADDR = 3'd1, PH_DUMMY = 3'd2, PH_WDATA = 3'd3, PH_RDATA = 3'd4;

  reg        sck_q;
  reg [2:0]  phase;
  reg [4:0]  bitcnt;
  reg [30:0] sh_in;
  reg [31:0] sh_out;
  reg        cmd_w, cmd_inc;
  reg        load_pend;

  wire sck_rise = sck & ~sck_q & ~csn;
  wire last8    = (bitcnt == 5'd7);
  wire last32   = (bitcnt == 5'd31);

  assign bus_wdata   = {sh_in, mosi};
  assign bus_we      = sck_rise & (phase == PH_WDATA) & last32;
  assign bus_rd_done = sck_rise & (phase == PH_RDATA) & last32;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sck_q <= 1'b0;
      phase <= PH_CMD;
      bitcnt <= 5'd0;
      sh_in <= 31'd0;
      sh_out <= 32'd0;
      cmd_w <= 1'b0;
      cmd_inc <= 1'b0;
      load_pend <= 1'b0;
      bus_addr <= 8'd0;
      miso <= 1'b0;
    end else begin
      sck_q <= sck;
      if (csn) begin
        phase <= PH_CMD;
        bitcnt <= 5'd0;
        load_pend <= 1'b0;
        miso <= 1'b0;
      end else begin
        if (load_pend) begin
          sh_out <= bus_rdata;
          miso <= bus_rdata[31];
          load_pend <= 1'b0;
        end
        if (sck_rise) begin
          sh_in <= {sh_in[29:0], mosi};
          bitcnt <= bitcnt + 5'd1;
          case (phase)
            PH_CMD: if (last8) begin
              cmd_w <= sh_in[6];
              cmd_inc <= sh_in[5];
              phase <= PH_ADDR;
              bitcnt <= 5'd0;
            end
            PH_ADDR: if (last8) begin
              bus_addr <= {sh_in[6:0], mosi};
              phase <= cmd_w ? PH_WDATA : PH_DUMMY;
              bitcnt <= 5'd0;
            end
            PH_DUMMY: if (last8) begin
              phase <= PH_RDATA;
              bitcnt <= 5'd0;
              load_pend <= 1'b1;
            end
            PH_WDATA: if (last32) begin
              bitcnt <= 5'd0;
              if (cmd_inc) bus_addr <= bus_addr + 8'd1;
            end
            PH_RDATA: if (last32) begin
              bitcnt <= 5'd0;
              load_pend <= 1'b1;
              if (cmd_inc) bus_addr <= bus_addr + 8'd1;
            end else begin
              sh_out <= {sh_out[30:0], 1'b0};
              miso <= sh_out[30];
            end
            default: phase <= PH_CMD;
          endcase
        end
      end
    end
  end

endmodule
