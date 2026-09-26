# Research postmortems

## c65e9e59-7084-4415-87b6-9ff242544054 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline remains below the 98% objective
in pooled development evidence, and working remains the strongest available
policy and best-known lineage. The trajectory evidence still favors a
sampled-control stabilization bottleneck over a persistent reachability or
branch failure: unsuccessful baseline episodes reached the open branch with
reasonable conditioning but did not settle. Experiment 4 tested whether a
stateful policy-side action low-pass would address that bottleneck. On the
compatible 7000-7159 panel, working scored 158/160, the early low-pass
checkpoint also scored 158/160, and the final low-pass checkpoint scored
152/160. Thus the intervention produced no demonstrated complete-task gain and
was harmful after continued training, while target-conditioned command
generation remains a live upstream source of the instability.

**Lessons and limits:** The action-effort and full-radius interventions already
failed to improve their paired complete-task outcomes. Experiment 4 adds a
direct negative result for reducing policy command bandwidth: the early
checkpoint had zero discordant wins over working, and the final checkpoint had
six working wins and no candidate wins. The early candidate's two failures
matched working's failure seeds but recorded no tolerance entry, whereas
working briefly entered and then lost the hold; the final candidate added six
failures and also did not enter tolerance. This is consistent with smoothing
altering approach behavior rather than reliably fixing stabilization. The
7000-7159 panel was reused for deterministic pairing, so these results are not
independent population confirmation. The observed trajectory instrumentation
also does not isolate whether the learned command, the physical sampled
actuation, or credit assignment is primary. Development evidence remains below
the objective, so no official assessment is justified.

**Competing explanations:** Training-radius mismatch is weakened as a sufficient
cause because full-radius exposure did not change the persistent failure set.
Initial-singularity escape and fixed branch selection are weakened as primary
causes because failures and successes both escaped the initial posture and
reached the open branch with comparable conditioning. A sampled-control or
braking pathology remains physically plausible, but experiment 4 weakens the
narrow claim that policy-side temporal smoothing alone is the decisive lever:
the intervention did not improve the paired outcome and later reduced entry
coverage. Target-conditioned representation and reward credit assignment remain
live explanations for commands that are inappropriate in a target sector.
The evidence cannot distinguish those learned-command causes from plant-level
discrete-time effects.

**Decision frontier:** Resolve whether the persistent failures are driven
primarily by target-conditioned command generation and credit assignment or by
the plant's sampled actuation and braking dynamics. Discriminating evidence
would require matched complete-task and trajectory comparisons that separately
measure entry coverage, entry speed, post-entry exits, saturation and sustained
hold, while preserving the successful approach regime. Until that distinction is
resolved, working is a reference policy rather than a demonstrated solution.

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

## c65e9e59-7084-4415-87b6-9ff242544054 / Experiment 4

**Result:** The stateful action low-pass intervention did not improve complete
reach-and-hold success. On the compatible 160-episode panel, working and the
early checkpoint-35840 both achieved 158/160, with no discordant candidate wins.
The final checkpoint-120832 fell to 152/160, with six discordant episodes
favoring working. The intervention is therefore closed and the parent recipe is
restored.

**Observed behavior:** The early candidate and working shared the same two
failure seeds, 7030 and 7155, but the candidate failures recorded no tolerance
entry while working briefly entered and held for only one step before exiting.
The final candidate retained those two failures and added six more
no-entry failures. The candidate outcomes did not show the predicted reduction
in complete-task failures or a reliable conversion of unstable approaches into
sustained holds. All three measurements used the same 7000-7159 panel and
matching evaluator semantics; the panel was reused for paired comparison and
is not independent population evidence.

**Hypothesis assessment:** The hypothesis that reducing effective command
temporal authority would suppress saturated reversals, preserve approach
coverage and improve the complete hold is contradicted as a policy-selection
intervention on this panel. The early tie supplies no evidence of improvement,
and the final regression with six working wins shows that continued learning
under the intervention can degrade the coupled reach-and-hold behavior. The
result weakens, but does not eliminate, sampled-control stabilization as a
physical explanation: one policy-side smoothing coefficient cannot separate
learned command generation from the plant's sampled dynamics or establish
generalization beyond the reused panel.

**Interpretation:** The low-pass filter changed the learned policy's effective
approach dynamics without producing a measurable hold benefit, so retaining it
would discard attribution without evidence of progress. The failure pattern
keeps target-conditioned representation and reward credit assignment live as
upstream explanations for inappropriate commands, while the original
sampled-braking mechanism remains plausible at the plant level. Working is
retained as the best-known reference, but its sub-98% development evidence does
not justify an official benchmark.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-4-working-160ep-seed7000-6f1bf1ee9f02.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-4-checkpoint-35840-160ep-seed7000-6f1bf1ee9f02.json`;
`research/evaluations/c65e9e59-7084-4415-87b6-9ff242544054/evaluation-c65e9e59-7084-4415-87b6-9ff242544054-experiment-4-checkpoint-120832-160ep-seed7000-6f1bf1ee9f02.json`;
`robot_learning/scenario/policy_io.py`;
`robot_learning/scenario/evaluation.py`.
