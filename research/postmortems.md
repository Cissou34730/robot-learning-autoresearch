# Research postmortems

## b8641d46-760b-4fa7-8933-fc9078535fca / Scientific strategy

**Current synthesis:** The campaign objective remains at least 98% success on
the distinct official 200-episode panel. Experiment 2 shows that the unchanged
PPO recipe can produce a strong policy: task-reference success was 96% at
checkpoint-95232, 98% at checkpoint-100352, and 97% at checkpoint-120832.
Checkpoint-100352 is the strongest measured policy evidence, but the official
panel has no result because the final assessment was rejected during isolated
evidence review. The selected lineage currently identifies only the
checkpoint-100352 task-reference artifact.

**Lessons and limits:** Training logs place the learning transition between
70656 and 90112 steps and show a high region through 100352, followed by lower
training-reported success through 120832. These metrics locate behavior but are
proxies rather than acceptance evidence. The task-reference measurements use
one deterministic 200-episode panel, so the 98% result does not establish
independent generalization. Its four failures cluster around short targets and
angles near -116 to -128 degrees, which characterizes this panel without
establishing a causal failure mechanism. Only one training seed has been
measured, and the retained artifact records the unchanged observation and
action contract from `robot_learning/scenario/policy_io.py`; no representation
or recipe change has been tested.

**Open questions:** It remains unknown whether the learned capability
reproduces from a fresh seed, whether the late difference between
checkpoint-100352 and checkpoint-120832 reflects continued-training
degradation, sampling variation, or both, and how the selected policy performs
on the distinct official panel. The evidential sufficiency of a future
best-known lineage for terminal review is also unresolved.

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
