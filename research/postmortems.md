# Research postmortems

## 3f02f914-505c-481f-b995-e040c009974f / Scientific strategy

**Direction:** Keep experiment-2 checkpoint-120832 as working and best-known.
Experiments 7 and 8 contradicted the focused angular-exposure and conservative
PPO-update routes: neither measured angular challenger repaired a recurring
failure, and the lower-learning-rate challenger retained all three recurring
failures while scoring below the working policy at every measured checkpoint.
Full hold-progress forfeiture, unchanged continuation, fresh full-range runs,
the tested angular curriculum, and the tested lower learning rate are
deprioritized under their tested transfer conditions. The remaining
investigation should separate hold/control behavior from representation before
another targeted training intervention; this is not a causal conclusion about
any one mechanism.

**Lessons and limits:** Experiment 2's transfer run reached 197/200 (98.5%)
with 55/57 successes below 10 cm, 48/48 at 10-14 cm, and 94/95 at 14-20 cm
on task-reference-v1. Experiments 3 and 4 reached only 63.5-66.5% and
63.5-64.0% respectively at their measured late checkpoints, with 61 failed
episode identities shared at checkpoint-120832. These are repeated outcomes on
one fixed development panel, not independent held-out confirmation or official
benchmark evidence.

Experiment 5's task-reference measurements were 191/200 (95.5%), 192/200
(96.0%), and 187/200 (93.5%) at checkpoints 105472, 110592, and 120832.
The corresponding strata were 49/57, 50/57, and 47/57 below 10 cm; 48/48,
48/48, and 47/48 at 10-14 cm; and 94/95, 94/95, and 93/95 at 14-20 cm.
Thus the expected observation--exceeding 197/200, reducing recurring failures,
and preserving at least 94/95 far-radius success--did not occur. The
contradicting observation occurred at every measured checkpoint for total and
near-target success; far-radius preservation held at the first two checkpoints
but failed at the final one. The experiment-5 final checkpoint retained all
three parent failure identities (84, 102, and 175), so it did not repair the
parent's residual panel failures. Its final failures overlapped only 4 of
experiment 3's and 3 of experiment 4's failed identities; this difference is
descriptive and does not establish a changed failure mechanism.

The training log supplies partial but non-task signals: experiment 5's proxy
was 0.99 around 70,656-100,352 steps, 0.98 at 105,472 and 110,592, and 0.96
at 120,832, while training reward peaked before the final checkpoint.
Experiments 6 and 7 likewise show that training proxy and reward do not select
the best measured task checkpoint. All measured failures in experiments 5-7
truncated at 500 steps. The artifacts do not emit first band entry, hold
duration, or hold-exit counts, so hold-specific explanations remain
unmeasured. Unmeasured checkpoints remain unknown rather than failed policies.

Experiment 7's task-reference measurements were 194/200 at checkpoint-105472
(54/57 near, 48/48 middle, 92/95 far) and 188/200 at checkpoint-120832
(50/57, 48/48, 90/95), versus the working policy's 197/200
(55/57, 48/48, 94/95). Both challengers retained working failures 84, 102,
and 175; the earlier checkpoint added failures 10, 94, and 100, while the
final checkpoint added 0, 10, 52, 60, 100, 124, 135, 148, and 161. The
paired research-evaluation comparison was unfavorable to the challenger at
both checkpoints: 0 candidate wins and 3 reference wins at 105472, and 0
candidate wins and 9 reference wins at 120832. These observations are
descriptive evidence from one fixed panel and one transfer trajectory, not
independent held-out confirmation or official benchmark evidence.

Experiment 8 tested a lower PPO learning rate by transfer from the working
policy. Task-reference measurements reached 195/200 at checkpoints 100352 and
105472, with 53/57 near-radius, 48/48 middle-radius, and 94/95 far-radius
successes at both checkpoints. Checkpoint 120832 reached 190/200, with 48/57,
48/48, and 94/95 respectively. The two earlier checkpoints failed on
episodes 10, 84, 102, 167, and 175; the final checkpoint failed those episodes
plus 18, 26, 53, 60, and 62. Thus every measured checkpoint retained the
working policy's recurring failures 84, 102, and 175, and none repaired a
working-policy failure. All measured failures truncated at 500 steps. The
training proxy was 0.99 at 25600 steps, 0.99 at 100352, 0.98 at 105472, and
0.98 at 120832, which again did not identify the best task checkpoint. These
observations are from the same fixed development panel, not independent
held-out confirmation or official benchmark evidence.

