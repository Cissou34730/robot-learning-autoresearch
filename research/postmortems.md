# Research postmortems

## c65e9e59-7084-4415-87b6-9ff242544054 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline remains below the 98% objective
in pooled development evidence: the working lineage achieved 310/320 successes
(96.875%) across two distinct research panels. The action-effort intervention
did not improve complete success: its early checkpoint scored 158/160 against
working's 159/160, its parent-horizon candidate scored 151/160, and later
checkpoints scored 149/160 and 148/160. The working lineage remains the
strongest transfer parent and best-known policy. The failure set is instead
strongly target-conditioned: the baseline trains only on 14-20 cm radii, while
the official distribution spans 6-20 cm, and experiment-2 no-entry failures
clustered at 7-12 cm with angles near +/-140 to 180 degrees. The next
intervention tests whether this coverage gap, rather than action-cost weighting,
causes the persistent reach failures.

**Lessons and limits:** The action-cost change did not remove the shared
16.37 cm, -142.2 degree no-entry trajectory, which used saturated action on 499
of 500 steps, and it caused broad late-training regression. This weakens effort
regularization as the primary lever but does not prove effort irrelevant. The
experiment-2 failures were all no-entry cases at the measured checkpoints,
including repeated short-radius targets: 7.16-10.98 cm failures near negative
or wraparound angles, with additional 12.11 cm failures near -142 to -157
degrees. This aligns with the training range excluding all radii below 14 cm,
but the panel is reused for the candidates and does not estimate population
frequencies. The pooled development result remains below the objective, so no
official assessment is justified.

**Competing explanations:** The leading explanation is training-distribution
mismatch: the policy must extrapolate from 14-20 cm training targets to the
6-14 cm portion of the official task, where inverse-kinematic posture and
initial-singularity escape differ materially. A second explanation is a
target-conditioned observation-to-action representation failure, especially in
negative-angle and wraparound sectors, which full-radius coverage may or may
not repair. A third explanation is transient effort/sampled-control pathology,
because the shared 16.37 cm failure is nearly fully saturated, but changing the
action penalty did not improve it. Branch selection and Jacobian conditioning
remain unresolved because the summarized diagnostics do not replay complete
trajectories.

**Decision frontier:** Test whether exposing the learner to the complete official
radius distribution improves short-radius and negative-angle reach while
preserving the established broad behavior. Paired success and trajectory
evidence against working should show fewer no-entry failures in the 6-14 cm
strata without a compensating loss at 14-20 cm; improvement would support
coverage mismatch, while unchanged sector failures would redirect the inquiry
toward target encoding, initial-singularity escape, or branch-conditioned
representation.

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
