# Experiment log

| # | Date | Change | Hypothesis | Candidate success | Seeds passed | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-09-02 | Fresh baseline | Establish the initial baseline for the human-defined objective. | 38.5 | - | measured as requested; awaiting researcher analysis |
| 2 | 2026-09-03 | Train a fresh PPO policy with ent_coef reduced from 0.03 to 0.001, leaving the environment, network, rollout, and other optimizer settings unchanged. | The baseline's high PPO entropy regularization is maintaining excessive exploration and destabilizing the policy after its mid-training peak; reducing it should preserve or improve reach-and-hold success through the end of the budget. If late success still collapses or does not exceed the baseline peak, reward alignment or target-geometry coverage remains the more plausible cause. | 30.5 | - | measured as requested; awaiting researcher analysis |
