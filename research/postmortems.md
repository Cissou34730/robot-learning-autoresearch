# Research postmortems

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Scientific strategy

**Current synthesis:** The learned parent has substantial reach-and-hold
competence but remains a near-objective policy rather than an established
98% solution. It achieved 2925/3000 across fifteen distinct research panels,
including 196/200 on the latest panel. Experiments 2--9 did not establish a
reliable improvement over the working lineage. Experiment 9 directly measured
the targeted-exposure recipe: checkpoint-90112 matched the parent at 196/200,
and the final checkpoint fell to 194/200.

**Lessons and limits:** On the fresh experiment-9 panel, checkpoint-90112
shared all four parent failures and produced no paired win. The final
checkpoint shared those four failures and added two more, including one target
outside the oversampled sector. All six final-checkpoint failures switched the
nearest inverse-kinematic branch and remained saturated for roughly 497--499
control steps, but branch switching occurred in about 55% of all episodes and
the telemetry therefore remains associative rather than causal. The targeted
distribution changed neither the recurring failure identities nor the
failure-stage pattern, and its training-success proxy did not predict a task
improvement. Together with the headroom, slew, and representation controls,
the evidence weakens saturation removal, fixed command slew, targeted exposure,
and simple observation augmentation as sufficient explanations. Experiment 9
does not rule out a configuration-dependent transition/conditioning
mechanism, nor does any development panel establish the official objective.

**Open questions:** Which configuration-dependent mechanism creates the
repeatable negative-angle failures despite unchanged task mechanics: a
branch-transition policy error, poor local conditioning, insufficient
stabilization, or an interaction among them. It remains unresolved whether
the parent lacks a suitable control representation for this transition or
whether the learned trajectory can be changed without sacrificing broad
reach-and-hold behavior.

**Active inquiry:** The provisional inquiry is whether the recurring failures
come from a policy-controlled branch/conditioning transition that can be
altered while preserving the parent's robust 11-value observation contract and
broad task behavior. Experiment 9 ends the narrower targeted-exposure test:
matching failure identities at the proxy-peak checkpoint and added failures at
the final checkpoint provide no support for exposure alone. The inquiry would
be redirected by paired evidence showing a repeatable rescue of the shared
target situations with no broad regression, and ended if subsequent
task-level comparisons continue to show unchanged failures or trade them for
new broad failures.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 1

**Result:** The baseline produced a reproducible near-objective policy but did not
demonstrate the 98% objective. Checkpoint-100352 is selected as the working and
best-known lineage; checkpoint-120832 is retained as a measured alternative.

**Observed behavior:** Checkpoint-100352 and checkpoint-120832 each achieved
195/200 (97.5%) on both disjoint research panels, for 390/400 pooled successes
per model. Their paired comparison had zero discordant wins across the 400
shared episode identities. The same five target situations in the second panel
formed a narrow sector near -131 to -155 degrees: two never entered tolerance,
and three reached it for only one or two steps. The protected task-reference
panel measured checkpoint-100352 at 196/200 and checkpoint-120832 at 194/200;
the former is exactly at the threshold on that development panel, but the
disjoint research results do not reproduce 98%.

**Hypothesis assessment:** The hypothesis that the proxy-peak checkpoint would
reproducibly meet the complete objective is weakened: it reproducibly exhibits
strong reach-and-hold behavior, but both independent research panels remain one
episode below the 98% threshold. The hypothesis that it is preferable to the
final checkpoint is inconclusive on paired outcomes, although checkpoint-100352
has the stronger protected-panel result and no evidence favors the final
checkpoint. These conclusions are limited to this deterministic task,
observation contract, and measured checkpoints.

