# Research postmortems

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned substantial reach-and-hold
behavior, and the standing checkpoint-100352 lineage achieved 157/160 (98.125%)
on the new panel 4840-4999, disjoint from the panels used to select it. The
experiment-5 target-geometry challengers achieved only 38/160 and 84/160, so the
unchanged lineage remains working and best-known and is ready for the official
assessment.

**Lessons and limits:** Training proxies did not predict task success: the
experiment-5 challenger with the highest observed reward was substantially worse
than the control, and the direct target-geometry representation contradicted its
hypothesis under the tested fresh run. The control's three failures on panel
4840-4999 were no-reach episodes with no interrupted holds. The 157/160 result is
independent of the lineage-selection panels but is still development evidence;
only the official 200-episode assessment can establish the objective.

**Open questions:** Whether the frozen working lineage reaches at least 196/200
on the official panel remains unresolved. If it does not, the remaining
full-distribution no-reach failures and a different mechanism remain open
investigations.

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

## 5521c88b-2345-470f-a9dd-547cf3b569b7 / Experiment 5

**Result:** Adding target radius and sine/cosine target-angle features did not
improve the learned policy. The standing working lineage achieved 157/160
(98.125%) on the disjoint panel 4840-4999, while the 100352-step and final
120832-step challengers achieved 38/160 (23.75%) and 84/160 (52.5%).

**Observed behavior:** The working lineage was measured on a panel disjoint from
all panels used to select it, so its 157/160 result is independent development
evidence rather than a reuse of its selection score. Its three failures were
no-reach episodes, with no interrupted holds. Both geometry challengers were
dominated by the working policy in paired comparisons: the working policy won
119 and 73 discordant episodes respectively, while each challenger had zero
wins. The final challenger also remained far below the earlier challenger
despite having the highest observed training reward.

**Hypothesis assessment:** The hypothesis was contradicted under the tested
conditions. The fresh 14-value observation did not reduce no-reach or
interrupted-hold failures and substantially degraded task success at both
measured checkpoints. This conclusion is specific to this representation and
fresh run; it does not establish that every observation or learning-method
change is ineffective.

**Interpretation:** The established working and best-known lineage is the only
useful policy from this experiment. The experiment-5 observation change should
be reverted, and neither challenger has evidence that justifies retention.
Because the standing lineage now meets the 157/160 development threshold on a
disjoint panel, but development evidence cannot establish the official
objective, submit it for the official 200-episode assessment with an expected
goal-reached verdict.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`; `research/results.jsonl`;
`research/checkpoints/challengers/5521c88b-2345-470f-a9dd-547cf3b569b7/experiment-5/inventory.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-5-working-160ep-seed4840-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-5-checkpoint-100352-160ep-seed4840-f48545f83637.json`;
`research/evaluations/5521c88b-2345-470f-a9dd-547cf3b569b7/evaluation-5521c88b-2345-470f-a9dd-547cf3b569b7-experiment-5-checkpoint-120832-160ep-seed4840-f48545f83637.json`.
