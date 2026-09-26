# Research postmortems

## c65e9e59-7084-4415-87b6-9ff242544054 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline remains below the 98% objective
in pooled development evidence: the working lineage achieved 310/320 successes
(96.875%) across two distinct research panels, while the retained 120832-step
alternative achieved 309/320 (96.5625%). On the new disjoint panel, working
scored 159/160 and the alternative 158/160, with the only discordant episode
favoring working. The new evidence makes working the stronger transfer parent,
but the favorable 99.375% panel does not establish official readiness. The
alternative inverse-kinematic explanation is weakened: every episode that
entered tolerance in the new panel used the open branch, and no entrant was
classified as branch-ambiguous. The remaining failures are control-trajectory
failures rather than evidence that the target is unreachable.

**Lessons and limits:** The new instrumentation distinguishes two failure modes.
Both lineages failed on seed 5099 at radius 16.37 cm and angle -142.2 degrees;
the episode never entered tolerance, stayed on the open branch at termination,
and used saturated action on 499 of 500 control steps. The working lineage had
no other failure on the new panel. The retained alternative additionally failed
seed 5013 at radius 16.38 cm and angle 100.5 degrees: it entered at step 8,
held for at most 5 steps, interrupted the hold 244 times, and entered at
144.3 cm/s while using saturated action on all 500 steps. Successful entrants
also use open-branch motion and moderate Jacobian condition numbers, so the
current evidence does not isolate conditioning as the cause. The two-panel
aggregate remains below the objective and the old panel's nine shared failures
lack trajectory instrumentation, so the prevalence of the saturation pathology
and the extent of late-training regression remain uncertain.

**Competing explanations:** The leading explanation is an effort/sampled-control
pathology: the policy can remain at maximum effort instead of transitioning from
approach to braking, producing either a no-entry orbit or a high-speed,
interrupted hold. A second explanation is target-geometry dependence around the
16.4 cm radius, but one shared new-panel target is insufficient to establish a
region rather than a deterministic episode-specific failure. A third explanation
is late-training degradation of hold regulation, supported by the alternative's
additional seed-5013 failure but not by a statistically strong policy comparison.
Branch selection and severe entry conditioning are currently weaker explanations,
not eliminated ones, because the diagnostics summarize rather than replay full
trajectories.

**Decision frontier:** Determine whether reducing the reward incentive for
sustained high effort converts the shared no-entry and high-speed hold failures
into controlled reach-and-hold behavior without degrading the broad success
distribution. The discriminating evidence is a transfer policy's paired task
success against working plus trajectory diagnostics: fewer near-horizon
saturation episodes, lower entry speed for hold-loss cases, and preserved
open-branch reach should support the effort-regulation explanation; unchanged
failures or new no-entry cases would redirect the inquiry toward target-specific
geometry or representation rather than further action-cost tuning.

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
