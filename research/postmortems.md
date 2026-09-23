# Research postmortems

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned substantial reach-and-hold
behavior late in training, but the three measured late checkpoints each achieved
151/160 successes (94.375%), below the human objective of at least 98%. The
measured checkpoints were indistinguishable on their shared panel, so
checkpoint-100352 is selected as the practical working and best-known choice
because it had the strongest training success proxy, not because its measurement
was independently superior.

**Lessons and limits:** Training proxies identified the transition to useful
behavior, rising from 0.06 at checkpoint-75776 to 0.97 at checkpoint-100352,
but did not establish the task objective. Checkpoints 95232, 100352, and 120832
all scored 151/160, with zero discordant paired wins in both comparisons. This
is one research-evaluation panel only; it is not independent confirmation and
is not an official benchmark result. The baseline establishes a useful starting
point, while the remaining failures and generalization beyond this panel are
unresolved.

**Open questions:** Which training or task-learning changes can close the
remaining approximately 5.6 percentage-point gap to the objective, and whether
the measured residual failures are concentrated in particular target geometries
or episode conditions remain unknown.

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
