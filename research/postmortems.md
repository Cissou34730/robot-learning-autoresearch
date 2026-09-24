# Research postmortems

## 93fca4d6-78e6-41ed-a38d-36d3938ddeb1 / Scientific strategy

**Current synthesis:** The unchanged PPO checkpoint-100352 remains the strongest
learned policy, with 455/480 successes (94.7917%) across three disjoint
research panels. The experiment-2 transfer checkpoints each achieved 151/160
(94.375%) on their new panel, below the parent control's 152/160 (95.00%).
Residual failures are concentrated in the negative-angle sector and include
both failure to reach and occasional hold interruption.

**Lessons and limits:** The baseline trains on radii 14-20 cm, narrower than the
official 6-20 cm range. The tested transfer recipe combined full-range
sampling with focused-sector oversampling and was contradicted, so it does not
settle whether full-range coverage learned from scratch is useful. Training
proxies have not reliably selected held-out policies; the 98% task-reference
result for checkpoint-100352 was reused for selection, and every disjoint
development result remains below the objective. Failure geometry is descriptive
and does not establish a causal bottleneck.

**Open questions:** Whether uniform full-range training from fresh
initialization generalizes better than the narrow-range baseline or the
failed transfer recipe remains unresolved. The relative roles of target
coverage, representation, and optimization in the residual failures are also
unknown.

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
