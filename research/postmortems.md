# Research postmortems

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned substantial reach-and-hold
behavior, but all three measured late checkpoints achieved 151/160 successes
(94.375%) on the shared panel, below the human objective of at least 98%. The
recorded failures for the selected checkpoint are concentrated in a negative
target-angle sector of roughly -151 to -119 degrees; four of nine failures also
have target radii below 11 cm, outside the baseline's 14-20 cm training range.
The late checkpoints were behaviorally tied, so checkpoint-100352 remains the
practical working and best-known lineage based on its stronger training proxy,
not independently superior measurement.

**Lessons and limits:** Training proxies identified the transition to useful
behavior, rising from 0.06 at checkpoint-75776 to 0.97 at checkpoint-100352,
but did not establish the task objective. Checkpoints 95232, 100352, and 120832
all scored 151/160 with zero discordant paired wins in both comparisons. The
failure geometry is from one 160-episode research panel, so it may reflect
sampling rather than a complete map of the task distribution. Development
measurements are not independent confirmation or an official benchmark result.

**Open questions:** Whether full-radius training and additional exposure to the
observed difficult angular sector improve generalization without moving failures
to other angles remains unresolved. Representation and reward changes have not
yet been distinguished from training-distribution effects, and performance
beyond the single development panel remains unknown.

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
