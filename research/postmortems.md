# Research postmortems

## c1523389-1363-42a7-b973-1bc6847ac445 / Scientific strategy

**Current synthesis:** The campaign has learned robust reach-and-hold behavior
but remains below the human objective: the working and best-known policy has
778/800 pooled research successes and scored 192/200 on the latest disjoint
panel, versus the required 196/200. Transfer-based coverage shaping, hold-exit
reward shaping, and fresh full-radius training did not improve it; the fresh
full-radius challengers scored 121/200 and 122/200. The fixed task-reference
result of 98% is reused development evidence, not independent confirmation.

**Lessons and limits:** Working-lineage failures cluster around negative angles
near -122 to -150 degrees and include inner targets; most recent failures never
entered tolerance. The tested coverage recipes failed, and the fresh full-radius
run lost broad behavior despite training-proxy progress. The evidence is
consistent with a geometric representation or policy limitation, but does not
identify the cause or rule out other training conditions. Training reward and
success proxies can diverge substantially from measured task success.

**Open questions:** It remains unresolved whether the current observation gives
the policy a sufficiently direct, continuous representation of target geometry
in the residual failure region, and whether that limitation can be addressed
without sacrificing broad reach-and-hold behavior.

## c1523389-1363-42a7-b973-1bc6847ac445 / Experiment 1

**Result:** The fresh baseline produced a useful learned policy, but no measured
policy is ready for terminal assessment.

**Observed behavior:** `checkpoint-100352` scored 99.5% on the first 200-episode
research panel and 97.0% on the disjoint second panel, for 393/400 pooled
successes. `checkpoint-120832` scored 98.5% and 97.0%, for 391/400 pooled
successes. The paired comparison favored `checkpoint-100352` 2-0 over the
pooled 400 shared episodes. On the permanently reused task-reference panel,
the two policies scored 98.0% and 97.0%, respectively. `checkpoint-86016`
scored 95.0% on its research panel and 94.0% on the task-reference panel.

**Hypothesis assessment:** The baseline's learned-behavior expectation is
supported: late checkpoints substantially outperform the earlier reward-peak
candidate. The expectation that the first-panel lead would persist as
independent confirmation is weakened: the two late candidates tie at 97.0% on
the disjoint panel, and neither development panel declares the objective
reached. The fixed task-reference result is not independent evidence because
that panel is permanently reused.

**Interpretation:** `checkpoint-100352` is the best-supported working and
best-known lineage because it has the strongest pooled research result and the
paired lead, while remaining below the 98% objective on the independent panel.
The recipe is retained unchanged for provenance; further progress requires an
ordinary next experiment rather than more interpretation of this baseline.

**Evidence inspected:** `research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-100352-200ep-seed10000-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-100352-200ep-seed10200-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-120832-200ep-seed10000-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-120832-200ep-seed10200-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/task-reference-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/task-reference-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-86016-200ep-seed10000-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/task-reference-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-86016-task-reference-v1.json`;
`research/brief.md`.

## c1523389-1363-42a7-b973-1bc6847ac445 / Experiment 2

**Result:** The target-coverage intervention did not produce a better measured
policy, and the experiment-1 working lineage remains the most useful saved
policy.

**Observed behavior:** On the new disjoint 200-episode panel, the transferred
`checkpoint-100352` scored 194/200 (97.0%), matching the experiment-2 early
proxy-peak `checkpoint-10240` at 194/200. The final
`checkpoint-120832` scored 192/200 (96.0%). The paired comparison was 0-0
discordant wins for `checkpoint-10240` versus the transfer, and 0-2 in favor
of the transfer for the final checkpoint. All three remain below the official
98% threshold of 196/200; these are development measurements, not a final
assessment.

**Hypothesis assessment:** The hypothesis is weakened: expanding the training
radius to the official inner-radius range and oversampling the observed hard
angle sector produced no early improvement and did not preserve the transfer
level at the final checkpoint. The single disjoint panel does not identify
which failure mechanisms changed, so it does not prove that coverage is
irrelevant or that another coverage schedule could not help.

