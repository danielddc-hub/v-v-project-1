"""Project 1: constrained-random verification of a synchronous FIFO.

Run (from the existing repository): make SIM=icarus
Optional: FIFO_SEED=123 FIFO_VECTORS=5000 FIFO_STRICT_LEGAL=1 make SIM=icarus

Assumed DUT interface: clk, rst_n, wr_en, rd_en, wr_data, rd_data,
count, full, empty. Assumed behavior matches the original test_fifo.py:
- Writes accepted iff pre-edge FIFO is not full.
- Reads accepted iff pre-edge FIFO is not empty.
- rd_data exposes the queue head whenever nonempty (FWFT).
- Simultaneous read/write at empty accepts only the write.

Verify these assumptions against the provided *specification* before use.
No simulator or mutant-pool results are fabricated by this script.
"""
import csv
import json
import os
from collections import Counter, deque
from pathlib import Path

import cocotb
import vsc
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer
from cocotb_coverage.coverage import CoverPoint, CoverCross, coverage_db

WIDTH = int(os.getenv("FIFO_WIDTH", "8"))
DEPTH = int(os.getenv("FIFO_DEPTH", "8"))
SEED = int(os.getenv("FIFO_SEED", "1"))
VECTORS = int(os.getenv("FIFO_VECTORS", "5000"))
STRICT_LEGAL = os.getenv("FIFO_STRICT_LEGAL", "0") == "1"
OUTPUT_DIR = Path(os.getenv("FIFO_OUTPUT_DIR", "fifo_results"))
MASK = (1 << WIDTH) - 1
assert WIDTH > 0 and DEPTH >= 4 and VECTORS > 0


@vsc.randobj
class FifoTxn:
    """pyvsc transaction with occupancy-aware weighted legal operation selection.

    With STRICT_LEGAL=0, blocked boundary requests are intentionally generated
    to verify overflow/underflow rejection (not accepted transfers).
    """
    def __init__(self):
        self.wr_en = vsc.rand_bit_t(1)
        self.rd_en = vsc.rand_bit_t(1)
        self.wr_data = vsc.rand_bit_t(WIDTH)
        self.occupancy = vsc.uint32_t()
        self.mode = vsc.uint8_t()  # 0=random, 1=fill, 2=drain, 3=simul, 4=idle
        self.strict = vsc.uint8_t()

    @vsc.constraint
    def fifo_c(self):
        with vsc.if_then(self.strict == 1):
            with vsc.if_then(self.occupancy == 0):
                self.rd_en == 0
            with vsc.if_then(self.occupancy == DEPTH):
                self.wr_en == 0
        with vsc.if_then(self.mode == 1):
            self.wr_en == 1
            self.rd_en == 0
        with vsc.else_if(self.mode == 2):
            self.wr_en == 0
            self.rd_en == 1
        with vsc.else_if(self.mode == 3):
            self.wr_en == 1
            self.rd_en == 1
        with vsc.else_if(self.mode == 4):
            self.wr_en == 0
            self.rd_en == 0
        with vsc.else_then:
            with vsc.if_then(self.occupancy <= 1):
                vsc.dist(self.wr_en, [vsc.weight(1, 90), vsc.weight(0, 10)])
                vsc.dist(self.rd_en, [vsc.weight(1, 20), vsc.weight(0, 80)])
            with vsc.else_if(self.occupancy >= DEPTH - 1):
                vsc.dist(self.wr_en, [vsc.weight(1, 20), vsc.weight(0, 80)])
                vsc.dist(self.rd_en, [vsc.weight(1, 90), vsc.weight(0, 10)])
            with vsc.else_then:
                vsc.dist(self.wr_en, [vsc.weight(1, 70), vsc.weight(0, 30)])
                vsc.dist(self.rd_en, [vsc.weight(1, 70), vsc.weight(0, 30)])


def occ_bin(n):
    if n == 0:
        return "empty"
    if n == 1:
        return "near_empty"
    if n == DEPTH - 1:
        return "near_full"
    if n == DEPTH:
        return "full"
    return "middle"


def op_bin(wr, rd):
    return ("simul" if wr and rd else "write" if wr else "read" if rd else "idle")


# A legal cross is sampled only in the interior, where every request is
# accepted or idle; boundary conditions have their own explicit coverpoints.
@CoverPoint("fifo.occ", xf=lambda x: x["occ_bin"],
            bins=["empty", "near_empty", "middle", "near_full", "full"])
@CoverPoint("fifo.op", xf=lambda x: x["op"],
            bins=["idle", "write", "read", "simul"])
@CoverPoint("fifo.write_outcome", xf=lambda x: x["write_outcome"],
            bins=["none", "accepted", "blocked"])
