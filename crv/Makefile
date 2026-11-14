TOPLEVEL_LANG ?= verilog
SIM           ?= verilator

DUT ?= $(CURDIR)/../../code/dut/fifo.sv
VERILOG_SOURCES = $(DUT)

TOPLEVEL = fifo
MODULE   = test_fifo

export PYTHONPATH := $(CURDIR)/../../code/lib:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
