# Verification plan — Synchronous FWFT FIFO

**Author:** Dylan Hilaire  
**Spec version:** `dut/specs/fifo.md`  
**Date:** November 13, 2026

## 1. Scope

**In scope:** Verification of the parameterized synchronous first-word-fall-through FIFO, including reset behavior, write/read acceptance, overflow and underflow protection, simultaneous read/write, status flags, occupancy count, data ordering, pointer wrap-around, and FWFT head behavior.

**Out of scope:** Asynchronous clock-domain behavior, timing closure, analog effects, and implementation-specific internal logic that is not part of the written FIFO contract.

**Assumptions about the environment:** The FIFO is synchronous to the rising edge of `clk`. Reset is active-low and synchronous. Transactions use legal signal values. Default verification configuration uses `WIDTH=8` and `DEPTH=8`.

## 2. Feature list

| ID | Feature | Req | Priority | How it is verified |
|----|---------|-----|----------|--------------------|
| F1 | Reset clears occupancy and sets empty/full correctly | Behavior 1 | H | directed + scoreboard |
| F2 | Write accepted only when not full | Behavior 2 | H | directed + CRV + scoreboard |
| F3 | Write while full is dropped without corruption | Behavior 2 | H | directed + coverage |
| F4 | Read accepted only when not empty | Behavior 3 | H | directed + CRV + scoreboard |
| F5 | Read while empty is ignored | Behavior 3 | H | directed + coverage |
| F6 | `rd_data` shows the current head whenever non-empty | Behavior 3 | H | scoreboard |
| F7 | Simultaneous read/write keeps count unchanged when legal | Behavior 4 | H | directed + CRV + coverage |
| F8 | `full == (count == DEPTH)` | Behavior 5 | H | scoreboard |
| F9 | `empty == (count == 0)` | Behavior 5 | H | scoreboard |
| F10 | FIFO ordering is strictly first-in-first-out | Behavior 6 | H | reference-queue scoreboard |
| F11 | Pointer wrap-around preserves ordering | Corner cases | H | directed + CRV |
| F12 | Random interleaving preserves ordering and occupancy | Corner cases | M | seeded CRV |

## 3. Coverage model

| ID | Coverpoint | Bins | Why these bins |
|----|-----------|------|----------------|
| C1 | Occupancy | empty, partial, full | Boundary behavior is where overflow/underflow bugs hide |
| C2 | Requested operation | idle, write, read, simultaneous read+write | Covers every control combination |
| C3 | Write condition | accepted, blocked-full | Proves overflow protection is exercised |
| C4 | Read condition | accepted, blocked-empty | Proves underflow protection is exercised |
| C5 | Pointer wrap | no-wrap, wrap | Wrap bugs may preserve simple reads/writes but corrupt ordering |

**Crosses**

| ID | Cross | The interaction it is aimed at |
|----|-------|-------------------------------|
| X1 | occupancy × operation | Detects missing boundary combinations such as full × write and empty × read |
| X2 | occupancy × simultaneous read/write | Exercises read/write interaction near empty, partial, and full conditions |
| X3 | pointer-wrap × operation | Targets ordering bugs that appear only when pointers wrap |

**Illegal / ignore bins:** No legal occupancy/operation corner from the FIFO spec should be ignored. An observed `count` outside `0..DEPTH` is illegal. Undefined control behavior during reset will be tracked separately rather than counted as normal FIFO traffic.

## 4. Test matrix

| Test | Features | Kind | Pass criterion |
|------|----------|------|----------------|
| Reset test | F1, F8, F9 | directed | count=0, empty=1, full=0 after reset |
| Fill to full | F2, F8, F10 | directed | all writes accepted until DEPTH and ordering preserved |
| Write while full | F3 | directed | count and queue contents unchanged |
| Drain to empty | F4, F9, F10 | directed | values read in FIFO order until empty |
| Read while empty | F5 | directed | count remains 0 and no underflow occurs |
| FWFT head check | F6, F10 | directed | head data matches reference queue while non-empty |
| Simultaneous read/write | F7 | directed + CRV | both operations occur and count remains unchanged when legal |
| Pointer wrap test | F10, F11 | directed + CRV | data order remains correct across wrap |
| Seeded constrained-random regression | F2–F12 | CRV | scoreboard has zero mismatches and target coverage closes |

## 5. Risk and spec ambiguity

| # | Ambiguity or risk | Where in the spec | How I resolved it | Residual |
|---|-------------------|-------------------|-------------------|----------|
| 1 | Boundary behavior during simultaneous read/write at empty/full requires careful interpretation | Corner cases | Test boundary combinations separately and compare against the written acceptance rules | Hidden implementation-specific corner bugs may remain |
| 2 | Random traffic may spend too little time near empty/full | Project CRV requirement | Bias constraints toward near-empty and near-full occupancy | Some long sequences may still be rare |
| 3 | Pointer-wrap bugs may require long history before becoming visible | Ordering + corner cases | Include directed wrap traffic and random soak cycles | Very long-history bugs may still survive |
| 4 | Coverage closure does not prove correctness | Project coverage requirement | Require both scoreboard correctness and mutation-quality evidence | Unmodeled behavior can still remain |

## 6. Closure criteria

- Functional coverage target: **100%** of the coverage model in section 3
- Mutation target: **at least 90%** found on the grading pool, with a goal of all released mutants found
- Scoreboard: zero mismatches against the reference queue
- Seeded regression: same seed and command reproduce the same result
- What I will report as **not verified**: exhaustive proof over every possible long transaction history, timing closure, CDC behavior, and implementation details not specified by the FIFO contract
