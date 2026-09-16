# Research postmortems

## 2f80d343-e97b-4af0-90b0-51cba116b8ae / Scientific strategy

**Current synthesis:** Experiment 1 established that the baseline PPO recipe learns
substantial reach-and-hold behavior, but the measured policy is not close to the
98% objective. The late checkpoint with the strongest measured task performance is
`checkpoint-110592`; its advantage over `checkpoint-115712` is small and
directionally consistent across the researcher and protected task-reference
panels.

**Lessons and limits:** Training success and reward rose from 0 and -403.195 to
0.92 and 176.617 by 115,712 steps, but measured success was 60.0% or 61.0% on
the researcher panel and 55.0% or 56.5% on the task-reference panel. This
confirms that the training proxies do not establish task progress by themselves,
especially late in training. Diagnostics indicate both failure to reach the
tolerance region and reaching it without completing the uninterrupted hold; the
available panels also show lower success for nearer targets than for targets near
the outer radius. These are observations of the measured checkpoints, not causal
attributions about the training recipe.

**Open questions:** Which changes to learning conditions or task representation
can reduce the dominant reach and hold failures while preserving performance
across target geometry? The current evidence does not distinguish whether either
failure mode is primarily caused by representation, exploration, reward shaping,
or optimization.

## 2f80d343-e97b-4af0-90b0-51cba116b8ae / Experiment 1

**Result:** The fresh baseline produced a useful but insufficient learned policy.
`checkpoint-110592` is selected as working and best-known for continued
development; terminal assessment is not requested.

**Observed behavior:** Training proxies improved steadily through the run:
training success reached 0.92 and training reward 176.617 at 115,712 steps,
compared with 0 and -403.195 at 5,120 steps. On the 200-episode research panel,
`checkpoint-110592` achieved 61.0% success and `checkpoint-115712` achieved
60.0%. On the fixed 200-episode task-reference panel they achieved 56.5% and
55.0%, respectively. Paired outcomes were close: on the research panel,
110592-only successes were 37 versus 35 for 115712-only; on the task-reference
panel the counts were 30 versus 27. For `checkpoint-110592`, 58 of 78 research
panel failures never reached tolerance and 20 reached it but failed the complete
hold; for `checkpoint-115712`, the corresponding counts were 63 and 17.
Success was higher for targets at 18–20 cm than at 6–10 cm on both panels.

**Hypothesis assessment:** Partially supported. The baseline established
nontrivial learned task behavior and a clear training signal, but it did not
establish a policy satisfying the human objective. The later training-proxy
increase was not accompanied by higher measured task success, so proxy
improvement is insufficient evidence of late policy progress. The small
cross-panel advantage of `checkpoint-110592` supports selecting it as the
current development lineage, but does not establish a meaningful causal or
generalization superiority.

**Interpretation:** The baseline recipe can learn reaching and holding for a
substantial subset of sampled targets, while leaving large residual failure rates
in both initial reaching and uninterrupted holding. The protected task-reference
measurements confirm that the shortfall is not specific to the researcher
evaluator. The comparison supports retaining the earlier late checkpoint as the
most useful current parent, while further training or recipe changes remain
necessary before official assessment.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/2f80d343-e97b-4af0-90b0-51cba116b8ae/experiment-1/inventory.json`;
`research/evaluations/2f80d343-e97b-4af0-90b0-51cba116b8ae/evaluation-2f80d343-e97b-4af0-90b0-51cba116b8ae-experiment-1-checkpoint-110592-200ep-seed0-c5b54f36dc64.json`;
`research/evaluations/2f80d343-e97b-4af0-90b0-51cba116b8ae/evaluation-2f80d343-e97b-4af0-90b0-51cba116b8ae-experiment-1-checkpoint-115712-200ep-seed0-c5b54f36dc64.json`;
`research/evaluations/2f80d343-e97b-4af0-90b0-51cba116b8ae/task-reference-2f80d343-e97b-4af0-90b0-51cba116b8ae-experiment-1-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/2f80d343-e97b-4af0-90b0-51cba116b8ae/task-reference-2f80d343-e97b-4af0-90b0-51cba116b8ae-experiment-1-checkpoint-115712-task-reference-v1.json`.
