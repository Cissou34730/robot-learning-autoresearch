# Research postmortems

## 76a0e44c-15e1-4f0a-aad3-e75ef2d20c09 / Scientific strategy

**Direction:** Improve official-task generalization from the near-threshold baseline, focusing on the short-radius and lower-left-angle failures while preserving complete hold behavior.

**Lessons and limits:** The fresh PPO baseline trained on radii 14-20 cm, while the official task spans 6-20 cm (`robot_learning/scenario/environment.py`, `research/scenario.md`). The checkpoint at 100,352 steps reached 98% on the 200-episode protected task-reference development panel, whereas the final 120,832-step checkpoint reached 97%; both scored 97% on the same 200-episode research panel. This is development evidence, not the official benchmark. Failures in the detailed artifacts cluster at negative angles around -117 to -150 degrees, and include both failure to enter tolerance and unstable interrupted holds. The panel is too small to establish whole-distribution performance or a causal explanation.

**Open questions:** Whether training on the full official radius range improves the short-range failures; whether the lower-left pattern is caused by coverage, representation, or control/hold stability; and whether the 100,352-step checkpoint's apparent advantage persists on another panel.

**Conditional next steps:** Use `checkpoint-100352` as the working and best-known policy for a changed training experiment that broadens target-radius coverage and remeasures the same development panels. If that does not improve the structured failures, investigate observation/control or hold-reward changes rather than extending the unchanged late-stage recipe.

## 76a0e44c-15e1-4f0a-aad3-e75ef2d20c09 / Experiment 1

**Result:** The fresh baseline produced a strong but not officially validated policy. `checkpoint-100352` achieved 97% on research evaluation and 98% on the independent task-reference development panel; `checkpoint-120832` achieved 97% on both.

**Observed behavior:** This was a fresh baseline with the default PPO recipe, not a changed recipe, continuation, or replication. The training proxy rose from 0% to 97% by 97,280 steps, then remained around 93-97% through 120,832 steps while proxy reward declined from its peak. On the identical 200-episode research panel, the two measured checkpoints both had 6 failures and the paired comparison had one win each with two discordant episodes. On the protected task-reference panel, the 100,352-step checkpoint had 4 failures (98%) and the final checkpoint had 6 failures (97%). The late-checkpoint task-reference failures were concentrated at radii 6.7-9.9 cm and angles -116 to -128 degrees. Research-evaluation failures similarly concentrated at negative angles; diagnostics showed both episodes that never reached tolerance and episodes that reached it but repeatedly interrupted the hold. The task-reference evaluator is independent of the researcher-owned environment and reward, but both panels are fixed development measurements.

**Hypothesis assessment:** The baseline hypothesis was to establish an initial reference for the human objective, and it is supported as a useful near-threshold reference. It does not establish that the objective is reached: the 98% task-reference result is one development panel, the research panel is 97%, and no official benchmark was run. The late checkpoint is preferred over the final checkpoint on the available task-reference evidence, but the difference is uncertain and does not support a causal claim about training duration.

**Interpretation:** The default recipe learns the task substantially, but its restricted 14-20 cm training distribution leaves residual generalization and hold-stability failures on the official 6-20 cm task. This pattern motivates changing training coverage; it is an observed association rather than proof that radius coverage caused the failures.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/training_logs/76a0e44c-15e1-4f0a-aad3-e75ef2d20c09/experiment-1-attempt-1.log`; `research/checkpoints/challengers/76a0e44c-15e1-4f0a-aad3-e75ef2d20c09/experiment-1/inventory.json`; `research/checkpoints/challengers/76a0e44c-15e1-4f0a-aad3-e75ef2d20c09/experiment-1/parameters.json`; the two experiment-1 research evaluation artifacts; the two experiment-1 task-reference artifacts; `robot_learning/scenario/environment.py`; `robot_learning/scenario/evaluation.py`; `robot_learning/benchmark/reference_evaluation.py`; `robot_learning/benchmark/reference_contract.py`; `research/scenario.md`.
