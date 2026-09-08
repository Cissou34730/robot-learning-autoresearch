# Research postmortems

## b3580338-2b0b-4025-b9d7-1e64b5c9ef94 / Scientific strategy

**Direction:** Use direct official-task success as the decision criterion and
prefer a policy that reaches the objective on development evidence without
over-interpreting the training proxy. The baseline has reached the threshold
on one development panel, so the highest-value next step is terminal assessment
of the trained policy rather than another measurement on the same panel.

**Lessons and limits:** The fresh PPO baseline, with the unchanged recipe,
learned substantial reach-and-hold behavior: the 86,016-step checkpoint scored
95% and both 100,352 and 120,832 scored 98% in 100-episode
`research_evaluation` panels. The 100,352 and 120,832 panels reused the same
episode seeds and had identical successes, so this is not independent
confirmation. The highest training reward/proxy checkpoint was not the best
measured policy (163.85 reward and 95% success at 86,016), while later
checkpoints had lower reward/proxy and 98% measured success; training reward is
therefore not a reliable selector for the human objective. The two 98%
checkpoints each failed the same two episodes, including a short-radius target
at approximately -122 degrees, but the available panel is too small and
reused to establish the official rate or a general failure mechanism.

**Open questions:** Whether the 98% development result meets the unchanged
official distribution at the required rate remains unresolved. The two
development successes at 98% are compatible with the objective but do not
provide held-out confirmation, and no intervention or causal mechanism was
tested in this baseline experiment.

**Conditional next steps:** Freeze checkpoint-120832 as the best-known policy
and request the official benchmark now. If the terminal benchmark does not
reach the objective, use the recorded short-radius/negative-angle failures and
the reward/evaluation discrepancy to motivate a changed training recipe; if it
does, stop because the human objective has been met.

## b3580338-2b0b-4025-b9d7-1e64b5c9ef94 / Experiment 1

**Result:** The fresh baseline produced a promising policy and reached 98%
development success at checkpoints 100352 and 120832, but this remains
development evidence rather than an official result.

**Observed behavior:** The automatic baseline trained PPO from scratch with
the unchanged recipe for 120,000 requested steps. The measured checkpoints
were 86,016 (95%), 100,352 (98%), and 120,832 (98%), each on 100 episodes with
evaluation seed 0. The 100,352 and 120,832 evaluations had the same two
failures (episode seeds 11 and 25); 86,016 had those failures plus seeds 43,
72, and 92. The training proxy peaked at 0.97 at 100,352 and ended at 0.95,
while the highest recorded training reward was at 86,016.

**Hypothesis assessment:** This was a fresh baseline, not a changed recipe,
continuation, or replication, so there was no intervention hypothesis with
`expected_observation` or `contradicting_observation` fields to test. It
supports the limited baseline conclusion that the unchanged method can produce
a policy at the 98% development threshold. It does not establish that the
human objective is satisfied, does not justify a causal claim, and does not
show that 120,832 is superior to 100,352 because both were evaluated on the
same panel.

**Interpretation:** The final checkpoint is a reasonable working and
best-known selection because it matches the best direct task result and is the
terminal artifact of the completed baseline; this is a tie-based selection,
not evidence that additional training improved performance. Terminal official
assessment is more valuable than another same-panel measurement because it
directly resolves the remaining objective-level uncertainty.

**Evidence inspected:** `research/evaluations/b3580338-2b0b-4025-b9d7-1e64b5c9ef94/evaluation-b3580338-2b0b-4025-b9d7-1e64b5c9ef94-experiment-1-checkpoint-120832-100ep-seed0-e602a32560ea.json`, `research/evaluations/b3580338-2b0b-4025-b9d7-1e64b5c9ef94/evaluation-b3580338-2b0b-4025-b9d7-1e64b5c9ef94-experiment-1-checkpoint-100352-100ep-seed0-e602a32560ea.json`, `research/evaluations/b3580338-2b0b-4025-b9d7-1e64b5c9ef94/evaluation-b3580338-2b0b-4025-b9d7-1e64b5c9ef94-experiment-1-checkpoint-86016-100ep-seed0-e602a32560ea.json`, `research/checkpoints/challengers/b3580338-2b0b-4025-b9d7-1e64b5c9ef94/experiment-1/checkpoint-120832/artifact.json`, `research/results.jsonl`, and `research/brief.md`.
