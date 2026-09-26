# Research postmortems

## 6cd67bed-b2eb-410a-86fc-0bbb962ec1c1 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline produced a strong late-training policy, with `checkpoint-100352` as the best-supported working and best-known lineage at 394/400 pooled success (98.5%) across two disjoint research panels. The retained final checkpoint reached 392/400 (98.0%), so the intermediate checkpoint remains the stronger measured policy.

**Lessons and limits:** Training proxies located the useful late-training region but did not select the policy: `checkpoint-86016` measured 190/200, while the later candidates were stronger. The first 100352 panel was selection-biased; the disjoint panel confirmed strong but slightly lower performance. All measurements used researcher-owned semantics, with no task-reference panel and no official result, so transfer to the fixed human-owned assessment remains uncertain. Evidence: `research/research_state.json`, `research/results.jsonl`, and the five artifacts under `research/evaluations/6cd67bed-b2eb-410a-86fc-0bbb962ec1c1/`.

**Open questions:** Whether the frozen `checkpoint-100352` reaches the required 196/200 on the official panel remains unresolved. The causes and persistence of its residual failures, and the effect of training beyond the selected checkpoint, are also not established by the current evidence.

## 6cd67bed-b2eb-410a-86fc-0bbb962ec1c1 / Experiment 1

**Result:** The baseline produced a strong late-training policy. `checkpoint-100352` is selected as both working and best known; `checkpoint-120832` is retained as a measured late-training alternative.

**Observed behavior:** Training success rose from 0 at early checkpoints to 0.42 at 86016 steps and 0.97 at 100352 steps, then remained high but fluctuated through 120832 steps. On the first research panel, checkpoints 86016, 100352, and 120832 scored 190/200, 199/200, and 197/200. On the disjoint second panel, checkpoints 100352 and 120832 each scored 195/200. The paired comparison over their 400 distinct episodes favored 100352 by 2 discordant wins to 0. These are development measurements, not the official result.

**Hypothesis assessment:** The baseline established that the unchanged PPO recipe can learn a policy near the human objective, with the strongest measured behavior at an intermediate late-training checkpoint rather than the final checkpoint. This conclusion is supported for the tested research-evaluation semantics, but the single disjoint confirmation panel and absence of task-reference measurements limit confidence about the official panel.

**Expected observation disposition:** not tested - this automatic baseline had no non-baseline expected observation; the measured late-training evidence is recorded above.

**Interpretation:** Preserve the unchanged scientific recipe and the independently confirmed late-training peak. The pooled 98.5% research-evaluation result is encouraging but leaves six failures across 400 episodes and does not establish the required 196/200 official result. Retaining the final checkpoint preserves a concrete alternative for future comparison or continuation without treating it as the best policy.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/checkpoints/challengers/6cd67bed-b2eb-410a-86fc-0bbb962ec1c1/experiment-1/inventory.json`; `research/evaluations/6cd67bed-b2eb-410a-86fc-0bbb962ec1c1/evaluation-6cd67bed-b2eb-410a-86fc-0bbb962ec1c1-experiment-1-checkpoint-86016-200ep-seed10000-f48545f83637.json`; `research/evaluations/6cd67bed-b2eb-410a-86fc-0bbb962ec1c1/evaluation-6cd67bed-b2eb-410a-86fc-0bbb962ec1c1-experiment-1-checkpoint-100352-200ep-seed10000-f48545f83637.json`; `research/evaluations/6cd67bed-b2eb-410a-86fc-0bbb962ec1c1/evaluation-6cd67bed-b2eb-410a-86fc-0bbb962ec1c1-experiment-1-checkpoint-100352-200ep-seed20000-f48545f83637.json`; `research/evaluations/6cd67bed-b2eb-410a-86fc-0bbb962ec1c1/evaluation-6cd67bed-b2eb-410a-86fc-0bbb962ec1c1-experiment-1-checkpoint-120832-200ep-seed10000-f48545f83637.json`; `research/evaluations/6cd67bed-b2eb-410a-86fc-0bbb962ec1c1/evaluation-6cd67bed-b2eb-410a-86fc-0bbb962ec1c1-experiment-1-checkpoint-120832-200ep-seed20000-f48545f83637.json`.
