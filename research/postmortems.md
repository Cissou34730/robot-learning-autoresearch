# Research postmortems

## ee116313-a145-46aa-9c85-e6e591e18f5a / Scientific strategy

**Current synthesis:** The learned policy solves most reach-and-hold episodes,
but the standing `best_known` lineage remains below the 98% objective at
925/960 successes (96.4%) across five distinct research panels. Expanded target
coverage, hold-exit forfeiture, and a lower learning rate have not produced a
robust improvement; apparent early gains degraded or only matched the control.

**Lessons and limits:** Task success is not reliably predicted by training
reward or proxy success. Failures cluster around difficult inner-radius reaches,
interrupted holds, and 500-step truncation. The standing lineage has the
strongest broad evidence; retained alternatives have only one-panel evidence,
and development measurements cannot establish the official objective.

**Open questions:** It remains unresolved whether changing training exposure can
improve inner-radius reliability while preserving outer-target performance and
avoiding the late-checkpoint degradation seen in tested continuations.

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

## ee116313-a145-46aa-9c85-e6e591e18f5a / Experiment 3

**Result:** The hold-exit forfeiture intervention did not establish an
improvement. On the new disjoint panel, `checkpoint-35840` achieved 197/200
(98.5%), tying the contemporaneous best-known control; the later
`checkpoint-105472` achieved only 180/200 (90.0%). Keep the existing
best-known lineage as working, revert the intervention, and retain
`checkpoint-35840` as a reusable alternative.

**Observed behavior:** The measured panel covered episodes 4760-4959. The
early challenger had a perfect training proxy and matched the control's
197/200 task result, but its failures still included both a lost hold and
episodes that never reached tolerance. The late challenger had a higher
training proxy than the control but degraded substantially on the task panel.
The standing best-known lineage remains 727/760 (95.7%) across four distinct
research panels; the fixed task-reference panel is reused development
evidence, not independent confirmation.

**Hypothesis assessment:** The hypothesis that making hold interruptions
costly would improve complete-hold reliability without sacrificing reachability
is weakened. The intermediate checkpoint is compatible with a potentially
useful trajectory, but it tied rather than exceeded the control on the
independent panel, and the late checkpoint was materially worse. The single
new panel does not establish the human objective or a robust intervention
benefit.

**Interpretation:** `checkpoint-100352` remains the best-supported working and
best-known policy because its evidence spans more disjoint panels and is
consistent across the campaign. The experiment-3 recipe should not become the
standing science, while `checkpoint-35840` is worth preserving as a distinct
future parent because it matched the control at a useful intermediate point.
No final assessment is requested; further development remains an ordinary
post-closure decision.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/ee116313-a145-46aa-9c85-e6e591e18f5a/experiment-3/inventory.json`;
`research/evaluations/ee116313-a145-46aa-9c85-e6e591e18f5a/evaluation-ee116313-a145-46aa-9c85-e6e591e18f5a-experiment-3-best_known-200ep-seed4760-f48545f83637.json`;
`research/evaluations/ee116313-a145-46aa-9c85-e6e591e18f5a/evaluation-ee116313-a145-46aa-9c85-e6e591e18f5a-experiment-3-checkpoint-35840-200ep-seed4760-f48545f83637.json`;
`research/evaluations/ee116313-a145-46aa-9c85-e6e591e18f5a/evaluation-ee116313-a145-46aa-9c85-e6e591e18f5a-experiment-3-checkpoint-105472-200ep-seed4760-f48545f83637.json`;
`robot_learning/scenario/reward.py`.

## ee116313-a145-46aa-9c85-e6e591e18f5a / Experiment 4

**Result:** Lowering the PPO learning rate to 0.0001 did not improve the
standing lineage. The early `checkpoint-35840` scored 198/200 (99.0%) on the
new disjoint panel, exactly matching the contemporaneous `best_known` control,
while the final `checkpoint-120832` scored 189/200 (94.5%). Keep
`checkpoint-100352` as working and best-known, restore the parent recipe, and
retain the early low-rate checkpoint as an unproven fallback. No terminal
assessment is requested.

**Observed behavior:** The experiment-4 training proxy reached 1.00 success at
step 35,840 but was 0.97 at the final 120,832-step checkpoint. On the shared
episodes 4960-5159, `checkpoint-35840` and `best_known` had no discordant
outcomes and both achieved 198/200; the final checkpoint lost nine outcomes
relative to the control and achieved 189/200. The control's new-panel result
is independent of the panels used to establish the standing lineage, while
the fixed task-reference panel was not used for this conclusion.

**Hypothesis assessment:** The hypothesis that continuing with learning rate
0.0001 would preserve or improve task success while reducing late degradation
is weakened. The early checkpoint preserved the control's performance but did
not improve it, and the final checkpoint still degraded materially. This
single disjoint panel does not establish the 98% human objective or a durable
benefit from the lower learning rate.

**Interpretation:** The broad evidence still favors the existing
`checkpoint-100352` lineage: it has 925/960 successes (96.4%) over five
distinct research panels, whereas the experiment-4 challenger has only one
panel. The lower-rate early checkpoint is worth retaining because it matched
the control on a fresh panel and may support a future comparison, but its
selection-panel score is not independent evidence for treating it as a new
best-known lineage. The lower-rate continuation should not become the
standing recipe; further training remains an ordinary next experiment after
closure.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ee116313-a145-46aa-9c85-e6e591e18f5a/experiment-4/inventory.json`;
`research/evaluations/ee116313-a145-46aa-9c85-e6e591e18f5a/evaluation-ee116313-a145-46aa-9c85-e6e591e18f5a-experiment-4-best_known-200ep-seed4960-f48545f83637.json`;
`research/evaluations/ee116313-a145-46aa-9c85-e6e591e18f5a/evaluation-ee116313-a145-46aa-9c85-e6e591e18f5a-experiment-4-checkpoint-35840-200ep-seed4960-f48545f83637.json`;
`research/evaluations/ee116313-a145-46aa-9c85-e6e591e18f5a/evaluation-ee116313-a145-46aa-9c85-e6e591e18f5a-experiment-4-checkpoint-120832-200ep-seed4960-f48545f83637.json`.
