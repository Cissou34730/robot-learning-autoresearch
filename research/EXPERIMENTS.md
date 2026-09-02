# Experiment log

| # | Date | Change | Hypothesis | Candidate success | Seeds passed | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-09-02 | Fresh baseline | Establish the initial baseline for the human-defined objective. | 37.0 | - | measured as requested; awaiting researcher analysis |
| 2 | 2026-09-02 | Bias training target-angle resets to 75% in the lower half-plane and 25% in the upper half-plane, preserving the existing radius range, reward, episode mechanics, and all protected benchmark semantics. | The baseline's reach failures are primarily an exploration and coverage asymmetry: it reached only 19 of 100 lower-half targets versus 81 of 100 upper-half targets, while only 5 reached targets failed the hold. If the alternative explanation is an observation or action representation defect, reweighting target resets should not improve lower-half reach without degrading the learned upper-half behavior. | 9.0 | - | measured as requested; awaiting researcher analysis |
