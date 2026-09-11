# Research postmortems

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Scientific strategy

**Direction:** Preserve the measured experiment-7 action-smoothing policy as the
practical incumbent while diagnostically testing whether its reachability
residual is caused by weak reward resolution near the 1 cm tolerance. The
sector-specific smoothing reduction and low-rate replay did not help under
transfer, so this investigation changes the final-approach reward signal without
changing the learned observation or action interface. Fresh-run instability
remains a boundary condition for transfer experiments rather than a reason to
restart from scratch. Training proxies and development panels remain
development evidence rather than a terminal verdict.

**Lessons and limits:** Experiment 7's 50/50 per-joint action smoother raised
matched research success from 97.5% to 97.7%, reduced late interruption events
from 256 to 18, and retained 98.5% on the fixed task-reference panel.
Experiments 10 and 14, both fresh unchanged replications, instead remained far
below that transferred result: experiment 10 reached 70.4% late research
success, while experiment 14 reached 64.6%, 57.5%, and 52.3% at its three
measured checkpoints. In experiment 14, the late checkpoint had 431 never-reach
failures, 46 interrupted failures, and 632 interruption events; 265 of its 477
failures were in positive 60-to-180 degree bins, but substantial negative-angle
failures remained. This supports fresh-run instability or transfer dependence
under the tested recipe, without separating those explanations. Experiments 11 and 12 preserved broad transferred competence but did not remove
the incumbent's residual failures, experiment 13's low-rate negative-angle
replay did not improve them, and experiment 15's sector-specific reduction from
50/50 to 75/25 recovered none of the incumbent's 23 matched failures while
raising interruption events from 18 to 30 or 37. Experiment 15 did preserve
all incumbent successes outside the target sector and the 197/200
task-reference outcomes, so its negative result is specific to the proposed
recovery rather than a broad collapse. Training-proxy peaks and within-run
reward increases remain orthogonal to measured task progress. All comparisons
use fixed development panels and do not establish generalization or causality;
no official benchmark result exists.

**Open questions:** The cause of the incumbent's residual failures in the
negative-angle sector remains unresolved; 15 of 23 matched research failures
never reached tolerance, but the evidence does not distinguish weak final-
approach reward shaping from control, representation, optimization, or transfer
effects. The fresh-run regression is still not separated into optimization
variance, transfer history, or control dynamics. Unmeasured checkpoints cannot
be ranked from training proxies.

**Conditional next steps:** Measure the near-tolerance reward intervention on
compatible task-performance panels with angle and hold diagnostics. If it does
not reduce hard-sector never-reach failures without broad regression, retain the
incumbent and reassess representation or branch-selection explanations rather
than repeating smoothing or replay. Terminal assessment should wait for
stronger evidence that the selected policy is ready for the official objective.

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

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 10

**Result:** The fresh replication did not reproduce experiment 7's measured
50/50 action-smoothing performance. The experiment-7 `working` and
`best_known` lineages remain selected, the unchanged recipe is kept, the
experiment-10 candidates are not retained, and terminal assessment is not
requested.

**Observed behavior:** Training completed 120,832 local steps. The queried
training proxy was 0 through 90,112 steps, rose to 0.07 at checkpoint-100352,
and ended at 0.27 at checkpoint-120832; mean reward rose from -8.19 at 5,120
steps to 129.49 at completion. These are training facts, not held-out task
performance. On the matched 1,000-episode research panel,
checkpoint-100352 scored 694/1,000 (69.4%) and checkpoint-120832 scored
704/1,000 (70.4%). The late checkpoint improved by 10 episodes within this
run, but remained far below experiment 7's late 977/1,000 (97.7%) result.
At the late checkpoint, 191 episodes never reached tolerance and 105 reached
tolerance but failed the complete hold; the diagnostics recorded 125
interruption events. In contrast, experiment 7's late checkpoint had 15
never-reach failures, 8 interrupted failures, and 18 interruption events.

