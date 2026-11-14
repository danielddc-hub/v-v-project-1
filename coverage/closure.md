# Coverage closure — <FIFO> · <Dylan Hilaire, Daniel Delgado, Colby Toner>

> Coverage is a measure of what you *looked at*, never of what is *correct*.
> A closed model with a weak checker reports 100% and proves nothing. This file
> is the argument that your number means something — and the honest list of
> what it still cannot mean.

## 1. The number

|                             |                  |
|-----------------------------|------------------|
| Coverpoints closed          | 14 / 14          |
| Cross `top.occ_x_op` closed | 12 / 12 bins     |
| Other crosses closed        | 10 / 10 bins     |
| Target declared in my vplan | 100%             |
| Reached                     | 100% (36/36 bins)|
| Vectors to closure          | 288              |
| Vectors soaked past closure | 2,712            |

**How the report was produced:**
The coverage results were collected during the constrained-random simulation using cocotb-coverage. The test ran for 3,000 cycles, and the results were exported to coverage.yml using:

```bash
coverage_db.report_coverage(dut._log.info, bins=True)
coverage_db.export_to_yaml("coverage.yml")
```

## 2. The convergence argument

**Shape of the curve:** <Coverage reached 100% after 288 vectors. Most samples were at partial occupancy (2,673), while empty (172) and full (155) occurred less often.>

**The last bins to close, and what it took:**

| Bin                 | Why it was rare                         | What I changed to hit it |
|---------------------|-----------------------------------------|--------------------------|
| Full x Read (161)   | The FIFO was rarely full.               | No changes needed        |
| Full x Idle (163)   | Requires an idle operation whiole full. | No changes needed        |
| Empty x Write (288) | The FIFO was rarely empty.              | No changes needed        |

The existing constrained-random stimulus reached all bins without further changes.

**Why I stopped where I stopped:**

The test ran for 3,000 vectors, reaching full coverage after 288. The remaining 2,712 vectors helped check for errors that might take longer to appear.

## 3. Bin justification

Every `illegal` and `ignore` bin is a claim about the design. Each one needs an
authority — a line of `dut/specs/fifo.md`, or an argument you would defend.

| Bin         | illegal / ignore | The claim                                                                 | Authority (spec line, or the argument) |
|-------------|------------------|---------------------------------------------------------------------------|----------------------------------------|
| Wrap x idle | Ignore           | Neither pointer moves during an idle operation, so wrapping cannot occur. | FIFO specification, Behaviors 2–4.     |

**Corner bins that are legal and must be covered, not excluded:**

1. <Full x write>: The write is dropped because the FIFO is full (Behavior 2).
2. <Empty x read>: The read is ignored because the FIFO is empty (Behavior 3).
3. <Full x simulatenous>: The write is dropped, but the read is accepted (Behaviors 2-3).
4. <Empty x simultaneous>: The write is accepted, but the read is ignored (Behaviors 2-3).


## 4. What the cross is aimed at

A cross earns its place only if the interaction is where a bug would hide.

**The bug `top.occ_x_op` is aimed at:**

The cross checks that different read and write operations are tested at empty, partial, and full occupancy. This helps catch errors like accepting writes when full or reads when empty.

**Additional crosses:**

1. <top.occ_x_simul:> checks simultaneous read/write requests at different occupancy levels.
2. <top.wrap_x_op:> checks pointer wrapping during read, write, and simultaneous operations.

**A bug it would *not* see, even fully closed:**

The crosses do not check the actual FIFO data. Data corruption could go unnoticed without the scoreboard comparing rd_data against the golden model.

## 5. Coverage vs. correctness — the blind spots

My model is closed and my suite is green. That still establishes nothing about:

1. **<Specific data values>** — <The coverage model does not track individual data values, so errors caused by certain values might be missed.>
2. **<Long operation sequences>** — <The test runs for 3,000 cycles, but some errors may require longer or specific sequences of operations.>
3. **<Reset conditions>** — <The coverage model does not track reset during read or write operations, so errors involving these combinations might be missed.>

**Transients in particular:** <The scoreboard checks the FIFO outputs 1 ns after the rising clock edge. A temporary glitch that disappears before this check could go undetected.>

## 6. Correlation with mutation

Cross-reference `FINDINGS.md`. The interesting case is divergence.

|                      | found / total  |
|----------------------|----------------|
| Before closing holes | 8/8 (HW4)      |
| After closing holes  | 8/8 (Project 1)|

**Did closing holes raise the score?**

Both HW4 and Project 1 detected all 8 released mutants, so there was no improvement in the mutation score. We did not document any coverage holes that needed to be closed. The Project 1 coverage model reached 100%, but this does not guarantee that all possible FIFO errors will be detected.

---

- [ ] Every `illegal` and `ignore` bin in section 3 cites an authority.
- [ ] Section 5 names blind spots of this design, not of coverage in general.
- [ ] The numbers here agree with `coverage.yml` and `FINDINGS.md`.
