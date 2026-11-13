# cocotb tests for Mimic. `make` runs RTL tests; `make GATES=yes` runs them on the gate-level
# netlist (copy it to gate_level_netlist.v first, see docs/verification.md).
# COCOTB_TEST_FILTER=<regex> picks tests; WAVES=1 dumps tb.fst.

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
PROJECT_SOURCES = project.v mimic_host.v mimic_imem.v mimic_fifo.v mimic_sm.v

ifneq ($(GATES),yes)

SIM_BUILD = sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

SIM_BUILD = sim_build/gl
COMPILE_ARGS += -DGL_TEST
COMPILE_ARGS += -DFUNCTIONAL
COMPILE_ARGS += -DSIM
PDK ?= ihp-sg13cmos5l
PDK_CELL_PREFIX = $(patsubst ihp-%,%,$(PDK))
PDK_LIBS_REF = $(PDK_ROOT)/$(PDK)/libs.ref
VERILOG_SOURCES += $(PDK_LIBS_REF)/$(PDK_CELL_PREFIX)_io/verilog/$(PDK_CELL_PREFIX)_io.v
VERILOG_SOURCES += $(wildcard $(PDK_LIBS_REF)/$(PDK_CELL_PREFIX)_stdcell/verilog/$(PDK_CELL_PREFIX)_udp.v)
VERILOG_SOURCES += $(PDK_LIBS_REF)/$(PDK_CELL_PREFIX)_stdcell/verilog/$(PDK_CELL_PREFIX)_stdcell.v
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

COMPILE_ARGS += -I$(SRC_DIR)
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb
COCOTB_TEST_MODULES = test

ifeq ($(WAVES),1)
PLUSARGS += +fst
endif

export PYTHONPATH := $(PWD)/../sw:$(PWD)/../sw/tests:$(PYTHONPATH)

# Gate level is slow (a 40,000-cell netlist), so by default it runs a representative subset;
# COCOTB_TEST_FILTER=. runs everything.
ifeq ($(GATES),yes)
COCOTB_TEST_FILTER ?= test_(chip_id|fifo_echo|uart_tx|spi_ctrl_mode3|i2c_loopback|eth_tx_line_rate|random_isa_0)$$
endif

# cocotb's makefile puts the filter on a shell command line unquoted; quote it so regexes
# with | and () work: make COCOTB_TEST_FILTER='test_(uart|spi)'
ifneq ($(COCOTB_TEST_FILTER),)
override COCOTB_TEST_FILTER := '$(COCOTB_TEST_FILTER)'
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
