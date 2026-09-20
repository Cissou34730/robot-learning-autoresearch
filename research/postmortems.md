# Research postmortems

## 77bb76da-d4f2-4e42-8202-0a8fb412f5ee / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success on the
official 6-20 cm, full-angle reach-and-hold task. The unchanged PPO baseline
learned a useful policy, and checkpoint-100352 remains the best-supported
current lineage at 587/600 pooled success (97.83%), including 97.0% on each of
two disjoint panels. Expanding the training radius range and then oversampling
negative angles both failed to improve matched or fresh-panel performance; the
experiment-3 transfer reached 191/200 versus 192/200 for its retained control.
On the fresh experiment-4 panel, the unchanged working parent reached 196/200
(98.0%), while full hold-progress forfeiture reached 191/200 (95.5%) at 100352
steps and 179/200 (89.5%) at 105472 steps. The campaign has therefore made
substantial but sub-objective development progress, and the official result
remains unmeasured.

**Lessons and limits:** Complete reach-and-hold success, rather than training
success or reward, governs progress. The reward-peak checkpoint-86016 measured
95.0%, whereas checkpoint-100352 measured 97.83% pooled; the late endpoint was
weaker on the available comparisons. Across the two disjoint baseline panels,
all 12 checkpoint-100352 failures were at negative angles: five never reached
tolerance and seven reached it only briefly. On the experiment-3 panel, both
changed checkpoints again failed only at negative angles, with five never-reach
and four incomplete-hold failures for the 100352-step checkpoint. The radius,
angle-distribution, and full hold-forfeiture interventions provide evidence
against those tested transferred recipes, not against all possible control,
representation, or reward changes. Experiment 4 emitted no hold-specific
diagnostics; its lower aggregate success and zero paired wins weaken the
hold-shaping explanation under the tested recipe without establishing why it
failed. The reused first panel is selection-contaminated; seeds 10200, 10400,
10600, 10800, and 11000 provide disjoint development coverage.

**Open questions:** Whether the remaining never-reach failures arise from
angle-specific control or observation representation rather than reward
shaping. Whether a future intervention can improve the current policy without
losing its broad reach-and-hold behavior. Whether the current best-known policy
satisfies the official 98% criterion on the frozen 200-episode assessment.

## 77bb76da-d4f2-4e42-8202-0a8fb412f5ee / Experiment 1

**Result:** The fresh baseline produced a useful candidate. Checkpoint-100352
is selected as both the working and best-known lineage; the unchanged
scientific recipe is kept, and terminal assessment is deferred.

**Observed behavior:** Training success was 0 through 70,656 steps, rose to
0.42 at step 86,016, 0.93 at step 95,232, and 0.97 at step 100,352. The
highest training reward was 163.854 at step 86,016, then reward declined to
117.320 at step 100,352 and 112.017 at the 120,832-step endpoint. On the
first 200-episode research panel, checkpoint-100352 achieved 199/200
(99.5%), checkpoint-120832 achieved 197/200 (98.5%), and checkpoint-86016
achieved 190/200 (95.0%). On disjoint panels, checkpoint-100352 achieved
194/200 (97.0%) at seed 10200 and 194/200 (97.0%) at seed 10400, for
587/600 (97.83%) pooled. Checkpoint-120832 achieved 193/200 (96.5%) on the
seed-10400 panel, for 390/400 (97.5%) pooled. The paired comparison on the
shared disjoint panel favored checkpoint-100352 by 3 to 0 discordant wins.
The leader's disjoint failures were mostly at negative angles, including
targets around -116 to -152 degrees and radii from about 6.9 to 19.3 cm;
some reached tolerance only briefly while others never reached it. One
endpoint failure accumulated 287 in-tolerance steps but only 89 consecutive
held steps, showing that substantial partial behavior can still fail the
uninterrupted two-second criterion.

**Hypothesis assessment:** Partially supported. The baseline question was
whether late training-time success and reward signals would transfer to
complete reach-and-hold success and identify a working checkpoint. High
training success did transfer to high measured task success, and
checkpoint-100352 was better supported than the endpoint and the reward-peak
checkpoint. The result is not a complete transfer to the human objective:
the leader fell from 99.5% on the reused panel to 97.0% on each disjoint
panel, and no measurement was an official benchmark. The reward peak did not
predict the best measured policy. These conclusions are limited to this
recipe, its saved checkpoints, and the research-evaluation panels; they do
not establish a causal explanation for the geometry failures.

