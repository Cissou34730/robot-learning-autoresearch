# Research postmortems

## 7b31b401-98a4-423f-bd72-d6f85e0315f6 / Experiment 1

**Result:** The unchanged PPO baseline produced a policy that is a strong candidate for the human objective; checkpoint-100352 is selected for closure.

**Observed behavior:** The late training-reward peak at checkpoint-86016 did not identify the best measured policy: it reached 93.125% on the first research panel and 94% on the reused task-reference panel. Checkpoint-100352 reached 94.375% on the first research panel, 98% on the reused task-reference panel, and 99.5% (199/200) on a disjoint research panel. The final checkpoint-120832 reached 94.375%, 97%, and 99% respectively. On the two research panels, 100352 had one discordant win and 120832 had none over 360 distinct episodes.

**Hypothesis assessment:** The baseline hypothesis, "Establish the initial baseline for the human-defined objective," is supported as a baseline-establishment result, but it does not by itself establish official objective attainment. The measurements identify a reproducible late policy candidate and weaken the idea that the proxy reward peak is the right selection rule. The fixed task-reference score was used for candidate comparison but is not independent evidence because that panel is permanently reused; the disjoint 5000 panel provides the independent confirmation available in development.

**Interpretation:** Checkpoint-100352 is the strongest measured policy and is preferable to checkpoint-120832 for the working and best-known roles. Its disjoint result is above the 98% target, while the official 200-episode assessment remains the only authoritative verdict. The unchanged scientific recipe is retained because the useful result came from the baseline recipe and no evidence calls for restoring or reverting code.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/results.jsonl`; `research/checkpoints/challengers/7b31b401-98a4-423f-bd72-d6f85e0315f6/experiment-1/inventory.json`; `research/evaluations/7b31b401-98a4-423f-bd72-d6f85e0315f6/evaluation-7b31b401-98a4-423f-bd72-d6f85e0315f6-experiment-1-checkpoint-100352-200ep-seed5000-f48545f83637.json`; `research/evaluations/7b31b401-98a4-423f-bd72-d6f85e0315f6/task-reference-7b31b401-98a4-423f-bd72-d6f85e0315f6-experiment-1-checkpoint-100352-task-reference-v1.json`

## 7b31b401-98a4-423f-bd72-d6f85e0315f6 / Scientific strategy

**Current synthesis:** The baseline recipe learned a policy with strong measured reach-and-hold behavior. Checkpoint-100352 is supported by 199/200 successes on a disjoint research panel and outperforms the final checkpoint slightly on the shared comparison, while its 98% fixed task-reference result is not independent confirmation.

**Lessons and limits:** Training reward and training success are insufficient selection proxies: checkpoint-86016 had the highest reward but substantially weaker measured behavior. The late candidates are close on the disjoint panel, so the selection margin is modest. Development panels describe readiness but cannot declare the official objective; only the human-owned final benchmark can do so.

**Open questions:** Whether checkpoint-100352 reaches at least 196/200 on the official final panel remains unresolved, as does the distribution of its residual failures outside the measured panels.
