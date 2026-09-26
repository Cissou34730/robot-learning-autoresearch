# Research postmortems

## c65e9e59-7084-4415-87b6-9ff242544054 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned substantial reach-and-hold
behavior but has not established the 98% objective. Checkpoint 100352 is the
strongest measured lineage: it achieved 151/160 successes (94.375%) on the
research panel and 196/200 (98.0%) on the fixed task-reference panel. The final
checkpoint 120832 tied it on the research panel but achieved 194/200 (97.0%) on
the task-reference panel. The reward maximum at checkpoint 86016 was not the
behavioral maximum. The repeated research failures of 100352 and 120832 occur
on the same nine episode seeds, while the reference failures of 100352 all lie
at short target radii and negative target angles. This supports a persistent
target-geometry or configuration-dependent weakness, but does not identify its
mechanism.

**Lessons and limits:** Complete task success, rather than training reward or
training success, discriminated the late checkpoints. The paired research panel
found 100352 and 120832 identical on all 160 episodes; it found two wins for
100352 over 86016 and none in the reverse direction. On the fixed reference
panel, 100352 exceeded 86016 by four percentage points and exceeded 120832 by
one point. These are development measurements, not the official result, and
the research and reference panels each provide only one panel. The research
panel remains below the objective, and the exact 98% reference result is not
independent confirmation. The available measurements do not include joint
posture, Jacobian conditioning, action saturation, or branch identity, so they
cannot establish whether the failures arise from kinematics, sampled control,
stabilization, or policy configuration.

**Competing explanations:** The leading explanation is a target-sector
dependence involving the arm's alternative inverse-kinematic configurations and
the difficult approach from the straight initial posture; the concentration of
reference failures near 6-10 cm and approximately -116 to -128 degrees is
consistent with this, but is not proof. A second explanation is a controller
transient or hold-stability weakness that happens to appear in that sector,
including residual velocity or discrete-time overshoot. A third explanation is
panel composition: the fixed reference panel shows a stronger result than the
research panel, and one panel per instrument cannot separate a systematic
failure region from finite-sample variation. The current evidence cannot rank
these alternatives causally.

**Decision frontier:** Determine whether the persistent negative-angle and
short-radius failures are a reproducible configuration/conditioning problem or
panel-specific variation, and whether the small difference between 100352 and
120832 reflects real late-training regression. Discriminating evidence would
be disjoint-panel episode outcomes joined to target radius and angle with
trajectory-level joint posture, branch residual, Jacobian, velocity, and
action/hold measurements; it should distinguish failures that never enter the
tolerance disk from entries that lose the uninterrupted hold.

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
