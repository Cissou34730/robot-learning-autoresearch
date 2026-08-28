# Research postmortems

> One section per experiment, appended after reading the training summary and
> evaluation diagnostics.

## Experiment 37

**Result:** The linearly decayed learning-rate proposal was rejected before training because current_params.json was detected as an unexpected worktree change.

**Observed behavior:** No candidate was trained and the accepted champion remained unchanged.

**What was learned / do NOT retry:** Proposal validation must begin from a clean research surface; do not retry the learning-rate change before calibration.

**Recommended next experiment class:** Calibration is mandatory now because the training-seed noise floor is still unmeasured.
