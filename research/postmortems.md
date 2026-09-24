# Research postmortems

## 93fca4d6-78e6-41ed-a38d-36d3938ddeb1 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned a strong but
sub-target reach-and-hold policy. The working and best-known checkpoint-100352
achieved 303/320 successes (94.6875%) across two disjoint research panels,
while the retained checkpoint-120832 achieved 301/320. In the pooled
diagnostics, all 17 working-policy failures occurred in the -180 to -90 degree
target-angle quadrant.

**Lessons and limits:** Late training proxies tracked useful behavior but did
not establish the human objective, and continuing the baseline beyond
checkpoint-100352 did not improve independent success. The fixed
task-reference result of 98% for checkpoint-100352 was reused for selection,
so it is not independent confirmation. The baseline training distribution
also covered only 14-20 cm, narrower than the official 6-20 cm range; the
failure geometry is descriptive of 320 development episodes and does not
establish causality.

**Open questions:** Whether broader radius coverage and greater exposure to
the observed difficult angular sector improve held-out reach-and-hold success
without sacrificing performance elsewhere remains unresolved. It is also
unknown whether the remaining failures are primarily a target-coverage issue
or a limitation of the learned representation and optimization.

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
