"""STUDENT STARTER -- Week 6 functional-coverage FIFO testbench.

Goal: build a functional coverage model for the FIFO and drive constrained-
random stimulus until it closes, while scoreboarding against the golden model.

Right now this is deliberately weak:
  * the coverage model has only an *operation* coverpoint -- no occupancy
    coverpoint and no CROSS, so it can never tell you whether you exercised
    "write while full" or "read while empty";
  * the stimulus is a short uniform-random burst that rarely fills or drains
    the FIFO; and
  * the scoreboard checks only count.

Finish the TODOs: add the occupancy coverpoint (empty / partial / full), add
the occupancy x operation CROSS, drive (reuse the Week-5 biased @vsc.randobj)
until the cross is fully covered, and check full/empty/rd_data every cycle.

Run:    make SIM=icarus
Score:  cd code && just mutate fifo_cov            # released pool
        cd code && just mutate fifo_cov hidden     # hidden pool (grading)
"""
import random

import cocotb
import vsc
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
from cocotb_coverage.coverage import CoverPoint, CoverCross, coverage_db

from models.fifo_model import FifoModel

WIDTH = 8
DEPTH = 8
MASK = (1 << WIDTH) - 1


@vsc.randobj
class FifoTxn:
    def __init__(self, width=WIDTH):
        self.wr_en = vsc.rand_bit_t(1)
        self.rd_en = vsc.rand_bit_t(1)
        self.wr_data = vsc.rand_bit_t(width)
        self.count = vsc.uint32_t()

    @vsc.constraint
    def bias_c(self):

        with vsc.if_then(self.count <= 1):
            vsc.dist(self.wr_en, [
                vsc.weight(1, 90),
                vsc.weight(0, 10)
            ])
            vsc.dist(self.rd_en, [
                vsc.weight(1, 20),
                vsc.weight(0, 80)
            ])

        with vsc.else_if(self.count >= DEPTH - 1):
            vsc.dist(self.wr_en, [
                vsc.weight(1, 20),
                vsc.weight(0, 80)
            ])
            vsc.dist(self.rd_en, [
                vsc.weight(1, 90),
                vsc.weight(0, 10)
            ])

        with vsc.else_then:
            vsc.dist(self.wr_en, [
                vsc.weight(1, 70),
                vsc.weight(0, 30)
            ])
            vsc.dist(self.rd_en, [
                vsc.weight(1, 70),
                vsc.weight(0, 30)
            ])


def occ_bin(count):
    if count == 0:
        return "empty"
    if count == DEPTH:
        return "full"
    return "partial"
def op_bin(wr_en, rd_en):
    if wr_en and rd_en:
        return "simul"
    if wr_en:
        return "write"
    if rd_en:
        return "read"
    return "idle"


@CoverPoint("top.occ", xf=lambda occ, wr, rd: occ_bin(occ),
            bins=["empty", "partial", "full"])
@CoverPoint("top.op", xf=lambda occ, wr, rd: op_bin(wr, rd),
            bins=["idle", "write", "read", "simul"])
@CoverCross("top.occ_x_op", items=["top.occ", "top.op"])
def sample_coverage(occ, wr, rd):
    pass


@cocotb.test()
async def test_coverage(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    model = FifoModel(WIDTH, DEPTH)

    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    model.reset()
    await FallingEdge(dut.clk)
    random.seed(1)
    txn = FifoTxn()
    for _ in range(3000):                       # TODO: drive until coverage closes
        txn.count = model.count
        txn.randomize()
        wr, rd, data = int(txn.wr_en), int(txn.rd_en), int(txn.wr_data)
        sample_coverage(model.count,wr, rd)
        dut.wr_en.value = wr
        dut.rd_en.value = rd
        dut.wr_data.value = data
        model.step(wr, data, rd)
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")
        assert int(dut.count.value) == model.count, \
    f"count {int(dut.count.value)} != model {model.count}"

        assert int(dut.full.value) == int(model.full), \
            f"full {int(dut.full.value)} != model {int(model.full)}"
        
        assert int(dut.empty.value) == int(model.empty), \
            f"empty {int(dut.empty.value)} != model {int(model.empty)}"
        
        if not model.empty:
            assert int(dut.rd_data.value) == model.head, \
                f"rd_data {int(dut.rd_data.value)} != model {model.head}"

    op = coverage_db["top.op"].cover_percentage
    occ = coverage_db["top.occ"].cover_percentage
    cross = coverage_db["top.occ_x_op"].cover_percentage
    
    dut._log.info(f"operation coverage = {op:.2f}%")
    dut._log.info(f"occupancy coverage = {occ:.2f}%")
    dut._log.info(f"cross coverage = {cross:.2f}%")
    
    coverage_db.report_coverage(dut._log.info, bins=True)
    coverage_db.export_to_yaml("coverage.yml")
