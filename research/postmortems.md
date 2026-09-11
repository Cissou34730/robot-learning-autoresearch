# Research postmortems

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Scientific strategy

**Direction:** Diagnose whether the retained 50/50 action-smoothing recipe is
reproducible from fresh initialization before adding another representation or
control intervention. Experiment 9 did not make the periodic target-direction
representation useful in the tested fresh run, so that direction is abandoned.
Use matched task measurements for checkpoint selection and do not treat training
proxies or development panels as a terminal verdict.

**Lessons and limits:** Experiment 7's 50/50 per-joint action smoother raised
matched research success from 97.5% to 97.7%, hard-sector success from 50/74
to 52/74, and reduced total interruption events from 256 to 18 at the selected
late checkpoint, while preserving non-sector and radius-bin performance.
Experiment 8's 75/25 refinement retained low interruption counts relative to
the unsmoothed incumbent, but its late checkpoint reached only 97.5% on the
matched panel, had the same 52/74 hard-sector result, more never-reach
failures (17 versus 15), and modest non-sector and short-radius regressions
relative to experiment 7. Experiment 9's late periodic-direction checkpoint
reached 89.5% on the research panel, with 17/74 hard-sector and 878/926
non-sector successes, 105 never-reach failures, and no hold interruptions; its
task-reference panel reached 90.5% with 19 failures. The protected panel for
experiment 7 remained 98.5% with three failures. These are observations from
single transferred or fresh runs and fixed development panels; they do not
establish causality for other filters, representations, or seeds. Experiments
2 and 6 remain controls: full-radius training improved short-radius behavior,
while margin shaping changed interruption diagnostics without increasing task
success.

**Open questions:** Whether the residual negative-angle failures arise
primarily from reachability, action dynamics, or run variability remains
unresolved. The experiment-7 smoother gain came from one transferred run and
was not reproduced as a protected-panel gain, so its fresh-run reliability is
unknown. Experiment 9 shows that the tested periodic encoding did not resolve
the failures, but does not exclude other controls or representations.
Unmeasured checkpoints cannot be ranked from training proxies.

**Conditional next steps:** If fresh replication recovers the smoother's
measured behavior, treat it as a dependable control and then target the
remaining reachability failures. If it does not, reconsider the recipe's
reliability before testing another intervention. The margin-shaped policy
remains a diagnostic alternative, not evidence of a better task policy, and a
different representation requires a clear measured task-performance rationale.
Terminal assessment should wait for stronger evidence against the structured
failure sector.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 1

**Result:** The fresh baseline produced a strong but not terminal policy.
Checkpoint-100352 is selected as the working and best-known lineage; the
official benchmark is not requested.

**Observed behavior:** The baseline completed 120,832 steps. Training logs
reported success 0 through 70,656 steps, then 0.06 at 75,776, 0.93 at
95,232, 0.97 at 100,352, and 0.95 at 120,832. Logged reward peaked at
163.85 at 86,016 steps, then was 117.32 at 100,352 and 112.02 at the final
checkpoint. Research evaluation measured checkpoint-100352 at 974/1,000
(97.4%) and checkpoint-120832 at 969/1,000 (96.9%). On the task-reference
panel, checkpoint-95232 scored 192/200 (96.0%), checkpoint-100352 scored
196/200 (98.0%), and checkpoint-120832 scored 194/200 (97.0%). For
checkpoint-100352, 17 of 26 research-panel failures never reached tolerance
and 9 entered tolerance but did not complete the hold. Its four
task-reference failures were truncated episodes at radii 6.73, 7.24, 9.91,
and 9.36 cm, with angles from -127.9 to -116.4 degrees. The training
environment code samples only 14-20 cm targets.

**Hypothesis assessment:** Partially supported. As an automatic baseline, the
experiment established substantial learned task performance and identified a
usable checkpoint, but it did not establish satisfaction of the human
objective. There was no researcher-authored proposal for this baseline, so no
proposal-specific expected_observation or contradicting_observation was
available to assess. The higher measured success at checkpoint-100352 than at
the completed checkpoint is a selection observation, not evidence that stopping
at that point caused the improvement. The 98.0% task-reference result is
development evidence on a fixed 200-episode panel, while the 97.4% research
result and the concentrated failure sector leave readiness for the official
verdict unresolved.