**Open questions:** Do the persistent failures arise from hold stability,
target-relative representation, or PPO trajectory drift rather than angular
coverage? The unchanged continuation, hold-forfeiture intervention, and
angular oversampling all failed to improve the working policy under their
tested transfer conditions, and lower-learning-rate transfer also failed under
its tested condition, but none separates hold stability from representation or
other control effects. The available task-reference artifacts still cannot
determine whether a failure enters the tolerance band and exits during the hold
or never achieves a stable entry.

**Conditional next steps:** If development continues, add researcher-owned
diagnostics for first tolerance-band entry, achieved hold duration, and
hold-exit counts, then use those measurements to choose between a hold/control
and representation-focused intervention. The next training intervention should
not be another unchanged, angular-only, hold-forfeiture, or lower-rate transfer
under the tested recipes without a new reason those results do not apply. Any
future intervention should be compared with the retained working policy on
total success, radial strata, and the three recurring identities; only a
measured task improvement would justify changing lineage. Do not treat the
fixed-panel evidence as official attainment.

Experiment 6 adds a continuation test of checkpoint stability. Its three
task-reference measurements reached 194/200 (97.0%) at checkpoint-100352,
195/200 (97.5%) at checkpoint-105472, and 195/200 (97.5%) at
checkpoint-120832. The strata were respectively 55/57, 45/48, and 94/95;
53/57, 48/48, and 94/95; and 54/57, 48/48, and 93/95 for near, middle, and
far radii. Each measured checkpoint retained parent failures 84, 102, and
175. The first checkpoint additionally failed episodes 17, 76, and 173; the
second additionally failed 67 and 176; and the final additionally failed 10
and 196. All failures truncated at 500 steps. These are observations on the
same fixed development panel, not official or independent held-out evidence.

The continuation therefore contradicted its expected observation: no measured
checkpoint reached 197/200 or repaired either persistent near-target failure,
and the final checkpoint lost one far-radius success. Preserving 94/95 at the
first two checkpoints and preserving 48/48 in the middle stratum at the latter
two are partial stability signals, but not progress relative to the working
197/200 policy. The training proxy reached 1.0 around 102,400-105,472 steps
and ended at 0.98, while task success remained below the parent; training
proxy and reward remain unreliable checkpoint selectors. Twenty-one of 24
continuation checkpoints were not measured and remain unknown rather than
failed.

Under the sampled continuation checkpoints, additional unchanged PPO updates
did not produce a better task policy and are consistent with plateau or drift,
but the run does not identify whether the limitation is angular/control,
representation, hold behavior, or optimization. The absence of repaired
failure identities is descriptive and does not establish a causal
representation or control deficit. Close experiment 6 by restoring the
working experiment-2 recipe and preserve its checkpoint-120832 lineage. If
development continues, add the missing hold-trajectory diagnostics before a
targeted angular/control or representation intervention, and compare total
success, radial strata, and failure identities against the working policy.
Do not infer official attainment from this repeated fixed-panel evidence or
request final assessment from this challenger.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 1

**Result:** The baseline reached the development threshold at checkpoints
100352 and 110592, but the final checkpoint regressed below it; checkpoint
100352 is selected as the working and best-known policy.

**Observed behavior:** The automatic baseline trained 120,832 steps. The
task-reference-v1 panel used 200 deterministic episodes with seed 7300:
checkpoint-100352 and checkpoint-110592 each achieved 98.0% (196/200), and
checkpoint-120832 achieved 97.0% (194/200). Checkpoints 100352 and 110592
failed on the same episodes (0, 10, 84, 102); each failure truncated at 500
steps. The final checkpoint retained those four failures and added episodes
121 and 152. The shared failures had target radii 6.7, 7.2, 9.9, and 9.4 cm
and angles from -128 to -116 degrees. The training log's proxy success rose
from 0 through 70,656 steps to 0.97 at 100,352, then varied between 0.93 and
0.96 through the end; these are training measurements, not task-reference
results.

