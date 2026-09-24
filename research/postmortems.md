# Research postmortems

## 93fca4d6-78e6-41ed-a38d-36d3938ddeb1 / Scientific strategy

**Current synthesis:** The unchanged PPO checkpoint-100352 remains the strongest
learned policy, with 772/800 (96.5%) pooled successes across five disjoint
development panels. The three tested target-sampling interventions did not
improve it. Remaining failures are concentrated in the negative-angle sector
and include both failure to reach and occasional interruption after reaching.

**Lessons and limits:** The baseline trains on radii 14-20 cm rather than the
official 6-20 cm range, but both transfer and fresh full-range sampling
recipes were contradicted, and focused-angle transfer tied the parent early
then degraded after continued training. Training proxies have not reliably
selected held-out policies; the reused task-reference result cannot provide
independent confirmation, and pooled disjoint evidence remains below the 98%
objective. Failure geometry is descriptive and does not establish whether
coverage, reward, representation, or optimization is causal.

**Open questions:** It remains unknown whether the zero hold-exit forfeiture
leaves the learner insufficiently sensitive to brief departures from the
tolerance band, and whether improving that signal can reduce the residual
failures without sacrificing the established behavior elsewhere.

## 93fca4d6-78e6-41ed-a38d-36d3938ddeb1 / Experiment 1

**Result:** The baseline produced a useful but sub-target policy; checkpoint-100352
is selected as working and best known, with checkpoint-120832 retained as a
runner-up.

**Observed behavior:** The three measured checkpoints achieved 93.125%,
94.375%, and 94.375% on the first disjoint research panel for checkpoints
86016, 100352, and 120832 respectively. On the second disjoint panel,
checkpoint-100352 achieved 95.00% (152/160) and checkpoint-120832 achieved
93.75% (150/160). Their pooled distinct research-panel results were 303/320
(94.6875%) and 301/320 (94.0625%), with checkpoint-100352 winning two of two
discordant paired episodes. The reused task-reference panel reported 98.00%
for checkpoint-100352 and 97.00% for checkpoint-120832, but this is not
independent confirmation.

**Hypothesis assessment:** Partially supported. The baseline established that
the method can learn substantial reach-and-hold behavior, and late training
proxies corresponded to better measured policies than the reward-peak
intermediate checkpoint. However, no independent development measurement
reached the 98% objective, and the fixed-panel 98% result cannot establish
that objective because it was used in selection.

**Interpretation:** Checkpoint-100352 is the best-supported current lineage
because it generalizes slightly better than the final checkpoint on disjoint
episodes and avoids the unsupported inference that later training is better.
The evidence justifies preserving this policy for future work, but not
requesting the irreversible official assessment; a useful path toward the
remaining objective remains.

**Evidence inspected:** `research/brief.md`,
`research/research_state.json`,
`research/checkpoints/challengers/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/experiment-1/inventory.json`,
`research/evaluations/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/`,
`research/scenario.md`.

## 93fca4d6-78e6-41ed-a38d-36d3938ddeb1 / Experiment 2

**Result:** The target-coverage transfer did not improve the learned policy.
The existing checkpoint-100352 working lineage remains selected, and the
changed recipe is reverted.

**Observed behavior:** On the new disjoint panel covering episodes 4600-4759,
the parent achieved 152/160 successes (95.00%). Both the transfer
proxy-peak checkpoint-30720 and final checkpoint-120832 achieved 151/160
(94.375%). Each paired comparison had one discordant episode, won by the
parent. The experiment-2 training-success proxy peaked at 0.98 for
checkpoint-30720, but that proxy did not correspond to better held-out task
success. No development measurement reached the 98% objective.

**Hypothesis assessment:** Contradicted under the tested transfer recipe. The
predicted improvement from broader radii and focused angular exposure was
absent at both measured transfer checkpoints, with a small decrease relative
to the contemporaneous control. This is evidence against this specific
continuation and sampler mixture, not proof that every target-coverage
intervention would fail.

**Interpretation:** The parent is the best-supported reusable policy and should
remain both working and best known. The experiment's changed training
distribution did not resolve the residual failures, so its scientific recipe
should not be carried forward. No experiment-2 candidate is sufficiently
supported to retain as an alternative.

**Evidence inspected:** `research/brief.md`,
`research/research_state.json`,
`research/checkpoints/challengers/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/experiment-2/inventory.json`,
`research/evaluations/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/evaluation-93fca4d6-78e6-41ed-a38d-36d3938ddeb1-experiment-2-working-160ep-seed4600-f48545f83637.json`,
`research/evaluations/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/evaluation-93fca4d6-78e6-41ed-a38d-36d3938ddeb1-experiment-2-checkpoint-30720-160ep-seed4600-f48545f83637.json`,
`research/evaluations/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/evaluation-93fca4d6-78e6-41ed-a38d-36d3938ddeb1-experiment-2-checkpoint-120832-160ep-seed4600-f48545f83637.json`.

