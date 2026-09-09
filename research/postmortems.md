# Research postmortems

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Scientific strategy

**Direction:** Improve robust official-task success from the experiment-6
100,352-step full-radius policy with a semantically compatible target-relative
or kinematics-aware intervention for the recurring negative-angle failures.
Experiment 10 gives a modest signal that an explicit distance cue can repair
some transferred failure episodes, but it is not sufficient by itself. If
development continues, the next experiment should preserve full-radius
coverage, the mild transition penalty, and the saved-policy contract while
testing a concrete branch- or hold-aware change against the remaining failure
set.

**Lessons and limits:** The fresh baseline reached 98.0% on the protected
development panel at 100,352 steps, but fell to 97.0% at 120,832 steps. The
experiment-3 radius-coverage candidate reached 98.5% on the same
task-reference panel, reducing some inner-radius failures but adding one
outer-radius failure; its paired 400-episode research result remained 96.5%.
Experiments 4 and 5 degraded paired research and task-reference success, so
focused angle oversampling and full hold-exit forfeiture are not useful
directions under their tested recipes. Experiment 6's
ACTION_DELTA_COST_COEFFICIENT=0.02 candidate at 100,352 steps scored 96.75%
and 96.5% on the two paired research panels versus 96.5% and 96.25% for the
working parent, and 99% on the independent task-reference panel versus 98.5%
for the parent. It retained two negative-angle inner-radius failures and did
not reduce interrupted holds, so the improvement is practical but modest and
does not establish a causal jitter explanation. Experiment 7 then added
normalized radius and sine/cosine target-angle features from scratch; its
100,352- and 120,832-step checkpoints scored 0% on both the research and
independent task-reference panels, while the training proxy remained 0%.
The independent instruments agree that this candidate is unusable, although
fresh initialization prevents attributing the failure uniquely to the added
features. Experiment 8 transferred the experiment-6 policy and imposed a
global 0.15 normalized-action change limit. Both measured checkpoints scored
96.75% on the same 400-episode research panel, with two discordant episodes and
no net paired advantage. The 100,352-step candidate shifted failed research
episodes from 4 never-reached and 9 reached-then-failed-hold cases in the parent
to 9 never-reached and 4 reached-then-failed-hold cases, without reducing total
failures. On the independent task-reference panel it scored 98.0% versus the
parent's 99.0%, adding failures at 7.24 cm and 19.21 cm while retaining the two
negative-angle inner-radius failures. This rejects the tested global limiter as
a useful intervention, but one transferred run does not identify whether the
remaining gap is control, observation, inverse kinematics, or training
variability. Experiment 9 then transferred that policy and smoothed commands
only for negative-angle targets within 12 cm while the end effector was within
4 cm. Its two checkpoints both scored 96.5% on the same 400-episode research
panel. At 100,352 steps it had the parent's 13 failed episode identities plus
episode 327, with 11 reached-then-failed-hold cases versus 9 for the parent;
at 120,832 steps it retained the same 14 failed identities. Task-reference
success was 97.5% and 98.0%, respectively, versus 99.0% for the parent. The
later checkpoint repaired one task-reference episode but did not provide a
paired research improvement. The training proxy peaked at 0.99 near 20,480
steps and ended at 0.95, again failing to predict held-out success. All
measurements remain development evidence rather than the official final
benchmark. Experiment 10 replaced the redundant planar z-error slot with
explicit Euclidean distance and scored 97.0% on both measured research
checkpoints versus 96.5% for the parent, repairing two parent failure
identities without adding research-panel failures. It remained below 98%,
shifted task-reference failures at 100,352 steps, and fell to 98.5% at
120,832 steps, so this is a useful but non-robust representation signal rather
than evidence of a causal mechanism.

**Open questions:** Whether the modest experiment-10 repair signal is
reproducible, and which branch- or hold-aware information can remove the
remaining negative-angle failures without shifting failures to outer or
inner radii. Observation, inverse kinematics, control, and training
variability remain competing explanations. Robust 98% official-task success
remains unestablished.

**Conditional next steps:** Keep the experiment-6 100,352-step policy and its
full-radius, mild-transition-penalty recipe as working and best-known. If
development continues, test one concrete branch- or hold-aware
target-relative change with an explicit prediction that reduces the shared
negative-angle failure set without adding task-reference failures at other
radii. Do not repeat the tested distance-only replacement, local smoother,
uniform global rate limit, failed polar-observation recipe, angle oversampling,
hold forfeiture, or comparable reward-only change without new evidence that
distinguishes it.

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

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Experiment 7

**Result:** Adding normalized target radius and sine/cosine target-angle
features to the 11-feature observation failed decisively under the tested fresh
recipe. Both measured checkpoints scored 0% on the 400-episode research panel
and 0% on the independent 200-episode task-reference panel.

