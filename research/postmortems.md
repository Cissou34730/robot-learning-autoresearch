# Research postmortems

## 60ab6970-22ca-42f3-91de-94ef2a90d349 / Scientific strategy

**Direction:** Freeze the strongest measured policy and use the official terminal assessment to determine whether the learned reach-and-hold policy satisfies the 98% objective. If research continues in a future campaign, prioritize robustness on the recurring hard target instances and stability around the 100k-step checkpoint rather than assuming that more training improves the policy.

**Lessons and limits:** The unchanged PPO baseline reached 98.1667% over 600 development episodes at checkpoint-100352 (98/100 and 491/500), while checkpoint-120832 reached 97.5% (98/100 and 487/500); checkpoint-86016 reached 95/100. This supports selecting an intermediate checkpoint, but all measurements are non-official development evaluations from one training run and do not establish the official result. The repeated failures at episode seeds 11 and 25 identify difficult instances, not a causal failure mechanism.

**Open questions:** Whether checkpoint-100352 reaches at least 98% on the frozen official distribution, and whether its apparent margin survives the official panel's sampling uncertainty, remain unresolved.

**Conditional next steps:** The current campaign should request terminal assessment of checkpoint-100352. A future development direction, if needed, is targeted robustness and checkpoint-selection work around the observed hard instances, with comparisons designed to avoid treating repeated development-panel use as independent confirmation.

## 60ab6970-22ca-42f3-91de-94ef2a90d349 / Experiment 1

**Result:** The fresh baseline produced a development candidate at checkpoint-100352 that met the 98% target on both measured panels and was stronger than the later final checkpoint; it is selected for terminal assessment.

**Observed behavior:** This was a fresh baseline training run with the unchanged PPO recipe, not a changed-recipe test, continuation, or replication. The training proxy rose from 0.00 at 5,120 steps to 0.97 at 100,352 steps and ended at 0.95. Research evaluation measured checkpoint-100352 at 98.0% over 100 episodes (seed 0) and 98.2% over 500 episodes (seed 1), for 589/600 pooled successes. Checkpoint-120832 measured 98.0% and 97.4% on the same respective panels, while checkpoint-86016 measured 95.0% over 100 episodes. The 100,352-step and 120,832-step policies shared failures at episode seeds 11 and 25; the later policy had additional failures, including seeds 124, 430, 454, and 500.

**Hypothesis assessment:** Partially supported. The baseline established that the default fresh-trained recipe can produce a policy at or just above the human threshold on development measurements, and the measured learning trajectory shows substantial progress. The later degradation and the absence of an official benchmark leave robustness and the human objective unresolved; development success is not evidence of an official 98% result.

**Interpretation:** Checkpoint-100352 is the best available candidate because it has the highest pooled measured success and outperforms the later checkpoint by four net episode wins in the compatible 600-episode comparison. This is a policy-selection result, not a causal claim about training duration. The remaining uncertainty is proportionate to the terminal benchmark rather than another repeated development measurement, so the campaign should end development and assess this frozen candidate.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/scenario.md`; `research/evaluations/60ab6970-22ca-42f3-91de-94ef2a90d349/evaluation-60ab6970-22ca-42f3-91de-94ef2a90d349-experiment-1-checkpoint-100352-100ep-seed0-e602a32560ea.json`; `research/evaluations/60ab6970-22ca-42f3-91de-94ef2a90d349/evaluation-60ab6970-22ca-42f3-91de-94ef2a90d349-experiment-1-checkpoint-100352-500ep-seed1-e602a32560ea.json`; `research/evaluations/60ab6970-22ca-42f3-91de-94ef2a90d349/evaluation-60ab6970-22ca-42f3-91de-94ef2a90d349-experiment-1-checkpoint-120832-100ep-seed0-e602a32560ea.json`; `research/evaluations/60ab6970-22ca-42f3-91de-94ef2a90d349/evaluation-60ab6970-22ca-42f3-91de-94ef2a90d349-experiment-1-checkpoint-120832-500ep-seed1-e602a32560ea.json`; `research/evaluations/60ab6970-22ca-42f3-91de-94ef2a90d349/evaluation-60ab6970-22ca-42f3-91de-94ef2a90d349-experiment-1-checkpoint-86016-100ep-seed0-e602a32560ea.json`.
