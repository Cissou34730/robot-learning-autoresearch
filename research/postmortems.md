# Research postmortems

## 7624cdd2-25fb-489d-ab70-a31be819d2a1 / Scientific strategy

**Current synthesis:** The campaign objective is a policy with at least 196/200
successes on the official 200-episode reach-and-hold assessment. The unchanged
PPO baseline learned the task, and checkpoint-100352 remains the strongest
supported development lineage: it scored 199/200 (99.5%) on the first disjoint
research-evaluation panel, 196/200 on the reused task-reference panel, and
196/200 on the fresh late-lineage comparison panel. The retained alternatives
tested on that comparison scored 195/200 and 193/200. The campaign therefore
has strong evidence of progress and a stable model choice, but no official
verdict.

**Lessons and limits:** Training proxies identify a sharp learning transition
and later fluctuation, but they are not task measurements. The task-reference
scores (192/200 for checkpoint-95232, 196/200 for checkpoint-100352, and
194/200 for checkpoint-120832) are comparable but selection-contaminated
because the panel was reused. The disjoint result is independent confirmation
for checkpoint-100352 under the research evaluator, not a replacement for the
protected final assessment. On the fresh comparison panel, checkpoint-100352
had four failures, including one brief two-step hold and three episodes that
never reached tolerance; this expands the observed residual failure pattern
without establishing its frequency or cause. The paired comparisons gave the
working lineage one discordant win over alternative-115712 and three over
alternative-120832, with no wins for either alternative. Other retained
lineages remain unmeasured on task behavior, so their training proxies cannot
rank them against the selected policy.

**Open questions:** The official benchmark outcome for the standing best-known
lineage remains unknown. The frequency and cause of the observed reach and hold
failures are also unresolved, and some retained late-training lineages have not
been measured on task behavior. The evidence does not establish that further
training or replication would improve the submitted policy.

## 7624cdd2-25fb-489d-ab70-a31be819d2a1 / Experiment 1

**Result:** The fresh PPO baseline made substantial task progress. Closure
selects checkpoint-100352 as both working and best-known, keeps the unchanged
recipe, and retains plausible late-training alternatives.

**Observed behavior:** The training log reports zero training success through
70,656 steps, then a rise to 0.93 at 95,232 and a peak of 0.98 at 99,328;
training success fluctuated between 0.93 and 0.96 through the 120,832-step
endpoint. These are training proxies rather than task measurements. On the
reused task-reference-v1 panel, checkpoint-95232 achieved 192/200 (96%),
checkpoint-100352 achieved 196/200 (98%), and checkpoint-120832 achieved
194/200 (97%). On the disjoint research-evaluation panel with seeds
10000-10199, checkpoint-100352 achieved 199/200 (99.5%). Its one failure
briefly reached the target tolerance but held for only one step, had one hold
interruption, and truncated at 500 steps.

**Hypothesis assessment:** Supported for the baseline question of whether the
unchanged method can produce a useful learned policy: measured reach-and-hold
performance is high and the disjoint panel confirms the selected checkpoint's
behavior beyond the reused selection panel. This does not establish that the
policy satisfies the human objective on the official panel, and it does not
show that the baseline recipe is optimal or that later unmeasured checkpoints
are inferior.

**Interpretation:** Checkpoint-100352 is the best-supported working lineage
because it is the strongest of the measured task-reference candidates and the
only candidate with disjoint-panel confirmation. The single independent-panel
failure suggests a residual hold-stability issue, but one diagnostic failure
does not establish its frequency or cause. No causal claim is made about why
this checkpoint is better than the others.

**Evidence inspected:** `research/training_logs/7624cdd2-25fb-489d-ab70-a31be819d2a1/experiment-1-attempt-1.log`,
`research/query_training_log.py`,
`research/checkpoints/challengers/7624cdd2-25fb-489d-ab70-a31be819d2a1/experiment-1/inventory.json`,
`research/evaluations/7624cdd2-25fb-489d-ab70-a31be819d2a1/task-reference-7624cdd2-25fb-489d-ab70-a31be819d2a1-experiment-1-checkpoint-95232-task-reference-v1.json`,
`research/evaluations/7624cdd2-25fb-489d-ab70-a31be819d2a1/task-reference-7624cdd2-25fb-489d-ab70-a31be819d2a1-experiment-1-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/7624cdd2-25fb-489d-ab70-a31be819d2a1/task-reference-7624cdd2-25fb-489d-ab70-a31be819d2a1-experiment-1-checkpoint-120832-task-reference-v1.json`,
`research/evaluations/7624cdd2-25fb-489d-ab70-a31be819d2a1/evaluation-7624cdd2-25fb-489d-ab70-a31be819d2a1-experiment-1-checkpoint-100352-200ep-seed10000-f48545f83637.json`,
`research/results.jsonl`,
`research/research_state.json`.