**Observed behavior:** This was a fresh training run changing the saved
observation contract from 11 to 14 features while preserving the full-radius
training distribution and experiment-6 transition penalty. The training proxy
success stayed at 0 from the first logged checkpoint through 120,832 steps.
The 100,352- and 120,832-step research evaluations each recorded 400 failures,
and both task-reference evaluations recorded 200 failures. Task-reference
failures were broad across angles and radii, with episodes terminating by the
500-step horizon rather than showing the prior localized negative-angle
inner-radius pattern. The independent task-reference execution used the saved
14-feature runtime contract, so the agreement is not evidence of a
research-evaluator-only discrepancy.

**Hypothesis assessment:** Contradicted under the tested fresh recipe. The
expected reduction in negative-angle inner-radius failures, at least a
one-percentage-point paired improvement, and at least 98% task-reference
success were not observed; instead, the candidate failed every measured
episode. This strongly weakens the practical representation hypothesis for
this recipe. Because the run was fresh and changed the learned observation
semantics, the result does not isolate whether the added features, their
interaction with normalization and optimization, or fresh-training
variability caused the collapse.

**Interpretation:** No further measurement of the two zero-success checkpoints
is proportionate: the research and independent panels already agree and the
training trajectory provides no recovery signal. Revert the experiment-7
scientific recipe and keep the experiment-6 100,352-step policy as working and
best-known. If development continues, the evidence supports a concrete
control-trajectory or action-conditioning experiment against the recurring
negative-angle inner-radius and hold failures, not another polar-observation
variant or a terminal benchmark request.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/research_state.json`,
`research/training_logs/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/experiment-7-attempt-1.log`,
the experiment-7 research-evaluation and task-reference artifacts under
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/`,
`robot_learning/scenario/observations.py`,
`robot_learning/scenario/environment.py`,
`robot_learning/scenario/policy_io.py`, and
`robot_learning/training/checkpoint.py`.

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Experiment 8

**Result:** A global applied-command rate limit did not improve the transferred
experiment-6 policy. Both measured checkpoints scored 96.75% on the 400-episode
research panel, while the independent task-reference panel scored 98.0% versus
99.0% for the parent.

**Observed behavior:** The intervention limited each applied normalized joint
command change to 0.15 and reset that state at episode boundaries. At
100,352 steps, the candidate and parent had 12 shared research failures, one
candidate-only failure, and one parent-only failure, producing no aggregate
success change. The candidate's failed research episodes comprised 9
never-reached cases and 4 reached-then-failed-hold cases, compared with 4 and 9
for the parent. The task-reference candidate retained the parent's failures at
9.915 cm and 9.355 cm and added failures at 7.243 cm and 19.210 cm. The
120,832-step checkpoint had the same 96.75% research and 98.0% task-reference
success rates. Training proxy success rose to 0.94, but it did not predict a
research improvement.

**Hypothesis assessment:** Contradicted under the tested transferred recipe. The
expected reduction in hold interruptions and at least 98% success on both
development instruments were not observed. The intervention did reduce the
count of reached-then-failed-hold cases in this panel, but it increased
never-reached failures enough to leave research success unchanged and lowered
task-reference success relative to the parent. This weakens the usefulness of
the tested global rate limit; one transferred run on one research seed does not
establish a causal explanation for the residual failures.

**Interpretation:** The rate limit changed the failure mix rather than repairing
the residual task gap, and its added outer-radius task-reference failure is a
practical regression. The experiment-6 100,352-step policy remains the best
available measured lineage. Further development is justified only by a more
targeted state- or angle-conditioned control intervention that does not slow all
initial reaches. The official objective remains unestablished because these
are development panels, not the final benchmark.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/training_logs/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/experiment-8-attempt-1.log`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-8-checkpoint-100352-400ep-seed9200-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-8-checkpoint-120832-400ep-seed9200-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-8-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-8-checkpoint-120832-task-reference-v1.json`,
`robot_learning/scenario/policy_io.py`, and `research/postmortems.md`.

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Experiment 9

**Result:** Targeted near-hold action smoothing did not improve the transferred
experiment-6 policy. Both checkpoints scored 96.5% on the paired 400-episode
research panel; task-reference success was 97.5% at 100,352 steps and 98.0% at
120,832 steps, below or only at threshold on one development instrument.