**Hypothesis assessment:** The baseline proposal snapshot supplied no
intervention-specific `expected_observation` or `contradicting_observation`;
the relevant baseline expectation was to establish an initial measured policy
for the human-defined objective. That expectation is **partially supported**:
two intermediate checkpoints met 98% on the fixed development panel, but the
final checkpoint did not, and no checkpoint has official benchmark status.
The result is therefore insufficient to claim stable attainment of the 98%
campaign objective or to attribute the outcome to any scientific mechanism.

**Interpretation:** The best measured task behavior occurs before the final
training checkpoint, so selecting by training proxy and continuing unchanged
is not justified by this run. The concentration of failures below 10 cm is
consistent with the training environment's 14-20 cm radial range, making
full-range target exposure a useful next hypothesis. This is an interpretation
of one baseline and one repeated development panel, not a causal conclusion.

**Evidence inspected:** `research/results.jsonl`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-1-attempt-1.log`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-1-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-1-checkpoint-120832-task-reference-v1.json`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-1/inventory.json`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 2

**Result:** Full-range target-radius training partially supported the
intervention hypothesis. The final checkpoint reached 197/200 (98.5%) on the
fixed development panel and is selected as the working and best-known policy.

**Observed behavior:** The transferred parent reached 196/200 (98%). The
experiment-2 checkpoint at 105472 steps also reached 196/200, with 54/57
under-10-cm successes and 94/95 at 14-20 cm. The final checkpoint at 120832
steps reached 197/200, with 55/57 under-10-cm successes, 48/48 at 10-14 cm,
and 94/95 at 14-20 cm. It changed the parent outcomes on three episodes: it
fixed parent failures at 6.7 cm/-116.4 degrees and 7.2 cm/-125.4 degrees,
left the 9.9 cm/-122.9 degrees and 9.4 cm/-127.9 degrees failures unchanged,
and changed a successful 18.2 cm/-154.8 degrees episode to failure. All
failures truncated at 500 steps. The training proxy peaked at 1.0 at 105472
steps and ended at 0.94; this is not task-reference performance.

**Hypothesis assessment:** The hypothesis is **partially supported**. The
expected reduction in the shared near-target failures occurred and the final
panel score improved by one episode, while 10-14 cm performance was preserved.
However, the final checkpoint did not eliminate the near-target geometry and
introduced a far-target failure, reducing 14-20 cm performance by one episode.
The result supports retaining full-range exposure as a useful intervention
under this panel, but does not establish that radius alone caused the change or
that the 98.5% result generalizes.

**Interpretation:** Exposure to 6-14 cm targets plausibly addressed part of the
baseline's radial gap because two of four shared near-target failures were
repaired. The persistent negative-angle failures and the new far-target
failure mean angular control, PPO drift, and checkpoint selection remain viable
explanations. The selected checkpoint is better measured task behavior than the
parent on this panel, not official attainment of the campaign objective.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-2-attempt-1.log`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-2/inventory.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-2-working-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-2-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-2-checkpoint-120832-task-reference-v1.json`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 3

**Result:** The fresh replication contradicted its reproducibility hypothesis.
None of the three measured checkpoints approached the experiment-2 task
behavior, so the experiment-2 working and best-known lineage is preserved.

**Observed behavior:** The seed-1 full-range run completed 120832 training
steps. On the same 200-episode task-reference-v1 panel, checkpoint-105472
achieved 127/200 (63.5%), checkpoint-110592 achieved 131/200 (65.5%), and
checkpoint-120832 achieved 133/200 (66.5%). Below 10 cm the checkpoints
achieved 33/57, 35/57, and 35/57; at 10-14 cm they achieved 30/48, 33/48,
and 32/48; at 14-20 cm they achieved 64/95, 63/95, and 66/95. The measured
failures span near, middle, and far radii and include positive and negative
angles. The training proxy was 0.01 at its best reported point and at the
end. Three checkpoints were measured and 21 remained unmeasured; an
unmeasured checkpoint is not treated as a failed policy.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The expected observation was at least 55/57 below 10 cm while
preserving 95/95 at 14-20 cm, with a similar qualitative failure pattern.
The observed checkpoints instead reached 33-35/57 and 63-66/95, with a broad
failure pattern. This establishes that the experiment-2 behavior was not
reproduced by this fresh seed at the measured checkpoints. It does not
establish whether seed variance, optimization trajectory, checkpoint timing,
or another coupled factor caused the discrepancy.

**Interpretation:** The replication weakens the claim that full-range target
exposure reliably produces the experiment-2 improvement and makes process
stability a higher-value question. The modest increase from 63.5% to 66.5%
across the measured checkpoints is an unexpected partial learning signal, but
it remains far below the parent result and cannot support policy progress
relative to the selected working lineage. Because the run was a fresh
initialization and only one seed, the evidence is diagnostic of
non-reproducibility in these tested conditions, not a causal comparison of
initialization or a refutation of the recipe in general.

**Evidence inspected:** `research/research_state.json`;
`research/brief.md`; `research/results.jsonl`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-3-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-3-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-3-checkpoint-120832-task-reference-v1.json`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 4

