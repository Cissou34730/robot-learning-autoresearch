# Research postmortems

## 3f02f914-505c-481f-b995-e040c009974f / Scientific strategy

**Direction:** Keep the experiment-16 velocity-augmented recipe with
checkpoint-110592 as working and best-known. That checkpoint is the first
measured candidate to exceed the previous 197/200 working result and it repaired
one named recurring hold. Reward-only hold penalties and global command
attenuation remain deprioritized under their tested conditions. The velocity
result is promising state-feedback evidence, but fresh initialization and
checkpoint selection are coupled, so it does not yet establish that the added
features caused the improvement.

**Lessons and limits:** Experiment 16 checkpoint-110592 achieved 198/200 on
task-reference-v1, with 56/57 near-radius, 48/48 middle-radius, and 94/95
far-radius success. It repaired parent failure 84 with `max_held_steps=100`
and retained failures 102 and 175. This is measured task progress relative to
experiment-2 checkpoint-120832. The later checkpoint-120832 fell to 196/200,
with 55/57, 47/48, and 94/95 success and new failures 10 and 185; therefore
the improvement was not stable through the full measured trajectory.

Research evaluation showed the 110592 repair was a complete hold: episode 84
had first reach at step 17, 100 held steps, and zero interruptions. Episodes
102 and 175 remained incomplete, with maximum holds of 3 and 7 and one and
239 interruptions respectively. Aggregate interruptions were 245 at 110592
versus 240 for the working policy, so the result is not explained by a general
reduction in interruptions. The training proxy was 0.93 at both measured late
points and logged reward declined from 122.642 to 119.654; these training
facts did not identify the best task checkpoint. Only two of 24 checkpoints
were measured, the panel is fixed development evidence rather than official
benchmark evidence, and the fresh run has no control separating velocity
features from initialization or optimization trajectory.

Experiment 2's transfer run remains the relevant parent comparison at 197/200
with 55/57, 48/48, and 94/95 radial success. Experiments 3 and 4 showed that
fresh full-range training can also fail broadly, so experiment 16's single
successful fresh trajectory should not be generalized to the method or to the
official distribution.

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
truncated at 500 steps. The task-reference artifacts do not emit first band
entry, hold duration, or hold-exit counts, so those historical measurements
remain limited. The experiment-7 research-evaluation artifact does provide
these diagnostics for the working policy and identifies brief or unstable
holds at all three recurring failures. Unmeasured checkpoints remain unknown
rather than failed policies.

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

Experiment 9's task-reference measurements were 195/200 at checkpoint-100352
(54/57 near, 48/48 middle, 93/95 far) and 184/200 at checkpoint-120832
(52/57, 48/48, 84/95), versus 197/200 (55/57, 48/48, 94/95) for the working
policy. Both checkpoints retained failures 84, 102, and 175; the early
checkpoint also failed 67 and 160, while the final added 13 further failures.
Paired research-evaluation comparisons had zero challenger wins and two
reference wins at 100352, then zero challenger wins and thirteen reference
wins at 120832. The early checkpoint's preserved middle stratum is a partial
preservation signal, not measured task progress; the final checkpoint's
far-radius regression and expanded failure set are contrary signals. These
results are descriptive evidence from one fixed panel and one transfer
trajectory, not independent held-out confirmation or official benchmark
evidence.

Research-evaluation diagnostics show that the convex reward did not repair the
hold signatures: for failures 84, 102, and 175, maximum consecutive holds
were 4, 2, and 1 at 100352 and 5, 1, and 0 at 120832, versus 4, 1, and 6 for
the working policy. Episode 175 never entered the band at the final checkpoint,
and aggregate interruptions rose from 240 for the working policy to 1100.
Task-reference artifacts still do not emit these hold diagnostics, so this
mechanistic evidence is limited to the research-evaluation context. The
experiment-9 proxy reached 1.0 earlier, was 0.99 at 100352, and ended at 0.96;
this reinforces that training proxy and reward are not task-policy selectors.

