# Research postmortems

## 93fca4d6-78e6-41ed-a38d-36d3938ddeb1 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline remains the strongest learned
policy. The working and best-known checkpoint-100352 achieved 455/480
successes (94.7917%) across three disjoint research panels after the
experiment-2 control measurement. The target-coverage transfer produced
151/160 (94.375%) at both its training-proxy peak and final checkpoint, versus
152/160 (95.00%) for the parent on the same new panel.

**Lessons and limits:** The experiment-2 hypothesis is contradicted under the
tested continuation: expanding training radii to 6-20 cm and oversampling the
previously difficult angular sector did not improve held-out success, and each
transfer checkpoint lost the sole discordant paired episode to the parent.
Training proxies therefore remained insufficient for selecting a policy. The
fixed task-reference result for checkpoint-100352 was reused for selection and
is not independent confirmation; all development measurements remain below the
98% objective. This single transfer recipe does not establish that target
coverage can never help, nor does it identify whether representation or
optimization is the limiting factor.

**Open questions:** Which change to the learned representation, optimization,
or failure-directed training can close the remaining gap without degrading the
parent's broad-task behavior remains unresolved. The residual failure geometry
is descriptive evidence, not a causal diagnosis.

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
