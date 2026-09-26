# Research postmortems

## c65e9e59-7084-4415-87b6-9ff242544054 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline remains below the 98% objective
in pooled development evidence: the working lineage achieved 310/320 successes
(96.875%) across two distinct research panels. Increasing the action-effort
coefficient from 0.01 to 0.05 did not improve complete success: the early
experiment-2 checkpoint scored 158/160 against working's 159/160, the
parent-horizon candidate scored 151/160, and the later checkpoints scored
149/160 and 148/160. Continued training under the changed recipe therefore
produced a clear regression on the measured panel, and the working lineage
remains the strongest available transfer parent and best-known policy. The
action-cost result rejects this intervention as a useful explanation or
selection rule, but does not show that effort and sampled actuation are
irrelevant to the remaining failures.

**Lessons and limits:** All nine failures of the measured experiment-2
checkpoint-100352 candidate, like the failures of the other experiment-2
candidates, were no-entry failures; none supplied evidence of improved hold
regulation. The parent-horizon candidate lost all eight discordant episodes to
working on the paired panel. The shared seed 5099 failure remains a 16.37 cm,
-142.2 degree target with no tolerance entry and saturated action on 499 of 500
steps for working. Experiment-2 failures also include several short-radius and
negative-angle targets, but the reused 160-episode panel does not establish
population frequencies or prove that the changed coefficient caused each
failure. The pooled development result remains below the objective, so no
official assessment is justified.

**Competing explanations:** A real effort/sampled-control pathology remains
plausible because the shared no-entry trajectory is nearly fully saturated, but
the coefficient change neither removed it nor preserved broad success. Target
geometry or observation-to-action representation may govern the expanded
negative-angle and short-radius no-entry set. Late-training policy degradation
is supported by the 93.125%, 92.5%, and 94.375% candidate results, although the
experiment does not separate ordinary optimization drift from reward-shaping
effects. Branch selection and Jacobian conditioning remain weaker explanations:
measured entrants predominantly use the open branch, and the summarized
diagnostics do not provide enough replay detail to eliminate
configuration-dependent dynamics.

**Decision frontier:** Distinguish target-conditioned reach/control
representation failures from transient effort and braking failures. Evidence
that the same geometry strata improve with reduced saturation and preserved
entry/hold behavior would support a control explanation; persistent no-entry
failures despite controlled effort, especially across the negative-angle and
short-radius strata, would redirect the inquiry toward target encoding,
initial-singularity escape, or branch-conditioned reach representation. The
discrimination requires paired success and trajectory evidence rather than
another unmeasured training proxy.

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