Experiment 10's task-reference measurements were 8/200 (4.0%) at checkpoint
115712 and 9/200 (4.5%) at checkpoint 120832. The strata were 0/57 near-radius,
4/48 middle-radius, and 4/95 far-radius at 115712; and 0/57, 4/48, and 5/95 at
120832. Both checkpoints failed all recurring parent episodes 84, 102, and
175. Research evaluation matched these totals; most failures never entered the
tolerance band, while the few successful episodes completed the 100-step hold.
Paired comparisons gave zero challenger wins and 189 and 188 working-policy
wins at the two checkpoints. The training proxy remained 0 and the best
recorded training rewards did not predict task success. These measurements
strongly reject this exact representation-plus-fresh-training recipe as a
practical route, but they do not establish that periodic features or target
coordinates are intrinsically causal failures: initialization, optimization,
and changed observation semantics were not separately controlled. Twenty-two
checkpoints remain unmeasured and unknown rather than failed.

Experiment 11's task-reference checkpoints reached 196/200 at 100352 and
115712 (54/57 near, 48/48 middle, 94/95 far), then 195/200 at 120832
(54/57, 48/48, 93/95). All three retained recurring failures 84, 102, and
175, and all added episode 10; the final also added episode 100. Research
evaluation reported 8, 10, and 251 total hold interruptions at those
checkpoints versus 240 for the working policy. The early reduction coincided
with episode 175 never entering the band rather than completing a hold. These
are descriptive diagnostics, not evidence that action cost caused either
outcome.

Experiment 12's target-reference checkpoints reached 86/200 (43.0%) at
110592 and 89/200 (44.5%) at 120832. Both had 47/57 near-radius and 36/48
middle-radius successes; far-radius success increased from 3/95 to 6/95.
The final checkpoint repaired four failures from the earlier checkpoint and
added episode 79, but neither checkpoint repaired working-policy failures 84,
102, or 175. The paired research-evaluation comparisons had zero challenger
wins and 111 and 108 working-policy wins. All candidate failures truncated at
500 steps. The research-evaluation artifacts report matching totals but do not
emit hold-entry, hold-duration, or interruption diagnostics for this run, so
the stable-hold part of the prediction cannot be mechanistically assessed.
The training proxy was 0.19 and the final logged reward was 89.1; these are
training-process signals, not evidence of task progress. The 22 unmeasured
checkpoints remain unknown rather than failed.

The experiment-12 result strongly rejects this exact fresh, 14-feature
augmentation recipe as a practical route, but does not show that explicit
target geometry or representation changes are intrinsically harmful. Fresh
initialization, changed input dimension, optimization trajectory, and the
augmentation were coupled. All measurements use one fixed development panel
and are not official benchmark evidence.

**Open questions:** Is the episode-84 repair reproducible with the velocity
features when initialization is controlled, and can the remaining episodes 102
and 175 be repaired without the late regression seen at checkpoint-120832? Does
the velocity signal help specifically with braking and hold stability, or did
the fresh optimization trajectory select a favorable controller? Does the
development-panel gain generalize to the official task distribution?

**Conditional next steps:** After closure, prefer a controlled velocity
state-feedback follow-up only if it separates fresh initialization from the
observation change and predicts another complete 100-step repair while
preserving 55/57, 48/48, and 94/95 radial success. If that control fails or
the earlier checkpoint is not reproduced, retain checkpoint-110592 as the
development best-known policy but investigate a different unresolved
representation or optimization explanation. Do not repeat global command
damping or reward-only hold changes under the same conditions. All such
results remain fixed-panel development evidence rather than official
attainment.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 12

**Result:** The target-polar-augmentation hypothesis was contradicted under
the tested fresh-training conditions. Checkpoint-110592 reached 86/200
(43.0%) and checkpoint-120832 reached 89/200 (44.5%), far below the working
policy's 197/200 (98.5%), so the experiment-2 working and best-known lineage
remains selected.