## 93fca4d6-78e6-41ed-a38d-36d3938ddeb1 / Experiment 3

**Result:** Fresh PPO training with uniform target radii over 6-20 cm did
not produce a useful challenger. The existing `working` checkpoint-100352
remains selected, the experiment-3 recipe should be reverted, and no
experiment-3 candidate merits retention.

**Observed behavior:** On the new disjoint 160-episode panel, the
experiment-3 checkpoint-100352 achieved 120/160 (75.0%) and the final
checkpoint-120832 achieved 117/160 (73.125%). The matched working control
achieved 158/160 (98.75%). The paired comparisons favored `working` by net
wins of 38 and 41 episodes, respectively. The fresh run's training-success
proxy remained at 0.01 at both measured late checkpoints, so its rising
training reward did not indicate comparable held-out task success.

**Hypothesis assessment:** Contradicted under the tested fresh
uniform-full-radius recipe. The predicted improvement over the narrow-radius
policy was absent; both measured challengers were 23.75 to 25.625 percentage
points worse than the contemporaneous control, and the final checkpoint was
slightly worse than the matched checkpoint. This rejects the tested recipe as
the next development direction, but does not prove that every fresh
full-range curriculum or target-coverage intervention will fail.

**Interpretation:** The working lineage is the best-supported reusable policy,
but its independent pooled disjoint evidence is still 613/640 (95.78125%),
below the 98% human objective. The fixed task-reference result is not
independent confirmation because it was used during selection. Closure should
therefore preserve `working` and the existing `best_known` designation,
restore the parent's scientific recipe, discard the experiment-3 challengers,
and leave any further training to a future ordinary experiment rather than
requesting the final benchmark now.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`,
`research/checkpoints/challengers/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/experiment-3/inventory.json`,
`research/evaluations/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/evaluation-93fca4d6-78e6-41ed-a38d-36d3938ddeb1-experiment-3-working-160ep-seed4800-f48545f83637.json`,
`research/evaluations/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/evaluation-93fca4d6-78e6-41ed-a38d3938ddeb1-experiment-3-checkpoint-100352-160ep-seed4800-f48545f83637.json`,
`research/evaluations/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/evaluation-93fca4d6-78e6-41ed-a38d-36d3938ddeb1-experiment-3-checkpoint-120832-160ep-seed4800-f48545f83637.json`.

## 93fca4d6-78e6-41ed-a38d-36d3938ddeb1 / Experiment 4

**Result:** Focused negative-angle training did not improve the working
policy. The existing `working` and `best_known` checkpoint-100352 lineages
remain selected, the changed recipe should be reverted, and no experiment-4
candidate merits retention.

**Observed behavior:** On the new disjoint panel covering episodes 5000-5159,
the working control and experiment-4 checkpoint-5120 both achieved 159/160
(99.375%), with no discordant paired episodes. The final checkpoint-120832
achieved 156/160 (97.5%); the working policy won all three discordant paired
episodes. The working lineage now has 772/800 pooled successes (96.5%) across
five disjoint research panels, which remains below the 98% objective.

**Hypothesis assessment:** Contradicted under the tested focused-angle
continuation. Oversampling the observed -180 to -90 degree sector produced no
held-out gain at the early proxy checkpoint and degraded performance after the
full continuation. The tied early-checkpoint score does not independently
justify selecting that lineage because the same panel supplied the selection
evidence; it only supports retaining the established parent. This does not
rule out every intervention on angular exposure, representation, or
optimization.

**Interpretation:** Preserve checkpoint-100352 as both working and best known,
restore the parent's scientific recipe, and discard the experiment-4
challengers. The latest panel independently confirms strong behavior for the
established lineage, but the pooled evidence is still below the human
objective, so the irreversible final benchmark should not be requested.
Further training belongs to a future ordinary experiment after this closure.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`,
`research/checkpoints/challengers/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/experiment-4/inventory.json`,
`research/evaluations/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/evaluation-93fca4d6-78e6-41ed-a38d-36d3938ddeb1-experiment-4-working-160ep-seed5000-f48545f83637.json`,
`research/evaluations/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/evaluation-93fca4d6-78e6-41ed-a38d-36d3938ddeb1-experiment-4-checkpoint-5120-160ep-seed5000-f48545f83637.json`,
`research/evaluations/93fca4d6-78e6-41ed-a38d-36d3938ddeb1/evaluation-93fca4d6-78e6-41ed-a38d-36d3938ddeb1-experiment-4-checkpoint-120832-160ep-seed5000-f48545f83637.json`,
`research/scenario.md`.