**Result:** The second fresh replication contradicted its reproducibility
hypothesis, so the experiment-2 working and best-known lineage is preserved.

**Observed behavior:** Seed 2 completed 120832 training steps. On the same
200-episode task-reference-v1 panel, checkpoints 105472, 110592, and 120832
achieved 128/200 (64.0%), 127/200 (63.5%), and 127/200 (63.5%). Their
near/middle/far strata were 38/57, 32/48, 58/95; 38/57, 33/48, 56/95; and
38/57, 32/48, 57/95. The measured failures covered multiple radii and both
angle signs. At checkpoint-120832, 61 failed episode identities were shared
with experiment 3's checkpoint-120832 measurement. The training proxy was
0.22, 0.24, and 0.26 at the measured checkpoints and 0.26 at the end; these
are training measurements, not task-reference results.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The expected observation was a late checkpoint near 196/200 with
at least 55/57 near-target and 94/95 far-target successes, which would have
supported treating experiment 3 as an unstable draw. Instead, all three
measured checkpoints remained near 63.5-64.0%, with 38/57 near-target and
56-58/95 far-target successes. This strengthens the conclusion that the
experiment-2 behavior was not reproduced by either tested fresh seed. It does
not prove that full-range exposure is ineffective or identify whether seed,
optimization, reward interaction, representation, or control caused the gap.

**Interpretation:** The repeated broad deficit and substantial overlap in
failed fixed-panel episodes make a purely one-off seed explanation less
plausible, while the differing angle-sign balance prevents a simple claim of
one fixed angular failure mode. The small checkpoint movement and the rise in
the training proxy are unexpected partial process signals, but they do not
constitute policy progress relative to the 98.5% working lineage. The evidence
supports changing the next scientific question toward angular/control
robustness and diagnostic separation, not selecting or retaining a fresh
candidate.

**Evidence inspected:** `research/research_state.json`;
`research/brief.md`; `research/results.jsonl`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-4-attempt-1.log`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-4/inventory.json`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-4/parameters.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-4-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-4-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-4-checkpoint-120832-task-reference-v1.json`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 5

**Result:** Full forfeiture of accumulated hold-progress reward did not improve
the transferred policy. The best measured challenger checkpoint reached only
192/200, below the working policy's 197/200, so the experiment-2 working and
best-known lineage is preserved and the experiment-5 recipe is not retained.

**Observed behavior:** On the same 200-episode task-reference-v1 panel,
checkpoint-105472 achieved 191/200 (95.5%), checkpoint-110592 achieved
192/200 (96.0%), and checkpoint-120832 achieved 187/200 (93.5%). Their
below-10-cm, 10-14-cm, and 14-20-cm strata were respectively 49/57, 48/48,
94/95; 50/57, 48/48, 94/95; and 47/57, 47/48, 93/95. All failures in these
three artifacts truncated at 500 steps. The final checkpoint retained the
parent's failures on episodes 84, 102, and 175 and did not exceed the parent
in any measured total or near-target result. The first two checkpoints
preserved the parent's far-radius count, but the final checkpoint lost one
additional far-radius success. The training proxy reached 0.99 at measured
training points around 70,656-100,352 steps and ended at 0.96; these are
training-process measurements, not task-reference performance.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The expected observation was a transfer checkpoint above 197/200,
with fewer recurring failures and at least 94/95 far-radius success. No
checkpoint exceeded 197/200 or improved the near-target stratum; far-radius
preservation occurred only at the two earlier measured checkpoints and failed
at the final checkpoint. The partial preservation of the middle stratum and
early far-radius behavior is an unexpected limited signal, not policy progress
relative to the working lineage. The hold-specific expectation about failures
after long partial holds is inconclusive because the task-reference artifacts
do not emit hold-entry or hold-exit trajectories.

**Interpretation:** Under this single transfer trajectory and fixed development
panel, full hold-progress forfeiture is not a useful replacement for the
working recipe. The unchanged parent failures and late regression are
consistent with a control, representation, PPO-trajectory, or reward
interaction limitation, but the run has no control arm or hold-trajectory
diagnostic that identifies the cause. The task evidence supports rejecting
this intervention for lineage selection, not a causal claim that all hold
feedback changes are ineffective.

**Evidence inspected:** `research/results.jsonl`;
`research/brief.md`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-5-attempt-1.log`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-5/inventory.json`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-5/parameters.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-5-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-5-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-5-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-2-checkpoint-120832-task-reference-v1.json`;
`robot_learning/scenario/reward.py`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 6

