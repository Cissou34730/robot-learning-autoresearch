# Experiment log

| # | Date | Change | Hypothesis | Success | Closest cm | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-08-27 | Fresh PPO baseline | Establish the initial fixed-evaluator baseline. | 98.0 | 0.19675557021817883 | kept |
| 2 | 2026-08-27 | Reduce PPO entropy coefficient | Reducing PPO ent_coef from 0.01 to 0.003 will reduce late-training policy drift and preserve the high-performing reaching and holding behavior after the observed peak. | 98.0 | 0.24806672913799985 | reverted (no improvement) |
