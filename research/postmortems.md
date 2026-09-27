# Research postmortems

## f7e0bace-c0b5-4892-95a4-a1440c71de04 / Experiment 1

**Result:** The baseline learned a strong reach-and-hold policy, with
checkpoint-100352 selected as the best available candidate for closure.

**Observed behavior:** On two disjoint 200-episode research panels,
checkpoint-100352 achieved 199/200 and 194/200 successes, for 393/400
(98.25%) pooled success. Checkpoint-95232 achieved 389/400 (97.25%) and
checkpoint-120832 achieved 391/400 (97.75%). The protected task-reference
panel reported 98%, 96%, and 97% for checkpoints 100352, 95232, and 120832
respectively, but that panel is reused development evidence. Training success
rose to 0.97 at checkpoint-100352 while proxy reward peaked earlier, so the
proxy peak did not by itself establish the best task policy.

**Hypothesis assessment:** The baseline objective was to establish initial
performance rather than test a changed intervention. The measurements support
that a learned policy can approach the 98% objective and identify
checkpoint-100352 as the strongest measured candidate among the tested late
checkpoints. The 97% result on the disjoint panel leaves sampling uncertainty,
and development measurements do not establish official objective success.

**Expected observation disposition:** not tested - this fresh baseline had no
frozen expected observation beyond establishing the initial baseline; the
completed measurements characterize candidate task behavior.

**Interpretation:** Checkpoint-100352 is the evidence-backed best-known policy
for the next campaign decision and is suitable for official assessment, not a
claim that the objective has already been reached. Continued training to
checkpoint-120832 did not improve measured performance, and the unchanged
scientific recipe should be preserved for the selected lineage.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/f7e0bace-c0b5-4892-95a4-a1440c71de04/experiment-1/inventory.json`;
the six research-evaluation artifacts and three task-reference artifacts under
`research/evaluations/f7e0bace-c0b5-4892-95a4-a1440c71de04/`.

## f7e0bace-c0b5-4892-95a4-a1440c71de04 / Experiment 2

**Result:** Lower-learning-rate transfer preserved a near-threshold policy at
one checkpoint but did not improve the incumbent, so the existing best-known
lineage remains selected.

**Observed behavior:** On the disjoint research panel covering episodes
10400-10599, the incumbent scored 194/200 (97%), experiment-2
checkpoint-95232 scored 192/200 (96%), checkpoint-100352 scored 194/200
(97%), and checkpoint-120832 scored 190/200 (95%). The strongest challenger
therefore tied the incumbent on this panel but did not exceed the incumbent's
393/400 pooled result across the two earlier panels. The endpoint also showed
late degradation. The per-episode diagnostics include both full-episode misses
and interrupted holds, so the measured failures are not explained by a single
failure mode in this round.

**Hypothesis assessment:** The lower-learning-rate transfer hypothesis is
weakened. Checkpoint-100352 preserved broad reach-and-hold competence and tied
the incumbent on the fresh panel, but no measured checkpoint exceeded the
parent's pooled development result, and the endpoint regressed to 190/200.
This evidence does not establish that the learning rate is harmful in every
setting; it shows that this transfer run did not provide a stronger saved
policy under the tested checkpoints and panel.

**Expected observation disposition:** weakened - checkpoint-100352 reached
194/200 on the fresh panel, matching rather than exceeding the parent's
393/400 pooled development result, while checkpoint-120832 declined to
190/200.

**Interpretation:** The experiment does not justify replacing the incumbent or
continuing its reduced-rate recipe. The incumbent remains the evidence-backed
working and best-known policy, and the scientific recipe should return to the
parent PPO learning rate of 0.0003. Development evidence remains below the
official decision boundary on the fresh panel and cannot declare whether the
human objective has been reached; that requires the separate official
assessment after a subsequent campaign decision.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/evaluations/f7e0bace-c0b5-4892-95a4-a1440c71de04/evaluation-f7e0bace-c0b5-4892-95a4-a1440c71de04-experiment-1-delta-100352-200ep-seed10400-f48545f83637.json`;
`research/evaluations/f7e0bace-c0b5-4892-95a4-a1440c71de04/evaluation-f7e0bace-c0b5-4892-95a4-a1440c71de04-experiment-2-delta-95232-200ep-seed10400-f48545f83637.json`;
`research/evaluations/f7e0bace-c0b5-4892-95a4-a1440c71de04/evaluation-f7e0bace-c0b5-4892-95a4-a1440c71de04-experiment-2-delta-100352-200ep-seed10400-f48545f83637.json`;
`research/evaluations/f7e0bace-c0b5-4892-95a4-a1440c71de04/evaluation-f7e0bace-c0b5-4892-95a4-a1440c71de04-experiment-2-delta-120832-200ep-seed10400-f48545f83637.json`.

## f7e0bace-c0b5-4892-95a4-a1440c71de04 / Scientific strategy

**Current synthesis:** The baseline PPO recipe produces a near-threshold
reach-and-hold policy on development panels. The incumbent checkpoint-100352
remains best known at 393/400 across the first two disjoint research panels
and scored 194/200 on the later disjoint panel. The lower-rate transfer's
checkpoint-100352 tied that fresh-panel result, but its endpoint fell to
190/200, so the intervention did not improve the incumbent.

**Lessons and limits:** Measured task success, rather than training proxies,
distinguishes the late checkpoints and the reduced learning rate did not
produce a stronger measured policy in this run. The finite research panels
and reused task-reference panel support lineage comparison but do not
establish official success. Residual failures include occasional full-episode
misses and interrupted holds, but the current evidence does not isolate their
cause.

**Open questions:** Whether another scientific intervention can reduce the
residual failure rate without damaging broad competence, and whether
checkpoint-100352 reaches at least 98% on the official 200-episode panel,
remain unresolved.
