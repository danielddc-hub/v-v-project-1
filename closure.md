# HW6 Coverage Closure

The FIFO coverage model reached 100% of the occupancy x operation cross.

The cross includes:
- empty x idle/write/read/simul
- partial x idle/write/read/simul
- full x idle/write/read/simul

This means the test exercised all 12 combinations in the coverage model, including important cases like write while full and read while empty.

The coverage was sampled using the FIFO occupancy before the clock edge with the requested operation. This is important because boundary cases like full x write only exist before the edge changes the FIFO state.

100% coverage does not prove the FIFO is completely correct. It only proves that every case included in this coverage model was exercised.

The scoreboard still checks count, full, empty, and rd_data every cycle to determine whether the DUT behavior matches the golden model.

The model can still miss bugs that depend on things it does not measure, such as exact middle occupancies, specific data values, reset combinations, or long sequences of operations.

The test continues running after coverage closure so bugs that take longer to become visible can still be detected.
