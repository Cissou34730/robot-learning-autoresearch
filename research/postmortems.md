# Research postmortems

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Scientific strategy

**Direction:** Improve robustness of the reach-and-hold policy in the hard
short-range, negative-angle sector while preserving the broad success already
achieved by the baseline. The next experiment should target uninterrupted
holding rather than optimize the training proxy alone.

**Lessons and limits:** The fresh PPO baseline reached 98% on the 200-episode
research panel and 98% on the independent task-reference development panel at
100,352 steps, while the final 120,832-step checkpoint reached 97% on both
panels (`research/results.jsonl` and the four experiment-1 evaluation
artifacts). The earlier checkpoint won both discordant paired episodes and had
four failures, all at radii 6.7-9.9 cm and angles -116 to -128 degrees; the
diagnostics show these episodes generally reached tolerance but repeatedly
interrupted the hold. The later checkpoint retained those four failures and
added two more, so training proxy improvement or additional steps did not
establish better task behavior. The research and task-reference panels use the
same episode identities here, so their agreement is cross-instrument
confirmation, not independent held-out evidence; neither panel is the official
benchmark.

**Open questions:** Can a changed training recipe improve stability in the
short-range negative-angle sector without sacrificing the other target
geometries? Is the late-training regression specific to this seed and recipe,
or a repeatable consequence of continuing past the behavioral peak?

**Conditional next steps:** Continue from the 100,352-step policy as the
current best-known reference and run an ordinary targeted training experiment.
Prefer an intervention that improves hold stability in the identified sector;
reconsider this direction if a changed recipe harms the broad task or if
replication evidence shows the apparent late regression is seed-specific.

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Experiment 1

**Result:** Fresh baseline reached the 98% development target at 100,352
steps, but the final checkpoint regressed to 97%; the earlier checkpoint is
selected as working and best-known.

**Observed behavior:** The 100,352-step checkpoint succeeded on 196/200
episodes in both the research evaluation and task-reference panel. Its four
failures were the same across instruments and were concentrated at short
negative-angle targets; all truncated at 500 steps. Research diagnostics show
near-tolerance reach followed by interrupted holding. The 120,832-step
checkpoint succeeded on 194/200 episodes, retaining the same four failures and
adding failures at approximately 10 cm, -132 degrees and 17.9 cm, 169 degrees.
The paired research comparison favored the earlier checkpoint 2-0 among two
discordant episodes. The run was a fresh baseline with no changed recipe or
continuation.

**Hypothesis assessment:** Partially supported as a baseline-establishment
test: it demonstrated near-objective task performance and identified a
measured behavioral peak, but it did not establish official 98% success and
the final checkpoint did not sustain the peak. These are development-panel
measurements from one evaluation seed, not an official result or evidence
about learning-process reproducibility.

**Interpretation:** `checkpoint-100352` is the strongest measured policy in
this experiment, and the repeated hard-sector failures provide a concrete
target for the next recipe rather than a reason to select the later
checkpoint. The late regression is an observed checkpoint difference; its
cause is not established.

**Evidence inspected:** `research/results.jsonl`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-1-checkpoint-100352-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-1-checkpoint-120832-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-1-checkpoint-120832-task-reference-v1.json`;
`robot_learning/scenario/evaluation.py`.
