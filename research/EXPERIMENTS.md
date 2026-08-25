# Experiment log

**Best so far:** 55% (experiment 15: re-baseline at 60k budget, committed champion config; all pre-notice 30k scores retired)

## Lessons that shaped the current best (condensed from experiments 0-11)

- Exp 1 (n_steps 256, reverted): more updates alone did not help; noise-driven contact.
- Exp 2 (action cost 0.05): +8 pts. Flailing now pays; policy more directed.
- Exp 3 (SUCCESS_BONUS 25 -> 5): +26 pts. Sparse/dense scale balance stabilized value fitting — binding-constraint fix.
- Exp 4 (hard near-zone gate, reverted): discontinuity at the gate poisoned advantages. Lesson: shaping must be continuous in distance.
- Exp 5 (exponential closeness potential C=2, lambda=0.05): +4 pts, median 3.9 cm. Potential-based shaping works; healthiest training curve so far.
- Exp 6 (C=4): +4 pts, median 3.7 cm. Doubling C converted near-misses without instability.
- Exp 7 (C=8): 53%, reverted. Coefficient scaling exhausted around C=4.
- Exp 8 (ent_coef 0.01): +2 pts to 55%. Current champion; fresh-seed audit confirmed 54% on unseen targets.
- Exp 9 (n_epochs 20, reverted): faster start but mid-run overfit and exploration lock-down; optimization intensity is not the constraint.
- Exp 10 (ent_coef 0.02, reverted): collapsed hard; ent_coef peaked near 0.01.
- Exp 11 (lambda 0.08, reverted): collapsed to 9%. The sharp lambda=0.05 focus near target is load-bearing; do not stretch it outward.

## Remaining untried lever classes

gamma / gae_lambda (credit assignment), net_arch (capacity), PROGRESS_COEFFICIENT scale-up,
ent_coef fine-tune downward (0.005).

Full original notes for experiments 0-11: see `research/archive.md`.

Diff summary (exp 13, filled after edit, before training): `robot_learning/train.py | 2 +-` (`"net_arch": [64, 64]` -> `[128, 128]`).

## Results table

| # | Date | Change | Hypothesis | Success % | Mean dist (cm) | Median dist (cm) | Verdict |
|---|------|--------|------------|-----------|----------------|------------------|---------|
| 13 | 2026-08-25 | train.py: POLICY_KWARGS net_arch [64, 64] -> [128, 128] (no other change) | Network capacity is the last untried lever class: the champion's value function plateaus at explained_variance 0.75-0.88 and deterministic eval fails precisely on behind-arm targets whose approach requires representing both IK branches around the fully-extended reset singularity, which a [64,64] tanh net may underfit. Doubling layer width quadruples parameter count for that multi-modal value landscape without touching reward balance, exploration, lambda, or credit assignment (each already tuned or falsified). Expect higher success rate via far-tail conversion and lower mean distance; if capacity is not binding, watch for slower fitting within the fixed 30k-step budget. | 46 | 6.9 | 4.8 | reverted (worse) |
| 14 | 2026-08-25 | train.py: PPO_HYPERPARAMETERS adds use_sde=True (gSDE exploration; no other change) | Three coefficient tweaks then a capacity change all failed, so this switches exploration KIND: replace per-step i.i.d. Gaussian action noise with state-dependent (gSDE) noise whose samples are constant within a rollout, giving temporally smooth, directed exploration. Mechanism targets the observed binding constraint: median 3.7 cm hovering at the threshold suggests training-time action jitter blurs the final approach, and the deterministic eval policy inherits a jitter-corrupted mean. Expect near-miss conversion; risk is slower early fitting within the fixed 30k budget (same trap as exp 13). | 12 | 10.9 | 11.1 | reverted (worse) |

Diff summary (exp 13, filled after edit, before training): `robot_learning/train.py | 2 +-` (`"net_arch": [64, 64]` -> `[128, 128]`).

