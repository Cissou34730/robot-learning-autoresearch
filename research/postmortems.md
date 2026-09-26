# Research postmortems

## c65e9e59-7084-4415-87b6-9ff242544054 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline remains below the 98% objective
in pooled development evidence: the working lineage achieved 465/480 successes
(96.875%) across three distinct research panels. The action-effort intervention
did not improve complete success, and experiment 3's full-radius intervention
also did not improve it: the training-success peak, final checkpoint, and
working lineage each scored 155/160 on the new panel, with zero discordant
episodes in either paired comparison. The working lineage is the strongest
available policy and is the best-known designation selected at closure. The
remaining failures are concentrated in a negative-angle sector, but span both
short and long radii and include both no-entry and hold-loss outcomes. Radius
coverage alone is therefore not a sufficient explanation for the persistent
failures. The evaluator has now been instrumented to retain post-control
trajectories for the next saved-lineage measurement.

**Lessons and limits:** The action-cost change did not remove the shared
16.37 cm, -142.2 degree no-entry trajectory, which used saturated action on 499
of 500 steps, and it caused broad late-training regression. Full-radius
training likewise did not remove the five shared experiment-3 failures:
three never entered tolerance and two entered for only 1-2 control steps before
losing the hold. The failures occurred at radii from 9.37 to 16.76 cm and
angles from -125.3 to -145.4 degrees, so they are not confined to the
previously unsupported short-radius interval. These are paired deterministic
observations on one new panel, not population estimates, and the evaluator
does not expose joint/action trajectories. The pooled development result
remains below the objective, so no official assessment is justified. The new
instrumentation changes what the next measurement can observe but supplies no
evidence until that measurement is executed.

**Competing explanations:** Training-distribution mismatch is weakened as a
sufficient cause because exposing the policy to 6-20 cm targets did not change
the paired failure set, although it could still interact with another defect.
A target-conditioned observation-to-action representation failure remains
plausible in the negative-angle or wraparound sector. Initial-singularity
escape and inverse-kinematic branch selection remain plausible because the
same target geometry can require different joint postures and transient
motions. Sampled-control and braking pathology remains plausible because two
failures entered tolerance but could not sustain it. The current evidence
cannot separate these explanations: the evaluator summarizes distance and
hold stages but does not replay actions, joint states, branch choice, or
Jacobian conditioning.

**Decision frontier:** Determine whether the persistent negative-angle failures
are caused primarily by target-conditioned representation, singularity escape
and branch selection, or sampled braking and hold dynamics. Discriminating
evidence must pair matched successes and failures while recording complete
joint-state and action trajectories, branch residuals or posture identity,
Jacobian conditioning, effort saturation, and tolerance-entry velocity. A
sector-specific reach failure with consistent posture or branch divergence
would support a kinematic or representation mechanism; entry followed by
high-velocity exits without such divergence would redirect toward sampled
stabilization. Until that evidence exists, the current policy is useful as a
reference but not a demonstrated solution. The next measurement must use the
new trajectory evidence on a fresh panel, comparing the selected working lineage
with the retained late-training alternative before any intervention is chosen.

## c65e9e59-7084-4415-87b6-9ff242544054 / Experiment 1

**Result:** The baseline produced a useful but incomplete policy. Checkpoint
100352 was selected as working and best known; checkpoint 120832 was retained
as a close alternative. The terminal benchmark was not requested because the
research-panel result is 94.375% and the 98.0% task-reference result is a
single development-panel observation.

**Observed behavior:** On the research panel, checkpoint 86016 scored
149/160 (93.125%), while checkpoints 100352 and 120832 each scored 151/160
(94.375%). The paired comparisons showed two wins for 100352 over 86016, two
wins for 120832 over 86016, and no discordant episodes between 100352 and
120832. On the task-reference panel, the corresponding results were 188/200
(94.0%), 196/200 (98.0%), and 194/200 (97.0%). The four failures of 100352
were all short-radius targets from 6.2 to 9.9 cm with angles from -116.4 to
-127.9 degrees. The final checkpoint added failures at approximately 10.0 cm
and 17.9 cm. In the research diagnostics, 100352 and 120832 shared the same
nine failed episode seeds, concentrated around negative target angles, so the
research measurement did not show a late-training improvement.

**Hypothesis assessment:** The baseline hypothesis was supported only in its
limited role of establishing a learned reference policy. The measurement
hypothesis that the training-time proxy peaks identify complete task behavior
was partially supported and materially limited: the reward peak at 86016 was
worse, and the training-success peak at 100352 was best on the fixed reference
panel, but it remained below the research-panel objective and the final
checkpoint tied it on that panel. The evidence supports selecting 100352 over
the measured alternatives, not claiming that the causal weakness or the
official objective has been resolved.

