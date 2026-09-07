# Research postmortems

## 6f3b5e54-dc1e-4502-bd86-3318074de79c / Scientific strategy

**Direction:** Establish a reliable PPO baseline and use development evidence to
choose the strongest saved policy before testing a new scientific intervention.

**Lessons and limits:** Experiment 3 learned the task progressively: training
success remained zero through 70,656 steps, rose to 0.93 by 95,232 steps, and
peaked at 0.97 at checkpoint-100352. The later checkpoints remained strong but
were lower, with 0.94 at 105,472, 0.93 at 110,592, and 0.95 at 120,832
(`research/results.jsonl` and the experiment-3 checkpoint inventory). These are
training-rollout facts, not independent development-panel measurements, so the
selected checkpoint is a provisional working baseline and does not establish the
98% official objective.

**Open questions:** Whether the late decline is a genuine policy regression,
evaluation variance, or a training-metric artifact remains unresolved because
the requested research measurement could not be validated while the evaluator
does not expose the required primary-comparison semantics version.

**Conditional next steps:** If a future experiment can add the required
measurement semantics, compare the saved peak and final checkpoints on matched
development panels before changing the method. Otherwise, use the selected
peak checkpoint as the baseline for a new intervention and reassess with valid
development evidence.

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
