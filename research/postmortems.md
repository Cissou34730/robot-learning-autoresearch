# Research postmortems

## ee116313-a145-46aa-9c85-e6e591e18f5a / Scientific strategy

**Current synthesis:** The baseline learned substantial reach-and-hold behavior,
but its best measured lineage, `checkpoint-100352`, reached 95.0% on a disjoint
research panel. Its 98.0% fixed task-reference result is promising development
evidence, not an official result. The remaining observed fixed-panel failures
were concentrated at inner targets, while the baseline training distribution
covered only 14-20 cm.

**Lessons and limits:** The late proxy peak was more reliable than the final
checkpoint: disjoint results were 94.5% for `checkpoint-95232`, 95.0% for
`checkpoint-100352`, and 93.5% for `checkpoint-120832`. The measured task-
reference failures for `checkpoint-100352` were four targets from 6.73-9.91 cm,
each ending after the 500-step limit. These observations are limited to the
baseline recipe and completed development panels; they do not establish that
full-radius training will improve behavior or that the objective is met.

**Open questions:** It remains unresolved whether exposing the full official
6-20 cm radius range during training improves the inner-target failures without
reducing performance on the outer range, and whether the resulting policy can
reach the human objective on held-out official assessment.

## ee116313-a145-46aa-9c85-e6e591e18f5a / Experiment 1

**Result:** The baseline produced a useful but sub-objective policy. The
`checkpoint-100352` candidate is selected as working and best-known; the
distinct `checkpoint-95232` candidate is retained as a future fallback. No
terminal assessment is requested.

**Observed behavior:** Training progressed from zero training success in early
checkpoints to 0.93 at step 95,232, 0.97 at step 100,352, and 0.95 at the
final 120,832-step checkpoint. On the disjoint research panel, the candidates
achieved 189/200 (94.5%), 190/200 (95.0%), and 187/200 (93.5%) respectively.
On the fixed task-reference panel they achieved 192/200 (96.0%), 196/200
(98.0%), and 194/200 (97.0%). The task-reference panel is reused development
evidence, not independent confirmation. No researcher-owned source changed in
this experiment.

**Hypothesis assessment:** The baseline hypothesis, “Establish the initial
baseline for the human-defined objective,” is supported as a characterization
of learnability and late-checkpoint behavior, but only partially supported as
progress toward the objective: the policy learned the task substantially yet
the disjoint measurements remained about three percentage points below 98%.
The evidence does not support claiming that the human objective has been met.

**Interpretation:** `checkpoint-100352` is the best-supported working choice
among the measured candidates because it is highest on the independent
disjoint panel and did not show the late-training degradation of
`checkpoint-120832`. The fixed-panel 98.0% result strengthens its practical
priority but cannot serve as independent confirmation. Closure preserves the
best measured artifact while leaving further training as an ordinary next
experiment.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`;
`research/checkpoints/challengers/ee116313-a145-46aa-9c85-e6e591e18f5a/experiment-1/inventory.json`;
the six research-evaluation artifacts and three task-reference artifacts under
`research/evaluations/ee116313-a145-46aa-9c85-e6e591e18f5a/`.
