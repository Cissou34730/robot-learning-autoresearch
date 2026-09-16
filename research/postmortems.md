# Research postmortems

## 2f80d343-e97b-4af0-90b0-51cba116b8ae / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success on the
official 200-episode panel. Experiment 1's PPO baseline learned substantial
reach-and-hold behavior but remained far from that objective: the two measured
late checkpoints scored 60.0% and 61.0% on the researcher panel and 55.0% and
56.5% on the protected task-reference panel. `checkpoint-110592` is the
strongest measured policy in both panels, although its advantage over
`checkpoint-115712` is small.

**Lessons and limits:** Training proxies rose from 0 success and -403.195
reward at 5,120 steps to 0.92 and 176.617 at 115,712 steps, while measured task
success did not rise with the late proxy increase. For `checkpoint-110592`, 58
of 78 researcher-panel failures never reached tolerance and 20 reached it but
lost the uninterrupted hold; nearer targets also performed worse than outer
targets. The policy representation is a 14-value physical state description
containing joint state, end-effector error and velocity, and analytical
inverse-kinematics errors, with saved observation normalization. These findings
are measured behavior, not causal attribution: one training seed and the
available development panels do not distinguish representation, exploration,
reward shaping, or optimization effects, nor establish reproducibility.

**Open questions:** It remains unknown whether the late proxy/success
divergence reflects a temporary optimization plateau, degradation from further
updates, or a persistent mismatch between training signal and complete
official-task success. It also remains unresolved which mechanism most limits
near-target reaching and uninterrupted holding, and how much of the observed
shortfall varies across training seeds.

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
