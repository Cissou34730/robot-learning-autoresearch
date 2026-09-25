# Research postmortems

## ce975eba-5215-40a8-b0df-a44becc66a91 / Scientific strategy

**Current synthesis:** The unchanged baseline learned a strong reach-and-hold policy, but development evidence does not independently establish the human objective of at least 196 successes in 200 official episodes. Checkpoint-100352 is the best closure candidate: it achieved 159/160 on the disjoint research panel and 196/200 on the reused task-reference panel, while checkpoint-120832 achieved 158/160 and 194/200 on those respective panels. The task-reference result is not independent because that panel was used in selection. An official benchmark is therefore the highest-value next action.

**Lessons and limits:** Training proxies identified a useful late-training plateau but did not rank the measured policies reliably. Checkpoint-100352 and checkpoint-120832 tied at 151/160 on the first research panel, and their disjoint comparison favored 100352 by only one success over 320 comparable episodes. The pooled research result for 100352 was 310/320 (96.875%), below the 98% objective, so the evidence supports progress but not a definitive claim.

**Open questions:** Does checkpoint-100352 reach at least 196/200 on the official final benchmark, and do its remaining failures reflect sampling variation or a persistent task-generalization weakness?

## ce975eba-5215-40a8-b0df-a44becc66a91 / Experiment 1

**Result:** The fresh baseline produced a capable policy but did not yet provide conclusive evidence of satisfying the human objective. Checkpoint-100352 is selected as both working and best-known lineage, the unchanged scientific recipe is kept, and the official benchmark is requested.

**Observed behavior:** Checkpoint-86016 scored 149/160 on the first research panel and 188/200 on the fixed task-reference panel. Checkpoint-100352 scored 151/160 on the first research panel, 159/160 on the disjoint research panel, and 196/200 on the fixed task-reference panel. Checkpoint-120832 scored 151/160, 158/160, and 194/200 on those panels. The 100352 versus 120832 paired comparison had one discordant win for 100352 and none for 120832 over 320 pooled comparable episodes.

**Hypothesis assessment:** Partially supported. The baseline recipe learned the target behavior and reached objective-level performance on one reused reference panel and one disjoint research panel, but its pooled independent research evidence was 310/320, below the 98% threshold. Continued training to 120832 did not improve the measured behavior.

**Interpretation:** The evidence favors checkpoint-100352 over the final checkpoint, but the advantage is small and panel-dependent. The fixed task-reference score cannot independently confirm the selection because it was used to select 100352. The disjoint 159/160 result is the relevant independent support, while the 151/160 result on the other research panel and the pooled 96.875% rate leave the official outcome uncertain. No further development measurement is justified before the official benchmark.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/results.jsonl`; `research/checkpoints/challengers/ce975eba-5215-40a8-b0df-a44becc66a91/experiment-1/inventory.json`; the eight evaluation artifacts under `research/evaluations/ce975eba-5215-40a8-b0df-a44becc66a91/`; `research/program.md`; `research/scenario.md`; and `research/instruments.md`.
