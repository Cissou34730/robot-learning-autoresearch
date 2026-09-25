# Research postmortems

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Scientific strategy

**Current synthesis:** The PPO reach-and-hold policy is competent but remains
below the objective. The full-radius transfer produced 190/200 (95.0%) for
the pre-peak, proxy-peak, and final measured checkpoints on the disjoint
4600–4799 research panel, while the prior `best_known` scored 191/200
(95.5%) on the same panel. The selected baseline's 98% task-reference result
is development evidence only because that panel was reused for selection.

**Lessons and limits:** Direct task success, not training reward, determined
the lineage choices. Exposing training to the full official radial range did
not produce a material improvement over the prior policy: each of the three
measured experiment-2 checkpoints lost the only discordant paired episode to
the same-panel control. This weakens radius coverage as a sufficient
explanation for the residual failures, but one 200-episode panel cannot
exclude small effects or establish causal attribution. All development
measurements remain insufficient to declare the official objective reached.

**Open questions:** Whether the remaining failures primarily reflect hold
behavior, observations, or another learning-method limitation remains
unresolved. The experiment-2 working policy has only one disjoint research
panel, and no development measurement can replace the official final
assessment.

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

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Experiment 2

**Result:** Full-radius target training produced a useful but still
sub-threshold policy; `checkpoint-105472` is selected as the experiment-2
working lineage, while the prior `checkpoint-100352` remains best known.

**Observed behavior:** The pre-peak `checkpoint-95232`, proxy-peak
`checkpoint-105472`, and final `checkpoint-120832` each achieved 190/200
(95.0%) on the disjoint research panel covering episodes 4600–4799. The
same-panel `best_known` control achieved 191/200 (95.5%); each paired
comparison had zero challenger wins and one control win. These results remain
below the official threshold of 196/200. The experiment changed training
radius sampling from 0.14–0.20 m to 0.06–0.20 m without changing official task
mechanics or PPO hyperparameters.

**Hypothesis assessment:** Weakened. The prediction that full-radius transfer
would materially raise direct success above the established baseline was not
supported: all three measured checkpoints tied at 95.0% and were slightly
below the same-panel control. The result does not prove that radius coverage
has no effect because the comparison has one 200-episode panel and no
component-level control, but it weakens radius coverage as the primary
explanation for the remaining failures.

**Interpretation:** `checkpoint-105472` is a measured, reusable working policy
for the current full-radius recipe, but it is not a better-supported
best-known policy than `checkpoint-100352`. The new disjoint panel confirms
that the intervention did not reach the human objective; the fixed
task-reference panel is not independent confirmation, and no terminal
assessment is requested by this closure.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/8f4d116e-7b66-4ca1-ab31-5915330bf310/experiment-2/inventory.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-2-checkpoint-95232-200ep-seed4600-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-2-checkpoint-105472-200ep-seed4600-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-2-checkpoint-120832-200ep-seed4600-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-2-best_known-200ep-seed4600-f48545f83637.json`.
