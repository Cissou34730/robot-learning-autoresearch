# Research postmortems

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Scientific strategy

**Direction:** Improve official-task success by addressing the persistent
-150 to -120 degree failure sector, using full-radius training coverage as a
retained condition but no longer treating it as the leading explanation for
that sector.

**Lessons and limits:** Experiment 2's transferred full-radius policy improved
checkpoint-100352 research success from 97.4% to 97.5% and task-reference
success from 98.0% to 98.5%. In the same research panel, its 6-10 cm bin
improved from 97.2% to 98.2%, while the 18-20 cm bin fell from 98.2% to 97.3%.
The hard sector remained dominant and slightly worsened from 23/74 to 24/74
failures. The task-reference failures changed from four short-radius failures
to two short-radius failures plus one 18.24 cm failure. The completed
checkpoint regressed to 97.2% research success while retaining 98.5% on the
task-reference panel. These are development measurements, not the official
verdict; the single transferred run and fixed panels do not establish a causal
effect of radius coverage.

**Open questions:** Whether the negative-angle sector is caused by observation
or control generalization, whether checkpoint selection or late-training
regression is the more useful intervention, and whether the modest short-radius
gain persists on new coverage.

**Conditional next steps:** A future experiment may inspect observation or
control generalization while retaining broad-radius training, or test a
checkpoint-aware training schedule. The measured early challenger is useful
progress but is not ready for terminal assessment while the large structured
failure sector remains.

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
