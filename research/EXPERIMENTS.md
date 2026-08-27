# Experiment log

| # | Date | Change | Hypothesis | Success | Closest cm | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-08-27 | Fresh PPO baseline | Establish the initial fixed-evaluator baseline. | 98.0 | 0.19675557021817883 | kept |
| 2 | 2026-08-27 | Reduce PPO entropy coefficient | Reducing PPO ent_coef from 0.01 to 0.003 will reduce late-training policy drift and preserve the high-performing reaching and holding behavior after the observed peak. | 98.0 | 0.24806672913799985 | reverted (no improvement) |
| 3 | 2026-08-27 | Reduce PPO learning rate | Reducing PPO learning_rate from 0.0003 to 0.0001 will reduce late-training policy drift and preserve the high-performing reaching and holding behavior after the observed early peak. | 96.5 | 0.20161129657534882 | reverted (no improvement) |
| 4 | 2026-08-27 | Evaluate PPO selection checkpoints every rollout | Reducing selection_eval_every_steps from 20000 to 1024 will capture transient early-training PPO peaks, preventing late-training degradation from replacing the strongest policy and improving the fixed held-out evaluation. | 97.5 | 0.21309024200448223 | reverted (no improvement) |
