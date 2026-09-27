# Research postmortems

## bb00eecc-8011-4046-b8e7-823d3c432962 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned reliable reach-and-hold behavior, but the best measured checkpoint remains just below the human objective. Checkpoint-100352 is the strongest available policy: it achieved 194/200 on the disjoint confirmation panel and 389/400 pooled across the two research panels. Continued training to checkpoint-120832 regressed the measured outcome, while checkpoint-95232 was slightly weaker but remains a useful lower-step alternative.

**Lessons and limits:** Direct task measurements, not training proxies, distinguish the candidates. Checkpoint-100352 was selected by earlier panels, so those scores are not independent confirmation; the disjoint 3000-3199 panel provides the relevant confirmation and still reports 194/200. The fixed task-reference result of 196/200 is development evidence only and does not establish the official objective. The baseline does not identify which residual failure modes limit performance or whether another recipe can exceed 98%.

**Open questions:** Whether a subsequent intervention can eliminate the remaining failures without reproducing the post-100352 regression remains unresolved. The retained 95232-step policy provides a measured alternative for future continuation or comparison.

## bb00eecc-8011-4046-b8e7-823d3c432962 / Experiment 1

**Result:** The baseline produced a near-objective policy, with checkpoint-100352 selected as the working and best-known candidate.

**Observed behavior:** Checkpoint-100352 scored 195/200 on research episodes 2000-2199, 194/200 on the disjoint episodes 3000-3199, and 196/200 on the fixed task-reference panel. Checkpoint-95232 scored 195/200 and 193/200 on the two research panels, while checkpoint-120832 scored 194/200 and 192/200. Across the two research panels, the pooled scores were 389/400, 388/400, and 386/400 respectively. Paired comparisons favored checkpoint-100352 over checkpoint-95232 by 2-1 discordant wins and over checkpoint-120832 by 3-0 on the disjoint panel; continued training after 100352 therefore did not improve the measured task outcome.

**Hypothesis assessment:** The baseline establishes strong learned behavior and a reproducible candidate ranking across two research panels, but it does not satisfy the 98% objective in independent development evidence. The apparent proxy-peak advantage is partially supported: checkpoint-100352 remained best on the disjoint panel, while the final checkpoint regressed. These are development measurements, not an official benchmark result.

**Expected observation disposition:** not tested - the automatic baseline had no frozen expected observation beyond establishing an initial reference; the available measurements establish the reference and candidate ranking.

**Interpretation:** Checkpoint-100352 is the most useful current lineage despite not yet reaching the objective. Keeping the unchanged scientific recipe preserves the exact baseline conditions, and retaining checkpoint-95232 preserves a close, independently measured alternative. No measured evidence justifies selecting the later checkpoint.

**Evidence inspected:** research/brief.md; research/research_state.json; research/checkpoints/challengers/bb00eecc-8011-4046-b8e7-823d3c432962/experiment-1/inventory.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-100352-200ep-seed2000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-100352-200ep-seed3000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-95232-200ep-seed3000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-120832-200ep-seed3000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/task-reference-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-100352-task-reference-v1.json