**Interpretation:** The saved checkpoint is useful progress toward the
objective, but residual failures are structured rather than random in the
available diagnostics. The short-radius task-reference failures are consistent
with the current training distribution omitting 6-14 cm targets, and the
research-panel sector pattern motivates testing broader target coverage.
Because the same evidence also contains failures at larger radii and does not
isolate training coverage from observation, control, or policy variance, that
mechanism remains a hypothesis rather than a causal conclusion.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`, `research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-1/inventory.json`,
`research/training_logs/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-1-attempt-1.log`,
the five experiment-1 artifacts under
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/`, and
`robot_learning/scenario/environment.py`,
`robot_learning/scenario/evaluation.py`.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 2

**Result:** Broader target-radius training produced a useful but non-terminal
success improvement at checkpoint-100352. That checkpoint becomes the working
and best-known lineage; the completed checkpoint is not selected.

**Observed behavior:** The transferred run completed 120,832 local steps.
Training success was 0.966 at 5,120 steps, reached 0.99 at 100,352 steps,
then fell to 0.94 at completion; mean training reward fell from 113.72 at
100,352 to 110.99 at completion. These are training facts, not policy
rankings. Research evaluation measured checkpoint-100352 at 975/1,000
(97.5%), checkpoint-120832 at 972/1,000 (97.2%), and the incumbent at
974/1,000 (97.4%). On the task-reference panel, both experiment-2
checkpoints scored 197/200 (98.5%), versus 196/200 (98.0%) for the incumbent.
This unchanged task-reference result at the completed checkpoint is an
orthogonal cross-panel signal because its research-panel success was lower than
the early checkpoint's.
For checkpoint-100352, 11 of 25 research failures never reached tolerance and
14 lost the hold after reaching it. Its -150 to -120 degree sector had 24/74
failures; all other sectors had at most one failure. In the research
radius bins, success was 98.2% at 6-10 cm and 97.3% at 18-20 cm. The three
task-reference failures were two targets at 9.92 and 9.36 cm in the hard
sector and one target at 18.24 cm and -154.79 degrees.

**Hypothesis assessment:** Partially supported. The expected observation was
partly present: the early transferred checkpoint improved overall measured
success modestly and reduced short-radius failures, while task-reference
success increased to 98.5%. The contradicting observation was also present:
the concentrated negative-angle failures persisted and were slightly worse,
far-radius research success declined relative to the incumbent, and the
completed checkpoint was weaker than the early checkpoint. Therefore the
measurements support missing-radius coverage as a useful contributor to the
short-radius behavior under these panels, but weaken it as an explanation for
the dominant negative-angle failures. The comparison is limited to one
transferred run and compatible fixed development panels; it does not establish
causality or official-task attainment.

