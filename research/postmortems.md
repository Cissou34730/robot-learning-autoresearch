# Research postmortems

## 6f3b5e54-dc1e-4502-bd86-3318074de79c / Scientific strategy

**Direction:** Establish a reliable PPO baseline and use matched development
evidence to choose the strongest saved policy before testing a new scientific
intervention.

**Lessons and limits:** Experiment 4 confirms progressive PPO learning and
supports checkpoint-100352 as the working and best-known development policy.
Training success peaks at 0.97 and reward at 117.32 there, while the final
checkpoint reaches 0.95 and 112.02 (`research/results.jsonl` and the experiment
4 training log). The matched research panel gives both checkpoints 98.0% over
200 episodes with compatible comparison semantics; the paired comparison has
zero discordant episodes, and both policies fail on the same four seeds
(`research/evaluations/...experiment-4-checkpoint-100352-200ep-seed4000-...json`
and its checkpoint-120832 counterpart). Thus the late training decline is not
evidence of a measurable behavioral regression on this panel. Development
evidence still does not establish the official objective.

**Open questions:** Whether the shared four failures generalize beyond this
research panel, and whether another training realization would reproduce the
same late plateau, remain unknown.

**Conditional next steps:** Use checkpoint-100352 as the PPO baseline for a
future intervention or continuation. Revisit the late-training question only
if a future method changes the failure pattern or if independent development
evidence is needed; do not treat the current 98% research result as the final
benchmark verdict.

## 6f3b5e54-dc1e-4502-bd86-3318074de79c / Experiment 3

**Result:** Fresh PPO baseline trained successfully; checkpoint-100352 is
selected as the working policy from the available training evidence.

**Observed behavior:** The raw training log shows success increasing from 0 at
70,656 steps to 0.71 at 90,112, 0.93 at 95,232, and 0.97 at 99,328. Saved
checkpoint facts report 0.97 at checkpoint-100352, followed by 0.94, 0.93,
0.95, and 0.95 at checkpoints 105472, 110592, 115712, and 120832. Reward
peaked earlier and also declined from 117.32 at checkpoint-100352 to 112.02 at
checkpoint-120832.

**Hypothesis assessment:** As a fresh baseline there was no intervention
hypothesis to test. The expected observation was progressive improvement toward
the task objective, which occurred; the contradicting observation was a
late-training decline after the checkpoint-100352 peak, which also occurred.
The evidence supports selecting the peak as a provisional baseline but cannot
determine whether the decline reflects generalization or rollout variance.

**Interpretation:** The saved training trajectory favors checkpoint-100352 over
the final checkpoint for the working lineage. No development evaluation can
support a best-known designation or the official objective verdict. The
measurement request was not used because validation reported that
`PRIMARY_COMPARISON_SEMANTICS_VERSION` is absent from
`robot_learning/scenario/evaluation.py`; closure therefore relies only on
recorded training evidence and preserves the uncertainty for a later valid
measurement.

**Evidence inspected:** `research/results.jsonl`;
`research/checkpoints/challengers/6f3b5e54-dc1e-4502-bd86-3318074de79c/experiment-3/inventory.json`;
`research/checkpoints/challengers/6f3b5e54-dc1e-4502-bd86-3318074de79c/experiment-3/checkpoint-100352/artifact.json`;
`research/checkpoints/challengers/6f3b5e54-dc1e-4502-bd86-3318074de79c/experiment-3/checkpoint-120832/artifact.json`.

## 6f3b5e54-dc1e-4502-bd86-3318074de79c / Experiment 4

**Result:** Fresh PPO baseline reproduced the prior learning trajectory, and
checkpoint-100352 is selected as the working and best-known development policy.

**Observed behavior:** Training success rose from 0 through 70,656 steps to
0.97 at checkpoint-100352, then stayed between 0.93 and 0.96 through
checkpoint-120832; reward fell from 117.32 to 112.02 over the same late period.
On matched research evaluations (seed 4000, 200 episodes), both checkpoint-
100352 and checkpoint-120832 scored 98.0%. Their paired comparison had zero
candidate wins, zero reference wins, zero discordant episodes, and a 0.0
percentage-point success difference. The four failures were the same episode
seeds (4030, 4040, 4049, and 4134), each truncated at 500 steps.

**Hypothesis assessment:** As a fresh baseline there was no intervention
hypothesis to test. The expected observation, progressive improvement toward
the task objective, occurred. The contradicting observation, a late-training
decline after the checkpoint-100352 peak, also occurred in training metrics,
but the matched development comparison found no behavioral difference between
the peak and final policies. The decline is therefore unresolved as a training
statistic but is not supported as a policy regression by this development
measurement.

**Interpretation:** The peak checkpoint remains the best scientific choice
because its training trajectory is stronger and the valid development
comparison shows it is at least tied with the final checkpoint. The result is
development evidence, not an official benchmark verdict, and the shared
failure seeds leave generalization and run-to-run reproducibility open.

**Evidence inspected:** `research/results.jsonl`;
`research/evaluations/6f3b5e54-dc1e-4502-bd86-3318074de79c/evaluation-6f3b5e54-dc1e-4502-bd86-3318074de79c-experiment-4-checkpoint-100352-200ep-seed4000-a65343bc54c5.json`;
`research/evaluations/6f3b5e54-dc1e-4502-bd86-3318074de79c/evaluation-6f3b5e54-dc1e-4502-bd86-3318074de79c-experiment-4-checkpoint-120832-200ep-seed4000-a65343bc54c5.json`.
