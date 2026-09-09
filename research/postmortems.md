# Research postmortems

## 3f02f914-505c-481f-b995-e040c009974f / Scientific strategy

**Direction:** Retain full-range target exposure as the current recipe and
establish whether its partial near-target improvement is robust. The remaining
failures are concentrated in negative-angle geometries, while checkpoint
selection and training stability remain plausible alternatives to a purely
radial explanation.

**Lessons and limits:** On the same 200-episode task-reference-v1 panel, the
experiment-2 parent achieved 196/200 (98%), checkpoint-105472 achieved 196/200
(98%), and checkpoint-120832 achieved 197/200 (98.5%). Relative to the parent,
the final checkpoint fixed the failures at 6.7 cm/-116.4 degrees and 7.2
cm/-125.4 degrees, retained failures at 9.9 cm/-122.9 degrees and 9.4
cm/-127.9 degrees, and added one failure at 18.2 cm/-154.8 degrees. The
under-10-cm stratum therefore rose from 53/57 (93.0%) to 55/57 (96.5%), while
14-20 cm fell from 95/95 (100%) to 94/95 (98.9%); 10-14 cm remained 48/48.
These observations partially support the expected radial-robustness signal but
also match the proposal's contradicting signal of a new far-target failure.
They are repeated development-panel evidence, not official benchmark evidence
or independent confirmation. Training proxy success peaked at 1.0 at
105472 steps and ended at 0.94, so it did not identify task performance or the
best checkpoint.

**Open questions:** Will the near-target improvement and the single far-target
regression persist on a fresh evaluation panel or another seed? Are the two
remaining near-target failures and the new far-target failure an angular
robustness pattern, transient PPO drift, or checkpoint-specific behavior? The
single transfer run and fixed panel cannot establish generalization, seed
variance, or that radius alone caused the improvement.

**Conditional next steps:** Use checkpoint-120832 as the working and
best-known policy. If development continues, preserve full-range exposure and
test angular or training-stability robustness with task success and failure
geometry measured together; do not attribute gains to radial sampling without a
comparable fresh evaluation or control. Consider official assessment only after
a candidate improves both the residual near-target cluster and the 14-20 cm
behavior without a new concentration.

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