**Observed behavior:** On task-reference-v1, checkpoint-110592 achieved
47/57 near-radius, 36/48 middle-radius, and 3/95 far-radius successes.
Checkpoint-120832 achieved 47/57, 36/48, and 6/95. Both checkpoints failed
the working-policy episodes 84, 102, and 175. The later checkpoint repaired
episodes 1, 42, 48, and 147 from the earlier checkpoint but added episode 79.
Research evaluation matched the 43.0% and 44.5% totals; paired comparisons
had zero challenger wins versus 111 and 108 working-policy wins. Candidate
failures truncated at 500 steps. The research-evaluation artifacts do not
emit hold-entry or hold-interruption diagnostics for this experiment. The
training log ended at 120832 steps with proxy success 0.19 and reward 89.1;
these are training facts, not task-reference performance. Twenty-two of 24
checkpoints were unmeasured and remain unknown rather than failed.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The expected observation was a checkpoint at least 198/200,
repair of one of episodes 84, 102, or 175, preservation of 48/48
middle-radius and at least 94/95 far-radius success, and a stable hold
diagnostic for any repaired case. Neither checkpoint approached the total
threshold or repaired a recurring failure; both lost 12 middle-radius
successes and 88-91 far-radius successes relative to the working
policy. The small late improvement in total success, four repaired
non-recurring identities, and increase from 3/95 to 6/95 far-radius success
are partial signals of limited learning, not policy progress. The missing
hold diagnostics leave that mechanistic subcriterion unmeasured. This result
weakens target-polar augmentation as a practical route under fresh
initialization and this budget, but does not establish that target geometry,
representation, or optimization is the causal failure.

**Interpretation:** Preserving the old feature prefix while appending target
geometry did not preserve the working policy's performance when trained from
scratch. The large regression and unfavorable paired comparisons justify
rejecting this challenger for lineage selection and reverting its recipe.
Because fresh initialization, the changed observation dimension, and the
optimization trajectory were coupled, the result cannot distinguish whether
the added features were unhelpful, difficult to learn, or interacted poorly
with the fresh PPO run. The fixed panel, incomplete checkpoint coverage, and
absence of hold-trajectory diagnostics further limit causal claims.

**Evidence inspected:** `research/results.jsonl`; `research/brief.md`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-12-attempt-1.log`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-12-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-12-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-12-working-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-12-checkpoint-110592-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-12-checkpoint-120832-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-12-working-200ep-seed7300-ffdccdbf3357.json`;
`robot_learning/scenario/observations.py`.

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

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 9

**Result:** The convex hold-progress reward hypothesis was contradicted under
the tested transfer conditions. Checkpoint-100352 reached 195/200 and
checkpoint-120832 reached 184/200 on task-reference-v1, both below the
working policy's 197/200, so the experiment-2 working and best-known lineage
remains selected.

**Observed behavior:** On the fixed 200-episode task-reference panel,
checkpoint-100352 achieved 54/57 near-radius, 48/48 middle-radius, and 93/95
far-radius successes. Checkpoint-120832 achieved 52/57, 48/48, and 84/95.
Both retained recurring failures 84, 102, and 175. The early checkpoint also
failed 67 and 160; the final checkpoint also failed 26, 29, 44, 55, 57, 65,
99, 123, 129, 146, 148, 155, and 196. Research-evaluation measurements
matched the task-reference totals: 97.5% and 92.0%. Paired research-evaluation
comparisons had zero challenger wins versus two working-policy wins at 100352,
and zero challenger wins versus thirteen working-policy wins at 120832.

The research-evaluation diagnostics showed no repair of the targeted hold
deficits. For episodes 84, 102, and 175, the early checkpoint had maximum
consecutive holds of 4, 2, and 1 with one interruption each; the final had 5,
1, and 0, with episode 175 never entering the band. The working policy had
maximum holds of 4, 1, and 6, while episode 175 accumulated 242 in-tolerance
steps across 235 interruptions. The early increase for episode 102 was not a
success, and the final aggregate interruptions were 1100 versus 240 for the
working policy. All task-reference failures truncated at 500 steps. The
training proxy was 0.99 at checkpoint-100352 and 0.96 at checkpoint-120832,
despite the proxy reaching 1.0 earlier; these are training facts, not task
performance.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The expected observation was at least 197/200, repair of one or
more of episodes 84, 102, and 175, and at least 94/95 far-radius success.
Neither measured checkpoint met the total-success threshold or repaired a
recurring failure. The early checkpoint preserved 48/48 middle-radius success
and remained close to the parent in total success, which is an unexpected
partial preservation signal, but it lost one far-radius success and did not
improve the task. The final checkpoint lost ten far-radius successes and
expanded the failure set. This weakens convex hold shaping as a practical route
under this transfer condition; it does not prove that reward shaping is
universally ineffective or establish a representation/control cause.

