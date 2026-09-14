# Research postmortems

## 045ec01f-613e-4cd7-9cac-4b3c512b0f94 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned a useful reach-and-hold
policy, but the strongest measured checkpoint reached 97.0%, below the 98%
campaign objective. Performance peaked at checkpoint-100352 and declined
slightly by checkpoint-120832. The late-checkpoint failures include a persistent
cluster of target angles near -122 to -145 degrees, which is a useful diagnostic
signal but does not establish the underlying cause.

**Lessons and limits:** Measured task success, rather than training reward or
training success, supports claims of policy progress. On the shared 200-episode
development panel, checkpoint-100352 outperformed checkpoint-90112 (97.0% versus
93.0%) and was slightly better than checkpoint-120832 (97.0% versus 96.5%).
These are development measurements from one panel, not the official assessment,
and the paired comparison with checkpoint-120832 had only one discordant
episode. The baseline shows that the unchanged recipe can approach the target,
but does not show that additional training is monotonic or sufficient.

**Open questions:** It remains unknown whether the negative-angle failure
cluster is caused by the learned representation, reward/training coverage, or
another control limitation, and whether the measured peak generalizes to the
task-reference panel. Future work should target the residual failures without
treating this diagnostic pattern as a proven mechanism.

## 045ec01f-613e-4cd7-9cac-4b3c512b0f94 / Experiment 1

**Result:** The fresh baseline established substantial policy progress but did
not meet the human objective. Checkpoint-100352 is selected as the working and
best-known policy for continued development; terminal assessment is deferred.

**Observed behavior:** Training completed 120,832 steps against a requested
120,000. The checkpoint inventory reports training success rising from 0.71 at
90,112 steps to 0.97 at 100,352, then varying between 0.93 and 0.95 at
110,592-120,832; the associated episode-reward means were 160.85, 117.32,
118.28, and 112.02 respectively. The measured research-evaluation results were
93.0% (186/200) at checkpoint-90112, 97.0% (194/200) at checkpoint-100352, and
96.5% (193/200) at checkpoint-120832. Six failures at checkpoint-100352
(episode seeds 11, 25, 111, 167, 171, and 188) also failed at checkpoint-120832
and correspond to target angles from -122.1 to -145.4 degrees. The later
checkpoint additionally failed seed 124 after briefly entering tolerance. The
earlier checkpoint had fourteen failures, including repeated hold interruptions
outside that persistent cluster. Twenty-one other checkpoints were not measured
and remain unknown.

**Hypothesis assessment:** The baseline hypothesis, to establish an initial
baseline for the human-defined objective, is supported in the limited sense
that the unchanged recipe produced a policy near the target and a clear
measured learning progression. It is not evidence that the objective was
achieved: the best development result was 97.0%, and none of these measurements
is the official final assessment. The proxy metrics broadly tracked learning
but did not provide an acceptance threshold, and the late decline shows that
continued training was not monotonically beneficial under this run.

**Interpretation:** The saved policy is useful as a starting point for another
experiment, with checkpoint-100352 preferred because it has the highest
measured task success. The shared failure pattern suggests a targeted residual
behavioral problem, while the evidence is insufficient to attribute it to a
specific code or training component. The slight difference between the two
late checkpoints is also too small for a strong generalization claim.

**Evidence inspected:** `research/brief.md`,
`research/research_state.json`, `research/results.jsonl`,
`research/evaluations/045ec01f-613e-4cd7-9cac-4b3c512b0f94/`,
and the checkpoint inventory under
`research/checkpoints/challengers/045ec01f-613e-4cd7-9cac-4b3c512b0f94/experiment-1`.
