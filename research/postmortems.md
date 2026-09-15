# Research postmortems

## 96555391-6f71-4a29-9a53-199ce3d6c572 / Scientific strategy

**Current synthesis:** The fresh PPO baseline produced a policy with strong measured
development performance. The checkpoint at 100352 steps is the strongest measured
candidate: it achieved 98% on both the 100-episode research evaluation and the
200-episode protected task-reference panel. The final checkpoint at 120832 steps
also achieved 98% on the research evaluation but reached 97% on the task-reference
panel, so the earlier checkpoint is the better-supported candidate for terminal
assessment.

**Lessons and limits:** Measured task success, rather than training reward or
training success proxies, supports the policy-progress claim. The task-reference
failures for checkpoint-100352 cluster at targets from 6.7-9.9 cm and angles
from -116 to -128 degrees (4 of 4 failures); this characterizes residual
development-panel behavior but does not establish the official result. The final
checkpoint adds two failures on that panel, including one at a distant target, and
its lower success is an observational late-checkpoint difference, not evidence
that continued training caused the decline. The two research-evaluation
measurements share the same two failed episode identities and are not independent
coverage. Twenty-two checkpoints remain unmeasured, and raw training logs were not
available for causal training-dynamics analysis.

**Open questions:** Whether the residual difficult sector persists across new
episode coverage and how the selected policy performs on the distinct official
panel remain unresolved until terminal assessment.

## 96555391-6f71-4a29-9a53-199ce3d6c572 / Experiment 1

**Result:** The baseline established a measured candidate at the campaign target
on the development task-reference panel; checkpoint-100352 is selected for the
official benchmark.

**Observed behavior:** Training completed 120832 steps against a requested budget
of 120000. Inventory metrics rose from negative reward and zero training success
through late training, with training success values of 0.97 at checkpoint-100352
and 0.95 at checkpoint-120832; these are proxy signals rather than task
acceptance measurements. Checkpoint-100352 achieved 98/100 on the research
evaluation and 196/200 on task-reference-v1. Its four task-reference failures
were episodes 0, 10, 84, and 102, all truncated at 500 steps, with target radii
6.73, 7.24, 9.91, and 9.36 cm and target angles between -116.4 and -127.9
degrees. Checkpoint-120832 achieved 98/100 on the research evaluation and
194/200 on task-reference-v1; it retained those four failures and added failures
at episodes 121 and 152. Both research evaluations failed on episodes 11 and 25.

**Hypothesis assessment:** Supported as an initial baseline characterization:
the unchanged fresh method produced a policy reaching 98% on the fixed
development task-reference panel. The evidence does not establish the official
200-episode result, and the unmeasured checkpoints cannot be treated as failures
or successes.

**Interpretation:** Checkpoint-100352 is the most useful saved policy because it
matches the objective on the protected development panel while outperforming the
final checkpoint there. The shared research-evaluation failures and the
task-reference angular/radial cluster indicate residual behavior worth
characterizing in future work, but the current measured evidence is sufficient to
request the official verdict. The comparison between the two checkpoints is
descriptive; it does not isolate a causal effect of additional training.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/96555391-6f71-4a29-9a53-199ce3d6c572/experiment-1/inventory.json`;
`research/evaluations/96555391-6f71-4a29-9a53-199ce3d6c572/evaluation-96555391-6f71-4a29-9a53-199ce3d6c572-experiment-1-checkpoint-100352-100ep-seed0-6ba3ba6d7654.json`;
`research/evaluations/96555391-6f71-4a29-9a53-199ce3d6c572/evaluation-96555391-6f71-4a29-9a53-199ce3d6c572-experiment-1-checkpoint-120832-100ep-seed0-6ba3ba6d7654.json`;
`research/evaluations/96555391-6f71-4a29-9a53-199ce3d6c572/task-reference-96555391-6f71-4a29-9a53-199ce3d6c572-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/96555391-6f71-4a29-9a53-199ce3d6c572/task-reference-96555391-6f71-4a29-9a53-199ce3d6c572-experiment-1-checkpoint-120832-task-reference-v1.json`.
