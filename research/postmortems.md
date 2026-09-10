# Research postmortems

## 6bbe4246-0dbc-4e66-9f31-0b66c0388867 / Scientific strategy

**Direction:** Improve official-task success by testing whether the incumbent's
structured residual failures arise from missing short-radius training coverage,
while preserving the measured checkpoint-100352 policy as the comparison point.
This is a provisional diagnostic direction, not a commitment to radius
coverage if the hard negative-angle sector persists.

**Lessons and limits:** The baseline learned the task late in training: logged
training success rose from 0 through 70,656 steps to 0.97 at 100,352 steps,
then fluctuated and ended at 0.95 at 120,832 steps. These are training facts,
not policy rankings. Checkpoint-100352 measured 97.4% on a 1,000-episode
research panel and 98.0% on the 200-episode task-reference development panel;
checkpoint-120832 measured 96.9% and 97.0% on those respective panels, while
checkpoint-95232 measured 96.0% on the task-reference panel. The
research-evaluation diagnostics for checkpoint-100352 show 51/74 success in the
-150 to -120 degree sector and at least 97.8% in every other 30-degree sector.
Its 26 research-panel failures are all in that sector, with 17 never reaching
tolerance and 9 losing the hold; the four task-reference failures are 6-10 cm
targets in the same negative-angle sector. The training environment sampled
14-20 cm while the official task samples 6-20 cm, but these measurements do not
establish that radius coverage caused either failure pattern. The development
panels are not independent confirmation or the official verdict.

**Open questions:** Whether full-radius training improves short-radius
performance without sacrificing the already strong far-radius behavior; whether
it also reduces the negative-angle failures; and whether that sector instead
reflects an observation or control-generalization problem. Checkpoint selection
and the late-training regression remain separate uncertainties.

**Conditional next steps:** Measure the transferred full-radius challenger at
an early high-performing checkpoint and at completion with the same geometry
diagnostics. If short-radius failures improve, continue refining coverage or a
curriculum; if the negative-angle concentration remains, prioritize an
observation/control investigation rather than assuming radius coverage solved
the task. Preserve checkpoint-100352 until a measured successor is available,
and defer the official benchmark until terminal readiness is judged.

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