The fresh late checkpoint unexpectedly succeeded in all 74 episodes in the
experiment-7 hard sector (-150 to -120 degrees). Its research-panel success
was instead poor in positive-angle bins: 35/81 at 60 degrees, 2/76 at 90
degrees, 2/83 at 120 degrees, and 27/98 at 150 degrees. On the fixed
200-episode task-reference panel, both measured checkpoints scored 144/200
(72.0%). The late checkpoint failed all 24 targets in the 120-degree bin,
along with most targets from 90 to 180 degrees and three targets near -170
degrees. Twenty-two of the 24 available training checkpoints remain
unmeasured.

**Hypothesis assessment:** Contradicted under this fresh replication, with
partial and orthogonal signals. The proposal's expected observation of
experiment-7-like overall performance, low interruption counts, and comparable
protected-panel behavior was not observed. The contradicting observation was
present in the large overall regression, the much higher interruption count,
and the 72.0% task-reference result. The complete 74/74 hard-sector result is
a partial signal in the expected direction, while the shift to positive-angle
failures is unexpected relative to experiment 7. The within-run improvement in
research success and the rise in training reward are orthogonal to a claim of
task-policy progress. This weakens reproducibility of the recipe from fresh
initialization, but does not disprove smoothing under the original transferred
conditions or identify whether transfer history or run variability caused the
difference.