**Interpretation:** Learning progressed from no task success to a high-success
but sector-dependent controller. The fixed-panel regression after 100352 and
the unchanged research failure set make 100352 the safer working lineage, while
120832 remains scientifically useful for testing whether continued learning
changes the same failure mechanism. Keeping the unchanged scientific recipe
preserves attribution: this closure selects among baseline checkpoints and
does not establish that the PPO, reward, observation, or control design is the
cause of the remaining failures.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/c65e9e59-7084-4415-87b6-9ff242544054/experiment-1/inventory.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-1-checkpoint-86016-160ep-seed4200-48e4acc98c39.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-1-checkpoint-100352-160ep-seed4200-48e4acc98c39.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-1-checkpoint-120832-160ep-seed4200-48e4acc98c39.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/task-reference-c65e9e59-7084-4415-87b6-9ff242544054-experiment-1-checkpoint-86016-task-reference-v1.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/task-reference-c65e9e59-7084-4415-87b6-9ff242544054-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/task-reference-c65e9e59-7084-4415-87b6-9ff242544054-experiment-1-checkpoint-120832-task-reference-v1.json`

## c65e9e59-7084-4415-87b6-9ff242544054 / Experiment 2

**Result:** The action-effort intervention did not improve the learned task.
Checkpoint-35840 reached 158/160 successes (98.75%), checkpoint-100352 reached
151/160 (94.375%), checkpoint-75776 reached 149/160 (93.125%), and
checkpoint-120832 reached 148/160 (92.5%). On the paired 5000-5159 panel,
working beat these candidates by 1, 8, 10, and 11 discordant episodes,
respectively.

**Observed behavior:** The measured parent-horizon candidate had nine
no-entry failures, including the shared 5099 target at radius 16.37 cm and
angle -142.2 degrees; working had one failure on that panel. The other
experiment-2 candidates likewise failed by not entering tolerance, with no
measured hold-loss improvement. The later failures included short-radius and
negative-angle targets, showing broader reach degradation rather than a
selective hold-stability improvement. The shared panel was reused for paired
comparison and does not provide independent population estimates.

**Hypothesis assessment:** The hypothesis is contradicted as a policy-selection
intervention and weakened as a causal explanation. Raising the action cost did
not remove the diagnostic saturation failure, did not produce measured
hold-regulation gains, and was followed by substantial late-training
regression. The parent-horizon result confirms that the candidate identity
ambiguity was not hiding a competitive intervention policy. The evidence does
not establish that action cost caused every failure.

**Interpretation:** The failures remain coupled reach-and-control failures, not
evidence of unreachable targets. The intervention is closed and the parent
recipe is restored to preserve attribution. Working/checkpoint-100352 remains
both working and best known at 310/320 pooled research-panel successes
(96.875%), below the 98% objective; no final benchmark is requested. Future
inquiry should discriminate target-conditioned representation and initial
singularity escape from sampled braking dynamics using paired trajectory
evidence, rather than increasing this action penalty again.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-2-working-160ep-seed5000-a6f00af22b57.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-2-checkpoint-35840-160ep-seed5000-a6f00af22b57.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-2-checkpoint-75776-160ep-seed5000-a6f00af22b57.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-2-checkpoint-120832-160ep-seed5000-a6f00af22b57.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-2-checkpoint-100352-160ep-seed5000-a6f00af22b57.json`;
`robot_learning/scenario/reward.py`;
`research/scenario.md`;
`research/scientific_model.md`.

## c65e9e59-7084-4415-87b6-9ff242544054 / Experiment 3

**Result:** Expanding the training target-radius range from 14-20 cm to the
full 6-20 cm interval did not improve complete-task behavior. The measured
training-success peak and final checkpoint each achieved 155/160 (96.875%) on
episodes 6000-6159, matching working. Both paired comparisons had zero
discordant wins. Closure restores the parent's recipe and selects working as
both working and best-known.

**Observed behavior:** The three measured policies shared the same five failing
episode seeds: 6057 (15.80 cm, -140.6 degrees), 6065 (10.35 cm, -129.9
degrees), 6072 (9.37 cm, -125.3 degrees), 6100 (16.76 cm, -145.4 degrees),
and 6155 (14.75 cm, -140.9 degrees). Seeds 6057, 6072, and 6100 never
entered tolerance. Seeds 6065 and 6155 entered tolerance briefly but reached
only 1 held step before interruption. The shared set spans both the previously
unsupported short-radius regime and the trained long-radius regime.

**Hypothesis assessment:** The hypothesis that full-radius exposure would
reduce short-radius and negative-angle no-entry failures while preserving broad
behavior is weakened and, as a policy-selection intervention on this panel,
contradicted. It produced no paired success gain, no failure-set change, and
no evidence of a selective short-radius benefit. The result does not prove
that target coverage is irrelevant outside this panel or that representation,
branch choice, or sampled dynamics is the sole cause; it shows that coverage
expansion alone did not resolve the observed mechanism.

**Interpretation:** The persistent sector-specific failure across all three
policies indicates that the causal bottleneck is not explained by radius
support alone. The mixture of no-entry and hold-loss outcomes is consistent
with a coupled approach and stabilization problem, but the summarized
diagnostics cannot identify whether target encoding, escape from the initial
singularity, inverse-kinematic branch selection, or sampled braking dominates.
Because the intervention supplied no complete-task improvement and the working
lineage has the strongest pooled evidence, retaining the changed recipe would
discard attribution without a demonstrated benefit. No official benchmark is
justified at 96.875% development success.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-3-working-160ep-seed6000-48e4acc98c39.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-3-checkpoint-105472-160ep-seed6000-48e4acc98c39.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-3-checkpoint-120832-160ep-seed6000-48e4acc98c39.json`;
`robot_learning/scenario/training_environment.py`.
