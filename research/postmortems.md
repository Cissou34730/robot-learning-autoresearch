# Research postmortems

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Scientific strategy

**Current synthesis:** The campaign objective remains at least 98% success on the
official 6-20 cm reach-and-hold distribution. The fresh PPO baseline learned
substantial task behavior, with checkpoint-100352 the strongest measured policy at
150/160 and 151/160 successes on two disjoint panels (301/320 pooled, 94.06%).
Experiment 2's full-radius training-support change did not improve the transferred
policy: checkpoint-30720 reached 154/160 and 150/160 on two new disjoint panels,
while the parent reached 155/160 and 150/160. Detailed episode diagnostics show
that the baseline's 19 failures and nearly all subsequent parent/challenger
failures are concentrated in target angles from -180 to -90 degrees. The measured
task outcome, rather than training proxy success, identifies the useful policy
point.

**Lessons and limits:** All 19 recorded baseline failures occurred in the
target-angle bin from -180 to -90 degrees; 11/19 were also below 14 cm, a region
absent from the baseline training radius range. Expanding the radius range in one
transferred run did not remove the parent's residual pattern: on the first new
panel the challenger added one failure, and on the second it exchanged two
failure identities with the parent while retaining the same success rate. The
training proxy was non-monotonic (0.99 success and -2.70 reward at 30,720 steps,
degradation near 90,112-100,352, then 0.96 and -6.11 at 115,712), but the later
recovery measured only 61.25% on its panel. These observations weaken the tested
radius-support explanation without establishing that it is impossible or
separating it from angular control asymmetry or late-training degradation. The
research panels provide independent development coverage, not an official
verdict. Their detailed artifacts do expose target geometry, but the panels are
not large enough to establish the official result or isolate representation and
control causes.

**Open questions:** It remains unresolved whether increased training exposure to
the negative-angle sector can improve the residual failures without sacrificing
the rest of the official angular range, whether the concentration instead
reflects a representation or control issue, and why both recipes can regress
after their strongest proxy period. The transfer value of the learned
outer-radius representation and the variance of changed recipes are also
unknown.

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 1

**Result:** The baseline produced a useful learned policy but did not yet
demonstrate the human objective. Checkpoint-100352 is selected as the working
and best-known policy for the next experiment.

**Observed behavior:** Training-time success increased from 0.00 at early
checkpoints to 0.86 at checkpoint-95232 and 0.91 at checkpoint-100352, while
training reward improved from -440.877 at 5120 steps to -4.767 at 100352
steps. The best recorded training reward was -4.658 at checkpoint-105472, then
the proxies fluctuated: training success was 0.90 at 110592, 0.89 at 115712,
and 0.91 at 120832. On research episodes, checkpoint-100352 achieved 150/160
(93.75%) on seeds 4200-4359 and 151/160 (94.375%) on disjoint seeds
4360-4519. Checkpoint-105472 achieved 148/160 and 149/160; checkpoint-110592
achieved 146/160; and checkpoint-120832 achieved 134/160 (83.75%) on the first
panel. Paired comparisons favored checkpoint-100352 over checkpoint-105472 by
4-0 discordant outcomes across 320 shared episodes, and over checkpoint-110592
by 5-0 on the second panel. Every recorded failure used all 500 control steps
and was truncated rather than successfully completing the hold.

**Hypothesis assessment:** The automatic baseline hypothesis was to establish
an initial baseline, so it supplied no type-specific confirmatory or diagnostic
prediction to test. It is supported as a baseline characterization and
partially supports progress toward the objective: the learned policy reaches
approximately 94% on two disjoint development panels. The evidence weakens any
assumption that the final checkpoint or training proxies identify the best
policy. It does not establish the 98% objective or explain why later training
regressed.

**Interpretation:** Checkpoint-100352 is the best available measured artifact
and its result is reproducible across the two independent research panels, so
it is the appropriate lineage for continued development. The evidence is
strong enough to close this baseline without another measurement round, but
not to request the terminal benchmark. Selecting this policy does not imply
that the baseline recipe caused the observed peak or that its development
success will equal the official result.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-1/inventory.json`;
and the six artifacts under
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/` for checkpoints
100352, 105472, 110592, and 120832 on seeds 4200 and 4360.

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 2

**Result:** Expanding the training target-radius support to the official 6-20 cm
range produced a useful but not improved policy checkpoint, so the experiment's
scientific recipe is reverted to the parent and the existing baseline remains
working and best-known. The campaign objective is not demonstrated.

**Observed behavior:** The training trace improved from 0.75 success and -8.94
reward at 1,024 steps to a proxy peak of 0.99 and -2.70 at 30,720 steps. The
proxy then degraded through 0.83 success and -9.55 reward at 90,112 steps before
recovering to 0.96 and -6.11 at 115,712; it ended at 0.92 and -7.47 at 120,832.
On research panel 4520, checkpoint-30720 achieved 154/160 (96.25%) versus the
parent's 155/160 (96.875%); the challenger had the parent's five failed episode
identities plus episode 4527. On disjoint panel 4680, both achieved 150/160
(93.75%); eight failed episode identities were shared, while each policy had two
panel-specific failures. The paired comparisons therefore favored the parent by
one discordant episode on panel 4520 and by one net episode across both panels.
The later proxy-recovery checkpoint-115712 achieved only 61.25% (98/160), with
62 failures, so proxy recovery did not indicate useful saved-policy behavior.
The measured failures in these artifacts were truncated at 500 steps. The
research-evaluation records contain success, reward and step outcomes but no
target geometry, so this round does not directly establish whether inner-radius
or negative-angle rates changed.

**Hypothesis assessment:** The radius-support proposition is weakened under the
tested transferred recipe. The early proxy peak produced near-parent measured
performance on two disjoint panels, but did not improve pooled success or
systematically remove residual failures, and the later proxy recovery was
strongly contradicted by its poor measurement. This is evidence against the
usefulness of this intervention and training trajectory for the present
decision, not a causal disproof of every possible radius curriculum or a claim
that the parent would meet the official 98% criterion.

**Interpretation:** The parent is the safer working policy because it matches or
slightly exceeds the changed recipe on comparable independent development panels
and remains the strongest measured lineage. The early checkpoint is not retained:
its measured behavior is comparable rather than superior, while its recipe did
not resolve the residual problem. The large gap between training proxies and
saved-policy measurements reinforces that checkpoint selection must use measured
task success; neither development evidence nor the training log is an official
verdict.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-2/inventory.json`;
`research/training_logs/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-2-attempt-1.log`;
and the five experiment-2 artifacts under
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/` for checkpoint-30720,
checkpoint-115712 and `working` on seeds 4520 and 4680.