**Interpretation:** The fresh policy learned a materially different behavior
from the retained transferred policy: late training reduced never-reach
failures but left broad positive-angle reachability failures and introduced
many more failed holds. The evidence is consistent with the experiment-7 gain
depending on transfer history or ordinary run variability, but one fresh
replication cannot separate those explanations. The retained experiment-7
policy remains the strongest measured candidate and is useful progress toward
the objective, but the development evidence is not sufficient for terminal
assessment.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/query_training_log.py`,
`research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-10/inventory.json`,
`research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-10/parameters.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-10-checkpoint-100352-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-10-checkpoint-120832-1000ep-seed91000-ffdccdbf3357.json`,
the corresponding experiment-10 task-reference artifacts, and the
experiment-7 late research and task-reference artifacts used for comparison.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 11

**Result:** The unchanged continuation preserved the retained basin but did
not improve measured task performance. The experiment-7 `working` and
`best_known` lineages remain selected, the experiment-11 candidates are not
retained, and terminal assessment is not requested.

**Observed behavior:** Training completed 120,832 local steps, reaching 442,368
accumulated steps. Training success ranged from 0.94 to 1.00 across the
queried checkpoints; it reached 1.00 at several intermediate checkpoints and
ended at 0.98, while mean reward peaked at 106.27 at checkpoint-110592 and
ended at 104.46. These are training facts, not held-out task performance. On
the matched 1,000-episode research panel, checkpoint-100352 scored 976/1,000
(97.6%), checkpoint-110592 scored 975/1,000 (97.5%), and
checkpoint-120832 scored 975/1,000 (97.5%). Their diagnostics recorded,
respectively, 18, 17, and 18 never-reach cases and 18, 17, and 17 interruption
events. On the fixed 200-episode task-reference panel, all three checkpoints
scored 197/200 (98.5%); the same three episodes failed each time, at target
angles approximately -122.9, -127.9, and -154.8 degrees.

**Hypothesis assessment:** Partially supported, with the improvement branch
weakened. The expected observation that continuation would preserve broad
competence was present: all measured checkpoints remained close to the
experiment-7 research result of 97.7%, matched its 98.5% task-reference result,
and showed no broad panel regression. The expected observation of reduced
residual reachability or hold failures was not observed, and no checkpoint
exceeded the incumbent on the matched research panel. The contradicting
observation therefore supports a plateau under this unchanged continuation,
but does not establish why the plateau occurred. The high training proxies and
their within-run oscillation are orthogonal to a claim of task-policy progress.

**Interpretation:** The measured policies are practically equivalent to the
retained experiment-7 policy on the available development panels, with a small
research-panel decline rather than a gain. The repeated task-reference
failures and nearly unchanged research diagnostics are consistent with a
residual behavior that further unchanged PPO updates did not remove. Because
the evidence uses fixed development panels and only three continuation
checkpoints, it does not establish generalization, causality, or whether a
different intervention could address those failures. The retained policy
remains useful progress toward the objective, but the evidence is not ready for
terminal assessment.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/query_training_log.py`,
`research/training_logs/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-11-attempt-1.log`,
`research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-11/inventory.json`,
`research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-11/parameters.json`,
the three experiment-11 research-evaluation artifacts, and the three
experiment-11 task-reference artifacts under
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/`.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 12

**Result:** Distance-conditioned action smoothing did not improve measured
task performance. The experiment is closed with the experiment-7 `working`
and `best_known` lineages unchanged, the smoothing intervention reverted, and
terminal assessment not requested.

**Observed behavior:** Training completed 120,832 local steps (442,368
accumulated steps). Queried training success ranged from 0.94 to 1.00,
including 1.00 at checkpoint-110592, and ended at 0.97; mean training reward
was 105.73 at checkpoint-110592 and 104.38 at checkpoint-120832. These are
training facts, not held-out policy evaluations. Research evaluation measured
both checkpoints at 975/1,000 (97.5%), versus 977/1,000 (97.7%) for the
incumbent on the compatible 1,000-episode panel. The 110592 and 120832
checkpoints had 25 failures each, with 13 and 14 never-reach cases, 23 hard
sector failures each, and 35 and 39 total hold-interruption events; the
incumbent had 23 failures, 15 never-reach cases, 22 hard-sector failures, and
18 interruption events. On the fixed 200-episode task-reference panel, both
checkpoints scored 197/200 (98.5%) and repeated the incumbent's same failures
at approximately 9.91 cm/-122.9 degrees, 9.36 cm/-127.9 degrees, and
18.24 cm/-154.8 degrees.

**Hypothesis assessment:** Contradicted under this transferred run, with the
scope limited to the tested recipe and development panels. The expected
observation of fewer never-reach or residual-sector failures did not occur:
overall research success was lower, hard-sector failures were not reduced, and
the late checkpoint had more never-reach cases. The expected low interruption
profile was also not preserved, with 35 and 39 total events versus 18 for the
incumbent. Broad task-reference success was preserved, which is a partial
non-regression signal, but it did not establish policy progress. These results
match the proposal's contradicting observation and weaken the approach-lag
explanation; they do not establish that the alternative explanation is causal.

**Interpretation:** Changing the approach blend outside 3 cm did not make the
retained basin more successful and did not preserve its hold-stability
diagnostic. The repeated task-reference failures and near-incumbent research
profile suggest that this control change is not useful for the current
residual pattern under the tested transfer. The measured incumbent remains
the stronger policy selection, but its 97.7% research result and fixed-panel
98.5% result do not justify an official-task claim or terminal assessment.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/query_training_log.py`,
`research/training_logs/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-12-attempt-1.log`,
`research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-12/inventory.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-12-checkpoint-110592-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-12-checkpoint-120832-1000ep-seed91000-ffdccdbf3357.json`,
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/evaluation-6bbe4246-0dbc-4e66-9f31-0b66c0388867-experiment-12-working-1000ep-seed91000-ffdccdbf3357.json`,
and the three experiment-12 task-reference artifacts under
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/`.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 13

**Result:** The 10% residual-angle replay did not improve measured task
performance. The experiment is closed with the experiment-7 `working` and
`best_known` lineages unchanged, the training-sampler intervention reverted,
and terminal assessment not requested.