**Result:** Continuing the unchanged PPO recipe did not improve the working
policy on the measured task-reference checkpoints. The continuation hypothesis
was contradicted under its stated conditions, so the experiment-2
checkpoint-120832 working and best-known lineage is preserved.

**Observed behavior:** On task-reference-v1's fixed 200-episode panel,
checkpoint-100352 achieved 194/200 (97.0%), checkpoint-105472 achieved
195/200 (97.5%), and checkpoint-120832 achieved 195/200 (97.5%). Their
near/middle/far strata were 55/57, 45/48, 94/95; 53/57, 48/48, 94/95; and
54/57, 48/48, 93/95. All three retained the working policy's failures on
episodes 84, 102, and 175. The first checkpoint also failed 17, 76, and 173;
the second also failed 67 and 176; and the final also failed 10 and 196. All
listed failures truncated at 500 steps. The training log reported a proxy
success of 1.0 around 102,400-105,472 steps and 0.98 at 120,832, but these
are training measurements rather than task-reference results. Of 24 available
checkpoints, only these three were measured; the other 21 remain unmeasured.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The expected observation was a checkpoint at least 197/200 that
repaired one or more of episodes 84 and 102 without losing far-radius
performance. No measured checkpoint reached 197/200 or repaired either
failure. Far-radius performance was preserved at the first two measured
checkpoints but fell to 93/95 at the final checkpoint, while the middle
stratum reached 48/48 only at the latter two. These partial preservation
signals do not support policy progress relative to the working 197/200
policy. The result weakens unchanged continuation as a practical route under
this transfer trajectory, but does not prove that every unmeasured checkpoint
fails or that any representation or control component is causally
insufficient.

**Interpretation:** The measured continuation checkpoints stayed close to, but
below, the parent and did not change its recurring failure identities. This is
consistent with a plateau or optimization drift after transfer and with the
existing angular/control, representation, or hold-stability alternatives, but
the fixed panel, three sampled checkpoints, and missing entry/hold/exit
trajectory diagnostics prevent causal attribution. The mismatch between
training proxy and task success further argues against using the proxy or
training reward as a checkpoint selector.

