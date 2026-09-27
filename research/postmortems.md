# Research postmortems

## bb00eecc-8011-4046-b8e7-823d3c432962 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline remains the strongest available lineage: checkpoint-100352 scored 194/200 on the earlier disjoint research panel and 196/200 on the new 4000-4199 panel. Continuing it with full-range 6-20 cm target training produced three measured checkpoints at 196/200, exactly matching the same-panel baseline control and repeating the same four failures. The fixed task-reference result was also 196/200, but all development measurements remain distinct from the official result.

**Lessons and limits:** Direct task measurements, not training proxies, distinguish the candidates. The full-range target intervention did not separate from the baseline on the new panel: checkpoints 100352, 105472, and 120832 all failed episode seeds 4030, 4040, 4049, and 4134, while the control failed those same episodes. This weakens the training-distribution explanation under the tested continuation, but finite panels do not establish why those residual failures occur and the new panel is now selection exposure for the retained lineage.

**Open questions:** It remains unresolved whether a different intervention can remove the recurring residual failures without harming broader reach-and-hold behavior, and whether the post-100352 regression reflects ordinary continued-training variance or a broader optimization limitation.

## bb00eecc-8011-4046-b8e7-823d3c432962 / Experiment 1

**Result:** The baseline produced a near-objective policy, with checkpoint-100352 selected as the working and best-known candidate.

**Observed behavior:** Checkpoint-100352 scored 195/200 on research episodes 2000-2199, 194/200 on the disjoint episodes 3000-3199, and 196/200 on the fixed task-reference panel. Checkpoint-95232 scored 195/200 and 193/200 on the two research panels, while checkpoint-120832 scored 194/200 and 192/200. Across the two research panels, the pooled scores were 389/400, 388/400, and 386/400 respectively. Paired comparisons favored checkpoint-100352 over checkpoint-95232 by 2-1 discordant wins and over checkpoint-120832 by 3-0 on the disjoint panel; continued training after 100352 therefore did not improve the measured task outcome.

**Hypothesis assessment:** The baseline establishes strong learned behavior and a reproducible candidate ranking across two research panels, but it does not satisfy the 98% objective in independent development evidence. The apparent proxy-peak advantage is partially supported: checkpoint-100352 remained best on the disjoint panel, while the final checkpoint regressed. These are development measurements, not an official benchmark result.

**Expected observation disposition:** not tested - the automatic baseline had no frozen expected observation beyond establishing an initial reference; the available measurements establish the reference and candidate ranking.

**Interpretation:** Checkpoint-100352 is the most useful current lineage despite not yet reaching the objective. Keeping the unchanged scientific recipe preserves the exact baseline conditions, and retaining checkpoint-95232 preserves a close, independently measured alternative. No measured evidence justifies selecting the later checkpoint.

**Evidence inspected:** research/brief.md; research/research_state.json; research/checkpoints/challengers/bb00eecc-8011-4046-b8e7-823d3c432962/experiment-1/inventory.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-100352-200ep-seed2000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-100352-200ep-seed3000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-95232-200ep-seed3000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-120832-200ep-seed3000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/task-reference-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-100352-task-reference-v1.json

## bb00eecc-8011-4046-b8e7-823d3c432962 / Experiment 2

**Result:** Full-range target-radius continuation did not improve measured reliability. Checkpoints 100352, 105472, and 120832 each achieved 196/200 (98%) on research episodes 4000-4199, matching the same-panel best-known control.

**Observed behavior:** All three changed-recipe checkpoints and the control failed the same four episodes, seeds 4030, 4040, 4049, and 4134; each failed episode truncated at 500 steps. Paired comparisons recorded zero discordant wins for every changed checkpoint versus the control, and no measured checkpoint showed inner-radius separation.

**Hypothesis assessment:** The hypothesis is weakened. The transferred full-range policies reached the expected overall count of 196/200 on a new panel without broad regression, but they did not improve inner-radius reliability or outperform the control; the recurring failures remained unchanged. This supports retaining the original baseline lineage, while the finite panel cannot establish whether another training intervention would help.

**Expected observation disposition:** weakened - all three changed-recipe checkpoints scored 196/200 on research episodes 4000-4199, but each matched the best-known control and repeated its four failures rather than improving inner-radius reliability.

**Interpretation:** The full-range target distribution alone did not repair the observed residual failures under this transferred continuation. Checkpoint-100352 remains the most useful working and best-known policy, and the changed experiment recipe should not be retained as the active scientific recipe. No experiment-2 challenger is retained because none provides evidence of an improvement over the established lineage.

**Evidence inspected:** research/brief.md; research/research_state.json; research/checkpoints/challengers/bb00eecc-8011-4046-b8e7-823d3c432962/experiment-2/inventory.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-2-delta-100352-200ep-seed4000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-2-delta-105472-200ep-seed4000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-2-delta-120832-200ep-seed4000-f48545f83637.json; research/evaluations/bb00eecc-8011-4046-b8e7-823d3c432962/evaluation-bb00eecc-8011-4046-b8e7-823d3c432962-experiment-1-delta-100352-200ep-seed4000-f48545f83637.json