**Interpretation:** The failure pattern is stable across checkpoints and research
panels, making it more consistent with a target-geometry or controller
interaction than with training-proxy noise. The measurements do not establish
whether branch selection, Jacobian conditioning, approach velocity, or local
stabilization is causal. Selecting checkpoint-100352 preserves the strongest
available development result without claiming that the official objective has
been reached; retaining checkpoint-120832 preserves a nearly identical late
policy for future comparison.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-100352-200ep-seed20000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-120832-200ep-seed20000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-100352-200ep-seed21000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-120832-200ep-seed21000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/task-reference-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/task-reference-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-120832-task-reference-v1.json`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 2

**Result:** Expanding training target radii from 0.14--0.20 m to the complete
0.06--0.20 m range did not improve the measured policy lineage. The parent
achieved 194/200 on the first disjoint panel and 197/200 on the telemetry panel;
both measured continuation checkpoints achieved 193/200 and 197/200,
respectively. The parent remains working and best-known. The radius-expanded
checkpoints are retained as measured alternatives, and the scientific recipe is
reverted to the parent recipe.

**Observed behavior:** The first disjoint panel preserved the negative-angle
failure sector, with both no-entry and interrupted-hold failures. On the
telemetry panel, all three policies failed on the same episodes (35, 67, and
150), all near -144 to -153 degrees. Every episode that entered tolerance was
closer to the elbow-open inverse-kinematic branch than the folded branch at
entry. Failure episodes had no consistent excess endpoint speed at entry, but
they remained actuator-saturated for about 499 of 500 control steps and showed
lower minimum planar Jacobian determinants than successful episodes in the same
panel.

**Hypothesis assessment:** The hypothesis that complete radius coverage would
reduce the recurring negative-angle failures is weakened. The continuation did
not improve the independent panel, pooled performance was 97.5% versus 97.6%
for the parent, and the common failure identities persisted. The evidence does
not establish that radius coverage has no benefit outside this failure sector.
The telemetry weakens branch-entry and entry-speed explanations as sole causes
and makes prolonged saturation in poorly conditioned trajectories a more useful
working explanation, but the association is not causal and does not identify a
single sufficient mechanism.

**Interpretation:** The intervention answered the radius question without
solving the task. The stable target identities across policies indicate a
shared geometry/controller interaction rather than random checkpoint noise.
Selecting the parent preserves the strongest accumulated development evidence;
retaining both continuation checkpoints preserves distinct policies whose
trajectory variants may be useful for future paired work without treating their
98.5% telemetry-panel result as independent objective attainment.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/results.jsonl`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-working-200ep-seed22000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-checkpoint-105472-200ep-seed22000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-checkpoint-120832-200ep-seed22000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-working-200ep-seed23000-a27165d6de57.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-checkpoint-105472-200ep-seed23000-a27165d6de57.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-checkpoint-120832-200ep-seed23000-a27165d6de57.json`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 3

**Result:** Stronger action regularization and full hold-credit forfeiture did
not improve stabilization. On the paired 24000--24199 panel, the working
parent achieved 196/200, while experiment-3 checkpoint-100352 achieved
176/200 and checkpoint-120832 achieved 186/200. The parent remains working and
best-known; the experiment-3 reward recipe is rejected and the parent recipe
is restored. Both measured challengers are retained as negative controls for
future mechanism comparisons.

**Observed behavior:** The parent lost four episodes, all by failing to enter
tolerance. The 100352-step challenger lost 24 episodes: four no-entry failures
and 20 failures that entered tolerance but never sustained 100 uninterrupted
steps. The 120832-step challenger lost 14 episodes: three no-entry failures
and 11 incomplete holds. The challengers' failures extended beyond the
recurring negative-angle sector, and paired comparisons recorded zero
challenger wins against the parent.

**Hypothesis assessment:** The hypothesis that stronger action regularization
combined with full hold-credit forfeiture would reduce interrupted holds while
preserving broad reach-and-hold behavior is contradicted on this panel. The
intervention produced a large complete-task regression and more incomplete
holds, not the predicted stabilization. Because both reward terms changed
together and the policies were continued through learning, the measurements
reject the recipe as a useful intervention but do not identify which term or
learning interaction caused the regression.

**Interpretation:** The evidence does not support continuing reward shaping as
the primary explanation for the failure sector. The parent is the most
defensible lineage for subsequent work, while the two measured challengers
remain useful negative controls. The next scientific distinction is between
conditioning, branch-transition behavior, and the information or control
representation; no official objective attainment is claimed.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/results.jsonl`;
`research/checkpoints/challengers/9f1de290-24cf-4a97-8dab-6026ac343493/experiment-3/parameters.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-3-working-200ep-seed24000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-3-checkpoint-100352-200ep-seed24000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-3-checkpoint-120832-200ep-seed24000-48e4acc98c39.json`;
`robot_learning/scenario/reward.py`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 4

