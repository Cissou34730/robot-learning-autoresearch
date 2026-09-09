# Research postmortems

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Scientific strategy

**Direction:** Improve robust official-task success by addressing the
angle-conditioned reach and hold instability that remains after matching
training coverage to the official 6-20 cm radius range. The focused
angle-oversampling intervention is rejected; use the experiment-3 checkpoint
at 100,352 steps as the current working policy while testing a concrete
hold-stability or angle-conditioned control/representation intervention.

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
causal effect or robustly satisfy the objective. Experiment 4's 50%
hard-sector angle oversampling reduced comparable research success from 96.5%
to 91.5% and produced 34 rather than 14 failures, with most candidate
failures involving interrupted holds; task-reference success also fell below
98% at both measured checkpoints. Training proxy success is not a sufficient
selection signal. Development panels are not the official final benchmark.

**Open questions:** Can a hold-stability or angle-conditioned
observation/control intervention remove the recurring negative-angle failures
while preserving the full-radius gains? Is the residual limitation in the
observation representation, the reward, or the control trajectory, and can
the next intervention avoid the broad degradation seen from angle
oversampling?

**Conditional next steps:** In the next preparation phase, start from the
restored experiment-3 checkpoint at 100,352 steps, preserve full-radius
training coverage, and test one concrete researcher-owned change to
hold-stability reward, observation, or control trajectory. Prefer an
intervention that directly targets the interrupted holds and evaluate it
against the paired negative-angle failures without sacrificing the
task-reference result. Reconsider this direction if a concrete intervention
does not improve the paired failure pattern.

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Experiment 4

**Result:** Oversampling the observed hard angle sector did not improve the
transferred full-radius policy. Both measured candidates scored 91.5% on the
400-episode paired research panel, versus 96.5% for the working parent, and
the task-reference candidates scored 94.5% and 93.5% at 115,712 and 120,832
steps respectively.

**Observed behavior:** The intervention was a transfer training run from the
experiment-3 checkpoint at 100,352 steps, with 50% of targets sampled from
-160 to -110 degrees and the remaining targets sampled uniformly over the
full angle range. On the identical research episodes, the 115,712-step
candidate had one win and 21 parent wins among 22 discordant episodes
(net wins -20); the 120,832-step candidate had two wins and 22 parent wins
among 24 discordant episodes (net wins -20). Each candidate had 34 research
failures, compared with 14 for the parent. In the diagnostic artifacts, 28
of the candidate failures involved reaching tolerance and then interrupting
the hold, while six never reached tolerance; the parent had nine interrupted
and five never-reached failures. The candidate therefore retained failures
in the targeted negative-angle region while adding failures at other angles
and radii. Training proxy success peaked at 0.94, but did not predict the
held-out research or task-reference result. The remaining 22 checkpoints
were not measured.

**Hypothesis assessment:** Contradicted under the tested transferred recipe.
The expected reduction in negative-angle reach and hold failures, paired
success near or above 98%, and preservation of the experiment-3 gains were
not observed. The paired comparison strongly favors the parent on this
development panel, and both task-reference results are below the 98% target.
This weakens targeted angular exposure as a useful standalone intervention in
this recipe; it does not identify whether observation, reward, control
trajectory, or training variability caused the degradation, and one run does
not rule out every angular curriculum.

**Interpretation:** The experiment-3 full-radius policy remains the strongest
available working and best-known lineage. More comparable angle-oversampling
measurement is not justified before changing the intervention. The strongest
supported development opportunity is a concrete researcher-owned change
aimed at hold stability or angle-conditioned control/representation, starting
from experiment 3 and retaining full-radius coverage. The official objective
remains unestablished because all current evidence is development evidence
and the candidate results are below threshold.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`, `research/training_logs/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/experiment-4-attempt-1.log`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-4-working-400ep-seed9200-6b923ebb0d16.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-4-checkpoint-115712-400ep-seed9200-6b923ebb0d16.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-4-checkpoint-120832-400ep-seed9200-6b923ebb0d16.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-4-checkpoint-115712-task-reference-v1.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-4-checkpoint-120832-task-reference-v1.json`,
`robot_learning/scenario/environment.py`, and
`robot_learning/scenario/evaluation.py`.

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