**Interpretation:** The intervention should not replace the experiment-1
working or best-known lineage. The current experiment-2 code is reverted so
the scientific surface matches the selected lineage; the measured challenger
artifacts are not retained because none provides a demonstrated future-use
advantage. Further training remains an ordinary subsequent experiment, not a
decision made in this closure.

**Evidence inspected:** `research/brief.md`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-2-checkpoint-100352-200ep-seed10400-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-2-checkpoint-10240-200ep-seed10400-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-2-checkpoint-120832-200ep-seed10400-f48545f83637.json`;
`research/checkpoints/challengers/c1523389-1363-42a7-b973-1bc6847ac445/experiment-2/inventory.json`.

## c1523389-1363-42a7-b973-1bc6847ac445 / Experiment 3

**Result:** The hold-stability reward intervention did not improve task success
and degraded substantially by the final checkpoint; the prior working lineage
remains the strongest measured policy.

**Observed behavior:** On the new disjoint 200-episode research panel, the
unchanged `working` policy scored 193/200 (96.5%), the experiment-3
`checkpoint-35840` scored 190/200 (95.0%), and the final
`checkpoint-120832` scored 171/200 (85.5%). Paired comparisons favored
`working` over `checkpoint-35840` by 3-0 and over `checkpoint-120832` by 22-0
discordant wins. The early checkpoint favored the final checkpoint 22-3, but
both challengers were below the official 196/200 threshold and this was
development evidence rather than a final assessment.

**Hypothesis assessment:** The hypothesis is contradicted under the tested
recipe: setting `HOLD_EXIT_FORFEIT_FRACTION` to `1.0` produced neither an early
task-success improvement nor persistence through continued training, and the
final policy was materially worse than the unchanged control. The panel
comparison supports rejecting this intervention for lineage selection, but it
does not prove that all hold-stability reward shaping is ineffective or identify
the complete cause of the late degradation.

**Interpretation:** The experiment-1 working/best-known policy should be
preserved, and the experiment-3 reward change should be reverted. The measured
challengers provide no demonstrated future-use advantage, so their weights
should not be retained. Further training remains a separate ordinary next
experiment after this closure; the current evidence does not justify terminal
assessment because the best disjoint development result remains below 98%.

**Evidence inspected:** `research/brief.md`;
`research/postmortems.md`;
`research/checkpoints/challengers/c1523389-1363-42a7-b973-1bc6847ac445/experiment-3/inventory.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-3-working-200ep-seed10600-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-3-checkpoint-35840-200ep-seed10600-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-3-checkpoint-120832-200ep-seed10600-f48545f83637.json`.

## c1523389-1363-42a7-b973-1bc6847ac445 / Experiment 4

**Result:** Fresh training over the full official radius range produced no
useful challenger; the existing working lineage remains the strongest saved
policy.

**Observed behavior:** On the new disjoint research panel, the working policy
scored 192/200 (96.0%), while fresh full-radius `checkpoint-86016` scored
121/200 (60.5%) and `checkpoint-120832` scored 122/200 (61.0%). Paired
comparisons favored the working policy by 71-0 and 70-0 discordant wins,
respectively. The final challenger was only one success better than the early
challenger, and both remained far below the official 196/200 threshold.

**Hypothesis assessment:** The hypothesis is contradicted under the tested
recipe: fresh PPO training with uniform 0.06-0.20 m radii did not learn the
residual cases while preserving broad reach-and-hold behavior, either at the
training-reward peak or at the final checkpoint. The evidence is a single fresh
run and two measured checkpoints, so it rejects this tested recipe rather than
proving that all fresh training or radius curricula are ineffective.

**Interpretation:** Keep the existing working and best-known lineage and revert
the experiment-4 training-environment change. Neither measured challenger has a
future-use advantage, so no experiment-4 candidate should be retained. The
working policy remains below the human objective on the latest disjoint
development panel; further training is an ordinary subsequent experiment, not
part of this closure.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/c1523389-1363-42a7-b973-1bc6847ac445/experiment-4/inventory.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-4-working-200ep-seed10800-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-4-checkpoint-86016-200ep-seed10800-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-4-checkpoint-120832-200ep-seed10800-f48545f83637.json`.