**Interpretation:** Full-radius coverage is worth retaining because it produced
a measured short-radius improvement without a broad collapse in performance,
but it did not resolve the residual failure pattern that limits readiness.
The early checkpoint is more useful than the completed checkpoint on the
research panel, so the lineage decision preserves that checkpoint. Future
scientific effort should prioritize observation or control generalization and
checkpoint selection rather than assume that adding radius coverage alone
will satisfy the objective.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-2-checkpoint-100352-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-2-checkpoint-120832-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-2-working-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/task-reference-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-2-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/task-reference-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-2-checkpoint-120832-task-reference-v1.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/task-reference-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-2-working-task-reference-v1.json`,
`robot_learning/scenario/environment.py`,
`robot_learning/scenario/evaluation.py`, and
`research/query_training_log.py`.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 3

**Result:** The absolute-target-geometry intervention did not improve the
measured policy. The experiment is closed with the existing `working` and
`best_known` lineage unchanged; the geometry observation recipe is reverted and
the official benchmark is not requested.

**Observed behavior:** The fresh run completed 120,832 steps. Training proxy
success rose from 0 to 0.81; logged mean reward was 167.668 at checkpoint
105,472 and 129.873 at checkpoint 120,832. These are training facts, not
policy evaluations. Research evaluation measured checkpoint-105472 at
92.8% (928/1,000), checkpoint-120832 at 95.1% (951/1,000), and the unchanged
working policy at 97.5% (975/1,000). The paired comparisons on the same
research episodes favored the working policy by 47 and 24 successes,
respectively. Task-reference measurements were 89.5% (179/200), 94.5%
(189/200), and 98.5% (197/200), respectively.

In the research diagnostics, checkpoint-105472 had 72 failed episodes, of
which 30 were in the -150 to -120 degree sector, 22 never reached tolerance,
and 50 had at least one hold interruption. Checkpoint-120832 had 49 failed
episodes, 27 in that sector, 17 never reaching tolerance, and 32 with hold
interruptions. The working policy had 25 failed episodes, 24 in that sector,
11 never reaching tolerance, and 14 with hold interruptions. On the fixed
task-reference panel, the working policy had 3 failures, while the two
geometry checkpoints had 21 and 11. The 22 other experiment-3 checkpoints
remain unmeasured.

**Hypothesis assessment:** Contradicted under the tested fresh run. The
expected observation was fewer hard-sector reach and hold failures without
regressing other geometry; neither measured geometry checkpoint beat the
working policy, and both showed worse overall and task-reference success. The
hard-sector failure count and failed-episode diagnostics did not improve.
Checkpoint-120832 was better than checkpoint-105472, which is an unexpected
training-trajectory signal but not evidence of policy acceptance. The result
weakens the representation explanation for this residual under the tested
recipe, while the single fresh run and incompatible observation contract limit
causal claims about other encodings or transfer conditions.

**Interpretation:** Directly appending target x and y did not solve the
structured failure pattern and was accompanied by broad measured regression.
The discrepancy between rising training proxy success and sub-control
development success indicates that training logs were useful for checkpoint
selection but did not predict held-out task behavior here. The evidence favors
preserving the experiment-2 full-radius working policy and investigating
control or hold-stability shaping before another representation test.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`,
`research/training_logs/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-3-attempt-1.log`,
`research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-3/inventory.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-3-checkpoint-105472-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-3-checkpoint-120832-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-3-working-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/task-reference-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-3-checkpoint-105472-task-reference-v1.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/task-reference-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-3-checkpoint-120832-task-reference-v1.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/task-reference-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-3-working-task-reference-v1.json`,
`robot_learning/scenario/observations.py`.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 4

**Result:** Full hold-progress forfeiture did not improve the measured policy.
The experiment is closed with the existing `working` and `best_known`
lineages unchanged, the experiment-4 reward recipe reverted, and the official
benchmark not requested.

**Observed behavior:** Training completed 120,832 local steps. Training proxy
success ranged from 0.94 to 1.00 across the recorded checkpoints, with 0.971
at the first checkpoint and 0.99 at the final checkpoint; mean reward was
103.747 at checkpoint-95232 and 102.474 at checkpoint-120832. These are
training facts, not task-performance measurements. On the compatible
1,000-episode research panel, both checkpoint-95232 and checkpoint-120832
scored 954/1,000 (95.4%), versus 975/1,000 (97.5%) for `working`. The paired
comparisons had no challenger wins and 21 working wins for each checkpoint.
On the fixed 200-episode task-reference panel, the checkpoints scored 96.5%
and 96.0%, versus 98.5% for `working`.

The research diagnostics showed 50/74 successes in the -150 to -120 degree
sector for each experiment-4 checkpoint and for `working`. Among failed
research episodes, 11 and 12 never reached tolerance for the two challenger
checkpoints, versus 11 for `working`; failed episodes with at least one hold
interruption numbered 35 and 34, versus 14 for `working`. Radius behavior was
also lower for the challenger: short-radius success was 271/283 and 264/283,
versus 278/283 for `working`, while far-radius success was 108/111 and
107/111, versus 108/111. The two measured late checkpoints had identical
research success, while the completed checkpoint was slightly lower on the
task-reference panel.

**Hypothesis assessment:** Contradicted under the tested transferred recipe
and development panels. The expected observation was fewer hold interruptions
and hard-sector failures while preserving short- and far-radius competence.
Hard-sector success was unchanged, failed episodes with hold interruptions
were higher, and short-radius success regressed; far-radius success was
preserved at the earlier checkpoint but slightly lower at completion. The
contradicting observations weaken hold-exit forfeiture as a useful direction
for this policy, but one transferred intervention and these development
panels do not establish that every hold-stability intervention is ineffective.

