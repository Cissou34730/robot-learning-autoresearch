# Research postmortems

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success on the
official 200-episode reach-and-hold panel. The fresh PPO baseline reached
89.5% on research evaluation and 92.0% on the reused task-reference panel.
Unchanged continuation improved the retained policy to 96.5% (193/200) at
experiment-2 checkpoint-100352, while its later checkpoint reached 96.0%.
Experiment 3 measured the retained working policy at 96.5% on a different
seed-2 panel, but its continuation checkpoints reached only 86.5%, 89.5%, and
86.0%. The campaign therefore has substantial, reproducible-across-panels
evidence of progress over the baseline, but no development result reaches the
objective and none is official terminal evidence. This synthesis is provisional
memory rather than a prescribed direction.

**Lessons and limits:** The raw logs show that the unchanged 0.0003 learning
rate can produce strong proxy peaks followed by deterioration: experiment 2
fell from 0.95 success and reward 329.1 at step 100352 to 0.87 and 282.5 at
step 120832, and experiment 3 similarly declined from 0.99 and 342.5 at step
70656 to 0.94 and 318.2 at its endpoint
(`research/training_logs/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-2-attempt-1.log`,
`research/training_logs/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-3-attempt-1.log`).
Saved-policy success is not monotonic with those proxies: the experiment-2
checkpoint-100352 policy scored 193/200, and the same incumbent scored 193/200
on experiment 3's seed-2 panel, while every recorded failure in these detailed
evaluations exhausted the horizon. The matched experiment-3 comparison favored
the incumbent by 15 to 1 discordant episodes, but one continuation trajectory
and one independent panel do not establish distribution-wide degradation.
There is still only one training seed and no replication, so learning-process
variance and the generality of the continuation outcome are unresolved
(`research/results.jsonl`, `research/research_state.json`,
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-2-checkpoint-100352-200ep-seed1-a69293a214ad.json`,
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-3-working-200ep-seed2-a69293a214ad.json`).

**Open questions:** The evidence does not yet distinguish an update-size
problem from a representation or task-coverage limit. It also leaves the
robustness of the 96.5% result across training seeds and independent task draws
uncertain, and does not establish whether a changed PPO recipe can close the
remaining gap to 98%.

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

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 3

**Result:** Further unchanged PPO continuation did not improve the incumbent
and produced lower-scoring measured checkpoints. The existing working lineage
remains the useful policy and best-known designation.

**Observed behavior:** The experiment-3 proxy peak at checkpoint-70656
(training success 0.99, reward 342.54) achieved 173/200 (86.5%) on the fresh
seed-2 research panel. The late proxy rebound at checkpoint-110592
(success 0.97, reward 335.33) achieved 179/200 (89.5%), and the endpoint
checkpoint-120832 (success 0.94, reward 318.24) achieved 172/200 (86.0%).
The retained working policy achieved 193/200 (96.5%) on that same seed-2
panel. The paired comparison between working and checkpoint-110592 had 15
working wins versus 1 checkpoint win. Every failure in these four measurements
truncated at the 500-step horizon.

**Hypothesis assessment:** Partially supported. The original prediction allowed
either further improvement or a plateau/degradation after checkpoint-100352.
No continuation checkpoint exceeded the incumbent, and the same-panel paired
result supports a policy-specific loss for checkpoint-110592 under these
evaluation conditions. The proxy peak and rebound did not transfer to higher
measured task success, weakening the continued-optimization branch. Because
the evidence is one seed-2 panel from one continuation trajectory, it does not
establish distribution-wide degradation or disprove that another recipe could
improve the remaining gap.

**Interpretation:** Experiment 3 provides measured evidence against selecting
its continued checkpoints over the incumbent, while preserving the earlier
96.5% policy as meaningful progress toward the 98% objective. Training proxies
were again orthogonal to saved-policy task success: the strongest proxy
checkpoint was not the strongest measured policy. The working lineage and its
unchanged recipe should therefore be kept for the next investigation; the
development evidence is not terminal evidence and does not justify requesting
the irreversible official benchmark.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`; `research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-3/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-3-checkpoint-70656-200ep-seed2-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-3-checkpoint-110592-200ep-seed2-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-3-checkpoint-120832-200ep-seed2-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-3-working-200ep-seed2-a69293a214ad.json`.