Note (exp 13): hypothesis half-right, result worse — the bigger net DID fit value better (explained_variance hit 0.91-0.95 late, above every prior run) but rollout success was only 0.53 and still climbing steeply at the 30k cap (ep_len_mean falling 145 -> 119), i.e. classic under-convergence from slower per-sample learning. With timesteps frozen at 30k, network size acts as an optimization-speed knob, and exps 1/9 already showed optimization throughput is not what's binding — so capacity cannot pay off inside this fixed budget. Do not revisit wider nets unless the timestep budget changes; remaining untried levers are PROGRESS_COEFFICIENT scale-up (sparse/dense rebalancing risk) and ent_coef fine-tuning downward (0.005).

Diff summary (exp 14, filled after edit, before training): `robot_learning/train.py | 1 +` (adds `"use_sde": True` to PPO_HYPERPARAMETERS).

Note (exp 14): gSDE collapsed learning (rollout success plateaued ~0.20 vs ~0.5+ for every Gaussian run): noise sampled once per rollout acts as a persistent per-episode action bias on this torque-driven arm, which the policy must un-learn rather than average out, and std barely decayed (0.99 -> 0.72 over 30k) so the deterministic mean never sharpened. Lesson: i.i.d. Gaussian action noise is load-bearing here — it averages to zero within an episode and lets the mean controller converge. Do not switch exploration mechanisms again; safest remaining levers are ent_coef 0.005 fine-tune and PROGRESS_COEFFICIENT scale-up.

| 15 | 2026-08-25 | re-baseline at 60k budget: committed champion config re-run completely unchanged, only --timesteps 60000 (per budget change notice) | The budget doubling directly targets the falsified binding constraint: exps 9/13/14 were under-converged at the 30k cap, not bad ideas. Expect the unchanged champion config to convert near-misses with double the samples, scoring above its retired 55% and defining the new comparison baseline. | 55 | 6.5 | 3.0 | new best (baseline reset) |
| 16 | 2026-08-25 | train.py: POLICY_KWARGS net_arch [64, 64] -> [128, 128] (no other change; first width retest under the 60k budget) | Exp 13's width failure was purely under-convergence (rollout success still climbing steeply at the 30k cap, best-ever explained_variance 0.91-0.95) and its own note deferred a retest until the budget changed; exp 15 then proved the [64,64] champion genuinely plateaus (~0.71 rollout success by 28k) so extra samples alone cannot convert near-misses. The wider net's slower per-sample fitting should now have room to finish within 60k, converting near-threshold hoverers and behind-arm far-misses via better multi-modal value representation. Expect >55%; if rollout success again stalls well below the champion's ~0.71 by 60k, width is falsified independent of budget. | | | | |

Diff summary (exp 15, before training): intentionally EMPTY — no code edit by design (budget notice consequence #2 mandates the current committed configuration unchanged); verified `robot_learning/` clean in git status before training.

Diff summary (exp 16, before training): `robot_learning/train.py | 2 +-` (`"net_arch": [64, 64]` -> `[128, 128]`).

Note (exp 15): hypothesis falsified — doubling the budget did NOT lift eval success: same 55% as the retired 30k score, rollout success plateaued ~0.71 by 28k steps and merely oscillated (0.63-0.78) through 60k despite healthy explained_variance (0.8-0.94), median stuck at exactly 3.0 cm. The asymptote is a real plateau, not under-convergence, so "needs longer training" is falsified beyond ~30k for this config. Next-session levers should shift to the remaining structural candidates: observation/joint-space target signal or target-radius curriculum (both need env un-freeze) — coefficient jitter on the current surface looks exhausted.
| 18 | 2026-08-25 | POLICY_KWARGS net_arch [64,64] -> [128,128] (retry at 60k budget) | Exp 13 showed the wider net still climbing at the 30k cutoff; the doubled budget removes the convergence constraint that killed it. Expect capacity to convert far-tail failures now. | 54 | 6.3 | 3.0 | reverted (worse) |