**Interpretation:** Increasing the exponent changed the learned policy's
post-entry behavior inconsistently: the early checkpoint slightly changed one
brief hold but did not complete it, while the final checkpoint failed to enter
one recurring target and accumulated substantially more interruptions overall.
The measured task regression and unfavorable paired comparisons justify
rejecting this challenger for lineage selection. The fixed panel, single
transfer trajectory, unmeasured checkpoints, and differing reward semantics
limit causal claims; the new hold diagnostics are development-evaluator
evidence, not official benchmark evidence.

**Evidence inspected:** `research/results.jsonl`; `research/brief.md`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-9-attempt-1.log`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-9-checkpoint-100352-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-9-checkpoint-120832-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-9-working-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-9-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-9-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-9-working-task-reference-v1.json`;
`robot_learning/scenario/reward.py`.

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

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 10

**Result:** The periodic-target representation hypothesis was contradicted under
the tested fresh-training conditions. The measured challenger is rejected for
lineage selection; experiment-2 checkpoint-120832 remains working and
best-known, and the observation change will be reverted.

**Observed behavior:** The proposal expected at least 198/200 success, repair
of one or more recurring failures 84, 102, and 175, and preservation of at
least 94/95 far-radius and 48/48 middle-radius success. On the fixed
task-reference-v1 panel, checkpoint-115712 achieved 8/200 (4.0%): 0/57
near-radius, 4/48 middle-radius, and 4/95 far-radius. Checkpoint-120832
achieved 9/200 (4.5%): 0/57, 4/48, and 5/95. Both checkpoints failed episodes
84, 102, and 175. Their successes were episodes 19, 23, 39, 107, 155, 160,
and 182, with episode 191 also successful at both checkpoints and episode 154
successful only at checkpoint-120832. Research evaluation matched the totals;
most failures never entered the tolerance band, while the few successes
completed the 100-step hold. Every task-reference failure truncated at 500
steps. The paired research-evaluation comparisons had zero challenger wins
versus 189 and 188 working-policy wins at checkpoints 115712 and 120832.
The 22 unmeasured checkpoints remain unknown rather than failed.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. Neither measured checkpoint approached 198/200, repaired a
recurring failure, preserved the parent radial strata, or improved on the
working policy's 197/200 (55/57 near, 48/48 middle, 94/95 far). The small
set of successful holds and the one additional success at the later checkpoint
are partial signals of limited learned behavior, not measured task progress.
The matching task-reference and research-evaluation totals and strongly
unfavorable paired comparisons make another measurement round unnecessary for
the lineage decision. This conclusion is scoped to this encoding, fresh
initialization, training budget, and evaluated panel; it does not prove that
periodic features, explicit target coordinates, or representation changes are
universally ineffective.

**Interpretation:** The exact replacement observation did not support useful
policy learning in this run. The code preserved an 11-element observation
space and the identity physical-action mapping, but equal dimensionality did
not preserve the parent policy's feature semantics, which justified fresh
initialization and also prevents this result from isolating representation
from initialization and optimization effects. The catastrophic measured
regression nevertheless makes this recipe impractical under the tested
conditions. Training proxy and reward were not evidence of task progress:
the proxy remained 0, and the best logged rewards occurred without a
corresponding successful policy.