**Interpretation:** Checkpoint-100352 is the most useful current policy and
should anchor the next scientific intervention, but the independent
97.0% panels make terminal assessment premature. The evidence supports
closure of this baseline and further development, not rejection of the
learned policy.

**Evidence inspected:** `research/results.jsonl`;
`research/checkpoints/challengers/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/experiment-1/inventory.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-100352-200ep-seed10000-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-100352-200ep-seed10200-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-100352-200ep-seed10400-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-120832-200ep-seed10000-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-120832-200ep-seed10400-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-1-checkpoint-86016-200ep-seed10000-543af51fd137.json`.

## 77bb76da-d4f2-4e42-8202-0a8fb412f5ee / Experiment 2

**Result:** Expanding the training radius range to 6-20 cm did not improve
measured reach-and-hold success on the matched disjoint panel. The retained
baseline remains the working and best-known lineage; the experiment recipe is
reverted and terminal assessment remains deferred.

**Observed behavior:** The changed recipe reached training success 0.99 at
100352 steps and 1.0 at 105472 steps, but those training proxies measured
192/200 successes (96.0%) at both checkpoints on episodes 10600-10799. The
retained baseline measured 193/200 (96.5%) on the same panel. Paired
comparisons recorded no discordant wins for either changed checkpoint against
the baseline, with one baseline win; the two changed checkpoints had no
discordant wins against each other. The changed checkpoint-100352 and
checkpoint-105472 failures were the baseline's seven failures plus episode 42,
whereas the baseline failed on episodes 75, 140, 165, 185, 196, 197, and 199.
Training reward was an orthogonal proxy: it was 121.367 at 10240 steps and
110.176 at 105472 steps, while the measured task success stayed at 96.0% for
both measured changed checkpoints. The research-evaluation artifacts report
success, reward, steps, termination and truncation, but not target geometry or
held-step diagnostics for this round.

**Hypothesis assessment:** Weakened. The confirmatory prediction that broader
radial coverage would reduce the observed failure pattern without sacrificing
performance was not observed on the matched disjoint panel: the changed
policies were slightly worse in aggregate and added a failure while retaining
the baseline failures. This is evidence against this intervention under the
tested transferred run and panel, not proof that radial coverage can never
help; because target geometry and hold subdiagnostics were not emitted here,
the result cannot distinguish radial effects from angle-dependent control or
hold dynamics.

**Interpretation:** The saved baseline policy remains useful progress toward the
98% official objective, but this intervention does not provide a stronger
candidate or evidence that the negative-angle and interrupted-hold failures
were caused by the 14-20 cm training-radius restriction. The matched control
and disjoint episode coverage are directly comparable for this decision, while
the measured 96.0%/96.5% values are development evidence rather than an
official verdict. Reverting the changed training distribution preserves the
best-supported policy and leaves further training as a separate future
experiment.

