# Research postmortems

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Scientific strategy

**Current synthesis:** The PPO reach-and-hold policy is competent but remains
below the objective: `checkpoint-100352` achieved 189/200 (94.5%) on each of
two disjoint research panels, while continued training to `checkpoint-120832`
did not improve it. The selected policy's 98% task-reference result is
development evidence only because that panel was reused for selection. Its
pooled residual failures include target radii throughout the official 6–20 cm
range, including targets below the current 14–20 cm training range.

**Lessons and limits:** Direct task success, not training reward, determined the
lineage choice, and the selected policy is reproducible but sub-threshold.
Detailed failures include interrupted holds and timeouts, and their geometry
does not establish that radius coverage is the sole cause. The two research
panels provide 400 distinct episodes for the selected model; the fixed
task-reference panel and all development measurements remain insufficient to
declare the official objective reached.

**Open questions:** Whether exposing training to the full official radial
distribution improves inner-radius reach-and-hold reliability without reducing
outer-radius performance remains unresolved. It is also unresolved whether the
remaining failures primarily reflect target distribution, hold behavior, or
another learning-method limitation.

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Experiment 1

**Result:** The baseline produced a useful policy, with
`checkpoint-100352` the strongest and most stable measured candidate, but the
independent research evidence remains below the 98% objective.

**Observed behavior:** `checkpoint-100352` achieved 189/200 (94.5%) on both
research panels (episodes 4200-4399 and 4400-4599), for 378/400 pooled
successes. `checkpoint-115712` achieved 188/200 on the second panel;
`checkpoint-120832` achieved 188/200 and 187/200 on the two panels; and
`checkpoint-86016` achieved 187/200. The fixed task-reference panel gave
`checkpoint-100352` 196/200 (98%), versus 194/200 for `checkpoint-120832` and
188/200 for `checkpoint-86016`. Pairwise comparisons on shared research
episodes favored `checkpoint-100352` over `checkpoint-120832` by 3-0
discordant outcomes pooled across both panels, but only three episodes were
discordant. The detailed evaluation for the selected checkpoint includes
episodes that timed out or interrupted the required 100-step hold.

**Hypothesis assessment:** Partially supported. The baseline successfully
established substantial task competence and a reproducible late-checkpoint
plateau, but the two disjoint research panels both measured 94.5%, not the
98% objective. The task-reference 98% result cannot independently confirm the
policy because that fixed panel was reused for selection, and development
measurements cannot declare the official objective reached.

**Interpretation:** `checkpoint-100352` is the evidence-backed working and
best-known lineage for the next experiment. The unchanged scientific recipe is
worth preserving because it produced the strongest available policy, while
additional training alone is not supported by the measured decline at
`checkpoint-120832`. No unmeasured checkpoint is treated as a failed policy,
and no unmeasured alternative is retained because it has no demonstrated
future advantage over the selected lineage.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-1-checkpoint-100352-200ep-seed4200-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-1-checkpoint-100352-200ep-seed4400-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/task-reference-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-1-checkpoint-100352-task-reference-v1.json`.