**Observed behavior:** Training completed 120,832 local steps. Training
success ranged from 0.93 to 1.00, reached 1.00 at checkpoint-25,600, and
ended at 0.95; mean training reward peaked at 107.37 near checkpoint-30,720
and was 101.21 at completion. Research evaluation measured checkpoint-25,600
at 975/1,000 (97.5%), checkpoint-90,112 at 974/1,000 (97.4%), and
checkpoint-115,712 at 974/1,000 (97.4%). The 25, 26, and 26 failures were all
in the -160 to -115 degree sector. Never-reach cases were 19, 20, and 19;
interruption events were 16, 12, and 24. On the fixed 200-episode
task-reference panel, all three checkpoints scored 197/200 (98.5%) and
repeated the same three failures at approximately 9.91 cm/-122.9 degrees,
9.36 cm/-127.9 degrees, and 18.24 cm/-154.8 degrees. The other 175 reference
episodes succeeded. Twenty-one additional experiment-13 checkpoints remain
unmeasured.

**Hypothesis assessment:** Contradicted under this transferred run and the
available development panels, with scope limited by the changed research
evaluation context. The expected sector improvement and removal of the three
recurring task-reference failures did not occur. Broad task-reference success
was preserved, and interruption events were lower at the first two measured
checkpoints than the incumbent's 18 events, but the late checkpoint had 24,
so the expected stable hold profile was not established. The research
evaluation context identifier differs from the incumbent's, limiting direct
cross-experiment percentage comparisons; within experiment 13, later
checkpoints did not improve over the early checkpoint. The training-proxy
peaks are orthogonal to measured policy progress, and the result does not
establish whether replay failed because of transfer, optimization variance,
or control dynamics.

**Interpretation:** Modest additional exposure to the recurring sector was
not sufficient to change the residual behavior of this transferred policy
basin. The unchanged task-reference failures and concentrated research
failures weaken low-rate replay as a practical intervention under this recipe,
while preserving the incumbent as the stronger measured policy selection.
The evidence supports closing this intervention, not a causal conclusion
about all angle curricula or readiness for the official task.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/query_training_log.py`,
`research/training_logs/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-13-attempt-1.log`,
the experiment-13 checkpoint inventory and parameters under
`research/checkpoints/challengers/6bbe4246-0dbc-4e66-9f31-0b66c0388867/experiment-13/`,
the three experiment-13 research-evaluation artifacts and three
experiment-13 task-reference artifacts under
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/`,
`robot_learning/scenario/environment.py`, and
`robot_learning/scenario/evaluation.py`.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 14

**Result:** The second fresh replication reproduced the broad fresh-run
regression rather than the transferred experiment-7 competence. The experiment
is closed with the experiment-7 `working` and `best_known` lineages unchanged,
the unchanged recipe kept, no challenger retained, and terminal assessment not
requested.

**Observed behavior:** Training completed 120,832 local steps. The training
success proxy rose from 0 to 0.27 at step 110,592 and ended at 0.26; mean
training reward rose from -7.28 at step 5,120 to 110.44 at step 100,352, then
fell to 89.89 at completion. These are training facts, not policy rankings.
Research evaluation measured 646/1,000 (64.6%) at checkpoint-100352,
575/1,000 (57.5%) at checkpoint-110592, and 523/1,000 (52.3%) at
checkpoint-120832. The corresponding task-reference panel measured 121/200
(60.5%), 106/200 (53.0%), and 102/200 (51.0%). Thus both panels declined
within this run while the training proxy was highest.

At the three research checkpoints, failures and diagnostics were respectively
354, 425, and 477 total failures; 339, 379, and 431 never-reach cases; and
100, 670, and 632 interruption events. At the late checkpoint, 265 of 477
research failures were in positive 60-to-180 degree bins, matching the
proposal's expected positive-angle regression branch. The run also retained
substantial negative-angle failures, and its hold profile differed from
experiment 10: 46 late failures were interrupted, but those failures
contained 632 interruption events. Every failed task-reference episode was
truncated; its late failures covered both negative and positive angle bins.

