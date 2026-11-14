# Project 1 AI Log

## AI Use

I used AI to help draft the FIFO coverage model and constrained-random verification approach for Project 1.

The main areas where AI helped were:

- defining occupancy and operation coverage bins
- choosing useful coverage crosses
- reusing the HW4 layered driver/monitor/scoreboard structure
- reusing the HW5 constrained-random stimulus
- reusing the HW6 functional-coverage testbench
- identifying important FIFO corner cases to verify
- organizing the verification plan and mutation findings

## Prompt / Request

I asked AI to help build a Project 1 verification plan and constrained-random FIFO testbench based on my previous HW4, HW5, and HW6 work.

The target cases included:

- empty, partial, and full occupancy
- idle, write, read, and simultaneous read/write
- write while full
- read while empty
- pointer wrap-around
- FIFO ordering
- seeded constrained-random traffic

## Prediction Before Running

Before running the suggested coverage model and stimulus, I expected that the main risk would be missing boundary combinations.

In particular, I thought the test might fail to reach:

- full × write
- empty × read
- simultaneous read/write near a boundary
- pointer wrap-around

I also expected that a random-only approach could spend too much time in the middle occupancy states and not stress empty and full often enough.

## Evidence After Running

The final constrained-random test ran successfully on the clean RTL.

The functional coverage model reached all 12 occupancy × operation combinations.

The released mutation result was:

**found/total = 8/8 = 100%**

The suite found:

- `full_offbyone`
- `empty_offbyone`
- `ignore_full`
- `ignore_empty`
- `count_wr_dec`
- `rd_data_wrptr`
- `mem_corrupt`
- `wrptr_wrap_early`

This showed that the stimulus reached the important boundary and ordering cases and that the scoreboard made those faults observable.

## Fixes and Changes

The first copied constrained-random test came from the earlier HW5 work.

I then replaced it with the HW6 version because that version already included the functional coverage model and closure reporting.

The Makefile also had to be changed because the copied HW6 Makefile assumed it still lived inside `code/tb/`. The Project 1 version was updated so the DUT and Python model paths point back to the course `code/` directory.

The mutation command also required a symlink under `code/tb/` because the course mutation tool assumes testbenches are located under that structure.

## What AI Did Not Prove

AI-generated suggestions were not treated as proof that the verification was correct.

Every change was run against the clean RTL, the coverage results were measured, and the suite was scored against the released mutant pool.

The final evidence was based on the actual simulation, coverage, and mutation results rather than the AI-generated plan alone.
