# Research postmortems

## f332c079-6021-457e-be60-1f0804528d76 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned a useful reach-and-hold
policy, with the working lineage reaching 197/200 (98.5%) on the latest
disjoint panel and 766/800 (95.8%) across four distinct research panels. The
latest panel exceeds the 196/200 development threshold, but development
measurements do not establish the official result. The tested reward and
angular target-distribution interventions did not improve overall success.

**Lessons and limits:** Experiment 1 identified checkpoint-100352 as the
best-supported development lineage at 94.5% on two disjoint panels, while the
late proxy peak tied it and the final checkpoint declined. Experiment 2's
full hold-progress forfeiture was contradicted in the tested transfer run:
checkpoint-105472 reached 175/200 (87.5%) and checkpoint-120832 reached
162/200 (81.0%) on the same new panel where the unchanged working policy
reached 191/200. Paired comparisons favored the working policy by 16 and 29
discordant episodes respectively. These are development measurements under
`research_evaluation`, not an official result or a causal explanation of every
failure mode; the negative result is scoped to this intervention, continuation,
and measured checkpoints. Experiment 3's angular reweighting was also
contradicted: both measured checkpoints were far below the unchanged policy on
the same disjoint panel, despite one having the highest training-reward proxy.
The independent 197/200 result supports terminal assessment of the unchanged
working lineage, not a claim that the official objective has already been met.

**Open questions:** The fixed task-reference panel and official benchmark have
not been run. If the official result is insufficient, any further training or
intervention should be prepared as a new experiment rather than inferred from
this closure.

## f332c079-6021-457e-be60-1f0804528d76 / Experiment 1

**Result:** The fresh baseline produced a strong but sub-target policy. The
best-supported checkpoint was checkpoint-100352 at 94.5% on both disjoint
research panels; checkpoint-110592 tied it on the second panel, while the final
checkpoint declined to 93.75% pooled.

**Observed behavior:** Checkpoint-100352 succeeded on 189/200 episodes for
seeds 4200 and 4400, for 378/400 distinct executions. Checkpoint-110592
succeeded on 189/200 episodes on seed 4400. Checkpoint-120832 succeeded on
188/200 and 187/200 on seeds 4200 and 4400. On the shared seed-4400 panel,
checkpoint-100352 and checkpoint-110592 had equal outcomes; checkpoint-100352
had a small advantage over checkpoint-120832 in pooled paired comparisons.
The training proxy rose through the late run but did not track a policy meeting
the 98% objective.

**Hypothesis assessment:** Partially supported. The baseline established
substantial learned task performance and a defensible late-run checkpoint, but
the measured policies remained below the objective of at least 196 successes
in 200 official episodes. The disjoint panel supports checkpoint-100352 as a
reliable development leader, not as independent proof of official success.

