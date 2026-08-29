# Research postmortems

No experiments recorded.

## Experiment 1

**Result:** The fresh PPO baseline achieved 0.00% pooled benchmark success at both requested measurements.

**Observed behavior:** Training reward improved from -101 to -47.1 and explained variance reached 0.686, but measured policies failed essentially immediately, with failed hold of 0.1/100 and 0.0/100 steps.

**What was learned / do NOT retry:** Reward and value learning alone did not produce benchmark behavior; do not treat improving training reward as evidence of reach precision or sustained hold.

**Recommended next experiment class:** Test whether excessive PPO exploration is blocking exploitation and precise hold control before changing the reward or task.