**Result:** Adding sine/cosine encodings of the four inverse-kinematic
branch-angle errors to the existing observation produced a severe complete-task
regression. The 100352-step and 120832-step candidates achieved 41/200
(20.5%) and 53/200 (26.5%) on the disjoint episodes 25000--25199 panel, while
the paired working parent achieved 196/200 (98.0%). The parent won every
discordant episode: 155 for the proxy-peak candidate and 143 for the final
candidate. The working lineage remains selected and best-known; the periodic
recipe is rejected and reverted. Both measured candidates are retained as
negative controls for the representation investigation.

**Observed behavior:** The periodic candidates did not merely preserve the
known no-entry sector. They failed on a broad set of targets where the parent
completed reach and hold, with many failures never entering tolerance and
additional trajectories entering briefly or failing to hold. Their late
checkpoint improved from 20.5% to 26.5% but remained far below the parent, so
continued training did not recover the parent's behavior within this run.

**Hypothesis assessment:** The hypothesis that periodic branch-error features
would remove negative-angle no-entry failures while preserving broad behavior
is contradicted on the paired panel. The result rejects this observation
recipe as a useful intervention and strongly weakens the claim that scalar
wrapped branch errors are the primary actionable cause. Because the policy was
trained fresh with a changed observation dimension, the result does not
identify whether optimization, feature interactions, branch selection, or
physical control dynamics caused the regression.

**Interpretation:** The parent is the only defensible continuation: it retains
the broadest measured reach-and-hold behavior and is exactly at the 98.0%
threshold on this development panel, without establishing the official
objective. The experiment rules out a broad periodic augmentation as a safe
next step, but leaves configuration-dependent control, branch-transition
dynamics, conditioning, and saturation as competing explanations. Retaining
the two measured challengers preserves a sharply negative representation
control for later mechanism comparisons without treating it as a viable
training parent.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/scientific_model.md`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-4-working-200ep-seed25000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-4-checkpoint-100352-200ep-seed25000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-4-checkpoint-120832-200ep-seed25000-48e4acc98c39.json`;
`robot_learning/scenario/observations.py`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 5

**Result:** The stateless 0.9 action-headroom map did not produce a reliable
complete-task improvement. Both measured checkpoints achieved 391/400 over
the two fresh panels, compared with 390/400 for the parent on the same
episodes. The experiment-5 recipe is reverted, the parent remains working
and best-known, and both measured headroom checkpoints are retained as
controlled alternatives.

**Observed behavior:** On episodes 27000-27199, each headroom checkpoint
rescued the parent's failure at episode 27089 and shared the parent's other
four failures. On episodes 28000-28199, the parent and both headroom
checkpoints shared all five failures: 28018, 28030, 28145, 28171, and 28194.
The corrected evaluator measured zero physical saturation steps for both
headroom checkpoints, while the parent averaged 119.3 saturation steps per
episode and its failures averaged 498.6. The headroom failures still had
near-zero minimum Jacobian determinants, delayed entry when entry occurred,
and incomplete holds. The 100352- and 105472-step checkpoints had the same
complete-task outcomes; continued adaptation did not add evidence.

**Hypothesis assessment:** The hypothesis is weakened. The intervention
successfully changed the physical command regime and removed the measured
actuator saturation signature without broad success collapse, but the expected
failure-sector recovery was not reproducible: it occurred once on the first
panel and not at all on the second. The shared failures under zero measured
saturation reject saturation as a sufficient causal explanation. The evidence
does not establish whether saturation contributes upstream to the trajectory
or is only a consequence or marker of poor conditioning.

**Interpretation:** Reducing command authority alone does not solve the
repeatable negative-angle failures. The unchanged failure identities despite
the changed physical command regime redirect the scientific inquiry toward
configuration-dependent conditioning, branch-transition behavior, and local
stabilization. The parent is the safer working lineage because the headroom
mapping adds no reliable task benefit, while both checkpoints remain useful
controlled alternatives for later comparisons.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/results.jsonl`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-checkpoint-100352-200ep-seed27000-6f556e2004f1.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-checkpoint-105472-200ep-seed27000-6f556e2004f1.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-working-200ep-seed27000-6f556e2004f1.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-checkpoint-100352-200ep-seed28000-238ccfe3776f.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-checkpoint-105472-200ep-seed28000-238ccfe3776f.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-working-200ep-seed28000-238ccfe3776f.json`;
`robot_learning/scenario/policy_io.py`;
`robot_learning/scenario/evaluation.py`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 6

