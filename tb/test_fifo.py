"""HW4 FIFO testbench."""

import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
from models.fifo_model import FifoModel


class FifoDriver:
    def __init__(self, dut):
        self.dut = dut

    async def reset(self):
        self.dut.wr_en.value = 0
        self.dut.rd_en.value = 0
        self.dut.wr_data.value = 0
        self.dut.rst_n.value = 0

        for _ in range(3):
            await RisingEdge(self.dut.clk)

        await FallingEdge(self.dut.clk)
        self.dut.rst_n.value = 1

    async def cycle(self, wr_en, rd_en, wr_data=0):
        # Drive before the next rising edge
        await FallingEdge(self.dut.clk)

        self.dut.wr_en.value = wr_en
        self.dut.rd_en.value = rd_en
        self.dut.wr_data.value = wr_data

        await RisingEdge(self.dut.clk)


class FifoMonitor:
    def __init__(self, dut):
        self.dut = dut

    async def sample(self):
        # Let the outputs settle after the rising edge
        await Timer(1, units="ns")

        empty = int(self.dut.empty.value)

        return {
          "wr_en": int(self.dut.wr_en.value),
          "rd_en": int(self.dut.rd_en.value),
          "wr_data": int(self.dut.wr_data.value),
          "count": int(self.dut.count.value),
          "full": int(self.dut.full.value),
          "empty": empty,
          "rd_data": None if empty else int(self.dut.rd_data.value),
    	}


class FifoScoreboard:
    def __init__(self):
        self.model = FifoModel(8, 8)
        self.checks = 0
    def reset(self):
        self.model.reset()

    def check(self, observed):
        # Advance golden model using the transaction seen on the pins
        self.model.step(
            observed["wr_en"],
            observed["wr_data"],
            observed["rd_en"],
        )

        assert observed["count"] == self.model.count, (
            f"count mismatch: expected {self.model.count}, "
            f"got {observed['count']}"
        )

        assert observed["full"] == int(self.model.full), (
            f"full mismatch: expected {int(self.model.full)}, "
            f"got {observed['full']}"
        )

        assert observed["empty"] == int(self.model.empty), (
            f"empty mismatch: expected {int(self.model.empty)}, "
            f"got {observed['empty']}"
        )

        if not self.model.empty:
            assert observed["rd_data"] == self.model.head, (
                f"rd_data mismatch: expected {self.model.head:#04x}, "
                f"got {observed['rd_data']:#04x}"
            )

        self.checks += 1


async def run_cycle(driver, monitor, scoreboard, wr_en, rd_en, wr_data=0):
    await driver.cycle(wr_en, rd_en, wr_data)
    observed = await monitor.sample()
    scoreboard.check(observed)
    return observed


@cocotb.test()
async def test_fifo(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())

    driver = FifoDriver(dut)
    monitor = FifoMonitor(dut)
    scoreboard = FifoScoreboard()

    # Reset
    await driver.reset()
    scoreboard.reset()

    observed = await run_cycle(driver, monitor, scoreboard, 0, 0)
    assert observed["empty"] == 1

    # Read while empty: must be ignored
    observed = await run_cycle(driver, monitor, scoreboard, 0, 1)
    assert observed["count"] == 0
    assert observed["empty"] == 1

    # Fill FIFO completely
    for i in range(8):
        observed = await run_cycle(
            driver, monitor, scoreboard,
            1, 0, 0x10 + i
        )

    assert observed["count"] == 8
    assert observed["full"] == 1

    # Write while full: must be dropped
    observed = await run_cycle(
        driver, monitor, scoreboard,
        1, 0, 0xEE
    )
    assert observed["count"] == 8
    assert observed["full"] == 1

    # Simultaneous read/write while full:
    # read is accepted, write is dropped
    observed = await run_cycle(
        driver, monitor, scoreboard,
        1, 1, 0xE1
    )
    assert observed["count"] == 7

    # Refill back to full
    observed = await run_cycle(
        driver, monitor, scoreboard,
        1, 0, 0x55
    )
    assert observed["count"] == 8
    assert observed["full"] == 1

    # Drain FIFO completely
    for _ in range(8):
        observed = await run_cycle(
            driver, monitor, scoreboard,
            0, 1
        )

    assert observed["count"] == 0
    assert observed["empty"] == 1

    # Another read while empty
    observed = await run_cycle(
        driver, monitor, scoreboard,
        0, 1
    )
    assert observed["count"] == 0

    # Simultaneous read/write while empty:
    # write is accepted, read is ignored
    observed = await run_cycle(
        driver, monitor, scoreboard,
        1, 1, 0x66
    )
    assert observed["count"] == 1

    # Drain it again
    observed = await run_cycle(
        driver, monitor, scoreboard,
        0, 1
    )
    assert observed["empty"] == 1

    # Pointer wrap: move both pointers past DEPTH
    for i in range(12):
        await run_cycle(
            driver, monitor, scoreboard,
            1, 0, (0x70 + i) & 0xFF
        )

        await run_cycle(
            driver, monitor, scoreboard,
            0, 1
        )

    # Put a few entries in the FIFO
    for value in [0xA1, 0xA2, 0xA3]:
        await run_cycle(
            driver, monitor, scoreboard,
            1, 0, value
        )

    # Normal simultaneous read + write:
    # both accepted, count must stay the same
    before = scoreboard.model.count

    observed = await run_cycle(
        driver, monitor, scoreboard,
        1, 1, 0xB0
    )

    assert observed["count"] == before

    # Seeded random interleave
    rng = random.Random(4701)

    for _ in range(400):
        wr_en = rng.randint(0, 1)
        rd_en = rng.randint(0, 1)
        wr_data = rng.randint(0, 0xFF)

        await run_cycle(
            driver,
            monitor,
            scoreboard,
            wr_en,
            rd_en,
            wr_data,
        )

    # Reset again while the FIFO may contain data
    await driver.reset()
    scoreboard.reset()

    observed = await run_cycle(
        driver, monitor, scoreboard,
        0, 0
    )

    assert observed["count"] == 0
    assert observed["empty"] == 1
    assert observed["full"] == 0

    # Make sure the checker actually ran
    assert scoreboard.checks > 0