**Interpretation:** The intervention did not convert the structured
negative-angle failures into completions. The high training proxy and reward
signals did not predict held-out task performance in this run, and neither
measured late checkpoint provided a useful alternative to the incumbent.
The unchanged never-reached count and unchanged hard-sector success leave
reachability or control as plausible residual limitations; the increased
interruption count is consistent with, but does not prove, degraded hold
stability. The saved experiment-4 candidates are therefore not useful
working or best-known policies.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`,
`research/training_logs/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-4-attempt-1.log`,
`research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-4/inventory.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-4-checkpoint-95232-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-4-checkpoint-120832-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-4-working-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/task-reference-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-4-checkpoint-95232-task-reference-v1.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/task-reference-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-4-checkpoint-120832-task-reference-v1.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/task-reference-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-4-working-task-reference-v1.json`,
`robot_learning/scenario/reward.py`.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 5

**Result:** Focused angular training coverage did not improve the measured
policy. The experiment is closed with the existing `working` and `best_known`
lineages unchanged, the focused-angle training recipe reverted, and the
official benchmark not requested.

**Observed behavior:** The transferred run completed 120,832 local steps.
Training proxy success was 0.9429 at 5,120 steps, declined to 0.78 at 75,776,
and recovered to 0.82 at completion; mean reward peaked at 108.63 at
checkpoint-100352 and was 98.51 at completion. These are training facts, not
task-performance measurements. On the compatible 1,000-episode research panel,
checkpoint-100352 scored 88.7% and checkpoint-120832 scored 87.9%, versus
97.0% for `working`. Paired comparisons favored `working` by 83 and 91
successes, respectively, with no challenger wins. The task-reference panel
similarly measured 95.5% and 91.0% for the two checkpoints versus 98.5% for
`working`.

The research diagnostics showed hard-sector success of 46/70 and 47/70 for
the two focused-coverage checkpoints, versus 48/70 for `working`. Non-sector
success was 841/930 and 832/930, versus 922/930 for `working`; short-radius
success was 239/265 and 243/265, versus 256/265; far-radius success was
155/164 for both, versus 156/164. Among failed research episodes, never-reach
counts were 13 and 15, versus 10, while episodes with hold interruptions were
100 and 106, versus 20. On the smaller task-reference panel, the early
checkpoint matched `working` in the hard sector at 15/17 and far radius at
31/32, but regressed outside the sector; the completed checkpoint fell to
14/17 in the hard sector and 168/183 outside it.

**Hypothesis assessment:** Contradicted under the tested transferred recipe
and development panels. The expected observation—improved hard-sector reach
and hold success while preserving non-sector and radius-bin performance—was
not observed. The hard sector was unchanged or slightly worse, while
non-sector success and hold-interruption outcomes regressed substantially.
The contradicting observation was therefore present. This weakens simple
angular under-coverage as the explanation for the residual failures in this
recipe, but one transfer run does not disprove every coverage schedule or
establish that control or hold dynamics is causal.

**Interpretation:** The measured task behavior does not support retaining the
focused-angle candidates: both were materially worse than the incumbent on
the matched research panel and the protected development panel. The early
candidate's preserved far-radius result and matched small-panel hard-sector
count are partial, orthogonal signals, not evidence of overall progress.
The non-monotonic training proxy and reward trajectory also show that training
logs did not identify a useful policy checkpoint here. The increased
hold-interruption count is consistent with degraded hold stability, while the
never-reach counts remain similar; neither observation isolates the mechanism.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/training_logs/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-5-attempt-1.log`,
`research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-5/inventory.json`,
the three experiment-5 research-evaluation artifacts under
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/`, the three
experiment-5 task-reference artifacts under that directory, and
`research/query_training_log.py`.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 6

**Result:** Bounded hold-margin shaping produced a useful hold-diagnostic
signal but no measured task-success improvement. The experiment is closed with
the existing `working` and `best_known` lineages unchanged, the margin-shaped
reward recipe reverted, the early margin-shaped checkpoint retained as a
diagnostic alternative, and the official benchmark not requested.

**Observed behavior:** The transferred run completed 120,832 local steps.
Training proxy success ranged from 0.92 to 1.00: it was 0.9737 at 5,120
steps, reached 1.00 around 18,432-22,528 steps, and was 0.94 at both
100,352 and 120,832 steps. Logged mean reward rose to 169.07 at 110,592
steps and fell to 157.15 at completion. These are training facts, not task
performance measurements. On the matched 1,000-episode research panel,
checkpoint-100352 scored 975/1,000 (97.5%), checkpoint-120832 scored
974/1,000 (97.4%), and `working` scored 975/1,000 (97.5%). The early
checkpoint had 1 paired win and 1 paired loss against `working`; the late
checkpoint had 1 paired win and 2 paired losses.

The early checkpoint had 51/74 successes in the -150 to -120 degree sector
versus 50/74 for `working`, 924/926 non-sector successes versus 925/926,
278/283 short-radius successes for both, and 108/111 far-radius successes
for both. Its failed episodes included 12 never-reach cases versus 11 for
`working`, and 13 with an interruption versus 14; total recorded interruption
events were 35 versus 256. The late checkpoint had 51/74 hard-sector,
923/926 non-sector, 278/283 short-radius, and 107/111 far-radius successes,
with 17 never-reach cases, 9 failed episodes with interruptions, and 251
total interruption events. On the fixed task-reference panel, both
checkpoints and `working` scored 197/200 (98.5%), with identical 15/17
hard-sector, 182/183 non-sector, 55/57 short-radius, and 31/32 far-radius
results. Their three task-reference failures were the same targets near
9.91 cm at -122.90 degrees, 9.36 cm at -127.91 degrees, and 18.24 cm at
-154.79 degrees.

**Hypothesis assessment:** Partially supported, with important limits. The
expected diagnostic branch appeared at the early checkpoint: repeated
interruption events were much fewer, hard-sector success increased by one
episode, and radius-bin performance was preserved. However, the measured
research success was unchanged, the count of failed episodes with
interruptions changed only from 14 to 13 while never-reach failures increased
from 11 to 12, and the task-reference outcomes were identical. The late
checkpoint lost one research success, regressed outside the hard sector and
at far radius, and did not preserve the early interruption reduction. Thus
the intervention's hold-margin signal is informative, but the contradicting
observation of no aggregate task-success gain is also present. This is
evidence about one transferred reward intervention on these development
panels, not a causal conclusion about all hold shaping.

**Interpretation:** The early policy appears to avoid repeated excursions
within some failed trajectories without converting those trajectories into
successful uninterrupted holds. The unchanged task-reference failure set and
the persistent negative-angle concentration leave reachability or control
dynamics as plausible limiting factors. The training proxy and reward
trajectory again did not identify a superior held-out checkpoint. The early
candidate is worth retaining as a diagnostic control because its task success
matches `working` while its interruption-event profile differs, but it is not
supported as the new working or best-known policy. Neither development panel
supports requesting the official benchmark for this closure.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/query_training_log.py`, the experiment-6 research-evaluation
artifacts for `checkpoint-100352`, `checkpoint-120832`, and `working` under
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/`, and the three
corresponding experiment-6 task-reference artifacts.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 7

**Result:** Action smoothing partially supported the control hypothesis and
produced the strongest measured research-panel result in the campaign so far,
but it did not improve the protected task-reference panel or establish the
98% objective. The late smoothed checkpoint is selected as working and
best-known, the smoothed recipe is kept, and terminal assessment is not
requested.

**Observed behavior:** The transferred run completed 120,832 local steps
against a requested 120,000. The queried training proxy success was 0.884615
at 5,120 steps, reached 1.00 at 22,528 steps, varied non-monotonically
thereafter, and was 0.99 at both measured checkpoints and at completion.
Logged mean reward was 104.846 at checkpoint-100352 and 105.245 at
checkpoint-120832. These are training facts, not held-out task-performance
measurements; 22 of the 24 available checkpoints remain unmeasured.

On the matched 1,000-episode research panel, checkpoint-100352 and
checkpoint-120832 each scored 977/1,000 (97.7%), while `working` scored
975/1,000 (97.5%). Each smoothed checkpoint had 52/74 successes in the
-150 to -120 degree sector versus 50/74 for `working`, 925/926 outside that
sector versus 925/926, 278/283 at short radius versus 278/283, and 109/111
at far radius versus 108/111. Failed episodes that never reached tolerance
numbered 16 and 15 for the early and late checkpoints versus 11 for
`working`; failed episodes with at least one hold interruption numbered 7 and
8 versus 14. Total recorded interruption events were 26 and 18 versus 256,
including a maximum of 236 for one incumbent episode. The paired comparisons
had two challenger wins and no incumbent wins among two discordant episodes
for each smoothed checkpoint.

On the fixed 200-episode task-reference panel, both smoothed checkpoints and
`working` scored 197/200 (98.5%) and had the same three failed episode
identities: targets at 9.91 cm and -122.90 degrees, 9.36 cm and -127.91
degrees, and 18.24 cm and -154.79 degrees. The research and task-reference
panels therefore provide an orthogonal signal: the research gain is not
reproduced as a success gain on the protected panel.

**Hypothesis assessment:** Partially supported under the tested transferred
recipe and development panels. The expected observations were present in the
research evaluation: hard-sector success increased, interruption events
decreased sharply, and non-sector and radius-bin performance did not regress.
The contradicting observation was also present: never-reach failures
increased, and task-reference success and its failure set were unchanged.
Thus the measurements support temporal command dynamics as a contributor to
the tested research-panel behavior, but do not show that smoothing converts
the residual failures into a reliable official-task improvement. This is
evidence from one smoothing factor, one transferred run, and repeated fixed
development panels; it does not establish causality for other filters or
control representations.

**Interpretation:** The smoother appears to suppress repeated excursions in
failed trajectories and converts two hard-sector research episodes into
successes without broad measured regression. The accompanying increase in
never-reach failures indicates a lag or reachability tradeoff remains, and
the unchanged task-reference failures show that the structured negative-angle
limitation is not resolved. The late checkpoint is preferred to the early
checkpoint because it has the same aggregate success and sector/radius
results with fewer total interruption events and fewer failed never-reach
episodes, but that selection is diagnostic rather than proof that late
training caused the difference. The 97.7% research result is useful progress
toward the human objective but remains below a conclusive terminal-readiness
claim.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/query_training_log.py`, `robot_learning/scenario/policy_io.py`, the
experiment-7 research-evaluation artifacts for `checkpoint-100352`,
`checkpoint-120832`, and `working` under
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/`, and the three
corresponding experiment-7 task-reference artifacts.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 8

**Result:** The 75/25 action-smoothing refinement is closed with the
experiment-7 `working` and `best_known` lineages unchanged. The experiment-8
recipe is reverted, no experiment-8 candidate is retained, and the official
benchmark is not requested.

**Observed behavior:** The transferred run completed 120,832 local steps.
Training proxy success was 0.975 at 5,120 steps, reached 1.00 at 20,480
steps, varied non-monotonically thereafter, and was 0.97 at completion.
Logged mean reward peaked at 108.58 at 90,112 steps and was 104.22 at
120,832. These are training facts, not held-out task-performance
measurements; 22 of the 24 checkpoints remain unmeasured.

On the matched 1,000-episode research panel, checkpoint-100352 scored 974/1,000
(97.4%) and checkpoint-120832 scored 975/1,000 (97.5%), below experiment 7's
selected 977/1,000 (97.7%). The early and late experiment-8 checkpoints had
51/74 and 52/74 successes in the -150 to -120 degree sector, 923/926 and
923/926 outside it, 277/283 and 277/283 at short radius, and 108/111 and
108/111 at far radius. Failed episodes that never reached tolerance numbered
18 and 17, versus 15 for experiment 7. Failed episodes with at least one
hold interruption numbered 8 at both checkpoints, and total interruption
events were 19 and 8, versus 18 for experiment 7; all were still far below
the unsmoothed incumbent's 256 events. Matched episode outcomes favored
experiment 7 by 3 wins to 0 for the early checkpoint and 2 to 0 for the late
checkpoint.

On the fixed 200-episode task-reference panel, the early checkpoint scored
196/200 (98.0%) and the late checkpoint scored 197/200 (98.5%). The late
checkpoint had the same three failed target identities as experiment 7:
9.91 cm at -122.90 degrees, 9.36 cm at -127.91 degrees, and 18.24 cm at
-154.79 degrees. The early checkpoint additionally failed at 7.24 cm and
-125.40 degrees. These are development-panel observations, not an official
benchmark result.

**Hypothesis assessment:** Weakened under the tested transferred recipe and
development panels. The expected interruption reduction relative to the
unsmoothed incumbent was retained, but the less-lagging filter did not improve
matched success or hard-sector success, did not reduce never-reach failures,
and introduced modest non-sector and radius-bin regressions relative to the
experiment-7 smoother. The late protected-panel score and failure set were
unchanged, while the early protected-panel score regressed. Thus the
measurements weaken the proposition that this 75/25 refinement recovers
reachability while preserving the 50/50 policy's benefits. They do not
disprove other temporal filters, representations, or the possibility of
run-to-run variation.

**Interpretation:** Less lag alone did not address the residual negative-angle
failure pattern in this transferred run. The low interruption count indicates
that temporal smoothing can remain diagnostically relevant, but the measured
task behavior does not support replacing the experiment-7 recipe with the
75/25 refinement. The stronger training proxies at several checkpoints did
not identify a better held-out policy, reinforcing that checkpoint selection
must use measured task behavior.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/query_training_log.py`,
`research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-8/inventory.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-8-checkpoint-100352-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-8-checkpoint-120832-1000ep-seed91000-ffdccdbf3357.json`,
the corresponding experiment-8 task-reference artifacts under
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/`, and the
experiment-7 late research and task-reference artifacts used for comparison.
## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 9

**Result:** The fresh periodic target-direction observation did not improve the
learned task policy under the tested run. The experiment-7 `working` and
`best_known` lineages remain selected, the experiment-9 recipe is reverted, and
terminal assessment is not requested.

**Observed behavior:** Training completed 120,832 local steps. The training
proxy ranged from 0 to 0.52 and ended at 0.52; logged reward rose from -4.09 at
5,120 steps to 144.696 at checkpoint-120832. These are training facts, not
held-out task-performance measurements. On the matched 1,000-episode research
panel, checkpoint-100352 scored 799/1,000 (79.9%) and checkpoint-120832 scored
895/1,000 (89.5%). The late checkpoint improved over the early checkpoint, but
the matched paired comparisons favored the experiment-7 late checkpoint by
178 and 82 discordant episodes respectively. Relative to that checkpoint's
52/74 hard-sector and 925/926 non-sector results, the experiment-9 late
checkpoint achieved 17/74 and 878/926. It had 105 never-reach failures and no
hold-interruption events; the early checkpoint had 192 never-reach failures and
148 interruption events. On the fixed 200-episode task-reference panel, the
early and late checkpoints scored 81.0% and 90.5%, with 38 and 19 failures,
versus 98.5% and three failures for the experiment-7 late checkpoint. The
zero-interruption result is a partial hold-stability signal, while the
within-run late improvement and the training-proxy increase are orthogonal to
the claim of improved task performance.

**Hypothesis assessment:** Contradicted under the tested fresh recipe and
development panels, with an important partial signal. The expected sector and
overall improvements were absent: the late periodic checkpoint was far below
the 50/50 smoother in hard-sector, non-sector, research-panel, and
task-reference success, and never-reach failures remained numerous. The
expected hold-stability component was present as zero interruption events, but
that did not yield reachability or overall task progress. This matches the
proposal's contradicting observation of sacrificing broad performance while
failing to resolve reachability. The result weakens this periodic encoding as a
useful contributor in this run; it does not disprove other representations or
attribute the residual failures causally to action dynamics.

**Interpretation:** The added absolute-direction sine and cosine channels did
not make the structured failure sector learnable in this fresh PPO run. The
policy appears to have avoided hold interruptions when it reached tolerance,
but usually failed before reaching it, so the representation change traded
away broad reachability rather than complementing the smoother. The late
checkpoint is better than the early one within this run, but both are
inferior to the retained measured policy; this checkpoint selection is
descriptive and does not show that additional training caused the improvement.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/query_training_log.py`, `research/postmortems.md`,
`robot_learning/scenario/observations.py`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-9-checkpoint-100352-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-9-checkpoint-120832-1000ep-seed91000-ffdccdbf3357.json`,
the corresponding experiment-9 task-reference artifacts, and the experiment-7
late research and task-reference artifacts used for comparison.