@CoverPoint("fifo.read_outcome", xf=lambda x: x["read_outcome"],
            bins=["none", "accepted", "blocked"])
@CoverPoint("fifo.wr_wrap", xf=lambda x: x["wr_wrap"], bins=[0, 1])
@CoverPoint("fifo.rd_wrap", xf=lambda x: x["rd_wrap"], bins=[0, 1])
@CoverPoint("fifo.simul_boundary", xf=lambda x: x["simul_boundary"],
            bins=["none", "empty", "middle", "full"])
@CoverPoint("fifo.burst", xf=lambda x: x["burst"],
            bins=["random", "fill", "drain", "simul", "idle"])
@CoverCross("fifo.occ_x_op", items=["fifo.occ", "fifo.op"],
            ign_bins=([("empty", "read"), ("full", "write")] if STRICT_LEGAL else []))
def sample_coverage(x):
    pass


class FifoDriver:
    def __init__(self, dut):
        self.dut = dut

    async def reset(self):
        d = self.dut
        d.wr_en.value = 0
        d.rd_en.value = 0
        d.wr_data.value = 0
        d.rst_n.value = 0
        for _ in range(3):
            await RisingEdge(d.clk)
        await FallingEdge(d.clk)
        d.rst_n.value = 1

    async def drive(self, wr, rd, data):
        d = self.dut
        d.wr_en.value = wr
        d.rd_en.value = rd
        d.wr_data.value = data
        await RisingEdge(d.clk)
        await Timer(1, units="ns")


class FifoMonitor:
    def __init__(self, dut):
        self.dut = dut

    def sample(self):
        d = self.dut
        result = {key: int(getattr(d, key).value) for key in
                  ("count", "full", "empty")}
        # The RTL leaves FIFO memory uninitialized on reset. rd_data is
        # undefined while empty, so never convert its X bits to an integer.
        result["rd_data"] = (int(d.rd_data.value) if not result["empty"]
                             else None)
        return result


class QueueScoreboard:
    def __init__(self):
        self.q = deque()
        self.wr_ptr = 0
        self.rd_ptr = 0

    @property
    def count(self):
        return len(self.q)

    def predict_and_advance(self, wr, rd, data):
        before = len(self.q)
        do_wr = bool(wr) and before < DEPTH
        do_rd = bool(rd) and before > 0
        wr_wrap = int(do_wr and self.wr_ptr == DEPTH - 1)
        rd_wrap = int(do_rd and self.rd_ptr == DEPTH - 1)
        if do_rd:
            self.q.popleft()
            self.rd_ptr = (self.rd_ptr + 1) % DEPTH
        if do_wr:
            self.q.append(data & MASK)
            self.wr_ptr = (self.wr_ptr + 1) % DEPTH
        return before, do_wr, do_rd, wr_wrap, rd_wrap

    def check(self, observed, cycle):
        expected = {"count": self.count, "full": int(self.count == DEPTH),
                    "empty": int(self.count == 0)}
        for key, value in expected.items():
            assert observed[key] == value, (f"cycle={cycle} {key}: "
                f"DUT={observed[key]}, expected={value}")
        assert 0 <= observed["count"] <= DEPTH
        if self.q:  # FWFT behavior, consistent with original testbench
            assert observed["rd_data"] == self.q[0], (
                f"cycle={cycle} rd_data: DUT={observed['rd_data']:#x}, "
                f"expected head={self.q[0]:#x}")


def mode_schedule(cycle, count):
    """Constraint-guided closure: recurring bursts plus random exploration.

    0-DEPTH+1 fill; next DEPTH+1 drain; then repeated burst/random blocks.
    The modes are *constraints*, not direct pin assignments.
    """
    period = 8 * DEPTH + 32
    pos = cycle % period
    if pos < DEPTH + 2:
        return 1, "fill"
    if pos < 2 * (DEPTH + 2):
        return 2, "drain"
    if pos < 3 * (DEPTH + 2):
        return 3, "simul"
    if pos < 3 * (DEPTH + 2) + 3:
        return 4, "idle"
    return 0, "random"


def expected_coverage_keys(strict):
    keys = {("occ", x) for x in ("empty", "near_empty", "middle", "near_full", "full")}
    keys |= {("op", x) for x in ("idle", "write", "read", "simul")}
    keys |= {("wr_wrap", 1), ("rd_wrap", 1), ("burst", "fill"),
             ("burst", "drain"), ("burst", "simul"), ("burst", "random"),
             ("simul_boundary", "empty"), ("simul_boundary", "middle")}
    if not strict:
        keys |= {("write_outcome", "blocked"), ("read_outcome", "blocked")}
    return keys


