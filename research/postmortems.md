# Research postmortems

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Scientific strategy

**Direction:** Improve robust official-task success from the experiment-6
100,352-step full-radius policy by making target geometry explicit in the
observation, especially for the remaining negative-angle inner-radius reach and
hold failures. The action-transition penalty is retained as a useful foundation,
but the next change should target the residual representation/control behavior
rather than repeat reward-only variants.

**Lessons and limits:** The fresh baseline reached 98.0% on the protected
development panel at 100,352 steps, but fell to 97.0% at 120,832 steps. The
experiment-3 radius-coverage candidate reached 98.5% on the same
task-reference panel, reducing some inner-radius failures but adding one
outer-radius failure; its paired 400-episode research result remained 96.5%.
Experiment 4's focused angle oversampling and experiment 5's full hold-exit
forfeiture both degraded paired research and task-reference success, so those
tested recipes are not useful practical directions. Experiment 6's
ACTION_DELTA_COST_COEFFICIENT=0.02 candidate at 100,352 steps scored 96.75%
and 96.5% on the two paired research panels versus 96.5% and 96.25% for the
working parent, with one candidate win and no parent wins on each panel. It
also scored 99% on the protected task-reference panel versus the parent's
98.5%, fixing the parent's outer-radius failure while retaining two
negative-angle inner-radius failures. However, interrupted holds stayed at
nine on each comparable research panel, and the 120,832-step candidate
regressed to 96.5% while keeping the same 99% task-reference result. The
intervention therefore supplies a modest practical improvement signal but does
not establish that command jitter caused the failures. Training proxy success
is not a sufficient selection signal, and all measurements remain development
evidence rather than the official final benchmark.

**Open questions:** Can an observation or control-trajectory change improve the
remaining negative-angle inner-radius cases without sacrificing the
experiment-6 outer-radius repair? The current evidence does not distinguish an
inverse-kinematics observation limitation from angle-conditioned control
behavior or training variability, and it does not establish robust 98% success
outside the development panels.

**Conditional next steps:** Retain the experiment-6 100,352-step policy as the
comparison reference, keep the full-radius recipe and mild transition penalty,
and test a fresh policy with explicit normalized target radius and sine/cosine
angle features. Require paired research evaluation and independent task-reference
evidence. If this representation does not materially improve negative-angle
failures without broad degradation, revisit angle-conditioned control or
training variability instead of repeating angle oversampling, hold-exit
forfeiture, or comparable action-penalty measurement.

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

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Experiment 5

**Result:** Full forfeiture of accumulated hold-progress credit did not
improve the transferred full-radius policy. The 100,352-step candidate scored
94.0% on the paired 400-episode research panel and the 120,832-step candidate
scored 95.25%, versus 96.5% for the unchanged working parent. Task-reference
success was 95.5% and 96.0%, respectively.

**Observed behavior:** The proposal predicted fewer interrupted holds and
negative-angle failures, comparable reach-failure counts, and at least 98%
success. At 100,352 steps, the candidate had 24 failures: 19 interrupted
holds and 5 never-reached cases, compared with the parent’s 14 failures
(9 interrupted and 5 never-reached). At 120,832 steps it had 19 failures
(16 interrupted and 3 never-reached); it fixed parent failures on episodes
209 and 327 but added seven failures on other episodes, leaving 12 failures
shared with the parent. The candidate’s failure concentration remained
predominantly negative-angle, while its task-reference failures changed
between checkpoints and remained above the 2% target. Training proxy success
reached 1.0 at an intermediate checkpoint and ended at 0.99, but this did not
predict held-out task success.

**Hypothesis assessment:** Contradicted under the tested transferred recipe.
The 100,352-step checkpoint worsened the paired research result by 2.5
percentage points and increased interrupted failures. The later checkpoint
partially recovered the result and reduced the total failure count, but still
trailed the parent by 1.25 points, retained more interrupted failures, and
missed 98% on the task-reference panel. This weakens the practical hold-exit
reward explanation and is more consistent with a remaining observation or
angle-conditioned control limitation. One transferred run does not establish
that every hold reward formulation is ineffective or identify the cause of the
degradation.

**Interpretation:** The paired research panel, episode diagnostics, and
independent task-reference panel provide proportionate evidence for the
reward question; further measurement of the unmeasured intermediate
checkpoints is unlikely to change the lineage choice because neither measured
candidate beats the parent. Restore the experiment-3 working recipe and
checkpoint. The campaign should continue only with a concrete observation or
control-trajectory opportunity grounded in the recurring negative-angle
failures, rather than another comparable hold-reward or angle-oversampling
run.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/postmortems.md`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-5-working-400ep-seed9200-ffdccdbf3357.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-5-checkpoint-100352-400ep-seed9200-ffdccdbf3357.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-5-checkpoint-120832-400ep-seed9200-ffdccdbf3357.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-5-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-5-checkpoint-120832-task-reference-v1.json`,
and `robot_learning/scenario/reward.py`.

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

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Experiment 6

**Result:** The mild action-transition penalty produced a modest improvement
signal at the 100,352-step checkpoint, but did not establish robust 98%
research success or the predicted reduction in hold interruptions.

**Observed behavior:** This was a transferred training run from the
experiment-3 working policy, changing only the reward with a
`ACTION_DELTA_COST_COEFFICIENT=0.02` term on consecutive clipped physical
actions. On the two comparable 400-episode research panels, the 100,352-step
candidate scored 96.75% and 96.5%, versus 96.5% and 96.25% for the parent.
Each paired panel had one candidate win and no parent wins. Candidate failures
were 13 and 14 versus 14 and 15 for the parent; interrupted holds remained at
nine on each panel, while never-reached failures fell from five to four on each.
The 120,832-step candidate scored 96.5% on its research panel, with 11
interrupted and three never-reached failures. Both candidate checkpoints scored
99% on the independent task-reference development panel, versus 98.5% for the
parent. The candidate fixed the parent's failure at radius 18.240 cm but
retained the two negative-angle inner-radius failures at 9.915 and 9.355 cm.
Training proxy success reached 1.0 at an intermediate checkpoint and ended at
0.96; this did not predict the held-out research result.

**Hypothesis assessment:** Partially supported under the tested transferred
recipe. The 100,352-step policy improved every comparable aggregate outcome
slightly and reached 99% on the task-reference panel, supporting a practical
benefit from the change. However, it remained below 98% on both research
panels, did not reduce interrupted holds, and the later checkpoint regressed on
research evaluation. The evidence therefore does not support the stronger
claim that command jitter was the main cause of the residual hold failures,
and one transferred run cannot establish a causal effect.

**Interpretation:** The 100,352-step candidate is the strongest measured policy
and is preferable to the prior working lineage, while the mild transition term
is worth retaining as a foundation. The remaining failures are still
negative-angle and inner-radius cases, so another comparable reward or
measurement round is less useful than a concrete observation or control-
trajectory intervention. The official objective remains unestablished because
all evidence is from development panels.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/postmortems.md`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-6-checkpoint-100352-400ep-seed9200-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-6-checkpoint-100352-400ep-seed9300-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-6-checkpoint-120832-400ep-seed9200-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-6-working-400ep-seed9200-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-6-working-400ep-seed9300-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-3-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-6-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-6-checkpoint-120832-task-reference-v1.json`,
`robot_learning/scenario/reward.py`,
`robot_learning/scenario/environment.py`, and
`robot_learning/scenario/evaluation.py`.