**Hypothesis assessment:** Partially supported under the tested fresh recipe and
fixed development panels. The expected observation was present in its main
behavioral direction: the fresh policy remained materially below the
transferred incumbent and developed a majority of late research failures in
positive-angle sectors, rather than recovering broad competence. The result
also contains partial and unexpected signals: negative-angle failures remained
substantial, and the interruption-event profile was not a direct reproduction
of experiment 10. The contradicting branch that a fresh run would recover
incumbent-like broad performance was not observed. The measured within-run
decline and proxy/reward rise are orthogonal evidence against using training
metrics as a policy-progress claim. This supports a fresh-run or
transfer-dependent instability hypothesis, but one additional fresh run cannot
separate initialization, seed/optimization variance, or control dynamics and
does not establish causality.

**Interpretation:** The unchanged 50/50 action-smoothing recipe is not
reliably sufficient from fresh initialization under the observed runs, whereas
the transferred experiment-7 basin remains the strongest measured candidate.
The second replication makes the fresh-versus-transfer discrepancy more
credible as a research question and makes another narrow replay less
promising, but it does not show that transfer itself is causal. The retained
incumbent is useful progress toward the objective, yet its available
development evidence remains below the human objective and is not an official
benchmark result.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/query_training_log.py`, the experiment-14 training-log query for
steps 5,120-120,832, the experiment-14 checkpoint inventory exposed by the
brief, and the six experiment-14 research-evaluation and task-reference
artifacts under
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/`.

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Experiment 15

**Result:** The angle-conditioned smoothing intervention did not improve the
incumbent's residual sector and introduced small research-panel regressions.
The experiment is closed with the experiment-7 `working` and `best_known`
lineages unchanged, the experiment-15 code reverted, no challenger retained,
and terminal assessment not requested.

**Observed behavior:** Training completed 120,832 local steps. The training
proxy ranged from 0.95 to 1.00, reached 1.00 at several checkpoints, and
ended at 0.97; mean training reward was 106.525 at checkpoint-86016,
106.711 at checkpoint-110592, and 104.710 at checkpoint-120832. These are
training facts and did not establish policy progress. On the matched
1,000-episode research panel, the incumbent measured 977/1,000 (97.7%),
checkpoint-86016 measured 975/1,000 (97.5%), and checkpoint-120832 measured
976/1,000 (97.6%). The incumbent had 23 failures, all in the -160 to -115
degree target sector (94/117 successes there); the challengers had 25 and 24
failures respectively, with 92/117 and 93/117 successes in that sector.
Neither challenger converted an incumbent failure into a success. Outside
that sector, both challengers matched all 883 incumbent successes. The
challengers nevertheless added two and one failures on episodes the incumbent
solved. Total hold-interruption events increased from 18 for the incumbent to
30 and 37. On the fixed task-reference panel, all three policies produced the
same 197/200 (98.5%) result and the same episode outcomes.

**Hypothesis assessment:** Contradicted under the tested transferred recipe
and fixed development panels, with an important partial signal. The expected
sector-local recovery did not occur at either measured checkpoint, and the
small research-panel regressions plus higher interruption counts run against
the proposed control benefit. The expected preservation branch was partly
supported: success outside the target sector and every task-reference outcome
were preserved. This does not establish that action lag is absent in general;
it weakens this sector-specific smoothing explanation under this transfer and
does not separate control dynamics from other policy or optimization effects.

**Interpretation:** Reducing smoothing from 50/50 to 75/25 only in the
-160 to -115 degree sector was not a useful intervention for the measured
incumbent. The unchanged task-reference outcomes and failure overlap indicate
that the observed residual failures were not remedied by this narrow temporal
change, while the increased interruption events are an unexpected orthogonal
signal. The incumbent remains the strongest measured candidate, but its 97.7%
research-panel result and 98.5% development-panel result are not an official
benchmark result and do not justify terminal assessment.

**Evidence inspected:** `research/brief.md`, `research/results.jsonl`,
`research/query_training_log.py`, the experiment-15 training-log query for
steps 5,120-120,832, the experiment-15 checkpoint inventory and parameters,
the three experiment-15 research-evaluation artifacts, the three experiment-15
task-reference artifacts under
`research/evaluations/6bbe4246-0dbc-4e66-9f31-0b66c0388867/`, and
`robot_learning/scenario/policy_io.py`.
