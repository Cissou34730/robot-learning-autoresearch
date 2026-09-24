# Research postmortems

## 8635b3d2-8904-405a-a15e-d72fb56435d8 / Scientific strategy

**Current synthesis:** The baseline learned a strong reach-and-hold policy, but the best measured candidate remains below the 98% human objective. `checkpoint-100352` is the strongest available lineage: it achieved 95.0% on a disjoint 200-episode research panel and 94.375% on the earlier panel, while the later `checkpoint-120832` achieved 93.5% and 94.375%. The 98.0% task-reference result for `checkpoint-100352` was used to select it and is therefore not independent confirmation.

**Lessons and limits:** Training proxies identify the learned transition but do not establish task success: measured success was 93.125% at the reward peak and 94.375–95.0% for the stronger late checkpoints. The paired comparison favors `checkpoint-100352` over `checkpoint-120832` by 3 discordant episodes to 0 across 360 shared episodes, but this is a small behavioral margin and development panels do not establish the official result. The unchanged baseline recipe is a useful starting point for further training, while the cause of the residual failures is unresolved.

**Open questions:** Which training or task-coverage change can reduce the remaining failures without repeating the late-training regression, and whether the selected policy's measured 95.0% transfers to the official 200-episode assessment remain unresolved.

## 8635b3d2-8904-405a-a15e-d72fb56435d8 / Experiment 1

**Result:** The baseline produced a useful but sub-target policy. `checkpoint-100352` is selected as the working and best-known lineage for continued development.

**Observed behavior:** Training success rose from zero to high values after approximately 75,000 steps. `checkpoint-86016` reached 93.125% on 160 research episodes and 94.0% on the fixed task-reference panel. `checkpoint-100352` reached 94.375% on the first 160-episode research panel, 95.0% on the disjoint 200-episode panel, and 98.0% on the fixed task-reference panel. `checkpoint-120832` reached 94.375%, 93.5%, and 97.0% on those corresponding panels. The fixed task-reference panel was used for candidate selection and is not independent confirmation.

**Hypothesis assessment:** Supported for establishing a strong baseline, but the evidence does not support claiming that the baseline satisfies the human objective: the best disjoint research result is 95.0%, below 98%. The measurements also indicate that continuing from `checkpoint-100352` to the final checkpoint was not beneficial under these conditions, although this is a checkpoint comparison rather than a causal attribution of late-training degradation.

**Interpretation:** `checkpoint-100352` is the best-supported saved policy because it generalizes better than the final checkpoint on the disjoint panel and wins the pooled paired comparison, while retaining the strongest task-reference score. It should anchor a subsequent training experiment aimed at the residual failures; no final benchmark is requested because development evidence does not justify expecting the objective-reaching verdict.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/checkpoints/challengers/8635b3d2-8904-405a-a15e-d72fb56435d8/experiment-1/inventory.json`; `research/evaluations/8635b3d2-8904-405a-a15e-d72fb56435d8/evaluation-8635b3d2-8904-405a-a15e-d72fb56435d8-experiment-1-checkpoint-86016-160ep-seed4200-f48545f83637.json`; `research/evaluations/8635b3d2-8904-405a-a15e-d72fb56435d8/evaluation-8635b3d2-8904-405a-a15e-d72fb56435d8-experiment-1-checkpoint-100352-160ep-seed4200-f48545f83637.json`; `research/evaluations/8635b3d2-8904-405a-a15e-d72fb56435d8/evaluation-8635b3d2-8904-405a-a15e-d72fb56435d8-experiment-1-checkpoint-100352-200ep-seed4360-f48545f83637.json`; `research/evaluations/8635b3d2-8904-405a-a15e-d72fb56435d8/evaluation-8635b3d2-8904-405a-a15e-d72fb56435d8-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json`; `research/evaluations/8635b3d2-8904-405a-a15e-d72fb56435d8/evaluation-8635b3d2-8904-405a-a15e-d72fb56435d8-experiment-1-checkpoint-120832-200ep-seed4360-f48545f83637.json`; and the three task-reference artifacts for experiment 1.