**Evidence inspected:** `research/results.jsonl`; `research/brief.md`;
`research/postmortems.md`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-10-checkpoint-115712-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-10-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-10-checkpoint-115712-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-10-checkpoint-120832-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-10-working-200ep-seed7300-ffdccdbf3357.json`;
`robot_learning/scenario/observations.py`;
`robot_learning/scenario/policy_io.py`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 11

**Result:** The action-regularization hypothesis was contradicted under the
tested transfer conditions. No measured checkpoint improved the working policy,
so experiment-2 checkpoint-120832 remains working and best-known and the
action-cost change will be reverted.

**Observed behavior:** On task-reference-v1, checkpoints 100352 and 115712
each achieved 196/200 (98.0%), with 54/57 near-radius, 48/48 middle-radius,
and 94/95 far-radius successes. Checkpoint 120832 achieved 195/200 (97.5%),
with 54/57, 48/48, and 93/95. The first two checkpoints failed episodes
10, 84, 102, and 175; the final retained those failures and added episode
100. All three retained recurring working-policy failures 84, 102, and 175.
Research-evaluation totals matched the task-reference results. Aggregate hold
interruptions were 8, 10, and 251 at the three checkpoints, compared with 240
for the working policy. At the early checkpoints episode 175 never entered the
band; at the final it reached at most two consecutive held steps, while the
working policy reached six but still failed that episode. The training proxy
was 0.99 at its best sampled point and 0.96 at the end; the best logged reward
was at 25600 steps. These are training-process facts, not task performance.
Twenty-one of 24 checkpoints were unmeasured and remain unknown rather than
failed.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The expected observation was a checkpoint at least 197/200,
repair of one of episodes 84, 102, or 175, preservation of at least 94/95
far-radius and 48/48 middle-radius success, and improved hold diagnostics for
a repaired case. No checkpoint reached 197/200 or repaired a recurring failure.
The first two checkpoints preserved the middle and far strata but added the
same near-radius failure, so that is an unexpected partial preservation signal,
not policy progress. The final checkpoint lost one far-radius success and
added another failure. The lower early interruption totals reflect failure to
enter the band, not a completed or stabilized hold; the final total exceeded
the working-policy total. This weakens action regularization as a practical
route under this transfer condition, but does not prove that action cost,
control, or representation is causally responsible for the residual failures.

**Interpretation:** Increasing the action cost did not produce the predicted
hold-stability improvement. The measured task regression and unchanged
recurring failures justify rejecting this challenger for lineage selection.
The matching task-reference and research-evaluation totals make another
measurement round unnecessary for that decision. Causal claims remain limited
by the single transfer trajectory, fixed development panel, reward change
without a paired training control, and incomplete checkpoint coverage.

**Evidence inspected:** `research/results.jsonl`; `research/brief.md`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-11-attempt-1.log`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-11-checkpoint-100352-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-11-checkpoint-115712-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-11-checkpoint-120832-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-11-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-11-checkpoint-115712-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-11-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-9-working-200ep-seed7300-ffdccdbf3357.json`;
`robot_learning/scenario/reward.py`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 13

**Result:** The mild hard-sector target-frequency hypothesis was contradicted
under the tested transfer conditions. Both measured checkpoints matched the
working policy at 197/200, repaired none of its recurring failures, and are
rejected for lineage selection; experiment-2 checkpoint-120832 remains working
and best-known.

**Observed behavior:** The proposal expected at least 198/200 success, repair
of at least one of episodes 84, 102, and 175 through a complete 100-step hold,
preservation of 48/48 middle-radius and at least 94/95 far-radius success, and
no broad regression. On task-reference-v1, checkpoints 105472 and 120832 each
achieved 197/200 (98.5%), with 55/57 near-radius, 48/48 middle-radius, and
94/95 far-radius successes. The working-policy measurement had the same
strata and total. All three candidate and working-policy failure sets were
exactly episodes 84, 102, and 175; every listed failure truncated at 500
steps. The 22 other candidate checkpoints were not measured and remain
unknown. The training log's proxy peaked at 0.97 around 15360 steps and ended
at 0.88; these are training-process signals, not task performance.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The candidate preserved the parent's radial strata and did not
show a broad regression, which is an unexpected preservation signal, but it
did not meet the total-success threshold or repair any recurring failure.
Because no recurring case was repaired, the proposed stable-hold diagnostic
was not testable. This weakens hard-sector target resampling as a practical
route for this transfer recipe and budget; it does not establish that target
frequency, angular control, representation, or optimization is the causal
source of the residual failures.

**Interpretation:** Increasing exposure to the sector containing the recurring
failures did not change the measured failure identities or improve complete
task success relative to the working policy. The matching candidate and parent
measurements support rejecting this challenger for lineage selection, not a
claim that the policy is officially at the 98% objective. The conclusion is
limited to two measured checkpoints from one transfer trajectory, one fixed
development panel, and task-reference outputs without hold-entry or
interruption diagnostics; unmeasured checkpoints remain unknown.

**Evidence inspected:** `research/results.jsonl`; `research/brief.md`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-13-attempt-1.log`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-13-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-13-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-13-working-task-reference-v1.json`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 14

**Result:** The stronger post-hold outside-band penalty hypothesis was
contradicted under the tested transfer conditions. Checkpoint-120832 matched
the working policy at 197/200 but repaired none of its recurring failures, so
experiment-2 checkpoint-120832 remains working and best-known.

**Observed behavior:** The proposal expected at least 198/200 task-reference
success, repair of episode 84, 102, or 175 through a complete 100-step hold,
preservation of 48/48 middle-radius and at least 94/95 far-radius success, and
no concentrated new failure group. Checkpoint-100352 measured 196/200 with
54/57 near-radius, 48/48 middle-radius, and 94/95 far-radius successes; its
failures were 10, 84, 102, and 175. Checkpoint-120832 measured 197/200 with
55/57, 48/48, and 94/95 successes; its failures were 84, 102, and 175,
exactly matching the working policy's task-reference result.

Research evaluation reported the same totals. For recurring failures 84, 102,
and 175, all candidates first reached tolerance at step 17, but maximum
consecutive holds were 4, 2, and 2 steps at 100352 and 4, 2, and 3 steps at
120832; no recurring case achieved the required 100-step hold. The final
checkpoint removed the extra episode-10 failure seen at 100352. The training
proxy peaked at 1.0 near 20480 steps and ended at 0.99, while reward was
111.592 at 100352 and 108.548 at 120832.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. The final checkpoint preserved the middle- and far-radius
thresholds and avoided a lasting new failure group, which is an unexpected
preservation signal, but it did not reach 198/200 or repair any recurring
failure. The absence of a complete repaired hold directly fails the proposed
mechanistic success criterion. The result weakens stronger post-hold reward
feedback as a practical route for this transfer recipe and budget; it does not
show that the penalty is intrinsically non-causal or that angular control,
state information, or optimization is the universal explanation. The
conclusion is limited to two measured checkpoints from one transfer trajectory
on one fixed development panel; the 22 unmeasured checkpoints remain unknown.

**Interpretation:** Increasing the outside-band penalty from 0.1 to 0.5 did not
change the measured residual failure set or improve complete task success
relative to the working policy. The final candidate is therefore not retained.
Training proxy and reward again did not distinguish the measured task
checkpoint. This closure selects the existing working recipe, not an official
98% result.

**Evidence inspected:** `research/results.jsonl`; `research/brief.md`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-14-checkpoint-100352-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-14-checkpoint-120832-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-14-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-14-checkpoint-120832-task-reference-v1.json`;
`robot_learning/scenario/reward.py`;
`robot_learning/scenario/environment.py`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 15

