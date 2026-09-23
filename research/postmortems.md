# Research postmortems

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned substantial reach-and-hold
behavior, but the standing parent achieved only 151/160 successes (94.375%) on
the disjoint experiment-2 panel, below the human objective of at least 98%.
The changed target-distribution recipe tied the parent at its measured
intermediate checkpoint and fell to 149/160 at the final checkpoint, so
checkpoint-100352 remains the practical working and best-known lineage.

**Lessons and limits:** Training proxies identified useful behavior but did not
establish the task objective or predict improvement from the distribution
change: the experiment-2 final proxy was 0.91 while its task result was below
the parent. The intermediate challenger and parent had zero discordant paired
wins; the final challenger lost two discordant episodes and won none. These
results are one 160-episode development panel and are not an official
benchmark result.

**Open questions:** Which representation or reward intervention can address the
remaining failures without sacrificing the broad reach-and-hold behavior
remains unresolved. Performance on the full official distribution remains
unknown until the separate final assessment.

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Experiment 1

**Result:** The fresh PPO baseline produced a useful learned policy, but did not
meet the human objective in development measurement.

**Observed behavior:** Training success was 0.93 at checkpoint-95232, 0.97 at
checkpoint-100352, and 0.95 at checkpoint-120832. Each checkpoint achieved
151/160 successes (94.375%) on research-evaluation episodes 4200-4359.
Both paired comparisons had zero discordant wins, so the measurements showed no
detectable late-training regression or improvement. The measurements were
development evidence and not the official final assessment.

**Hypothesis assessment:** The baseline hypothesis was partially supported:
training established substantial task behavior and a clear late-learning
transition, but the resulting policy remained below the required 98% success
rate. The equal shared-panel measurements do not establish that the
100352-step checkpoint is intrinsically better than the other measured
checkpoints.

**Interpretation:** The baseline recipe is a viable starting point but appears
to plateau below the objective under the tested conditions. Checkpoint-100352
is selected as working and best-known because it combines the tied measured
performance with the strongest training success proxy; this choice is
pragmatic rather than independently confirmed. Further training or a changed
recipe should be treated as a subsequent experiment after this closure.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/5521c88b-2345-470f-a9dd-547cf3b569b7/experiment-1/inventory.json`;
`research/results.jsonl`;
`research/research_state.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-1-checkpoint-95232-160ep-seed4200-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-1-checkpoint-100352-160ep-seed4200-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json`.

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Experiment 2

**Result:** The changed training target distribution did not improve the learned
policy. On a disjoint 160-episode panel, the standing parent and the
45,056-step challenger each achieved 151/160 successes (94.375%), while the
120,832-step final challenger achieved 149/160 (93.125%). All remain below the
98% objective.

**Observed behavior:** The parent and intermediate challenger had no discordant
paired wins. The final challenger lost two discordant episodes to the parent
and had no wins. Its failures included no-reach cases in the targeted
negative-angle sector and interrupted holds elsewhere, despite the changed
recipe's 0.91 final training success proxy. Training proxies therefore did not
predict a task-measured improvement.

**Hypothesis assessment:** The hypothesis was contradicted under the tested
conditions: the expected disjoint-panel improvement to at least 157/160 was
not observed, and the final challenger was five percentage points below that
target and 1.25 points below the parent. This does not rule out every
distribution intervention because the evidence is one transferred run and one
160-episode panel, but it weakens this specific target-distribution route.

**Interpretation:** The standing `working` and `best_known` lineage remains the
most useful saved policy at 151/160 on the disjoint panel. The experiment's
training-only distribution change should be reverted rather than carried into
the next experiment; the residual gap warrants a different scientific
intervention after closure. No experiment-2 challenger has evidence of future
reuse beyond the existing lineage.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`; `research/results.jsonl`;
`research/checkpoints/challengers/5521c88b-2345-470f-a9dd-547cf3b569b7/experiment-2/inventory.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-2-checkpoint-120832-160ep-seed4360-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-2-checkpoint-45056-160ep-seed4360-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-2-working-160ep-seed4360-f48545f83637.json`.
