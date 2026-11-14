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


def write_bin(wr, do_wr):
    if not wr:
        return None
    return "accepted" if do_wr else "blocked-full"


def read_bin(rd, do_rd):
    if not rd:
        return None
    return "accepted" if do_rd else "blocked-empty"


def simul_bin(wr, rd):
    return "simul" if wr and rd else None


@CoverPoint(
    "top.occ",
    xf=lambda occ, wr, rd, do_wr, do_rd, wrap: occ_bin(occ),
    bins=["empty", "partial", "full"]
)
@CoverPoint(
    "top.op",
    xf=lambda occ, wr, rd, do_wr, do_rd, wrap: op_bin(wr, rd),
    bins=["idle", "write", "read", "simul"]
)
@CoverPoint("top.write_condition", xf=lambda occ, wr, rd, do_wr, do_rd, wrap: write_bin(wr, do_wr), bins=["accepted", "blocked-full"])
@CoverPoint("top.read_condition", xf=lambda occ, wr, rd, do_wr, do_rd, wrap: read_bin(rd, do_rd), bins=["accepted", "blocked-empty"])
@CoverPoint("top.pointer_wrap", xf=lambda occ, wr, rd, do_wr, do_rd, wrap: wrap, bins=["no-wrap", "wrap"])
@CoverPoint("top.simul_requested", xf=lambda occ, wr, rd, do_wr, do_rd, wrap: simul_bin(wr, rd), bins=["simul"])
@CoverCross("top.occ_x_op", items=["top.occ", "top.op"])
@CoverCross("top.occ_x_simul", items=["top.occ", "top.simul_requested"])
@CoverCross("top.wrap_x_op", items=["top.pointer_wrap", "top.op"], ign_bins=[("wrap", "idle")])
def sample_coverage(occ, wr, rd, do_wr, do_rd, wrap):
    pass



@cocotb.test()
async def test_coverage(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    model = FifoModel(WIDTH, DEPTH)

    # Initialize and reset the FIFO
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.wr_data.value = 0
    dut.rst_n.value = 0

    for _ in range(3):
        await RisingEdge(dut.clk)

    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    model.reset()

    # Track expected FIFO pointer positions
    wr_ptr = 0
    rd_ptr = 0

    # Initialize constrained-random stimulus
    random.seed(1)
    txn = FifoTxn()

    # Track coverage convergence
    seen_bins = set()
    last_bins = []
    vectors_to_closure = None
    total_vectors = 3000

    # Run constrained-random transactions
    for i in range(total_vectors):
        txn.count = model.count
        txn.randomize()

        wr = int(txn.wr_en)
        rd = int(txn.rd_en)
        data = int(txn.wr_data)

        # Determine which operations are accepted
        do_wr = bool(wr) and not model.full
        do_rd = bool(rd) and not model.empty

        # Detect pointer wrap-around
        write_wrap = do_wr and wr_ptr == DEPTH - 1
        read_wrap = do_rd and rd_ptr == DEPTH - 1

        if write_wrap or read_wrap:
            wrap = "wrap"
        else:
            wrap = "no-wrap"

        # Sample coverage using the pre-edge FIFO state
        sample_coverage(
            model.count, wr, rd, do_wr, do_rd, wrap
        )

        # Track newly reached occupancy x operation bins
        bin_name = (occ_bin(model.count), op_bin(wr, rd))

        if bin_name not in seen_bins:
            seen_bins.add(bin_name)
            last_bins.append((i + 1, bin_name))

        # Track closure of the entire coverage model
        if (
            coverage_db["top"].cover_percentage >= 100.0
            and vectors_to_closure is None
        ):
            vectors_to_closure = i + 1

        # Apply inputs to the DUT
        dut.wr_en.value = wr
        dut.rd_en.value = rd
        dut.wr_data.value = data

        # Check simultaneous read/write at the empty boundary
        empty_simul = model.empty and wr == 1 and rd == 1

        # Advance the golden reference model
        model.step(wr, data, rd)

        # Update expected pointer positions
        if do_wr:
            wr_ptr = (wr_ptr + 1) % DEPTH

        if do_rd:
            rd_ptr = (rd_ptr + 1) % DEPTH

        # Wait for the rising clock edge
        await RisingEdge(dut.clk)
        await Timer(1, units="ns")

        # Security & Trust: verify empty-boundary behavior
        if empty_simul:
            assert int(dut.count.value) == 1, (
                "Simultaneous read/write at empty boundary failed"
            )
            assert int(dut.rd_data.value) == data, (
                "Incorrect data after simultaneous read/write at empty"
            )

        # Check FIFO occupancy
        assert int(dut.count.value) == model.count, (
            f"count {int(dut.count.value)} != model {model.count}"
        )

        # Check full flag
        assert int(dut.full.value) == int(model.full), (
            f"full {int(dut.full.value)} != model {int(model.full)}"
        )

        # Check empty flag
        assert int(dut.empty.value) == int(model.empty), (
            f"empty {int(dut.empty.value)} != model {int(model.empty)}"
        )

        # Check FIFO data ordering
        if not model.empty:
            assert int(dut.rd_data.value) == model.head, (
                f"rd_data {int(dut.rd_data.value)} != model {model.head}"
            )

        # Check valid occupancy range
        assert 0 <= int(dut.count.value) <= DEPTH, (
            "FIFO occupancy outside valid range"
        )

        # Set up inputs at the next falling edge
        if i < total_vectors - 1:
            await FallingEdge(dut.clk)

    # Report individual coverage measurements
    coverage_items = [
        "top.occ",
        "top.op",
        "top.write_condition",
        "top.read_condition",
        "top.pointer_wrap",
        "top.simul_requested",
        "top.occ_x_op",
        "top.occ_x_simul",
        "top.wrap_x_op",
    ]

    for name in coverage_items:
        percent = coverage_db[name].cover_percentage
        dut._log.info(f"{name} = {percent:.2f}%")

    # Report total coverage
    total_coverage = coverage_db["top"].cover_percentage
    dut._log.info(f"Total coverage = {total_coverage:.2f}%")

    coverage_db.report_coverage(dut._log.info, bins=True)
    coverage_db.export_to_yaml("coverage.yml")

    # Report coverage convergence
    dut._log.info(f"Vectors to closure: {vectors_to_closure}")

    if vectors_to_closure is not None:
        dut._log.info(
            f"Vectors soaked past closure: "
            f"{total_vectors - vectors_to_closure}"
        )

    # Report last 3 occupancy x operation bins
    dut._log.info("Last 3 occupancy x operation bins covered:")

    for vector, bin_name in last_bins[-3:]:
        dut._log.info(f"Vector {vector}: {bin_name}")

    # Verify the expanded coverage model closed
    assert total_coverage >= 100.0, (
        f"Coverage did not close: {total_coverage:.2f}%"
    )