**Result:** The global command-damping hypothesis was contradicted under the
tested transfer conditions. Checkpoints 100352 and 120832 both measured
196/200, below the working policy's 197/200, and repaired none of its recurring
failures. Experiment-2 checkpoint-120832 remains working and best-known.

**Observed behavior:** The proposal expected at least 198/200, an uninterrupted
100-step hold for at least one of episodes 84, 102, or 175, and preservation of
55/57 near-radius, 48/48 middle-radius, and 94/95 far-radius success. Both
checkpoints instead measured 54/57, 48/48, and 94/95, with failures 10, 84,
102, and 175. Research evaluation found first reach at steps 22, 22, and 21
for recurring episodes 84, 102, and 175, and maximum consecutive holds of
3/2/4 at checkpoint-100352 and 3/1/4 at checkpoint-120832. The working policy
had first reach at step 17 and maximum holds of 4/1/6. No candidate completed a
100-step hold. Aggregate interruptions fell from 240 for the working policy to
5 and 7 for the candidates. The training proxy reached 1.0 near 20480 steps
and ended at 0.98; the task-reference and research-evaluation results did not
show a corresponding task improvement. Twenty-two checkpoints were unmeasured.

**Hypothesis assessment:** **Contradicted** under the proposal's stated
conditions. Neither measured checkpoint reached 198/200 or repaired a named
recurring case, so the central task-progress and hold-repair predictions failed.
Preservation of the middle and far strata is a partial preservation signal, not
policy progress relative to the working policy. The much lower interruption
count is an unexpected diagnostic signal, but it occurred with later tolerance
entry and only brief holds; it does not establish reduced angular overshoot or
stable control. This conclusion is limited to the 0.75 scale, one transfer
trajectory, two measured checkpoints, and one fixed development panel. The
unmeasured checkpoints remain unknown, and the panel is not official benchmark
evidence.

