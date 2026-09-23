# Research postmortems

## ee116313-a145-46aa-9c85-e6e591e18f5a / Scientific strategy

**Current synthesis:** The baseline learned substantial reach-and-hold behavior,
but its best measured lineage, `checkpoint-100352`, remains below the objective:
it scored 95.0% on the earlier disjoint research panel and 94.5% on the new
seed-4560 panel. Full-radius training did not improve this position: both
measured experiment-2 challengers scored 94.0%.

**Lessons and limits:** The full 6-20 cm training intervention did not transfer
the proxy peak into higher task success; the proxy-peak and final challengers
both lost one episode to the contemporaneous control on their paired panel.
The existing baseline lineage is therefore the most useful saved policy and its
parent 14-20 cm recipe should be restored. These development measurements do
not establish that the 98% objective is met or predict the official result.

**Open questions:** The residual reach-and-hold failures remain unresolved,
including failures in the inner-radius regime and episodes that end at the
500-step limit. Further progress would require an ordinary later experiment
with a different intervention; the current evidence does not identify which
intervention will reach the human objective.

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

## ee116313-a145-46aa-9c85-e6e591e18f5a / Experiment 2

**Result:** Expanding training coverage from 14-20 cm to the full official
6-20 cm range did not improve the learned policy. The proxy-peak
`checkpoint-105472` and final `checkpoint-120832` each scored 188/200 (94.0%)
on the new research panel, below the contemporaneous best-known control at
189/200 (94.5%). Neither challenger is retained.

**Observed behavior:** The proxy peak reached 1.00 training success, but its
task measurement was 94.0%; the final challenger also measured 94.0% after
120,832 steps. Paired comparisons gave each challenger zero wins and one
control win over 200 shared episodes. Failures included lost or unmaintained
holds and episodes ending at the 500-step truncation limit.

**Hypothesis assessment:** The hypothesis that full-radius training would
reduce inner-target failures without sacrificing outer-target performance is
weakened for this recipe and these checkpoints. The intervention did not exceed
the baseline on the disjoint panel, and the measurements provide no evidence
that its apparent training-proxy advantage transfers to task success. This
does not establish whether another training or learning intervention can reach
the 98% objective.

**Interpretation:** The existing `checkpoint-100352` lineage remains the most
useful working and best-known policy. The full-radius code change should be
reverted, no experiment-2 challenger should survive closure, and the campaign
should remain open for a later ordinary experiment rather than request the
official benchmark.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/ee116313-a145-46aa-9c85-e6e591e18f5a/experiment-2/inventory.json`;
`research/evaluations/ee116313-a145-46aa-9c85-e6e591e18f5a/evaluation-ee116313-a145-46aa-9c85-e6e591e18f5a-experiment-2-best_known-200ep-seed4560-f48545f83637.json`;
`research/evaluations/ee116313-a145-46aa-9c85-e6e591e18f5a/evaluation-ee116313-a145-46aa-9c85-e6e591e18f5a-experiment-2-checkpoint-105472-200ep-seed4560-f48545f83637.json`;
`research/evaluations/ee116313-a145-46aa-9c85-e6e591e18f5a/evaluation-ee116313-a145-46aa-9c85-e6e591e18f5a-experiment-2-checkpoint-120832-200ep-seed4560-f48545f83637.json`;
`robot_learning/scenario/training_environment.py`.
