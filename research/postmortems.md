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

## f7e0bace-c0b5-4892-95a4-a1440c71de04 / Scientific strategy

**Current synthesis:** The baseline recipe produces a policy near the human
objective on development panels. Checkpoint-100352 is currently best known
because it leads on disjoint research measurements, while later training to
checkpoint-120832 did not improve measured success.

**Lessons and limits:** Training proxies are useful for locating candidate
checkpoints but do not reliably rank task policies. The research measurements
support lineage selection, but their finite panels and the reused
task-reference panel do not establish official success; only the final
assessment can do that.

**Open questions:** Whether checkpoint-100352 reaches at least 98% on the
official 200-episode panel remains unresolved.