**Observed behavior:** The candidate was a transfer run that preserved the
11-feature observation, full-radius training distribution, transition penalty,
and official task semantics, while smoothing the applied command only for
negative-angle targets within 12 cm and end-effector distance within 4 cm. The
100,352-step candidate retained all 13 parent research failures and added
episode 327. Its failed research episodes included 11 reached-then-failed-hold
cases and 3 never-reached cases, compared with 9 and 4 for the parent. The
120,832-step candidate had the same 14 failed research episode identities, with
10 hold interruptions and 4 never-reached cases. On the independent panel, the
100,352-step candidate retained the parent failures near 9.91 and 9.36 cm and
added failures near 6.73, 7.24, and 19.21 cm; the later checkpoint repaired the
6.73 cm case but retained the other four. The training proxy peaked at 0.99
near 20,480 steps and ended at 0.95, unlike the held-out research result.

**Hypothesis assessment:** Contradicted under the tested transferred recipe.
The expected reduction in localized hold failures, preservation of non-target
reaches, and at least 98% success on both development instruments were not
observed. The small change in failure composition was not a reduction in total
failures, and the later task-reference result reaching 98.0% was accompanied by
unchanged 96.5% research success and identical failed episode identities. This
weakens the practical local action-trajectory hypothesis, but does not establish
that observation, inverse kinematics, or training variability is causal, since
only this smoothing rule and transferred run were tested.

**Interpretation:** The experiment-6 100,352-step policy remains the best-known
and working lineage. Further measurement of the remaining experiment-9
checkpoints is not proportionate: the two measured checkpoints agree on the
research outcome, and the independent panel shows no robust improvement. The
campaign should continue only through a new concrete target-relative or
kinematics-aware intervention, rather than another comparable postprocessing
variant. The official objective remains unestablished because all evidence is
from development panels.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/training_logs/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/experiment-9-attempt-1.log`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-9-checkpoint-100352-400ep-seed9200-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-9-checkpoint-120832-400ep-seed9200-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-9-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-9-checkpoint-120832-task-reference-v1.json`,
and `robot_learning/scenario/policy_io.py`.

## 812f1297-8535-4e4b-befe-eaaeb7f3ad5d / Experiment 10

**Result:** Replacing the redundant planar z-error observation slot with
explicit end-effector-to-target distance produced a modest, panel-specific
research improvement at both measured checkpoints, but did not establish
robust 98% task success.

**Observed behavior:** This was a transferred run from the experiment-6
working policy. The 100,352- and 120,832-step candidates both scored 97.0% on
the identical 400-episode research panel, compared with 96.5% for the parent.
Each candidate had one paired win and no parent wins, with only one discordant
episode. The candidate failure set was the parent's 14 failures minus episodes
209 and 327, leaving 12 failures; the remaining failures stayed concentrated
at negative target angles. Failure diagnostics changed from five
never-reached and nine reached-then-failed cases for the parent to three
never-reached and nine reached-then-failed cases for the candidate, so the
repaired identities did not reduce the reached-then-failed count overall.
Task-reference success was 99.0% at 100,352 steps and 98.5% at 120,832 steps.
The earlier checkpoint repaired the parent's 9.91 cm failure but added an
18.24 cm failure; the later checkpoint also failed at 7.24 cm. Training
proxy success reached 0.99, which did not establish held-out improvement.

**Hypothesis assessment:** Partially supported under the tested transferred
recipe. The distance cue produced the predicted small paired research gain
and repaired two parent research episodes without adding failures on that
panel, but it did not reach 98%, did not reduce the aggregate
reached-then-failed category, and shifted or added task-reference failures.
The two checkpoints agree on the research result, but one research panel,
one transferred run, and near-threshold task-reference panels cannot
distinguish a useful representation effect from training or panel
variability. The result weakens the stronger prediction that the cue would
preserve all geometry coverage.

**Interpretation:** The experiment-6 100,352-step policy remains the best
working and best-known lineage because its evidence is broader and its
task-reference result is at least as strong, while experiment 10 is worth
retaining as a reusable alternative because it repairs two compatible-panel
failures and preserves 99% task-reference success at the earlier checkpoint.
Further measurement of experiment 10 is not proportionate: the measured
checkpoints have identical research failures and the available evidence
already supports restoring the parent recipe while pursuing a new
branch- or hold-aware intervention. The official objective remains
unestablished.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/research_state.json`, `research/postmortems.md`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-6-working-400ep-seed9200-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-10-checkpoint-100352-400ep-seed9200-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/evaluation-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-10-checkpoint-120832-400ep-seed9200-479599417eaf.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-6-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-10-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/812f1297-8535-4e4b-befe-eaaeb7f3ad5d/task-reference-812f1297-8535-4e4b-befe-eaaeb7f3ad5d-experiment-10-checkpoint-120832-task-reference-v1.json`,
`robot_learning/scenario/observations.py`, and
`robot_learning/scenario/evaluation.py`.
