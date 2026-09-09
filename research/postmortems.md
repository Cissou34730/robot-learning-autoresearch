# Research postmortems

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Scientific strategy

**Direction:** Improve near-threshold official-task success by addressing the
geometries that still fail, prioritizing training coverage of the official
6-20 cm radius range rather than extending the current recipe past its observed
peak.

**Lessons and limits:** The fresh baseline reached 98.0% on the protected
development panel at 100,352 steps, but fell to 97.0% at 120,832 steps. The
100,352-step policy also reached 98.0% on the 200-episode research panel with
seed 7300 and 97.5% with seed 8400. Its four protected-panel failures were all
at radii from 6.7 to 9.9 cm; the final checkpoint added two failures and
remained at 97.0%. The researcher training environment currently samples only
14-20 cm, whereas evaluation samples the official 6-20 cm range. These
observations support a radius-coverage intervention, but do not establish that
the training range caused the failures. The development panels are not the
official final benchmark.

**Open questions:** Can expanding or rebalancing training toward the 6-10 cm
region remove the inner-radius failures without degrading performance at larger
radii? Is the remaining angular concentration a separate control or
representation limitation?

**Conditional next steps:** In the next preparation phase, test a changed
training target distribution that includes the full official radius range,
with checkpoint measurements near the current 100,352-step peak and the
protected task-reference panel. If inner-radius performance improves while
outer-radius success is retained, continue that direction; otherwise inspect
angle-conditioned control behavior before choosing another intervention.

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Experiment 2

**Result:** The fresh baseline produced a near-threshold learned policy. The
100,352-step checkpoint achieved 98.0% on the protected task-reference
development panel and 97.75% pooled success over two 200-episode research
panels. The completed 120,832-step checkpoint achieved 97.0% on both research
seeds and on the task-reference panel.

**Observed behavior:** The run completed 120,832 steps and its training proxy
peaked at 0.97 at 100,352 steps before ending at 0.95. The 100,352-step
checkpoint had four task-reference failures, at target radii 6.734, 7.243,
9.915, and 9.355 cm; the final checkpoint had those same difficult cases plus
two additional failures. Research diagnostics show a mixture of never reaching
tolerance and reaching it only briefly or interrupting the required hold.
The 21 unmeasured checkpoints remain unmeasured, not failed policies.

**Hypothesis assessment:** This baseline was intended to establish feasibility,
not test a changed scientific intervention. It partially supports feasibility:
one checkpoint met the 98% development-panel threshold and the independent
task-reference execution agreed with the research evaluation. It does not
support treating the objective as robustly achieved because the final
checkpoint was 97.0%, the peak policy was below 98% on one research panel, and
the failures are concentrated in a distinct part of the official distribution.
No causal claim about the training range is warranted from this single recipe.

**Interpretation:** The best measured policy is the 100,352-step checkpoint,
not the final checkpoint. The current training implementation samples only
14-20 cm (`robot_learning/scenario/environment.py`), while the official task
and evaluations cover 6-20 cm. The concentration of failures at 6-10 cm makes
full-radius training coverage the strongest concrete next development
opportunity, while the angle and hold diagnostics leave room for alternative
explanations.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`, the five research-evaluation artifacts and three
task-reference artifacts under
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/`,
`research/scenario.md`, `robot_learning/scenario/environment.py`, and
`robot_learning/scenario/evaluation.py`.
