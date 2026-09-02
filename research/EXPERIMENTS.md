# Experiment log

| # | Date | Change | Hypothesis | Candidate success | Seeds passed | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-09-02 | Fresh baseline | Establish the initial baseline for the human-defined objective. | 18.5 | - | measured as requested; awaiting researcher analysis |
| 2 | 2026-09-02 | Run fresh PPO training with ent_coef increased from 0.01 to 0.03, keeping the environment, reward, observations, optimizer and architecture unchanged. Compare endpoint success, reach rate and angle-sector coverage against experiment 1. | The baseline is collapsing into a narrow set of target angles because exploration is insufficient: only 41 of 200 episodes reached tolerance, concentrated in a few angle sectors, while policy entropy declined during training. The plausible alternative is that the baseline simply needs more optimization time; a fresh run with stronger entropy regularization tests whether angular coverage improves within the same budget. | 22.0 | - | measured as requested; awaiting researcher analysis |
