# Research postmortems

## 6dab7993-582d-4243-b0a2-f935e51c2728 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned the reach-and-hold behavior but remains below the human objective on the independent researcher panels. Checkpoint-100352 is the strongest measured policy: it achieved 151/160 (94.375%) on each of two disjoint panels, while checkpoint-120832 achieved 151/160 and 149/160. The fixed task-reference panel reported 196/200 (98%) for checkpoint-100352, but that panel is reused and is not independent confirmation.

**Lessons and limits:** Training proxies identified a useful late checkpoint but did not establish the 98% objective. The disjoint research measurements support selecting checkpoint-100352 over the final checkpoint, with 2 versus 0 discordant wins in the matched comparison across 320 pooled executions, but the comparison is small in absolute margin and development measurements are not the official result. The task-reference result demonstrates transfer to the protected task panel, yet its permanent reuse limits confirmation. The measured failures show that the policy is close but not reliably at the required success level.

**Open questions:** Whether additional training or a targeted scientific intervention can raise the independent success rate from roughly 94% to at least the 98% objective remains unresolved. The failure pattern and generalization across the full official distribution also remain to be established.

## 6dab7993-582d-4243-b0a2-f935e51c2728 / Experiment 1

**Result:** The baseline produced a useful late-run policy, with checkpoint-100352 selected as the working and best-known lineage, but the policy is not yet sufficiently supported as meeting the human objective.

**Observed behavior:** Checkpoint-100352 succeeded on 151/160 episodes (94.375%) on both research panels, for 302/320 pooled research episodes. Its task-reference result was 196/200 (98%) on the fixed `task-reference-v1` panel. Checkpoint-120832 scored 151/160 and 149/160 on the two research panels and 97% on the fixed task-reference panel. The matched comparison over 320 episodes gave checkpoint-100352 two wins and checkpoint-120832 zero wins, with two discordant episodes. Training proxies rose late in the run, but the final checkpoint's measured research success was lower than checkpoint-100352's.

**Hypothesis assessment:** Partially supported. The baseline established that the unchanged method can learn the task and that late checkpoints substantially outperform early training, but it did not establish the 98% objective on independent development evidence. The apparent 98% task-reference result cannot serve as independent confirmation because the protected panel is permanently reused; the conclusion is limited to this trained artifact, evaluation semantics, and observed panels.

**Interpretation:** Checkpoint-100352 is the best-supported policy from this experiment and is worth carrying forward. The stable 94.375% result on disjoint research panels indicates real progress but leaves a meaningful residual failure rate, so further development is warranted before requesting the irreversible official assessment. The current scientific recipe is retained because this baseline has demonstrated useful learning and no measured evidence yet justifies changing it.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/checkpoints/challengers/6dab7993-582d-4243-b0a2-f935e51c2728/experiment-1/inventory.json`; `research/evaluations/6dab7993-582d-4243-b0a2-f935e51c2728/evaluation-6dab7993-582d-4243-b0a2-f935e51c2728-experiment-1-checkpoint-100352-160ep-seed4200-f48545f83637.json`; `research/evaluations/6dab7993-582d-4243-b0a2-f935e51c2728/evaluation-6dab7993-582d-4243-b0a2-f935e51c2728-experiment-1-checkpoint-100352-160ep-seed4360-f48545f83637.json`; `research/evaluations/6dab7993-582d-4243-b0a2-f935e51c2728/task-reference-6dab7993-582d-4243-b0a2-f935e51c2728-experiment-1-checkpoint-100352-task-reference-v1.json`; corresponding checkpoint-120832 research and task-reference artifacts.
