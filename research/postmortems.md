# Research postmortems

## b8641d46-760b-4fa7-8933-fc9078535fca / Scientific strategy

**Current synthesis:** Experiment 2 established a learned PPO policy with a
late transition from zero training-reported success to high task behavior.
Protected task-reference success was 96% at checkpoint-95232, 98% at
checkpoint-100352, and 97% at checkpoint-120832. The measured peak checkpoint
is therefore the strongest current policy evidence, but the official panel
remains unmeasured.

**Lessons and limits:** Training reward and training success were useful for
locating the transition but are proxies, not policy-acceptance evidence. The
task-reference panel directly measured task success and showed that continuing
past checkpoint-100352 did not improve this panel. The three measurements use
the same deterministic development panel, so they do not establish independent
generalization or explain the late regression. The remaining failures of
checkpoint-100352 are concentrated in four repeated panel episodes, mostly
targets near 6.7-9.9 cm and angles about -116 to -128 degrees; this
characterizes the panel but does not establish a causal failure mechanism.

**Open questions:** Performance on the distinct official 200-episode panel is
unknown. It is also unresolved whether the late difference between
checkpoint-100352 and checkpoint-120832 reflects continued-training
degradation, sampling variation, or both.

## b8641d46-760b-4fa7-8933-fc9078535fca / Experiment 2

**Result:** The fresh baseline produced a policy with 98% task-reference
success at checkpoint-100352. That checkpoint is selected as the working and
best-known policy for official assessment.

**Observed behavior:** Training logs reported zero success through 70656
steps, then 0.71 at 90112, 0.93 at 95232, 0.97 at 100352, and 0.95 at
120832. On the fixed 200-episode task-reference panel, checkpoint-95232
achieved 96% (192/200), checkpoint-100352 achieved 98% (196/200), and
checkpoint-120832 achieved 97% (194/200). The four failures of
checkpoint-100352 all truncated at 500 steps; their target angles were
-116.4, -125.4, -122.9, and -127.9 degrees. The other 21 checkpoints were
not measured and remain unmeasured.

**Hypothesis assessment:** Supported within the limited scope of a baseline:
the experiment established substantial measured task progress toward the
human objective, and one saved checkpoint reached the objective percentage on
the development panel. This does not establish the official result, because
the final panel is distinct and has not been run, and the baseline design does
not identify why checkpoint-100352 outperformed the later checkpoint.

**Interpretation:** The saved checkpoint at the measured proxy peak is useful
and preferable to the final checkpoint for terminal assessment. The
training/evaluation agreement is partial rather than exact: both indicate a
late high-performing region, but training metrics alone would not distinguish
the 98% checkpoint from the 97% final checkpoint. No causal claim about
overtraining or the clustered failures is warranted from this evidence.

**Evidence inspected:** `research/brief.md`,
`research/research_state.json`, `research/results.jsonl`,
`research/evaluations/b8641d46-760b-4fa7-8933-fc9078535fca/task-reference-b8641d46-760b-4fa7-8933-fc9078535fca-experiment-2-checkpoint-95232-task-reference-v1.json`,
`research/evaluations/b8641d46-760b-4fa7-8933-fc9078535fca/task-reference-b8641d46-760b-4fa7-8933-fc9078535fca-experiment-2-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/b8641d46-760b-4fa7-8933-fc9078535fca/task-reference-b8641d46-760b-4fa7-8933-fc9078535fca-experiment-2-checkpoint-120832-task-reference-v1.json`,
`robot_learning/scenario/environment.py`, and
`robot_learning/scenario/evaluation.py`.