**Result:** The per-episode normalized-action slew limiter did not produce a
reliable complete-task improvement. On episodes 29000--29199, the parent
achieved 194/200, the 100352-step checkpoint achieved 193/200, and the
120832-step checkpoint achieved 195/200. The parent remains the working and
best-known lineage, the experiment-6 recipe is reverted, and the final
checkpoint is retained as a measured temporal-control alternative.

**Observed behavior:** The early checkpoint failed on episodes 29002, 29013,
29073, 29077, 29086, 29120, and 29142, while the parent failed on 29013,
29073, 29077, 29086, 29120, and 29142. The final checkpoint failed on 29013,
29073, 29086, 29120, and 29142. Thus the early checkpoint had no paired wins
and one paired loss, while the final checkpoint had one paired win (29077) and
no paired losses. Every failure truncated at 500 steps. Among successful
episodes, mean completion was 111.93 steps for the parent, 122.02 for the
early checkpoint, and 120.92 for the final checkpoint; the respective maximum
completion times were 122, 220, and 249 steps.

**Hypothesis assessment:** The hypothesis that limiting rapid command changes
would reduce persistent failures or interrupted holds while preserving broad
reach-and-hold behavior is weakened. Late adaptation changed one failure
identity and preserved a near-parent success rate on this panel, but five
failures remained shared and successful episodes were substantially slower.
The early checkpoint was worse and added a failure. Because this is one
development panel and the artifacts contain no entry or hold-stage telemetry,
the evidence does not prove that transient dynamics never contribute; it does
reject this fixed slew-limiter recipe as a sufficient or reliable solution.

**Interpretation:** Temporal smoothing trades command responsiveness for no
robust recovery of the recurring failure sector. Together with experiment 5,
the result redirects attention from saturation and command-rate limiting toward
configuration- or branch-dependent conditioning and local stabilization. The
final checkpoint is worth retaining as a controlled alternative because it
rescued one paired episode without broad collapse, but it is not a defensible
working policy and no official objective attainment is claimed.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/9f1de290-24cf-4a97-8dab-6026ac343493/experiment-6/inventory.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-6-checkpoint-100352-200ep-seed29000-1755b1c50cef.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-6-checkpoint-120832-200ep-seed29000-1755b1c50cef.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-6-working-200ep-seed29000-1755b1c50cef.json`;
`robot_learning/scenario/policy_io.py`;
`robot_learning/scenario/evaluation.py`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 7

**Result:** Targeted sampling of the observed negative-angle sector did not
produce a measured challenger that could displace the working lineage. The
working parent remains selected at 197/200 on the fresh development panel, and
the saved slew and headroom controls each scored 196/200.

**Observed behavior:** The parent failed at seeds 30030, 30045, and 30090.
The slew control shared those failures and added seed 30184; its failures had
490, 490, 45, and 10 saturated steps respectively, with seed 30184 reaching
only 71 held steps and suffering 14 hold interruptions. The headroom control
shared seed 30030 and failed at the other three seeds after zero saturation
steps; its maximum held steps on those failures were 0, 3, 2, and 1. The
failure trajectories crossed branch boundaries and reached low Jacobian
determinants, while branch switching also occurred in 90 of 197 successful
parent episodes. Experiment 7 produced 24 unmeasured candidates, so these
measurements characterize the parent and controls rather than directly
measuring the targeted-coverage policy.

**Hypothesis assessment:** The hypothesis that targeted exposure would rescue
the recurring sector while preserving broad reach-and-hold behavior is
inconclusive for the direct intervention because no experiment-7 candidate was
measured. The paired control evidence nevertheless weakens the narrower claim
that the failure is sufficiently explained by saturation or fixed command
slew: headroom removed saturation without rescuing the shared targets, and
slew preserved them while adding an incomplete hold. No available evidence
supports changing the working lineage, and the mechanism remains unresolved.

**Interpretation:** The failure is most consistent with a configuration-
dependent interaction among branch transition, local conditioning, and
stabilization, but the telemetry establishes association rather than cause.
Closing on the working recipe preserves the only lineage with broad,
repeatedly measured support; it does not claim that targeted coverage or the
underlying mechanism has been definitively ruled out. The development evidence
does not justify requesting the final benchmark.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/9f1de290-24cf-4a97-8dab-6026ac343493/experiment-7/inventory.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-7-working-200ep-seed30000-1796db8c3035.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-7-e6-temporal-slew-120832-200ep-seed30000-1796db8c3035.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-7-e5-action-headroom-105472-200ep-seed30000-1796db8c3035.json`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 8

