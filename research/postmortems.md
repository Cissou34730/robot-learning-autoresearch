# Research postmortems

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned substantial reach-and-hold
behavior late in training. The latest measured checkpoint is the strongest
available policy, but its development success remains below the 98% objective,
so the campaign has evidence of progress rather than objective satisfaction.

**Lessons and limits:** Training proxies improved from 0.00 success and
-479.3 mean reward at step 100352 to 0.11 success and -168.5 mean reward at
step 120832 (`research/results.jsonl`). On a matched 200-episode
research-evaluation setting, measured success increased from 85.5% (171/200)
at checkpoint-110592 to 89.5% (179/200) at checkpoint-120832, supporting
transfer of the late improvement to task behavior and selecting checkpoint-
120832 over the measured predecessor. The latest checkpoint reached 92.0%
(184/200) on the reused `task-reference-v1` panel, which is corroborating
development evidence but is selection-contaminated and not terminal evidence.
All 21 research-evaluation failures and all 16 task-reference failures
exhausted the 500-step horizon; the reference failures in this panel cluster
at several targets around 119-164 degrees, with both near and far radii, but
that pattern is descriptive of one fixed panel and not a causal or
distribution-wide diagnosis. The 22 unmeasured checkpoints and raw training
logs leave the learning trajectory and alternative-checkpoint behavior
unresolved.

**Open questions:** Whether further training or a changed recipe can reduce
the remaining horizon-exhaustion failures, and whether the observed
reference-panel angular pattern persists on independent task draws, remain
open.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 1

**Result:** The baseline produced a useful but not objective-satisfying
policy. Checkpoint-120832 is selected as the working and best-known lineage.

**Observed behavior:** Training proxies improved late: training success rose
from 0.00 at step 100352 to 0.05 at 110592 and 0.11 at 120832, while mean
episode reward improved from -479.3 to -168.5. The latest checkpoint achieved
179/200 (89.5%) on the research-evaluation panel; the preceding measured
checkpoint achieved 171/200 (85.5%) under the same evaluation semantics,
an 8-episode / 4-point improvement. The paired comparison had 9 latest-policy
wins versus 1 predecessor win across 10 discordant episodes. On the fixed
task-reference panel, checkpoint-120832 achieved 184/200 (92.0%). Every
failure in both detailed outcome sets truncated at 500 steps rather than
terminating successfully.

**Hypothesis assessment:** Partially supported. The baseline's measurement
question was whether late proxy improvement transferred to uninterrupted
reach-and-hold success and whether the latest checkpoint surpassed the prior
late checkpoint. Both observations occurred on the matched research panel,
so the transfer and relative-improvement claims are supported under those
settings. The result does not support claiming that the policy satisfies the
human objective: 89.5% and 92.0% development measurements are below 98%,
and neither development panel is the official verdict. The task-reference
result is consistent with the research evaluation but uses a reused panel,
and no causal claim about training duration or failure geometry is warranted.

**Interpretation:** The latest checkpoint is the best evidenced available
candidate and represents meaningful progress toward the human objective, but
the remaining failures are too frequent for terminal assessment to be
scientifically useful now. The baseline recipe should be kept with this
checkpoint so a later experiment can target the residual failures; the
baseline itself establishes behavior, not reproducibility or a causal
explanation.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-1/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-1-checkpoint-120832-200ep-seed0-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-1-checkpoint-110592-200ep-seed0-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/task-reference-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-1-checkpoint-120832-task-reference-v1.json`.
