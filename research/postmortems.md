# Research postmortems

## f36723a7-e062-477d-8972-e203af25d8c1 / Scientific strategy

**Direction:** Use `checkpoint-100352` as the current working and best-known
policy, and investigate robustness on the official task's short-radius and
negative-angle targets. The baseline established near-target performance but
did not establish the 98% objective. The measured failure concentration
prioritizes broader target-radius coverage or curriculum over further
optimization of the already saturated late checkpoints; it does not identify
target coverage as a causal mechanism.

**Lessons and limits:** Measured task behavior, rather than training proxy
success, distinguishes the checkpoints. `checkpoint-100352` achieved 97.0% on
the 200-episode research panel and 98.0% on the 200-episode protected
development task-reference panel (196/200), compared with 95.5%/96.0% for
`checkpoint-95232` and 97.0%/97.0% for `checkpoint-120832`. The research-panel
comparison favored `checkpoint-100352` over `checkpoint-95232` by 1.5
percentage points but found no difference from `checkpoint-120832`; these are
same-panel development comparisons, not independent confirmation. Across the
three research evaluations, five episode identities remained failures; for
`checkpoint-100352`, all six failures were in the negative-angle sector below
-90 degrees, while all 149 episodes at angles at least -90 degrees succeeded.
Its four task-reference failures were also negative-angle targets with radii
from 6.7 to 9.9 cm. The training environment samples 14-20 cm, whereas the
official task spans 6-20 cm. These observations motivate a coverage hypothesis,
but a single fresh baseline cannot separate coverage from representation,
control, reward, or sampling variance. The 200-episode development panels are
not the final benchmark, and unmeasured checkpoints remain unmeasured.

**Open questions:** Does adding official short-radius targets to training,
possibly with explicit emphasis on the difficult negative-angle sector,
improve task-reference success without sacrificing the already successful
regions? Are the persistent failures caused by target-distribution coverage,
policy/control behavior, hold stability, or finite-panel variation? Does the
98.0% task-reference result for `checkpoint-100352` generalize to the official
benchmark?

**Conditional next steps:** Close this baseline with `checkpoint-100352`
selected and keep its scientific recipe. If development continues or the
official benchmark does not meet the objective, prefer a new training
experiment that exposes the policy to the full 6-20 cm radius range while
preserving the official angular range, then compare against this checkpoint on
the same development panels. If that intervention does not improve the
negative-angle failures, investigate observation/action representation and
hold-control behavior rather than attributing the deficit to target coverage.
If an official benchmark later reaches at least 98%, treat that as the
objective result; development-panel scores alone do not establish it.

## f36723a7-e062-477d-8972-e203af25d8c1 / Experiment 1

**Result:** The fresh PPO baseline learned a near-target policy. The strongest
measured candidate was `checkpoint-100352`: 97.0% on the research evaluation
and 98.0% on the task-reference panel. The official 98% objective remains
unestablished because neither measurement is the final benchmark.

**Observed behavior:** Training proxy success rose from 0 at 5,120 steps to
0.97 at 100,352 steps and ended at 0.95 at 120,832 steps; these are training
facts, not task-performance results. Research evaluation success was 95.5% at
95,232 steps, 97.0% at 100,352 steps, and 97.0% at 120,832 steps. The
task-reference panel was 96.0%, 98.0%, and 97.0% at those checkpoints. The
100,352 research evaluation had six failures, all below -90 degrees; its
task-reference failures were four targets at negative angles below -116
degrees and radii below 10 cm. The 120,832 checkpoint did not improve the
research score and fell to 97.0% on the task-reference panel. The original
baseline record had no intervention-specific expected or contradicting
observation; its baseline prediction was only to establish an initial
reference.

**Hypothesis assessment:** Supported as a baseline-establishment objective:
the run produced a reproducible, measurable near-target reference and exposed
specific residual failures. It is not support for the 98% campaign objective,
nor evidence that PPO, the reward, or target coverage caused the outcome.
Checkpoint ranking is partially supported by measured task behavior:
`checkpoint-100352` is the best task-reference candidate, but the 1 percentage
point gap between the two panels and the lack of improvement over the final
checkpoint on the research panel limit the strength of that ranking.

**Interpretation:** The late policy learned the task broadly, but the
persistent negative-angle failures and the mismatch between the training
radius range and official range make short-radius/negative-angle coverage the
most useful next investigation. The evidence is descriptive and development
only; it does not isolate why those targets fail or establish generalization
to the final benchmark.

**Evidence inspected:** `research/scenario.md`;
`research/results.jsonl`;
`research/query_training_log.py` output for experiment 1, steps 5,120-120,832;
`research/evaluations/f36723a7-e062-477d-8972-e203af25d8c1/evaluation-f36723a7-e062-477d-8972-e203af25d8c1-experiment-1-checkpoint-95232-200ep-seed1000-6ba3ba6d7654.json`;
`research/evaluations/f36723a7-e062-477d-8972-e203af25d8c1/evaluation-f36723a7-e062-477d-8972-e203af25d8c1-experiment-1-checkpoint-100352-200ep-seed1000-6ba3ba6d7654.json`;
`research/evaluations/f36723a7-e062-477d-8972-e203af25d8c1/evaluation-f36723a7-e062-477d-8972-e203af25d8c1-experiment-1-checkpoint-120832-200ep-seed1000-6ba3ba6d7654.json`;
the three corresponding `task-reference-...-task-reference-v1.json` artifacts;
`robot_learning/scenario/environment.py`; and
`robot_learning/scenario/evaluation.py`.