**Evidence inspected:** `research/results.jsonl`;
`research/brief.md`;
`research/checkpoints/challengers/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/experiment-2/inventory.json`;
`research/training_logs/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/experiment-2-attempt-1.log`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-2-checkpoint-100352-200ep-seed10600-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-2-checkpoint-105472-200ep-seed10600-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-2-working-200ep-seed10600-543af51fd137.json`;
`robot_learning/scenario/training_environment.py`.

## 77bb76da-d4f2-4e42-8202-0a8fb412f5ee / Experiment 3

**Result:** The angle-biased training distribution did not improve the
measured policy. Both measured experiment-3 checkpoints reached 95.5% on the
fresh panel, versus 96.0% for the matched retained baseline. The experiment
recipe is reverted, the retained baseline remains working and best-known, and
terminal assessment is deferred.

**Observed behavior:** The training log's proxy success reached 0.98 around
15,360-25,600 steps, then declined to 0.93 at checkpoint-100352 and recovered
to 0.95 at checkpoint-120832; listed rewards followed the same broad
non-monotonic pattern. On the disjoint episodes 10800-10999, checkpoint-100352
and checkpoint-120832 each achieved 191/200 successes, while the working
baseline achieved 192/200. Every failure for all three policies was at a
negative target angle. The changed checkpoints had 9 failures each versus 8
for the baseline; the paired comparisons recorded 0 discordant wins for each
changed checkpoint and 1 for the baseline. The failure mix was also partial:
the 100352-step changed policy never reached tolerance in 5 failures and
reached it without a complete hold in 4, while the 120832-step policy had 3
never-reached and 6 incomplete-hold failures.

**Hypothesis assessment:** Weakened. The confirmatory prediction that
oversampling negative angles would reduce negative-angle failures while
preserving nonnegative performance was not observed on the fresh full-angle
panel: the changed policies had one more failure than the control and no
paired wins. The absence of nonnegative failures is consistent with preserved
nonnegative behavior on this panel, but does not show improvement. This
weakens the training-frequency explanation under the tested transferred run
and evaluation panel; it does not prove that angle sampling can never help or
distinguish angle control, representation, and hold-shaping causes.

**Interpretation:** Complete task measurements, rather than the higher early
training proxies, show that the intervention did not advance the policy toward
the 98% objective in this comparison. The same-panel control, disjoint episode
range, and failure diagnostics support reverting the changed recipe and
continuing from the established baseline. The development result remains
below the official criterion and is not an official verdict.

**Evidence inspected:** `research/results.jsonl`;
`research/brief.md`;
`research/checkpoints/challengers/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/experiment-3/inventory.json`;
`research/training_logs/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/experiment-3-attempt-1.log`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-3-checkpoint-100352-200ep-seed10800-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-3-checkpoint-120832-200ep-seed10800-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-3-working-200ep-seed10800-543af51fd137.json`;
`robot_learning/scenario/training_environment.py`.

## 77bb76da-d4f2-4e42-8202-0a8fb412f5ee / Experiment 4

**Result:** Full forfeiture of accumulated hold progress did not improve the
measured policy. The unchanged working parent remains the working and
best-known lineage; the reward recipe is reverted and terminal assessment is
deferred.

**Observed behavior:** The training log reached 1.00 proxy success and a
103.472 reward at 35,840 steps, then remained non-monotonic: proxy success was
0.99 around 95,232-108,544 steps and declined to 0.95 by 120,832, while the
listed reward declined to 98.006 at the endpoint. These are training proxies,
not task acceptance measurements. On the fresh, disjoint research panel
covering episodes 11000-11199, the unchanged parent achieved 196/200 (98.0%),
checkpoint-100352 achieved 191/200 (95.5%), and checkpoint-105472 achieved
179/200 (89.5%). The paired comparisons recorded 0 challenger wins versus 5
parent wins for checkpoint-100352 and 0 versus 17 for checkpoint-105472. The
100352-step challenger failed on the parent's four failed episodes plus five
additional episodes; the 105472-step challenger failed on those four plus
seventeen additional episodes. This measurement artifact emitted no target
geometry or held-step failure diagnostics, so the incomplete-hold prediction
cannot be assessed directly. Episode reward totals are not compared because
the intervention changed the reward definition.

**Hypothesis assessment:** Weakened. The confirmatory prediction that full
forfeiture would reduce interrupted holds while preserving reach and
nonnegative-angle behavior was not supported by complete-task success: both
changed checkpoints underperformed the same-panel parent, and neither won a
paired episode. The missing hold-specific diagnostics prevent a claim that the
intervention failed specifically by leaving interrupted holds unchanged.
This is evidence against the tested transferred reward recipe on this panel,
not proof that every hold-shaping change or explanation is ineffective.

**Interpretation:** The unchanged parent is the more useful saved policy and
the only current lineage supported by both the prior disjoint panels and this
fresh panel. The training proxies' peak and late fluctuations again do not
identify a reliable policy checkpoint. Reverting the reward change restores
the parent's complete scientific recipe; the current development evidence is
still not an official benchmark result and does not establish whether the
remaining failures are caused by hold shaping, angle-specific control, or
representation.

**Evidence inspected:** `research/results.jsonl`;
`research/brief.md`;
`research/checkpoints/challengers/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/experiment-4/inventory.json`;
`research/training_logs/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/experiment-4-attempt-1.log`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-4-checkpoint-100352-200ep-seed11000-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-4-checkpoint-105472-200ep-seed11000-543af51fd137.json`;
`research/evaluations/77bb76da-d4f2-4e42-8202-0a8fb412f5ee/evaluation-77bb76da-d4f2-4e42-8202-0a8fb412f5ee-experiment-4-working-200ep-seed11000-543af51fd137.json`;
`robot_learning/scenario/reward.py`.