**Result:** The fresh 15-value observation with endpoint velocity and signed
and absolute Jacobian determinants caused a severe complete-task regression.
The reward-peak checkpoint achieved 110/200 (55.0%) and the final checkpoint
achieved 109/200 (54.5%) on episodes 32000--32199, while the paired working
lineage achieved 198/200 (99.0%). The working policy won all 88 and 89
discordant episodes against the two checkpoints.

**Observed behavior:** The regression was broad rather than confined to the
previous negative-angle sector. Many challenger failures never entered
tolerance and showed hundreds of saturated control steps; the artifacts also
contain interrupted-hold failures. The final checkpoint did not improve on
the reward-peak checkpoint despite higher training success and later training.
The parent retained its broad reach-and-hold behavior on the identical panel.

**Hypothesis assessment:** The hypothesis that explicit endpoint velocity and
local conditioning information would help manage the branch-transition and
near-singular regime while preserving broad behavior is contradicted on this
paired panel. The large within-panel regression and zero challenger wins
reject this fresh observation recipe as a useful intervention for the
objective. The result does not isolate the causal contribution of any one
appended feature, feature scaling or interaction, or fresh-training
optimization variance.

**Interpretation:** Supplying physically meaningful dynamics quantities is not
by itself sufficient; the learned policy must use them with a representation
and optimization contract that preserves the parent's established behavior.
The active inquiry should move away from this augmentation and retain the
parent's observation contract as the defensible baseline. The two measured
checkpoints are retained as negative controls for future representation
analysis, not as policy alternatives or evidence of objective attainment.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-8-checkpoint-115712-200ep-seed32000-389c4f131ee0.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-8-checkpoint-120832-200ep-seed32000-389c4f131ee0.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-8-working-200ep-seed32000-389c4f131ee0.json`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 9

**Result:** Concentrating 70% of training targets in the recurring negative-angle
sector did not produce a measured policy that could displace the working
lineage. On the fresh episodes 34000--34199 panel, the parent and
checkpoint-90112 each achieved 196/200, while checkpoint-120832 achieved
194/200. The parent remains working and best-known; the experiment-9 recipe is
reverted, and both measured challengers are retained as controlled alternatives.

**Observed behavior:** Checkpoint-90112 and the parent failed on exactly
episodes 34039, 34099, 34108, and 34190, so the challenger had zero paired
wins. Checkpoint-120832 shared those four failures and added episodes 34022 and
34036, with no paired wins. The shared failures had target angles from about
-128 to -139 degrees; the two additional final-checkpoint failures were about
-111 and -122 degrees. The failure diagnostics consistently recorded a branch
switch and approximately 497--499 saturated control steps, with either no
tolerance entry or only one to four held steps. These patterns did not change
the fact that branch switching was also common in successful episodes.

**Hypothesis assessment:** The hypothesis that targeted exposure would rescue
the recurring sector while preserving broad reach-and-hold behavior is
contradicted for the measured checkpoints. The proxy-peak challenger matched,
rather than rescued, every parent failure, and the final checkpoint degraded
by adding two failures. This conclusion is limited to the transferred
experiment-9 trajectory and one fresh development panel: it rejects the
tested exposure recipe as a useful sufficient intervention, but it does not
identify the causal contribution of branch transition, conditioning,
saturation, or stabilization.

**Interpretation:** Direct task evidence is more informative than the
experiment-9 training proxy: neither the apparent proxy peak nor continued
training changed the failure set in the beneficial direction. The unchanged
shared failures after targeted exposure support carrying forward a
configuration-dependent control interaction as an unresolved inquiry rather
than treating target frequency as its explanation. Restoring the parent recipe
preserves the strongest repeatedly measured behavior without claiming that the
human objective has been reached.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/9f1de290-24cf-4a97-8dab-6026ac343493/experiment-9/inventory.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-9-working-200ep-seed34000-bb54672c3d8e.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-9-checkpoint-90112-200ep-seed34000-bb54672c3d8e.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-9-checkpoint-120832-200ep-seed34000-bb54672c3d8e.json`.
