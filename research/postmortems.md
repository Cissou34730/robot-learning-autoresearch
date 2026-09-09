# Research postmortems

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Scientific strategy

**Direction:** Improve robust official-task success by addressing the
angle-conditioned reach and hold instability that remains after matching
training coverage to the official 6-20 cm radius range. Use the
experiment-3 checkpoint at 100,352 steps as the current working policy while
testing that next direction.

**Lessons and limits:** The fresh baseline reached 98.0% on the protected
development panel at 100,352 steps, but fell to 97.0% at 120,832 steps. The
experiment-3 radius-coverage candidate reached 98.5% on that same
task-reference panel, reducing the parent’s four failures to two inner-radius
failures but adding one outer-radius failure. On the new 400-episode research
panel, candidate and parent had the identical 14 failures and both scored
96.5%; across the candidate’s three research panels it scored 97.25% pooled.
The 105,472-step candidate scored 98.0% on both 200-episode research panels
and the task-reference panel, so it did not improve on the 100,352-step
candidate. The remaining and paired-panel failures are concentrated in a
negative-angle region and often involve unstable or interrupted holds. Full
radius coverage therefore has a useful but limited signal: it can repair some
inner-radius cases, but the single transferred run does not establish a
causal effect or robustly satisfy the objective. Development panels are not
the official final benchmark.

**Open questions:** Can angle-conditioned control or hold-stability changes
remove the recurring negative-angle failures while preserving the candidate’s
inner-radius gains and larger-radius behavior? Is the residual limitation in
the observation representation, the reward, or the control trajectory?

**Conditional next steps:** In the next preparation phase, inspect the
angle-conditioned reach and hold diagnostics and test one concrete
researcher-owned intervention aimed at the recurring negative-angle failure
region, starting from the retained 100,352-step policy. Preserve the full
radius training coverage unless the new intervention shows a clear tradeoff;
reconsider the direction if it does not improve the paired-panel failure
pattern without sacrificing the task-reference result.

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

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Experiment 3

**Result:** Expanding training targets from 14-20 cm to the full 6-20 cm
range produced a partially improved but not robustly above-threshold policy.
The 100,352-step candidate is the strongest measured result and is selected
for continued development.

**Observed behavior:** The transferred 100,352-step candidate scored 98.5% on
the 200-episode protected task-reference panel, versus 98.0% for its parent.
It repaired the parent failures at 6.734 and 7.243 cm, retained failures at
9.355 and 9.915 cm, and added a failure at 18.240 cm. On the identical
400-episode research panel, candidate and parent both scored 96.5% and had
the same 14 failed episode identities. The candidate scored 98.5%, 97.5% and
96.5% on the 200, 200 and 400 episode research panels respectively, for
97.25% pooled success. The 105,472-step candidate scored 98.0% on each of
the two 200-episode research panels and on the task-reference panel. Most
paired-panel failures occurred at negative target angles and reflected either
failure to reach tolerance or repeated hold interruptions. The remaining 22
checkpoints were not measured.

**Hypothesis assessment:** Partially supported. The candidate met the
predicted 98% threshold on the task-reference development panel and reduced
some inner-radius failures, but it did not retain all outer-radius success,
did not improve the paired 400-episode research outcome, and did not show
robust 98% success across research panels. The result supports a useful
coverage signal under this transferred recipe, while weakening the claim that
radius coverage alone resolves the observed gap. Because this was one
changed, transferred run, these observations do not isolate coverage as a
causal mechanism.

**Interpretation:** Full-radius training is worth retaining as a foundation,
but the unchanged paired failure pattern indicates that the strongest next
opportunity is angle-conditioned reach and hold stability rather than more
comparable radius-only measurement. The 100,352-step candidate is preferable
to the 105,472-step candidate because it has the better task-reference result
and avoids the latter’s additional inner-radius failure.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/postmortems.md`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-3-checkpoint-100352-400ep-seed9200-ffdccdbf3357.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-3-working-400ep-seed9200-ffdccdbf3357.json`,
the experiment-3 task-reference artifacts, the experiment-2
100,352-step task-reference artifact, `research/scenario.md`,
`robot_learning/scenario/environment.py`, and
`robot_learning/scenario/evaluation.py`.
