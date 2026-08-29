# Experiment log

| # | Date | Change | Hypothesis | Candidate success | Seeds passed | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-08-29 | Fresh PPO baseline | Establish the initial baseline for the human-defined objective. | 0.0 | - | measured as requested; awaiting researcher analysis |
| 2 | 2026-08-29 | Switch the fresh training algorithm from PPO to SAC while preserving the corrected task, observations, reward, and policy architecture. | The baseline's dominant limitation is poor continuous-control exploration and credit assignment: deterministic evaluation never entered the 1 cm band, while training reward improved and then settled into repeatable limit-cycle behavior far from the target. SAC's off-policy replay and entropy-regularized exploration will learn useful reaching behavior more reliably than the single-rollout PPO baseline. | - | - | invalid; researcher changes preserved |
