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

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 2

**Result:** Continuing the unchanged PPO recipe produced a useful
improvement, but did not establish the 98% objective. Checkpoint-100352 is
selected as the working and best-known lineage; checkpoint-120832 is retained
as a near-tied alternative.

**Observed behavior:** The continuation's training proxies peaked at
checkpoint-100352: training success was 0.95, mean reward was 329.1, and mean
episode length was 158. At checkpoint-120832 they were 0.87, 282.5, and 187.
On the matched 200-episode research panel with seed 1, checkpoint-100352
achieved 193/200 (96.5%) and checkpoint-120832 achieved 192/200 (96.0%).
The prior working policy achieved 179/200 (89.5%) under the same evaluation
semantics. All 7, 8, and 21 failures respectively exhausted the 500-step
horizon. Paired comparisons had 2 versus 1 discordant wins for
checkpoint-100352 versus checkpoint-120832, 15 versus 1 for
checkpoint-100352 versus the prior working policy, and 15 versus 2 for
checkpoint-120832 versus the prior working policy.

**Hypothesis assessment:** Partially supported. The prediction that unchanged
continuation could improve measured task behavior was supported: both measured
continuation checkpoints substantially exceeded the prior working policy on
the matched research panel. The prediction that later optimization would
continue reducing horizon-exhaustion failures was not supported by the
observed endpoint relative to checkpoint-100352: the endpoint had one more
failure and one fewer success. The proxy decline is evidence of a late
training change, but the one-panel, single-seed measurements do not establish
policy degradation or a plateau across the task distribution.

**Interpretation:** Training-time proxies and measured task success were not
monotonic: the proxy peak was the strongest measured policy, while the later
endpoint retained nearly the same task performance. The continuation therefore
validated additional useful progress from the retained representation under
these settings, without showing that extending the unchanged recipe past
checkpoint-100352 is beneficial. The 96.5% research measurement is meaningful
development progress but remains below the 98% human objective, and it is not
official terminal evidence. Retaining checkpoint-120832 preserves a plausible
near-equivalent branch for future development without treating the reused
task-reference panel or checkpoint ordering as a lineage criterion.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-2/inventory.json`;
`research/training_logs/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-2-attempt-1.log`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-2-checkpoint-100352-200ep-seed1-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-2-checkpoint-120832-200ep-seed1-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-2-working-200ep-seed1-a69293a214ad.json`.
