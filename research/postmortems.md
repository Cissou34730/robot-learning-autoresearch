# Research postmortems

## 386870d9-6be7-4e11-8c36-f11b5e2f4cd4 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned useful reach-and-hold
behavior, but its measured task performance is only 54.0%-55.5% on the
development task-reference panel, far below the 98% objective. Performance is
strong for near targets and collapses for the outer radial range, so the
105472-step checkpoint is the most task-aligned measured baseline. Training
reward and training success are informative learning signals but do not select
the best task policy in this experiment.

**Lessons and limits:** On the fixed task-reference panel, the selected
checkpoint succeeds on 56/57 targets at 6-10 cm, 54/59 at 10-15 cm, and 1/84
at 15-20 cm. This is descriptive evidence from one baseline and one
development panel, not causal evidence about the source of the radial failure
and not official final assessment. The research panel gives 60.0% success for
the selected checkpoint, with the endpoint tied on its shared episodes; the
task-reference panel is the task-aligned basis for checkpoint selection.

**Open questions:** It remains unknown which changes to training coverage,
reward shaping, observations, or control behavior would address the outer-range
failures without degrading near-target reach-and-hold performance.

## 386870d9-6be7-4e11-8c36-f11b5e2f4cd4 / Experiment 1

**Result:** The baseline produced a partially capable learned policy but did
not approach the 98% human objective. The 105472-step checkpoint is retained
as the working and best-known measured baseline; no final benchmark is
requested.

**Observed behavior:** Training completed 120,832 steps against a requested
120,000. In the single training attempt, mean episode reward rose from -18.8
at 1,024 steps to a peak of 110.3 at 86,016 steps, then ended at 91.6.
Training success rose from 0% to 60%, and mean episode length fell from 500 to
309 steps. These are training signals, not task-success claims. Research
evaluation on 100 episodes at seed 9100 was 59.0% at 86,016 steps and 60.0%
at both 105,472 and 120,832 steps. The paired comparisons recorded one
endpoint win over 86,016 and a tie between 120,832 and 105,472, with only one
discordant episode in the former comparison.

On the fixed 200-episode task-reference panel, success was 54.0% at 86,016,
55.5% at 105,472, and 55.0% at 120,832. Successful episodes completed in
about 112-113 steps, while every failure used all 500 steps and truncated.
For 105,472, success was 56/57 (98.2%) at 6-10 cm, 54/59 (91.5%) at 10-15
cm, and 1/84 (1.2%) at 15-20 cm. The coarse angular bins ranged from 51.9%
to 62.2%, without the same sharp separation seen by radius. The task panel
therefore supplies a partial and unexpected signal: the baseline reaches and
holds many near targets, while outer targets almost uniformly fail; the
reward-peak checkpoint was not the best task-reference checkpoint, and the
endpoint's higher training success did not improve task-reference success.

**Hypothesis assessment:** Supported for the baseline's type-specific purpose
of establishing an initial reference and showing measurable learning from a
fresh run. Partially supported for progress toward the human objective:
measured task success is well above an untrained reference implied by the
early training behavior, but 55.5% on the development panel is far below
98%. The evidence weakens any interpretation that reward magnitude or
training success alone identifies a policy satisfying the task. It does not
identify a causal explanation for the radial deficit, and the task-reference
panel is development evidence rather than the official final verdict.

**Interpretation:** The policy has learned a reliable local reach-and-hold
solution for inner targets, but the learned behavior does not cover the
official radial range. The late checkpoint at 105,472 is selected because it
has the highest task-reference success among the measured candidates; its
one-success advantage over the endpoint is small, while both late checkpoints
are indistinguishable on the research panel. Keeping the unchanged recipe
preserves a valid baseline for a subsequent intervention, but the current
policy is not ready for terminal assessment.

**Evidence inspected:** `research/results.jsonl`;
`research/research_state.json`; `research/evaluations/386870d9-6be7-4e11-8c36-f11b5e2f4cd4/evaluation-386870d9-6be7-4e11-8c36-f11b5e2f4cd4-experiment-1-checkpoint-86016-100ep-seed9100-ffdccdbf3357.json`;
`research/evaluations/386870d9-6be7-4e11-8c36-f11b5e2f4cd4/evaluation-386870d9-6be7-4e11-8c36-f11b5e2f4cd4-experiment-1-checkpoint-105472-100ep-seed9100-ffdccdbf3357.json`;
`research/evaluations/386870d9-6be7-4e11-8c36-f11b5e2f4cd4/evaluation-386870d9-6be7-4e11-8c36-f11b5e2f4cd4-experiment-1-checkpoint-120832-100ep-seed9100-ffdccdbf3357.json`;
`research/evaluations/386870d9-6be7-4e11-8c36-f11b5e2f4cd4/task-reference-386870d9-6be7-4e11-8c36-f11b5e2f4cd4-experiment-1-checkpoint-86016-task-reference-v1.json`;
`research/evaluations/386870d9-6be7-4e11-8c36-f11b5e2f4cd4/task-reference-386870d9-6be7-4e11-8c36-f11b5e2f4cd4-experiment-1-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/386870d9-6be7-4e11-8c36-f11b5e2f4cd4/task-reference-386870d9-6be7-4e11-8c36-f11b5e2f4cd4-experiment-1-checkpoint-120832-task-reference-v1.json`;
the experiment 1 training-log query over steps 0-120,832.
