# Research postmortems

## bfd2ba5d-29c7-4c64-bf19-54cbd743ae39 / Experiment 1

**Result:** The fresh PPO baseline learned a policy that achieved 98.00% success on each of three compatible 100-episode research evaluations at checkpoints 95,232, 100,352, and 120,832 steps. The checkpoint at 100,352 steps is selected as the working and best-known policy, and terminal assessment is requested.

**Observed behavior:** The experiment was a fresh baseline from scratch, not a continuation or replication. Training proxy success rose from 0 at 5,120 steps to a peak of 0.97 at 100,352 steps, then ended at 0.95 after 120,832 steps. Each measured checkpoint succeeded on 98 of 100 episodes under evaluation semantics `e602a32560ea`. The same evaluation panel failures occurred at episode seeds 11 and 25 for all three checkpoints; both episodes truncated at 500 steps without success. The three checkpoints therefore showed no measured success difference, while 100,352 steps was the training-proxy peak.

**Hypothesis assessment:** The baseline objective was partially supported: learning produced a policy at the 98% development threshold, but the result does not establish performance on the official task distribution. The repeated failures indicate a stable residual blind spot on this development panel, while their exact repetition across checkpoints limits what can be inferred about broader-distribution failure modes. The training trajectory also does not show continued improvement after the proxy peak. The evidence is sufficient to choose a candidate and request the authoritative benchmark, but not to claim official success.

**Interpretation:** The unchanged PPO recipe is practically capable of reaching the target on the available development panel. Since all measured candidates are tied on task success and no causal comparison was performed, selecting 100,352 steps relies on its observed training-proxy peak rather than a demonstrated evaluation advantage. Further same-panel measurements would not resolve the principal uncertainty; the official benchmark is the appropriate next measurement.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/training_logs/bfd2ba5d-29c7-4c64-bf19-54cbd743ae39/experiment-1-attempt-1.log`; `research/evaluations/bfd2ba5d-29c7-4c64-bf19-54cbd743ae39/evaluation-bfd2ba5d-29c7-4c64-bf19-54cbd743ae39-experiment-1-checkpoint-95232-100ep-seed0-e602a32560ea.json`; `research/evaluations/bfd2ba5d-29c7-4c64-bf19-54cbd743ae39/evaluation-bfd2ba5d-29c7-4c64-bf19-54cbd743ae39-experiment-1-checkpoint-100352-100ep-seed0-e602a32560ea.json`; `research/evaluations/bfd2ba5d-29c7-4c64-bf19-54cbd743ae39/evaluation-bfd2ba5d-29c7-4c64-bf19-54cbd743ae39-experiment-1-checkpoint-120832-100ep-seed0-e602a32560ea.json`.

## bfd2ba5d-29c7-4c64-bf19-54cbd743ae39 / Scientific strategy

**Direction:** Establish whether the learned reach-and-hold policy satisfies the unchanged official task, using terminal assessment of the strongest measured baseline candidate rather than further same-panel optimization.

**Lessons and limits:** A fresh PPO recipe with a tanh 64x64 policy reached 98% on the three measured development checkpoints (Experiment 1; `research/results.jsonl` and the evaluation artifacts above). The identical two failures across checkpoints suggest a repeatable panel-specific blind spot, but the single 100-episode panel and nonterminal semantics do not establish generalization or official success. Proxy reward and success peaked before the final checkpoint, so later training was not clearly beneficial.

**Open questions:** Whether the 98% development result transfers to the official target distribution, and whether the repeated panel failures represent a broader geometric or control limitation, remain unresolved.

**Conditional next steps:** If research continues after a nonterminal decision, characterize and address the repeated failure pattern with measurements that vary coverage rather than repeating the same panel; otherwise use the requested terminal benchmark as the campaign result.
