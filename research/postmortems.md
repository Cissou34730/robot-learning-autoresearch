# Research postmortems

## 59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed / Scientific strategy

**Current synthesis:** Experiment 2's fresh baseline (auto baseline, 120,832 completed steps, trained on target radii 0.14-0.20 m only) produced a stable late-training plateau. Its leading measured policy, checkpoint-100352, scores 97.5% (195/200, seed 20000) and 95.5% (382/400, seed 21000) on two disjoint research panels and 98.0% (196/200) on the reused protected task-reference panel. Pooled research success is 577/600 = 96.2%, below the 98% objective, so the objective is not yet met. The residual error is strongly localized: on the seed-21000 panel the [-150, -120) degree sector scores 63.4% (26/41) and [-120, -90) scores 96.6%, while every other 30-degree sector is 100%; the human-owned task-reference panel independently shows the same pattern (all four failures between -116 and -128 degrees; 82.4% in [-150, -120)). Radius does not stratify the leader's success (6-20 cm bands 93-98%). The measured late plateau is behaviorally homogeneous: checkpoint-100352 and checkpoint-110592 have zero discordant outcomes over 400 shared episodes, and checkpoint-120832 zero over 200. Training-time proxies were unreliable for selection: checkpoint-86016 held the run's maximum ep_rew_mean (164) with training success 0.42 and measured 94.0%, whereas across the plateau ep_rew_mean declined from about 168 to about 112 while success_rate stayed 0.93-0.96.

**Lessons and limits:** Restricting training to 0.14-0.20 m did not by itself create a small-radius generalization deficit for the leading checkpoint; the limiting deficit is angular, not radial. The angular-sector failure is reproduced by the independent human-owned evaluator, so it is a property of the policy and task rather than of the researcher environment. Model selection must use measured task outcomes, not training success_rate or ep_rew_mean. Limits: one training seed and one recipe; only five of 24 checkpoints measured; two disjoint research panels plus the reused task-reference panel; small per-sector episode counts; no causal attribution of the sector failure.

**Open questions:** What mechanism causes the [-150, -90] degree deficit (reach failure versus hold loss; kinematic branch or observation ambiguity)? Would training on the full official 0.06-0.20 m distribution, a longer schedule, or targeted sampling of the failing sector remove the residual deficit? Is the 98.0% task-reference result a genuine performance peak or panel variance?

## 59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed / Experiment 2

**Result:** A fresh baseline trained on 0.14-0.20 m reaches 96.2% pooled research success (577/600) and 98.0% on the reused task-reference panel; the 98% objective is not met, and residual failures concentrate in a single angular sector.

**Observed behavior:**
- Candidate inventory records 24 exported checkpoints; training success is 0 for all checkpoints through 75,776 steps and rises through the 90k-121k plateau to 0.93-0.97.
- checkpoint-100352: research_evaluation seed 20000 = 195/200 (97.5%), seed 21000 = 382/400 (95.5%); task_reference = 196/200 (98.0%).
- checkpoint-120832: seed 20000 = 195/200 (97.5%). checkpoint-110592: seed 21000 = 382/400 (95.5%). checkpoint-115712: seed 21000 = 378/400 (94.5%). checkpoint-86016: seed 20000 = 188/200 (94.0%).
- Paired comparisons: checkpoint-100352 vs checkpoint-120832 0 discordant outcomes over 200 episodes; checkpoint-110592 vs checkpoint-100352 0 discordant over 400; checkpoint-115712 vs checkpoint-100352 0 vs 4 discordant over 400; checkpoint-86016 vs checkpoint-100352 0 vs 7.
- Failure geometry for checkpoint-100352 on seed 21000: success by 30-degree angle band is [-180,-150) 93.9%, [-150,-120) 63.4%, [-120,-90) 96.6%, and 100% in all other bands. Failures are either reach failures (min distance 0.7-1.5 cm, never within the 1 cm tolerance) or reach-then-lose-hold failures (max held 1-2 steps, one interruption).
- Failure geometry for checkpoint-100352 on task_reference: all four failures at angles -116 to -128 degrees, final distance 0.99-1.33 cm; all other bands 100%.
- checkpoint-100352 success by radius on seed 21000: 6-8 cm 96.0%, 8-10 93.0%, 10-12 98.3%, 12-14 94.2%, 14-16 94.9%, 16-18 96.2%, 18-20 96.4% (no radial gradient).
- checkpoint-86016 (seed 20000) fails differently: 6-8 cm band 81.1%, with large in_tolerance_steps and hold_interruptions (e.g. episode seeds 20106, 20176), i.e. oscillation in and out of tolerance rather than failure to reach.
- Training log: ep_rew_mean peaks at 164-168 near 86k-88k steps and declines to about 112 by 120,832 while success_rate stays 0.93-0.96; std declines from about 0.51 to 0.40.

**Hypothesis assessment:** The baseline-establishment hypothesis is supported: a trainable policy was produced and measured. The type-specific question of the measurement rounds, whether the restricted-radius fresh baseline generalizes to the full official 0.06-0.20 m distribution and whether a saved checkpoint reaches the 98% objective, is partially supported. Generalization across the radius range largely holds (no radial gradient for the leader), and the leading checkpoint reached 97.5% on one panel and 98.0% on the reused task-reference panel. However, the round-2 prediction that the leader would remain at or above 98% on a disjoint panel is contradicted: it scored 95.5% there, and the pooled research estimate is 96.2%, below the objective. No measured checkpoint convincingly satisfies the 98% criterion. Limits: only five of 24 checkpoints measured, two disjoint research panels, one training seed and recipe, and the reused task-reference panel is selection-contaminated and not privileged. The localized sector finding is descriptive and not causally attributed.

**Interpretation:** The experiment produced a strong but sub-objective baseline. Its residual error is not driven by the restricted training radius; it is concentrated in the angular sector roughly [-150, -90] degrees, worst at [-150, -120), and is reproduced by the independent protected evaluator on a different panel. This points to a configuration-specific control or observation limitation in that sector rather than a distribution-coverage gap. The late plateau is behaviorally stable and homogeneous, so further selection among those checkpoints is unlikely to change the picture materially, while the reward and success proxies disagree and cannot guide selection. The next experiment should target the residual angular-sector failure, plausibly by training on the full official distribution and/or with a longer or sector-targeted schedule.

**Evidence inspected:**
- `research/brief.md`
- `research/checkpoints/challengers/59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed/experiment-2/inventory.json`
- `research/evaluations/59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed/evaluation-59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed-experiment-2-checkpoint-100352-200ep-seed20000-543af51fd137.json`
- `research/evaluations/59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed/evaluation-59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed-experiment-2-checkpoint-100352-400ep-seed21000-543af51fd137.json`
- `research/evaluations/59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed/evaluation-59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed-experiment-2-checkpoint-110592-400ep-seed21000-543af51fd137.json`
- `research/evaluations/59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed/evaluation-59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed-experiment-2-checkpoint-115712-400ep-seed21000-543af51fd137.json`
- `research/evaluations/59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed/evaluation-59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed-experiment-2-checkpoint-120832-200ep-seed20000-543af51fd137.json`
- `research/evaluations/59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed/evaluation-59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed-experiment-2-checkpoint-86016-200ep-seed20000-543af51fd137.json`
- `research/evaluations/59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed/task-reference-59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed-experiment-2-checkpoint-100352-task-reference-v1.json`
- `research/results.jsonl`
- `robot_learning/scenario/training_environment.py`
- `robot_learning/scenario/evaluation.py`
- `robot_learning/benchmark/spec.py`