@cocotb.test()
async def test_coverage(dut):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dut._log.info("FIFO seed=%d width=%d depth=%d vectors=%d strict_legal=%s",
                  SEED, WIDTH, DEPTH, VECTORS, STRICT_LEGAL)
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    driver, monitor, sb = FifoDriver(dut), FifoMonitor(dut), QueueScoreboard()
    await driver.reset()
    sb.check(monitor.sample(), "reset")
    assert len(dut.wr_data) == WIDTH, "FIFO_WIDTH does not match RTL WIDTH"

    # pyvsc's own random state, rather than Python random.seed(), drives
    # randomize() deterministically. If using an older pyvsc, update it.
    rng = vsc.randstate.mkFromSeed(SEED)
    txn = FifoTxn()
    counts = Counter()
    observed_bins = set()
    required = expected_coverage_keys(STRICT_LEGAL)
    closure_cycle = None
    records = []

    for i in range(VECTORS):
        mode, mode_name = mode_schedule(i, sb.count)
        # Strict mode must not force a prohibited boundary operation.
        if STRICT_LEGAL and ((mode == 1 and sb.count == DEPTH) or
                             (mode == 2 and sb.count == 0) or
                             (mode == 3 and sb.count in (0, DEPTH))):
            mode, mode_name = 0, "random"
        txn.occupancy = sb.count
        txn.mode = mode
        txn.strict = int(STRICT_LEGAL)
        txn.randomize(randstate=rng)
        wr, rd, data = int(txn.wr_en), int(txn.rd_en), int(txn.wr_data)
        assert 0 <= data <= MASK
        if STRICT_LEGAL:
            assert not (wr and sb.count == DEPTH)
            assert not (rd and sb.count == 0)

        before = sb.count
        # Driver applies the request; monitor reads after the active edge.
        await driver.drive(wr, rd, data)
        pre, do_wr, do_rd, wr_wrap, rd_wrap = sb.predict_and_advance(wr, rd, data)
        assert pre == before
        obs = monitor.sample()
        sb.check(obs, i)

        op = op_bin(wr, rd)
        occ = occ_bin(before)
        boundary = ("empty" if before == 0 else "full" if before == DEPTH
                    else "middle") if wr and rd else "none"
        sample = {
            "occ_bin": occ, "op": op,
            "write_outcome": "none" if not wr else "accepted" if do_wr else "blocked",
            "read_outcome": "none" if not rd else "accepted" if do_rd else "blocked",
            "wr_wrap": wr_wrap, "rd_wrap": rd_wrap,
            "simul_boundary": boundary, "burst": mode_name,
        }
        sample_coverage(sample)
        for field in ("occ", "op", "wr_wrap", "rd_wrap", "burst", "simul_boundary",
                      "write_outcome", "read_outcome"):
            name = {"occ": "occ_bin"}.get(field, field)
            observed_bins.add((field, sample[name]))
        counts[(occ, op)] += 1
        records.append({"cycle": i, "seed": SEED, "mode": mode_name,
                        "pre_count": before, "wr_en": wr, "rd_en": rd,
                        "wr_data": data, "accepted_write": int(do_wr),
                        "accepted_read": int(do_rd), "wr_wrap": wr_wrap,
                        "rd_wrap": rd_wrap, "post_count": sb.count})
        if closure_cycle is None and required <= observed_bins:
            closure_cycle = i + 1
        if i != VECTORS - 1:
            await FallingEdge(dut.clk)

    with (OUTPUT_DIR / "transactions.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    coverage_db.report_coverage(dut._log.info, bins=True)
    coverage_db.export_to_yaml(str(OUTPUT_DIR / "coverage.yml"))
    missing = sorted(required - observed_bins, key=str)
    summary = {"seed": SEED, "width": WIDTH, "depth": DEPTH,
               "vectors": VECTORS, "strict_legal": STRICT_LEGAL,
               "required_bins_hit": len(required) - len(missing),
               "required_bins_total": len(required), "missing_bins": [str(x) for x in missing],
               "vectors_to_required_bin_closure": closure_cycle,
               "coverage_db_percent": coverage_db["fifo"].cover_percentage,
               "occupancy_operation_histogram": {f"{a}/{b}": n for (a, b), n in counts.items()},
               "wr_wrap_count": sum(r["wr_wrap"] for r in records),
               "rd_wrap_count": sum(r["rd_wrap"] for r in records),
               "simultaneous_count": sum(r["wr_en"] and r["rd_en"] for r in records)}
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    dut._log.info("Regression summary: %s", json.dumps(summary, sort_keys=True))
    assert not missing, f"Required coverage holes remain: {missing}"
