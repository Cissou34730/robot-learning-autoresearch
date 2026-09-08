# Research postmortems

## 556a14d8-1ec1-4130-be91-12fdbaee135f / Scientific strategy

**Direction:** Freeze the strongest measured baseline policy and use the protected
terminal benchmark to determine whether it meets the human objective. The
development evidence is already at the 98% threshold on the best checkpoint, so
the next useful question is official-task performance on the distinct final panel,
not more measurements of the same checkpoints.

**Lessons and limits:** The unchanged PPO baseline learned useful reach-and-hold
behavior, with its training proxy rising to 0.97 at 100,352 steps and ending at
0.95 after 120,832 steps (`research/results.jsonl`). On the matched 100-episode
research panel, checkpoints 95,232, 100,352, and 120,832 each achieved 98%.
On the independent protected development panel, they achieved 96%, 98%, and 97%,
respectively; therefore 100,352 is the best-supported policy, but the result is
development evidence rather than the official verdict. Failures were
geometry-specific: the best checkpoint missed four fixed-panel targets, including
three around 7--10 cm at angles near -116 to -128 degrees, and all three
research measurements consistently missed seeds 11 and 25 without entering
tolerance. This establishes task progress but not robustness beyond the sampled
panels or a causal explanation for the failures.

**Open questions:** Whether the 100,352-step policy reaches at least 98% on the
final seed-1000 panel remains unknown. The development panels do not establish
generalization to new target draws, and the baseline did not test an intervention
with proposal-level expected and contradicting observations.

**Conditional next steps:** Request terminal assessment now because the best
development policy reaches the human threshold and additional same-panel
measurements are unlikely to change the lineage choice. If development were to
continue after a nonterminal decision, a new recipe should explicitly address
short-radius and negative-angle coverage rather than extending this baseline
unchanged.

## 556a14d8-1ec1-4130-be91-12fdbaee135f / Experiment 1

**Result:** The fresh PPO baseline produced a policy with 98% success on the
protected development panel at checkpoint-100352. That checkpoint is selected as
working and best-known, and terminal assessment is requested.

**Observed behavior:** Training completed 120,832 steps against a requested
120,000, with the training proxy peaking at 0.97 at 100,352 steps and ending at
0.95. Research evaluation at seed 0 reported 98% for checkpoints 95,232,
100,352, and 120,832. The task-reference panel reported 192/200 (96%) at
95,232, 196/200 (98%) at 100,352, and 194/200 (97%) at 120,832. The selected
checkpoint's four failures were truncated at 500 steps, with radii 6.73--9.91 cm
and angles -116.4 to -127.9 degrees. In the research evaluator, the same two
episode seeds failed for every measured checkpoint, with no in-tolerance steps.

**Hypothesis assessment:** Supported only in the baseline sense that the
unchanged recipe can learn a policy at the human target on a 200-episode
development panel; no intervention hypothesis was tested. The evidence is
partial because the best score is exactly the threshold on one fixed
development panel, later training regressed slightly, and the recurring
failure geometry leaves uncertainty about the final panel. The protected
development result supports terminal assessment but does not itself declare
the objective reached.

**Interpretation:** Checkpoint-100352 is preferable to the final checkpoint
because it has the highest independent task-reference success and ties the
research-panel result. The difference is a checkpoint-selection observation,
not evidence that the training recipe caused the improvement. The protected
panel independently confirms substantial progress under the original task
semantics, while the fixed failure pattern limits claims of broad robustness.
The final benchmark is the proportionate next measurement because it directly
answers the human objective on a distinct 200-episode panel.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`,
`research/evaluations/556a14d8-1ec1-4130-be91-12fdbaee135f/evaluation-556a14d8-1ec1-4130-be91-12fdbaee135f-experiment-1-checkpoint-95232-100ep-seed0-6ba3ba6d7654.json`,
`research/evaluations/556a14d8-1ec1-4130-be91-12fdbaee135f/evaluation-556a14d8-1ec1-4130-be91-12fdbaee135f-experiment-1-checkpoint-100352-100ep-seed0-6ba3ba6d7654.json`,
`research/evaluations/556a14d8-1ec1-4130-be91-12fdbaee135f/evaluation-556a14d8-1ec1-4130-be91-12fdbaee135f-experiment-1-checkpoint-120832-100ep-seed0-6ba3ba6d7654.json`,
`research/evaluations/556a14d8-1ec1-4130-be91-12fdbaee135f/task-reference-556a14d8-1ec1-4130-be91-12fdbaee135f-experiment-1-checkpoint-95232-task-reference-v1.json`,
`research/evaluations/556a14d8-1ec1-4130-be91-12fdbaee135f/task-reference-556a14d8-1ec1-4130-be91-12fdbaee135f-experiment-1-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/556a14d8-1ec1-4130-be91-12fdbaee135f/task-reference-556a14d8-1ec1-4130-be91-12fdbaee135f-experiment-1-checkpoint-120832-task-reference-v1.json`,
`robot_learning/benchmark/final_contract.py`,
`robot_learning/benchmark/reference_evaluation.py`.
