# Research postmortems

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned substantial reach-and-hold
behavior. Checkpoint-100352 is the strongest measured policy: it achieved
93.75% and 94.375% on two disjoint 160-episode research panels, or 301/320
pooled successes. This is progress toward the objective but remains below the
98% target. Continuing to checkpoint-120832 regressed task success despite
similar training-time proxies.

**Lessons and limits:** Task success is the relevant selection signal here;
training success and reward did not identify the best checkpoint reliably.
Checkpoint-100352 consistently exceeded checkpoint-105472 and checkpoint-110592
in paired development comparisons, while all observed failures ran to the
500-step truncation. The two research panels provide independent episode
coverage, but this is not an official assessment and no causal explanation for
the late regression has been established.

**Open questions:** The cause of the late-training regression and the structure
of the remaining reach-and-hold failures are unresolved. It is also unknown
whether a changed training recipe can raise the measured policy from roughly
94% toward the human objective.

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
