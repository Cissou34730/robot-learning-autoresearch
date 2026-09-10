# Research postmortems

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Scientific strategy

**Direction:** Test whether bounded in-tolerance margin shaping can improve the
retained full-radius policy's hold completion, especially in the residual
-150 to -120 degree sector, without changing its policy interface or sacrificing
non-sector reach performance. This is a targeted diagnostic of hold stability,
not a commitment to reward shaping if the tradeoff persists.

**Lessons and limits:** Experiment 2's transferred full-radius policy improved
checkpoint-100352 research success from 97.4% to 97.5% and task-reference
success from 98.0% to 98.5%, but its hard sector still contained 24 of 25
research failures and included both never-reached targets and repeated hold
interruptions. Experiment 3's fresh 13-value observation policy scored 95.1%
on the research panel and 94.5% on the task-reference panel at 120,832 steps,
below the unchanged working policy's 97.5% and 98.5%. Its research failures
also included more never-reached and interrupted episodes than the control.
The comparison is evidence about this fresh run and these development panels,
not a causal estimate of every possible geometry representation or training
initialization. Before experiment 4, the parent reward forfeited none of the
accrued hold-progress potential on exit (`robot_learning/scenario/reward.py`).
Experiment 4 directly tested full forfeiture, but both measured checkpoints
scored 95.4% on the research panel
versus 97.5% for working, had 50/74 hard-sector successes just like working,
and had more failed episodes with hold interruptions (35 and 34 versus 14).
Its task-reference scores were also lower (96.5% and 96.0% versus 98.5%),
although this remains development evidence rather than an official verdict.
The available evidence still cannot distinguish whether all hard-sector
failures are caused by reachability, control, or hold stability.
Experiment 5's focused-angle transfer run did not improve the hard sector and
introduced broad non-sector and hold-interruption regressions, so this result
weakens insufficient angular coverage as the leading explanation under the
tested recipe. Training proxy success remained non-monotonic and did not
predict held-out task performance.

**Open questions:** Whether the remaining failures are primarily never-reach
events or control/hold dynamics remains unresolved. Whether checkpoint-aware
selection can reliably improve the current recipe remains uncertain. The
experiment does not show whether a geometry representation could help with
transfer or with a different encoding, nor whether a different coverage
schedule could avoid the regression observed here.

**Conditional next steps:** A future experiment may test control or hold
shaping, or a compatible observation/control intervention, using the retained
working policy as the comparison. If margin shaping fails, broaden the
investigation beyond hold stability toward action/control dynamics or a new
representation. Checkpoint selection should be measurement led rather than
inferred from training proxy metrics. Terminal assessment remains inappropriate
until a selected development policy has stronger evidence against the
structured failure sector.

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
