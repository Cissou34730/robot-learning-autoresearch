# Research postmortems

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned substantial reach-and-hold
behavior, but the standing checkpoint-100352 lineage remains below the objective
at 152/160 on the latest disjoint panel and 609/640 pooled across four panels.
Target-distribution changes and both tested hold-exit forfeiture doses failed to
improve it, leaving the unchanged lineage as working and best-known.

**Lessons and limits:** Training proxies did not predict task success: the
proxy-high challengers ranged from tied to substantially worse than the control.
Residual failures include both no-reach episodes and interrupted holds, but the
development panels do not establish their full-distribution frequency. No
official 200-episode result exists.

**Open questions:** The evidence does not resolve whether direct target-geometry
features, another reward formulation, or a different mechanism can close the
remaining gap without sacrificing broad reach behavior.

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Experiment 1

**Result:** The fresh PPO baseline produced a useful learned policy, but did not
meet the human objective in development measurement.

**Observed behavior:** Training success was 0.93 at checkpoint-95232, 0.97 at
checkpoint-100352, and 0.95 at checkpoint-120832. Each checkpoint achieved
151/160 successes (94.375%) on research-evaluation episodes 4200-4359.
Both paired comparisons had zero discordant wins, so the measurements showed no
detectable late-training regression or improvement. The measurements were
development evidence and not the official final assessment.

**Hypothesis assessment:** The baseline hypothesis was partially supported:
training established substantial task behavior and a clear late-learning
transition, but the resulting policy remained below the required 98% success
rate. The equal shared-panel measurements do not establish that the
100352-step checkpoint is intrinsically better than the other measured
checkpoints.

**Interpretation:** The baseline recipe is a viable starting point but appears
to plateau below the objective under the tested conditions. Checkpoint-100352
is selected as working and best-known because it combines the tied measured
performance with the strongest training success proxy; this choice is
pragmatic rather than independently confirmed. Further training or a changed
recipe should be treated as a subsequent experiment after this closure.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/5521c88b-2345-470f-a9dd-547cf3b569b7/experiment-1/inventory.json`;
`research/results.jsonl`;
`research/research_state.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-1-checkpoint-95232-160ep-seed4200-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-1-checkpoint-100352-160ep-seed4200-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json`.

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Experiment 2

**Result:** The changed training target distribution did not improve the learned
policy. On a disjoint 160-episode panel, the standing parent and the
45,056-step challenger each achieved 151/160 successes (94.375%), while the
120,832-step final challenger achieved 149/160 (93.125%). All remain below the
98% objective.

**Observed behavior:** The parent and intermediate challenger had no discordant
paired wins. The final challenger lost two discordant episodes to the parent
and had no wins. Its failures included no-reach cases in the targeted
negative-angle sector and interrupted holds elsewhere, despite the changed
recipe's 0.91 final training success proxy. Training proxies therefore did not
predict a task-measured improvement.

**Hypothesis assessment:** The hypothesis was contradicted under the tested
conditions: the expected disjoint-panel improvement to at least 157/160 was
not observed, and the final challenger was five percentage points below that
target and 1.25 points below the parent. This does not rule out every
distribution intervention because the evidence is one transferred run and one
160-episode panel, but it weakens this specific target-distribution route.

**Interpretation:** The standing `working` and `best_known` lineage remains the
most useful saved policy at 151/160 on the disjoint panel. The experiment's
training-only distribution change should be reverted rather than carried into
the next experiment; the residual gap warrants a different scientific
intervention after closure. No experiment-2 challenger has evidence of future
reuse beyond the existing lineage.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`; `research/results.jsonl`;
`research/checkpoints/challengers/5521c88b-2345-470f-a9dd-547cf3b569b7/experiment-2/inventory.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-2-checkpoint-120832-160ep-seed4360-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-2-checkpoint-45056-160ep-seed4360-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-2-working-160ep-seed4360-f48545f83637.json`.

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Experiment 3

**Result:** Increasing `HOLD_EXIT_FORFEIT_FRACTION` from `0.0` to `1.0` did
not improve the learned policy. On the disjoint 160-episode panel, the standing
`working` lineage achieved 155/160 successes (96.875%), while the
105472-step and 120832-step challengers achieved 143/160 (89.375%) and
135/160 (84.375%). Every result remains below the 98% objective.

**Observed behavior:** The unchanged working lineage was independently measured
on the panel used for this experiment and remained below the required 157/160
development threshold. Both changed-reward challengers lost decisively in paired
comparisons, with failures including no-reach behavior and interrupted holds.
The reward intervention therefore did not convert the residual task failures
into uninterrupted successes.

**Hypothesis assessment:** The hypothesis was contradicted under the tested
conditions: stronger forfeiture for leaving an accumulated hold did not produce
the expected improvement and substantially degraded both measured challengers.
This is evidence against this specific intervention and run, not proof that
every reward formulation or representation change is ineffective.

**Interpretation:** The standing `working` and `best_known` lineage remains the
most useful available policy, but it does not satisfy the human objective on
independent development evidence. The experiment-3 recipe should be reverted,
and neither challenger has evidence that justifies retention. The official
200-episode assessment remains unrequested because the available evidence does
not justify treating the objective as reached.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`; `research/results.jsonl`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-3-working-160ep-seed4520-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-3-checkpoint-105472-160ep-seed4520-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-3-checkpoint-120832-160ep-seed4520-f48545f83637.json`.

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Experiment 4

**Result:** Changing `HOLD_EXIT_FORFEIT_FRACTION` from `0.0` to `0.1` did
not improve the learned policy. On the disjoint 160-episode panel, the
standing `working` lineage achieved 152/160 successes (95.0%), while the
86,016-step and 120,832-step challengers achieved 131/160 (81.875%) and
130/160 (81.25%). All results remain below the 98% objective.

**Observed behavior:** The control was independently measured on episodes
4680-4839 and remained ahead of both challengers. Paired comparisons gave the
control 21 discordant wins against the 86,016-step challenger and 22 against
the 120,832-step challenger, with no challenger wins. The proxy-high
86,016-step checkpoint therefore did not translate its 0.99 training success
into task success, and continued training to the final checkpoint did not
recover performance.

**Hypothesis assessment:** The hypothesis was contradicted under the tested
conditions: mild hold-exit forfeiture did not produce the expected improvement
on a disjoint panel and substantially degraded both measured challengers.
This conclusion is specific to this reward dose and transferred run; it does
not establish that every persistence reward or other intervention is
ineffective.

**Interpretation:** The standing `working` and `best_known` lineage remains
the strongest available policy, but its 152/160 result is development evidence
below the human objective and does not justify terminal assessment. The
experiment-4 recipe should be reverted, and neither challenger has evidence
that justifies retention. Further training, if pursued, is a subsequent
experiment after closure.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`; `research/results.jsonl`;
`research/checkpoints/challengers/5521c88b-2345-470f-a9dd-547cf3b569b7/experiment-4/inventory.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-4-working-160ep-seed4680-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-4-checkpoint-86016-160ep-seed4680-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-4-checkpoint-120832-160ep-seed4680-f48545f83637.json`.
