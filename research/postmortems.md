# Research postmortems

## 2f80d343-e97b-4af0-90b0-51cba116b8ae / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success on the
official 200-episode panel. The fresh PPO baseline reached 61.0% on the
research panel and 56.5% on the task-reference panel. Unchanged continuation
produced a materially stronger development policy at continuation checkpoint
`checkpoint-75776`, scoring 84.5% and 85.5% on those panels, respectively, but
the later measured checkpoints declined to 83.5%/84.5% and 82.5%/81.0%.
`checkpoint-75776` is therefore the strongest measured policy and is selected
for the next development lineage, not for terminal assessment.

**Lessons and limits:** Experiment 2's training proxies peaked around the
measured best checkpoint (training success 0.98 and reward 189.728 at 75,776
continuation steps) and were lower at 110,592 (0.92 and 176.222) and 115,712
(0.89 and 169.413). Measured task success followed the same broad checkpoint
ordering in this continuation, so the run does not reproduce the earlier
proxy-only late improvement, but it does show that selecting a checkpoint
matters. For `checkpoint-75776`, 20 of 31 research-panel failures never reached
tolerance and 11 reached it but failed the uninterrupted hold. The two
development panels agree on the ranking, while both leave a large shortfall to
the objective. These observations describe saved policies and training
dynamics; they do not establish that optimization caused the differences or
identify whether reaching, holding, representation, exploration, or reward is
the limiting mechanism. The evidence remains one training seed and development
panels rather than an official result.

**Open questions:** It remains unknown whether a changed recipe can convert the
remaining reaching and hold failures into the 196 successes required by the
objective, and which intervention would do so. The variability across training
seeds and the durability of the checkpoint-selection effect are also unresolved.

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

## 2f80d343-e97b-4af0-90b0-51cba116b8ae / Experiment 2

**Result:** Unchanged continuation produced a substantially improved but still
insufficient policy. `checkpoint-75776` is selected as working and best-known
for continued development; terminal assessment is not requested.

**Observed behavior:** The continuation completed 115,712 training steps. The
candidate inventory recorded its highest measured candidate proxy near
`checkpoint-75776` (training success 0.98, reward 189.728), followed by lower
values at `checkpoint-110592` (0.92, 176.222) and `checkpoint-115712` (0.89,
169.413). On the 200-episode research panel, these checkpoints achieved 84.5%
(169 successes), 83.5% (167), and 82.5% (165), respectively. On the fixed
200-episode task-reference panel they achieved 85.5% (171), 84.5% (169), and
81.0% (162). For `checkpoint-75776`, the research diagnostics contained 20
failures that never reached tolerance and 11 failures that reached tolerance
but did not maintain the 100-step hold. The paired research-panel comparisons
favored `checkpoint-75776` by 17 to 15 over `checkpoint-110592` and 18 to 14
over `checkpoint-115712`, but neither comparison was decisive (exact p-values
0.8601 and 0.5966). Twenty other candidates remain unmeasured; they are not
treated as failures.

**Hypothesis assessment:** Partially supported. Continuation produced a
measured policy well above the late-baseline levels of 61.0% research success
and 56.5% task-reference success, so the result is more than a training-proxy
claim and provides useful progress toward the human objective. However, the
benefit was not monotonic across the measured continuation checkpoints:
`checkpoint-75776` was stronger than both later checkpoints, and the observed
proxy and task-success decline does not establish that further unchanged
updates would improve complete task success. The diagnostic conclusion is
limited to this recipe, continuation, seed, and development coverage.

**Interpretation:** The unchanged PPO recipe can improve the saved policy
substantially beyond the baseline, but its later continuation in this run
showed checkpoint-dependent degradation rather than a path to the 98% target.
The cross-panel agreement supports selecting `checkpoint-75776` as the most
useful current lineage and does not establish causal superiority or
generalization to the official panel. Its 31 research-panel failures and 29
task-reference failures show that terminal assessment would be premature.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/2f80d343-e97b-4af0-90b0-51cba116b8ae/experiment-2/inventory.json`;
`research/evaluations/2f80d343-e97b-4af0-90b0-51cba116b8ae/evaluation-2f80d343-e97b-4af0-90b0-51cba116b8ae-experiment-2-checkpoint-75776-200ep-seed0-c5b54f36dc64.json`;
`research/evaluations/2f80d343-e97b-4af0-90b0-51cba116b8ae/evaluation-2f80d343-e97b-4af0-90b0-51cba116b8ae-experiment-2-checkpoint-110592-200ep-seed0-c5b54f36dc64.json`;
`research/evaluations/2f80d343-e97b-4af0-90b0-51cba116b8ae/evaluation-2f80d343-e97b-4af0-90b0-51cba116b8ae-experiment-2-checkpoint-115712-200ep-seed0-c5b54f36dc64.json`;
`research/evaluations/2f80d343-e97b-4af0-90b0-51cba116b8ae/task-reference-2f80d343-e97b-4af0-90b0-51cba116b8ae-experiment-2-checkpoint-75776-task-reference-v1.json`;
`research/evaluations/2f80d343-e97b-4af0-90b0-51cba116b8ae/task-reference-2f80d343-e97b-4af0-90b0-51cba116b8ae-experiment-2-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/2f80d343-e97b-4af0-90b0-51cba116b8ae/task-reference-2f80d343-e97b-4af0-90b0-51cba116b8ae-experiment-2-checkpoint-115712-task-reference-v1.json`.
