# Research postmortems

## bb00eecc-8011-4046-b8e7-823d3c432962 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned reliable reach-and-hold behavior, with checkpoint-100352 the strongest available policy at 194/200 on the disjoint research panel and 389/400 pooled across both research panels. Its fixed task-reference result was 196/200, but this remains development evidence rather than an official result. The four task-reference failures were all inner-radius targets between 6.73 and 9.91 cm, while the training distribution sampled only 14-20 cm; continued training to checkpoint-120832 also regressed relative to checkpoint-100352.

**Lessons and limits:** Direct task measurements, not training proxies, distinguish the candidates. The disjoint 3000-3199 panel confirms near-objective behavior, but no development measurement establishes the official objective. The inner-radius failure pattern is consistent with a training-distribution gap, not proof of its cause; the measured panels are finite and the selected policy has already been evaluated on them.

**Open questions:** It remains unresolved whether exposure to the full 6-20 cm target-radius range improves inner-target reach-and-hold reliability without degrading performance elsewhere. It is also unresolved whether the post-100352 regression reflects ordinary continued-training variance or a broader optimization limitation.

## bb00eecc-8011-4046-b8e7-823d3c432962 / Experiment 1

**Result:** The baseline produced a near-objective policy, with checkpoint-100352 selected as the working and best-known candidate.

**Observed behavior:** Checkpoint-100352 scored 195/200 on research episodes 2000-2199, 194/200 on the disjoint episodes 3000-3199, and 196/200 on the fixed task-reference panel. Checkpoint-95232 scored 195/200 and 193/200 on the two research panels, while checkpoint-120832 scored 194/200 and 192/200. Across the two research panels, the pooled scores were 389/400, 388/400, and 386/400 respectively. Paired comparisons favored checkpoint-100352 over checkpoint-95232 by 2-1 discordant wins and over checkpoint-120832 by 3-0 on the disjoint panel; continued training after 100352 therefore did not improve the measured task outcome.

**Hypothesis assessment:** The baseline establishes strong learned behavior and a reproducible candidate ranking across two research panels, but it does not satisfy the 98% objective in independent development evidence. The apparent proxy-peak advantage is partially supported: checkpoint-100352 remained best on the disjoint panel, while the final checkpoint regressed. These are development measurements, not an official benchmark result.

**Expected observation disposition:** not tested - the automatic baseline had no frozen expected observation beyond establishing an initial reference; the available measurements establish the reference and candidate ranking.

**Interpretation:** Checkpoint-100352 is the most useful current lineage despite not yet reaching the objective. Keeping the unchanged scientific recipe preserves the exact baseline conditions, and retaining checkpoint-95232 preserves a close, independently measured alternative. No measured evidence justifies selecting the later checkpoint.

**Evidence inspected:** research/brief.md; research/research_state.json; research/checkpoints/challengers/bb00eecc-8011-4046-b8e7-823d3c432962/experiment-1/inventory.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-100352-200ep-seed2000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-100352-200ep-seed3000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-95232-200ep-seed3000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-120832-200ep-seed3000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/task-reference-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-100352-task-reference-v1.json
