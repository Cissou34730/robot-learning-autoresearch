# Research postmortems

## 6f3b5e54-dc1e-4502-bd86-3318074de79c / Scientific strategy

**Direction:** Establish a reliable PPO baseline, first checking whether the
high-performing realization is reproducible before testing a new scientific
intervention.

**Lessons and limits:** Experiment 4 confirms progressive PPO learning and
supports checkpoint-100352 as the working and best-known development policy.
Its matched research-panel result is 98.0% at both checkpoint-100352 and
checkpoint-120832, with the same four failures. Experiment 5 used the
unchanged recipe from a fresh seed but reached only 0.04 and 0.13 training
success at those checkpoints, and 42.0% and 55.5% on the same 200-episode
research panel. The episode-level comparison has 112 and 85 experiment-4-only
successes and zero experiment-5-only successes at the two checkpoints; the
four experiment-4 failures are shared. This makes a panel artifact or a
late-checkpoint explanation unlikely, but one replication cannot distinguish
an unusual seed from broader recipe or budget sensitivity. Development
evidence still does not establish the official objective.

**Open questions:** Whether experiment 5 is an unusually slow or failed
training realization, or evidence that the current PPO recipe and budget are
not reliably reproducible, remains unknown. Whether the shared four failures
generalize beyond this research panel also remains unknown.

**Conditional next steps:** Keep experiment 4 checkpoint-100352 as the PPO
baseline for a future intervention or continuation. If reproducibility is
the next question, use another fresh seed or a longer continuation to separate
seed variation from a budget or recipe limitation; do not treat either
development result as the final benchmark verdict.

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

## 6f3b5e54-dc1e-4502-bd86-3318074de79c / Experiment 5

**Result:** Fresh replication of the unchanged PPO recipe did not reproduce
experiment 4's high-performing policy; the existing experiment-4 working and
best-known lineages are retained.

**Observed behavior:** The experiment-5 training log improved gradually but
remained at success 0.04 and reward 84.60 at checkpoint-100352, then success
0.13 and reward 107.41 at checkpoint-120832. The compatible seed-4000,
200-episode research evaluations scored 42.0% and 55.5%, respectively. The
experiment-4 checkpoints scored 98.0% at both points. Reusing the episode
identities for a lightweight paired analysis produced 112 and 85
experiment-4-only successes and zero experiment-5-only successes; all four
experiment-4 failures were also experiment-5 failures.

**Hypothesis assessment:** The expected replication observation was a
comparable training trajectory and high matched-panel success, as seen in
experiment 4. That expectation is contradicted: experiment 5 learns more
slowly and remains far below the incumbent at both measured checkpoints. The
result supports run-to-run variability or a seed-sensitive convergence
problem, but a single fresh replication cannot identify whether seed 1 is an
outlier or exposes a broader recipe or budget limitation.

**Interpretation:** The matched research measurement was the smallest
sufficient test of whether the replication's weak result was only a panel or
checkpoint-selection artifact, and its episode-level outcomes rule out those
explanations as the basis for replacing the incumbent. No additional
task-reference or comparison measurement could change the current lineage
decision. The unchanged scientific recipe is kept, while reproducibility
remains an open question for a future experiment.

**Evidence inspected:** `research/results.jsonl`;
`research/evaluations/6f3b5e54-dc1e-4502-bd86-3318074de79c/evaluation-6f3b5e54-dc1e-4502-bd86-3318074de79c-experiment-5-checkpoint-100352-200ep-seed4000-a65343bc54c5.json`;
`research/evaluations/6f3b5e54-dc1e-4502-bd86-3318074de79c/evaluation-6f3b5e54-dc1e-4502-bd86-3318074de79c-experiment-5-checkpoint-120832-200ep-seed4000-a65343bc54c5.json`;
`research/evaluations/6f3b5e54-dc1e-4502-bd86-3318074de79c/evaluation-6f3b5e54-dc1e-4502-bd86-3318074de79c-experiment-4-checkpoint-100352-200ep-seed4000-a65343bc54c5.json`;
`research/evaluations/6f3b5e54-dc1e-4502-bd86-3318074de79c/evaluation-6f3b5e54-dc1e-4502-bd86-3318074de79c-experiment-4-checkpoint-120832-200ep-seed4000-a65343bc54c5.json`.
