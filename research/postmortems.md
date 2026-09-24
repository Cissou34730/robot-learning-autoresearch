# Research postmortems

## c1523389-1363-42a7-b973-1bc6847ac445 / Scientific strategy

**Current synthesis:** The baseline learned robust reach-and-hold behavior but
remains just below reliable attainment of the human objective: the selected
`checkpoint-100352` achieved 393/400 pooled research successes and 97% on the
latest disjoint panel. Experiment 2's target-coverage intervention produced no
gain over its transferred start and ended at 96%; the fixed task-reference
panel's 98% result is reused development evidence, not independent confirmation.

**Lessons and limits:** The residual failures are concentrated near angles
roughly -116 to -142 degrees, with the task-reference failures also at inner
radii of about 6.7-9.9 cm. The baseline training distribution began at 14 cm,
so the evidence is consistent with a coverage mismatch, but experiment 2 does
not establish that targeted oversampling fixes it or that coverage is the sole
cause. The failure episodes run to 500 steps and finish near the 1 cm
tolerance boundary, while the reward implementation currently assigns no
hold-capital forfeit when a nearly completed hold exits the tolerance band.

**Open questions:** It remains unresolved whether the residual pocket reflects
insufficient hold-stability learning, target-distribution coverage, or another
policy limitation, and whether the selected policy can reach the official
threshold without sacrificing its broad reach-and-hold behavior.

## c1523389-1363-42a7-b973-1bc6847ac445 / Experiment 1

**Result:** The fresh baseline produced a useful learned policy, but no measured
policy is ready for terminal assessment.

**Observed behavior:** `checkpoint-100352` scored 99.5% on the first 200-episode
research panel and 97.0% on the disjoint second panel, for 393/400 pooled
successes. `checkpoint-120832` scored 98.5% and 97.0%, for 391/400 pooled
successes. The paired comparison favored `checkpoint-100352` 2-0 over the
pooled 400 shared episodes. On the permanently reused task-reference panel,
the two policies scored 98.0% and 97.0%, respectively. `checkpoint-86016`
scored 95.0% on its research panel and 94.0% on the task-reference panel.

**Hypothesis assessment:** The baseline's learned-behavior expectation is
supported: late checkpoints substantially outperform the earlier reward-peak
candidate. The expectation that the first-panel lead would persist as
independent confirmation is weakened: the two late candidates tie at 97.0% on
the disjoint panel, and neither development panel declares the objective
reached. The fixed task-reference result is not independent evidence because
that panel is permanently reused.

**Interpretation:** `checkpoint-100352` is the best-supported working and
best-known lineage because it has the strongest pooled research result and the
paired lead, while remaining below the 98% objective on the independent panel.
The recipe is retained unchanged for provenance; further progress requires an
ordinary next experiment rather than more interpretation of this baseline.

**Evidence inspected:** `research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-100352-200ep-seed10000-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-100352-200ep-seed10200-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-120832-200ep-seed10000-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-120832-200ep-seed10200-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/task-reference-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/task-reference-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-86016-200ep-seed10000-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/task-reference-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-86016-task-reference-v1.json`;
`research/brief.md`.

## c1523389-1363-42a7-b973-1bc6847ac445 / Experiment 2

**Result:** The target-coverage intervention did not produce a better measured
policy, and the experiment-1 working lineage remains the most useful saved
policy.

**Observed behavior:** On the new disjoint 200-episode panel, the transferred
`checkpoint-100352` scored 194/200 (97.0%), matching the experiment-2 early
proxy-peak `checkpoint-10240` at 194/200. The final
`checkpoint-120832` scored 192/200 (96.0%). The paired comparison was 0-0
discordant wins for `checkpoint-10240` versus the transfer, and 0-2 in favor
of the transfer for the final checkpoint. All three remain below the official
98% threshold of 196/200; these are development measurements, not a final
assessment.

**Hypothesis assessment:** The hypothesis is weakened: expanding the training
radius to the official inner-radius range and oversampling the observed hard
angle sector produced no early improvement and did not preserve the transfer
level at the final checkpoint. The single disjoint panel does not identify
which failure mechanisms changed, so it does not prove that coverage is
irrelevant or that another coverage schedule could not help.

**Interpretation:** The intervention should not replace the experiment-1
working or best-known lineage. The current experiment-2 code is reverted so
the scientific surface matches the selected lineage; the measured challenger
artifacts are not retained because none provides a demonstrated future-use
advantage. Further training remains an ordinary subsequent experiment, not a
decision made in this closure.

**Evidence inspected:** `research/brief.md`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-2-checkpoint-100352-200ep-seed10400-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-2-checkpoint-10240-200ep-seed10400-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-2-checkpoint-120832-200ep-seed10400-f48545f83637.json`;
`research/checkpoints/challengers/c1523389-1363-42a7-b973-1bc6847ac445/experiment-2/inventory.json`.