**Interpretation:** Checkpoint-100352 is the appropriate working and
best-known lineage because it has the strongest independent coverage and ties
the only tested reward-peak alternative. The unchanged scientific recipe
should be kept for provenance, checkpoint-110592 should remain available as a
late-run alternative, and further training or intervention should be treated
as a new experiment rather than inferred from this closure.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`; `research/results.jsonl`;
`research/checkpoints/challengers/f332c079-6021-457e-be60-1f0804528d76/experiment-1/inventory.json`;
the six evaluation artifacts under
`research/evaluations/f332c079-6021-457e-be60-1f0804528d76/`.

## f332c079-6021-457e-be60-1f0804528d76 / Experiment 2

**Result:** The transferred reward intervention did not improve the learned
reach-and-hold policy. The established working lineage remains the strongest
available policy, and the intervention recipe should be reverted.

**Observed behavior:** On the new disjoint research panel (episodes 4600-4799),
the unchanged `working` policy succeeded on 191/200 episodes (95.5%).
Experiment-2 checkpoint-105472 succeeded on 175/200 (87.5%), while the final
checkpoint-120832 succeeded on 162/200 (81.0%). Paired comparisons recorded
16 working-policy wins over checkpoint-105472 and 29 over checkpoint-120832,
with no wins in the reverse direction. Neither measured experiment-2
checkpoint approached the 196/200 success level corresponding to the human
objective.

**Hypothesis assessment:** Contradicted under the tested transfer run and
measured checkpoints. Full forfeiture of accumulated hold-progress was expected
to improve uninterrupted success without harming reach behavior, but both
measured intervention checkpoints were substantially worse than the unchanged
working policy on the same disjoint panel. This does not establish that every
hold-related shaping method fails, nor does it isolate which failure mode caused
the degradation.

**Interpretation:** The intervention is not useful for the current lineage
decision, so the parent working policy and its original scientific recipe
should be restored. The existing best-known designation remains supported as a
development choice, but it is not independently confirmed for the official
task and remains below the objective.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`; `research/results.jsonl`;
`research/checkpoints/challengers/f332c079-6021-457e-be60-1f0804528d76/experiment-2/inventory.json`;
`research/evaluations/f332c079-6021-457e-be60-1f0804528d76/evaluation-f332c079-6021-457e-be60-1f0804528d76-experiment-2-working-200ep-seed4600-f48545f83637.json`;
`research/evaluations/f332c079-6021-457e-be60-1f0804528d76/evaluation-f332c079-6021-457e-be60-1f0804528d76-experiment-2-checkpoint-105472-200ep-seed4600-f48545f83637.json`;
`research/evaluations/f332c079-6021-457e-be60-1f0804528d76/evaluation-f332c079-6021-457e-be60-1f0804528d76-experiment-2-checkpoint-120832-200ep-seed4600-f48545f83637.json`.

## f332c079-6021-457e-be60-1f0804528d76 / Experiment 3

**Result:** The angular target-reweighting intervention did not improve the
learned reach-and-hold policy. The unchanged `working` lineage remains the
strongest policy, and the experiment recipe should be reverted.

**Observed behavior:** On the new disjoint research panel (episodes 4800-4999),
the unchanged `working` policy succeeded on 197/200 episodes (98.5%).
Experiment-3 checkpoint-115712, selected at the run's highest training-reward
proxy, succeeded on 123/200 (61.5%), while the final checkpoint-120832
succeeded on 129/200 (64.5%). Paired comparisons recorded 74 working-policy
wins over checkpoint-115712 and 68 over checkpoint-120832, with no wins in the
reverse direction. The independent working result is above the 196/200
development threshold, while the four-panel aggregate is 766/800 (95.8%).

**Hypothesis assessment:** Contradicted under the tested transfer run and
measured checkpoints. Oversampling the -180 to -120 degree sector during
training was expected to improve uniform-distribution success without harming
other sectors, but both measured intervention checkpoints were substantially
worse than the unchanged working policy on the same disjoint panel. This does
not establish that every target-distribution intervention fails, nor does it
explain which training dynamics caused the degradation.

**Interpretation:** Select `working` as the working lineage, restore its
complete parent recipe, and retain no experiment-3 candidate because neither
measured challenger is useful for future extension. The existing best-known
designation remains the unchanged working policy. The latest disjoint result
supports requesting the official benchmark with an expected `goal_reached`
verdict, while acknowledging that only the official benchmark can establish
the human objective.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`; `research/results.jsonl`;
`research/checkpoints/challengers/f332c079-6021-457e-be60-1f0804528d76/experiment-3/inventory.json`;
`research/evaluations/f332c079-6021-457e-be60-1f0804528d76/evaluation-f332c079-6021-457e-be60-1f0804528d76-experiment-3-working-200ep-seed4800-f48545f83637.json`;
`research/evaluations/f332c079-6021-457e-be60-1f0804528d76/evaluation-f332c079-6021-457e-be60-1f0804528d76-experiment-3-checkpoint-115712-200ep-seed4800-f48545f83637.json`;
`research/evaluations/f332c079-6021-457e-be60-1f0804528d76/evaluation-f332c079-6021-457e-be60-1f0804528d76-experiment-3-checkpoint-120832-200ep-seed4800-f48545f83637.json`.