**Interpretation:** Attenuating both physical commands changed the observed
hold trajectory without solving the residual task failures. The fewer recorded
interruptions may reflect fewer repeated tolerance contacts rather than better
holding, because all three recurring cases remained far below the required
duration. The result rejects this command-damping recipe for lineage selection
but does not distinguish state feedback, representation, target-specific
geometry, or PPO optimization as the cause of the persistent failures. The
working scientific recipe should therefore be restored before any later
experiment.

**Evidence inspected:** `research/results.jsonl`; `research/brief.md`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-15-attempt-1.log`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-15-working-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-15-checkpoint-100352-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-15-checkpoint-120832-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-15-working-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-15-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-15-checkpoint-120832-task-reference-v1.json`;
`robot_learning/scenario/policy_io.py`.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 16

**Result:** The velocity-augmented observation was partially supported under
fresh initialization. Checkpoint-110592 reached 198/200 and repaired recurring
episode 84 with a complete 100-step hold, so it replaces experiment-2
checkpoint-120832 as working and best-known development evidence. The later
checkpoint-120832 regressed to 196/200, so the improvement is not stable across
the measured trajectory and does not justify official assessment.

**Observed behavior:** On the fixed task-reference-v1 panel, the parent
working policy reached 197/200 with radial strata 55/57, 48/48, and 94/95 and
failed episodes 84, 102, and 175. Checkpoint-110592 reached 198/200 with
56/57, 48/48, and 94/95 and failed only 102 and 175, while checkpoint-120832
reached 196/200 with 55/57, 47/48, and 94/95 and failed 10, 102, 175, and
185. Research evaluation measured episode 84 at checkpoint-110592 with first
reach step 17, `max_held_steps=100`, and zero interruptions. Episodes 102 and
175 remained incomplete with maximum holds of 3 and 7; aggregate interruptions
were 245 at checkpoint-110592 versus 240 for the parent. The training log
reported proxy success 0.93 and reward 122.642 at 110592, then proxy success
0.93 and reward 119.654 at 120832. Twenty-two of 24 checkpoints were
unmeasured and remain unknown.

**Hypothesis assessment:** **Partially supported** under the proposal's tested
conditions. The expected observation was met at checkpoint-110592: it exceeded
197/200, repaired a named recurring episode with a complete 100-step hold, and
preserved or improved all radial strata. The later checkpoint contradicted the
stability part of that expectation by losing two successes, the middle-radius
stratum, and adding failures 10 and 185. Because the experiment used fresh
initialization, the evidence establishes measured policy progress for this
candidate but does not establish that the velocity features alone caused it;
initialization and optimization trajectory remain coupled. The result is from
one fixed development panel and is not official benchmark evidence.

**Interpretation:** Direct end-effector velocity is a plausible useful state
signal for at least one difficult near-target hold, consistent with the
episode-84 repair, but the unresolved episode-102 and episode-175 failures and
the late regression show that the mechanism is incomplete or the learned
trajectory is unstable. The unchanged aggregate interruption total and the
training proxy/reward trend argue against interpreting the result as a general
stability improvement or selecting by training metrics. A controlled
reproduction or transfer comparison is needed before claiming a velocity-specific
causal effect.

**Evidence inspected:** `research/results.jsonl`; `research/brief.md`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-16-attempt-1.log`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-16/inventory.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-16-working-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-16-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-16-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-16-working-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-16-checkpoint-110592-200ep-seed7300-ffdccdbf3357.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/evaluation-3f02f914-505c-481f-b995-e040c009974f-experiment-16-checkpoint-120832-200ep-seed7300-ffdccdbf3357.json`;
`robot_learning/scenario/observations.py`.
