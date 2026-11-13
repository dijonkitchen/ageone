/*
 * Mimic: a reprogrammable protocol emulator for Tiny Tapeout.
 *
 * Four state machines run programs from a shared 64-word instruction memory and drive a
 * 32-pin GPIO space; a host (the demo board's RP2350) loads programs, configures the state
 * machines, and moves data through FIFOs over an SPI port.
 *
 *   GPIO 0-7    uio[7:0]  bidirectional, optional open-drain
 *   GPIO 8-14   uo[6:0]   outputs (GPIO 15 has no pad: uo[7] is the host's MISO)
 *   GPIO 16-23  ui[7:0]   inputs (ui[5] CS_N, ui[6] SCK, ui[7] MOSI also feed the host port)
 *   GPIO 24-31  internal  outputs that read back as inputs, for signalling between SMs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_dijonkitchen_mimic (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  localparam [31:0] ID = 32'h4D494D31;  // "MIM1"
  localparam FIFO_DEPTH = 2;

  // ---------------------------------------------------------------------------
  // Input synchronizers
  // ---------------------------------------------------------------------------
  reg [7:0] ui_s1, ui_s2, uio_s1, uio_s2;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      ui_s1 <= 8'd0; ui_s2 <= 8'd0; uio_s1 <= 8'd0; uio_s2 <= 8'd0;
    end else begin
      ui_s1 <= ui_in;   ui_s2 <= ui_s1;
      uio_s1 <= uio_in; uio_s2 <= uio_s1;
    end
  end

  // ---------------------------------------------------------------------------
  // Host port
  // ---------------------------------------------------------------------------
  wire [7:0]  bus_addr;
  wire [31:0] bus_wdata;
  wire        bus_we, bus_rd_done;
  reg  [31:0] bus_rdata;
  wire        host_miso;

  mimic_host host (
      .clk(clk), .rst_n(rst_n),
      .sck(ui_s2[6]), .csn(ui_s2[5]), .mosi(ui_s2[7]), .miso(host_miso),
      .bus_addr(bus_addr), .bus_wdata(bus_wdata), .bus_we(bus_we),
      .bus_rd_done(bus_rd_done), .bus_rdata(bus_rdata)
  );

  wire        a_imem = (bus_addr[7:6] == 2'b00);
  wire        a_glob = (bus_addr[7:4] == 4'h4);
  wire        a_sm   = (bus_addr[7:6] == 2'b10);
  wire [1:0]  a_smn  = bus_addr[5:4];
  wire [3:0]  a_reg  = bus_addr[3:0];

  // ---------------------------------------------------------------------------
  // Global registers
  // ---------------------------------------------------------------------------
  reg  [3:0]  sm_en;
  reg  [3:0]  p_restart, p_divrst, p_step, p_txclr, p_rxclr;  // one-cycle pulses
  reg  [7:0]  irq;
  reg  [7:0]  od_en;
  reg  [19:0] fdebug;
  reg  [31:0] pin_out;
  reg  [7:0]  pin_oe;

  wire g_we = bus_we & a_glob;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sm_en <= 4'd0;
      p_restart <= 4'd0; p_divrst <= 4'd0; p_step <= 4'd0; p_txclr <= 4'd0; p_rxclr <= 4'd0;
      od_en <= 8'd0;
    end else begin
      p_restart <= 4'd0; p_divrst <= 4'd0; p_step <= 4'd0; p_txclr <= 4'd0; p_rxclr <= 4'd0;
      if (g_we && a_reg == 4'h1) begin
        sm_en <= bus_wdata[3:0];
        p_restart <= bus_wdata[7:4];
        p_divrst <= bus_wdata[11:8];
        p_step <= bus_wdata[15:12];
        p_txclr <= bus_wdata[19:16];
        p_rxclr <= bus_wdata[23:20];
      end
      if (g_we && a_reg == 4'h6) od_en <= bus_wdata[7:0];
    end
  end

  // ---------------------------------------------------------------------------
  // GPIO space
  // ---------------------------------------------------------------------------
  wire [31:0] pins_in = {pin_out[31:24], ui_s2, pin_out[15:8], uio_s2};

  assign uo_out = {host_miso, pin_out[14:8]};
  genvar gi;
  generate
    for (gi = 0; gi < 8; gi = gi + 1) begin : pad
      assign uio_out[gi] = od_en[gi] ? 1'b0 : pin_out[gi];
      assign uio_oe[gi]  = od_en[gi] ? ~pin_out[gi] : pin_oe[gi];
    end
  endgenerate

  // ---------------------------------------------------------------------------
  // Instruction memory
  // ---------------------------------------------------------------------------
  wire [5:0]  im_a [0:3];
  wire [31:0] im_d [0:3];

  mimic_imem imem (
      .clk(clk),
      .we(bus_we & a_imem), .waddr(bus_addr[5:0]), .wdata(bus_wdata),
      .raddr0(im_a[0]), .raddr1(im_a[1]), .raddr2(im_a[2]), .raddr3(im_a[3]),
      .rdata0(im_d[0]), .rdata1(im_d[1]), .rdata2(im_d[2]), .rdata3(im_d[3])
  );

  // ---------------------------------------------------------------------------
  // State machines and their FIFOs
  // ---------------------------------------------------------------------------
  wire [31:0] cfg_rd [0:3];
  wire [31:0] pmask [0:3], pval [0:3], dmask [0:3], dval [0:3];
  wire [7:0]  irq_s [0:3], irq_c [0:3];
  wire [3:0]  tx_empty, tx_full, rx_empty, rx_full, tx_pop;
  wire [31:0] tx_head [0:3], rx_head [0:3];
  wire [3:0]  tx_level [0:3], rx_level [0:3];
  wire [3:0]  push_req, push_drop, tx_stall, rx_stall, fjoin_tx, fjoin_rx, route_en;
  wire [31:0] push_data [0:3];
  reg  [3:0]  push_full;
  reg  [3:0]  tx_wr;
  reg  [31:0] tx_wdata [0:3];
  wire [3:0]  rx_wr;

  // TX FIFO writers: the host, else a push routed from the previous SM in the ring
  // (SM3 -> SM0 -> SM1 -> SM2 -> SM3). A routed push sees "full" while the host writes.
  wire [3:0] host_tx_wr;
  integer s;
  always @(*) begin
    for (s = 0; s < 4; s = s + 1) begin
      push_full[s] = route_en[s] ? (tx_full[(s + 1) % 4] | host_tx_wr[(s + 1) % 4]) : rx_full[s];
    end
    for (s = 0; s < 4; s = s + 1) begin
      tx_wr[s] = host_tx_wr[s] | (route_en[(s + 3) % 4] & push_req[(s + 3) % 4] & ~push_full[(s + 3) % 4]);
      tx_wdata[s] = host_tx_wr[s] ? bus_wdata : push_data[(s + 3) % 4];
    end
  end

  genvar gs;
  generate
    for (gs = 0; gs < 4; gs = gs + 1) begin : sm
      wire cfg_we = bus_we & a_sm & (a_smn == gs);

      assign host_tx_wr[gs] = cfg_we & (a_reg == 4'h0);
      assign rx_wr[gs] = push_req[gs] & ~route_en[gs] & ~rx_full[gs];

      mimic_fifo #(.DEPTH(FIFO_DEPTH)) fifo (
          .clk(clk), .rst_n(rst_n),
          .join_tx(fjoin_tx[gs]), .join_rx(fjoin_rx[gs]),
          .clr_tx(p_txclr[gs]), .clr_rx(p_rxclr[gs]),
          .tx_wr(tx_wr[gs]), .tx_wdata(tx_wdata[gs]), .tx_rd(tx_pop[gs]),
          .tx_head(tx_head[gs]), .tx_empty(tx_empty[gs]), .tx_full(tx_full[gs]), .tx_level(tx_level[gs]),
          .rx_wr(rx_wr[gs]), .rx_wdata(push_data[gs]),
          .rx_rd(bus_rd_done & a_sm & (a_smn == gs) & (a_reg == 4'h1)),
          .rx_head(rx_head[gs]), .rx_empty(rx_empty[gs]), .rx_full(rx_full[gs]), .rx_level(rx_level[gs])
      );

      mimic_sm #(.SM_ID(gs)) core (
          .clk(clk), .rst_n(rst_n),
          .enable(sm_en[gs]), .restart(p_restart[gs]), .div_restart(p_divrst[gs]), .step(p_step[gs]),
          .cfg_we(cfg_we), .cfg_addr(a_reg), .cfg_wdata(bus_wdata), .cfg_rdata(cfg_rd[gs]),
          .imem_addr(im_a[gs]), .imem_data(im_d[gs]),
          .pins_in(pins_in),
          .pin_mask(pmask[gs]), .pin_val(pval[gs]), .dir_mask(dmask[gs]), .dir_val(dval[gs]),
          .irq_in(irq), .irq_set(irq_s[gs]), .irq_clr(irq_c[gs]),
          .tx_empty(tx_empty[gs]), .tx_head(tx_head[gs]), .tx_level(tx_level[gs]), .tx_pop(tx_pop[gs]),
          .push_full(push_full[gs]), .rx_level(rx_level[gs]),
          .push_req(push_req[gs]), .push_data(push_data[gs]), .push_drop(push_drop[gs]),
          .tx_stall(tx_stall[gs]), .rx_stall(rx_stall[gs]),
          .fjoin_tx(fjoin_tx[gs]), .fjoin_rx(fjoin_rx[gs]),
          .route_en(route_en[gs])
      );
    end
  endgenerate

  // ---------------------------------------------------------------------------
  // Pin outputs: the highest-numbered SM writing a pin wins.
  // ---------------------------------------------------------------------------
  integer m;
  reg [31:0] pin_out_n;
  reg [7:0]  pin_oe_n;
  always @(*) begin
    pin_out_n = pin_out;
    pin_oe_n = pin_oe;
    for (m = 0; m < 4; m = m + 1) begin
      pin_out_n = (pin_out_n & ~pmask[m]) | (pval[m] & pmask[m]);
      pin_oe_n = (pin_oe_n & ~dmask[m][7:0]) | (dval[m][7:0] & dmask[m][7:0]);
    end
  end

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      pin_out <= 32'd0;
      pin_oe <= 8'd0;
    end else begin
      pin_out <= pin_out_n;
      pin_oe <= pin_oe_n;
    end
  end

  // ---------------------------------------------------------------------------
  // IRQ flags and FIFO debug flags
  // ---------------------------------------------------------------------------
  wire [7:0] irq_set_all = irq_s[0] | irq_s[1] | irq_s[2] | irq_s[3]
                         | ((g_we && a_reg == 4'h5) ? bus_wdata[7:0] : 8'd0);
  wire [7:0] irq_clr_all = irq_c[0] | irq_c[1] | irq_c[2] | irq_c[3]
                         | ((g_we && a_reg == 4'h4) ? bus_wdata[7:0] : 8'd0);

  wire [3:0] host_tx_drop;
  wire [3:0] host_rx_under;
  genvar gf;
  generate
    for (gf = 0; gf < 4; gf = gf + 1) begin : fdbg
      assign host_tx_drop[gf]  = host_tx_wr[gf] & tx_full[gf];
      assign host_rx_under[gf] = bus_rd_done & a_sm & (a_smn == gf) & (a_reg == 4'h1) & rx_empty[gf];
    end
  endgenerate

  wire [19:0] fdebug_set = {rx_stall, tx_stall, host_rx_under, host_tx_drop, push_drop};

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      irq <= 8'd0;
      fdebug <= 20'd0;
    end else begin
      irq <= (irq & ~irq_clr_all) | irq_set_all;
      fdebug <= (fdebug & ~((g_we && a_reg == 4'h3) ? bus_wdata[19:0] : 20'd0)) | fdebug_set;
    end
  end

  // ---------------------------------------------------------------------------
  // Register reads
  // ---------------------------------------------------------------------------
  wire [31:0] flevel = {rx_level[3], tx_level[3], rx_level[2], tx_level[2],
                        rx_level[1], tx_level[1], rx_level[0], tx_level[0]};

  always @(*) begin
    bus_rdata = 32'd0;
    if (a_glob) begin
      case (a_reg)
        4'h0: bus_rdata = ID;
        4'h1: bus_rdata = {28'd0, sm_en};
        4'h2: bus_rdata = flevel;
        4'h3: bus_rdata = {12'd0, fdebug};
        4'h4: bus_rdata = {24'd0, irq};
        4'h6: bus_rdata = {24'd0, od_en};
        4'h7: bus_rdata = pins_in;
        4'h8: bus_rdata = pin_out;
        4'h9: bus_rdata = {24'd0, pin_oe};
        default: bus_rdata = 32'd0;
      endcase
    end else if (a_sm) begin
      if (a_reg == 4'h1) bus_rdata = rx_empty[a_smn] ? 32'd0 : rx_head[a_smn];
      else bus_rdata = cfg_rd[a_smn];
    end
  end

  wire _unused = &{ena, 1'b0};

endmodule