**Evidence inspected:** `research/results.jsonl`;
`research/brief.md`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-6-attempt-1.log`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-6/inventory.json`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-6/parameters.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-6-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-6-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-6-checkpoint-120832-task-reference-v1.json`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 7

**Result:** The angular-oversampling hypothesis was contradicted under the
proposal's stated transfer conditions. Neither measured checkpoint repaired a
working-policy failure or reached 197/200, and the final checkpoint regressed
to 188/200. The experiment-2 checkpoint-120832 lineage remains working and
best-known.

**Observed behavior:** On task-reference-v1's fixed 200-episode panel,
checkpoint-105472 achieved 194/200 (97.0%), with 54/57 near-radius,
48/48 middle-radius, and 92/95 far-radius successes. Checkpoint-120832
achieved 188/200 (94.0%), with 50/57, 48/48, and 90/95 respectively. The
working policy measured in the same round achieved 197/200 (98.5%), with
55/57, 48/48, and 94/95. Both experiment-7 checkpoints retained working
failures 84, 102, and 175; checkpoint-105472 additionally failed 10, 94, and
100, while checkpoint-120832 additionally failed 0, 10, 52, 60, 100, 124,
135, 148, and 161. The research-evaluation paired comparisons had zero
challenger wins against the working policy, with three reference wins at
105472 and nine at 120832. The training proxy was 0.78 and 0.92 at the two
measured checkpoints, so it did not track the task-reference ordering.
Twenty-two of 24 checkpoints were unmeasured and are not treated as failed
policies. All measured failures truncated at 500 steps, and no artifact
reported first entry, hold duration, or hold exits.

**Hypothesis assessment:** **Contradicted** under the tested conditions. The
expected observation was repair of at least one of episodes 84, 102, or 175,
at least 197/200 total success, and at least 94/95 far-radius success. No
recurring failure was repaired, neither checkpoint reached 197/200, and
far-radius success was 92/95 and 90/95. Preserving 48/48 in the middle
stratum at both checkpoints is an unexpected partial preservation signal, but
it is not policy progress relative to the 197/200 working policy. This result
weakens angular coverage as the next practical route under this transfer
recipe; it does not establish that angular exposure is universally ineffective
or identify a causal failure mechanism.

**Interpretation:** The targeted mixture did not improve the known negative-
angle failures and was accompanied by new near- and far-radius failures,
especially at the final checkpoint. That pattern is consistent with
representation, hold/control, or PPO drift explanations, but the single
trajectory, fixed development panel, and missing hold diagnostics prevent
causal attribution. The measured task behavior supports rejecting the
challenger for lineage selection, while the retained working policy remains
the strongest development result and is not official benchmark evidence.

**Evidence inspected:** `research/results.jsonl`; `research/brief.md`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-7-checkpoint-105472-200ep-seed7300-dd53965887e8.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-7-checkpoint-120832-200ep-seed7300-dd53965887e8.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-7-working-200ep-seed7300-dd53965887e8.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-7-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-7-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-7-working-task-reference-v1.json`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 8

**Result:** The lower-learning-rate hypothesis was contradicted under the
tested transfer conditions. No measured checkpoint improved the working policy,
so the experiment-2 checkpoint-120832 lineage remains working and best-known.

**Observed behavior:** The proposal expected at least one checkpoint to reach
197/200 or better, repair one or more of episodes 84, 102, and 175, and
preserve at least 94/95 far-radius successes. Checkpoints 100352 and 105472
each reached 195/200, with 53/57 near-radius, 48/48 middle-radius, and 94/95
far-radius successes. Checkpoint 120832 reached 190/200, with 48/57, 48/48,
and 94/95 respectively. The earlier checkpoints failed on episodes 10, 84,
102, 167, and 175; the final checkpoint failed those episodes plus 18, 26, 53,
60, and 62. All measured checkpoints retained recurring failures 84, 102, and
175, and all listed failures truncated at 500 steps. The training proxy was
high at sampled checkpoints, including 0.99 at 100352 and 0.98 at 120832, but
did not track task-reference ordering. The unmeasured checkpoints remain
unknown rather than failed.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The expected total improvement and repair of recurring failures did
not occur at any measured checkpoint. Preservation of 94/95 far-radius success
at all three checkpoints and 48/48 middle-radius success are partial
preservation signals, but they are not policy progress relative to the
197/200 working policy. The evidence weakens conservative PPO updates as the
next practical route for this parent and learning-rate change; it does not
establish that learning rate is universally ineffective or identify whether
the residual failures are caused by hold behavior, representation, or control.

**Interpretation:** Lowering the learning rate did not overcome the working
policy's three recurring failures in this transfer trajectory. The late
checkpoint's additional failures are consistent with continued PPO trajectory
drift despite the smaller update scale, while the unchanged far-radius count
shows limited behavioral preservation. Because this is one transfer trajectory
on one fixed development panel and task-reference artifacts lack
hold-entry/hold-exit measurements, these observations support rejecting the
challenger for lineage selection but do not support a causal explanation.

**Evidence inspected:** `research/results.jsonl`;
`research/brief.md`;
`research/postmortems.md`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-8-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-8-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-8-checkpoint-120832-task-reference-v1.json`;
`robot_learning/scenario/evaluation.py`.
