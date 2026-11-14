# Project 1 FINDINGS

## Released Mutation Results

Final released mutation score:

**found/total = 8/8 = 100%**

The clean FIFO RTL passed before mutation testing.

The final constrained-random and coverage-based testbench found all eight released mutants:

- `full_offbyone`
- `empty_offbyone`
- `ignore_full`
- `ignore_empty`
- `count_wr_dec`
- `rd_data_wrptr`
- `mem_corrupt`
- `wrptr_wrap_early`

## Mutation Analysis

There were no surviving mutants in the final released pool. Because the final result was 8/8, the two cases below are representative fault analyses showing what part of the suite exposes them and what would be missing in a weaker suite.

### `full_offbyone`

This mutant asserts `full` one entry too early.

A suite that only writes and reads data without checking occupancy and flags could miss this fault.

The current scoreboard compares the DUT `full` output and `count` against the reference model every cycle. The coverage model also drives the FIFO through partial and full occupancy, making the incorrect full boundary observable.

This is mainly an **observability** risk in a weaker testbench because the bad flag may occur but go unchecked.

### `wrptr_wrap_early`

This mutant wraps the write pointer one entry too early.

Simple write/read tests that never run long enough to wrap the internal pointers could miss it.

The current suite repeatedly reads and writes enough data for the FIFO pointers to wrap. The reference-queue scoreboard checks the visible head data and FIFO ordering, so incorrect pointer movement eventually produces a data-order mismatch.

This is mainly a **reachability** risk in a weaker testbench because pointer wrap must first be reached before the corruption can become observable.

## Residual Risk

### Reachability

The released mutation pool is 8/8, but the constrained-random regression does not exhaust every possible FIFO transaction history.

Very long sequences, unusual combinations of reset and traffic, or behaviors that require a specific long history may still remain unreachable in the current regression.

The fixed seed makes the regression reproducible but also means one run explores only one deterministic random sequence.

### Observability

The scoreboard checks FIFO occupancy, `full`, `empty`, and the visible FIFO head against the reference model.

A fault that affects an internal state but never propagates to one of those checked outputs could remain undetected.

The functional coverage model also shows which modeled scenarios were exercised, but 100% coverage only means all bins in the chosen model were hit. It does not prove that every possible FIFO behavior or implementation fault has been tested.

## Conclusion

The final released score is **8/8 = 100%**, and the functional coverage target is closed.

These results provide evidence that the suite exercises the important FIFO boundary conditions and detects the released fault classes, but they do not constitute exhaustive proof of correctness.
