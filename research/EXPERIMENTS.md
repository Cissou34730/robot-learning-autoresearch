# Experiment log

| # | Date | Change | Hypothesis | Success | Closest cm | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-08-28 | Fresh PPO baseline | Establish the initial fixed-evaluator baseline. | 95.0 | 0.07938184312329896 | kept |
| 2 | 2026-08-28 | Reduce PPO learning rate | The baseline's late-training degradation and falling policy standard deviation indicate policy drift or premature collapse; reducing PPO learning rate to 0.0001 while transferring the accepted policy should preserve the strong behavior and improve final held-out success. | 98.5 | 0.14550245847722193 | kept |
