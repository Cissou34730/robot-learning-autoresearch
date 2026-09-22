# Research postmortems

## 0895e3ad-9bbe-48f1-b9c2-15a3cda64614 / Experiment 1

**Result:** The fresh PPO baseline produced a promising learned policy. `checkpoint-100352` is the strongest measured candidate and meets the development-panel objective, but the official result remains unresolved.

**Observed behavior:** The 100-episode research evaluation scored 96/100 for `checkpoint-86016`, 97/100 for `checkpoint-100352`, and 96/100 for `checkpoint-120832`. On the fixed task-reference panel, the same candidates scored 94/100, 98/100, and 97/100. Paired research-panel comparisons gave `checkpoint-100352` a one-episode advantage over each neighboring measured checkpoint. The selected checkpoint still had three research-panel failures and two task-reference failures.

**Hypothesis assessment:** The baseline measurement hypothesis was partially supported. The late high-training-success checkpoint (`checkpoint-100352`) performed better than the earlier proxy-peak checkpoint and the final checkpoint on both measured panels, while continued training to `checkpoint-120832` weakened task-reference performance. The conclusion is limited because the task-reference panel was reused for selection and the research evaluation covered only 100 episodes; neither is the official 200-episode benchmark.

**Interpretation:** Learning reached the human objective on the development task-reference panel, but the proxy improvement does not establish robust generalization and later training degraded the selected behavior. `checkpoint-100352` is therefore the best-supported saved policy for terminal assessment, while the unchanged PPO recipe remains the appropriate recipe record for this experiment.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/checkpoints/challengers/0895e3ad-9bbe-48f1-b9c2-15a3cda64614/experiment-1/inventory.json`; `research/evaluations/0895e3ad-9bbe-48f1-b9c2-15a3cda64614/`.

## 0895e3ad-9bbe-48f1-b9c2-15a3cda64614 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned effective reach-and-hold behavior. Among the measured late checkpoints, `checkpoint-100352` is the best-supported policy: it reached 98% on the fixed task-reference development panel and slightly exceeded both neighboring checkpoints in paired research-panel comparisons. The final checkpoint regressed, so training proxies are useful for locating candidates but do not reliably rank final task behavior.

**Lessons and limits:** Development evidence supports selecting `checkpoint-100352`, not claiming the official objective is satisfied. The research panel is only 100 episodes, and the task-reference panel was reused across candidates and therefore provides comparison rather than independent confirmation. Residual failures remain in both panels; the official frozen benchmark is the only terminal assessment.

**Open questions:** Whether `checkpoint-100352` reaches at least 196 successes on the official 200-episode benchmark, and whether its observed residual failures reflect generalization limits beyond the development panels, remain unresolved.
