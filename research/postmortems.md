# Research postmortems

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Scientific strategy

**Current synthesis:** The campaign objective remains at least 98% success on
the official 200-episode reach-and-hold panel. The fresh PPO baseline learned
substantial task behavior late in training, and checkpoint-120832 is the
strongest available policy at 89.5% on a fresh research panel and 92.0% on the
reused task-reference panel. The campaign therefore has clear progress toward
the objective, but no evidence that the objective has been reached.

**Lessons and limits:** The raw training log shows continued late improvement:
between steps 90112 and 120832, mean reward rose from about -770 to -168,
the training success proxy rose from 0.00 to 0.11, and mean episode length
fell from 500 to 469 (`research/training_logs/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-1-attempt-1.log`).
On matched 200-episode research evaluations, success rose from 85.5%
(171/200) at checkpoint-110592 to 89.5% (179/200) at checkpoint-120832, with
9 versus 1 discordant paired wins (`research/research_state.json` and
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-1-checkpoint-120832-200ep-seed0-a69293a214ad.json`).
The task-reference result is corroborating development evidence but uses a
reused, selection-contaminated panel. Its 16 failures all exhausted the
500-step horizon and cluster in this panel around 119-164 degrees across
near and far radii; this is descriptive evidence, not a causal or
distribution-wide diagnosis. The 22 unmeasured checkpoints, single training
seed, and absence of replication leave learning-process variability and the
eventual continuation trajectory unresolved.

**Open questions:** It remains unknown whether the unchanged PPO process can
continue reducing horizon-exhaustion failures from checkpoint-120832 or has
begun to plateau or degrade, whether the reference-panel angular pattern
persists on independent task draws, and whether a changed recipe is needed
after the behavior of continued optimization is understood.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 1

**Result:** The baseline produced a useful but not objective-satisfying
policy. Checkpoint-120832 is selected as the working and best-known lineage.

**Observed behavior:** Training proxies improved late: training success rose
from 0.00 at step 100352 to 0.05 at 110592 and 0.11 at 120832, while mean
episode reward improved from -479.3 to -168.5. The latest checkpoint achieved
179/200 (89.5%) on the research-evaluation panel; the preceding measured
checkpoint achieved 171/200 (85.5%) under the same evaluation semantics,
an 8-episode / 4-point improvement. The paired comparison had 9 latest-policy
wins versus 1 predecessor win across 10 discordant episodes. On the fixed
task-reference panel, checkpoint-120832 achieved 184/200 (92.0%). Every
failure in both detailed outcome sets truncated at 500 steps rather than
terminating successfully.

**Hypothesis assessment:** Partially supported. The baseline's measurement
question was whether late proxy improvement transferred to uninterrupted
reach-and-hold success and whether the latest checkpoint surpassed the prior
late checkpoint. Both observations occurred on the matched research panel,
so the transfer and relative-improvement claims are supported under those
settings. The result does not support claiming that the policy satisfies the
human objective: 89.5% and 92.0% development measurements are below 98%,
and neither development panel is the official verdict. The task-reference
result is consistent with the research evaluation but uses a reused panel,
and no causal claim about training duration or failure geometry is warranted.

**Interpretation:** The latest checkpoint is the best evidenced available
candidate and represents meaningful progress toward the human objective, but
the remaining failures are too frequent for terminal assessment to be
scientifically useful now. The baseline recipe should be kept with this
checkpoint so a later experiment can target the residual failures; the
baseline itself establishes behavior, not reproducibility or a causal
explanation.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-1/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-1-checkpoint-120832-200ep-seed0-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-1-checkpoint-110592-200ep-seed0-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/task-reference-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-1-checkpoint-120832-task-reference-v1.json`.
