# Research postmortems

## 045ec01f-613e-4cd7-9cac-4b3c512b0f94 / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success on the
official full-range reach-and-hold task. The fresh PPO baseline learned a useful
policy, but its strongest measured development checkpoint reached 97.0% (194/200)
at checkpoint-100352, below the objective. Performance then declined slightly to
96.5% at checkpoint-120832. Six failures persisted across those two checkpoints
in a target-angle cluster from -122.1 to -145.4 degrees, while the later
checkpoint added one different failure.

**Lessons and limits:** Measured task success, rather than training reward or
training success, supports claims of policy progress. On the shared 200-episode
development panel, checkpoint-100352 outperformed checkpoint-90112 (97.0% versus
93.0%) and checkpoint-120832 (97.0% versus 96.5%); the late paired comparison
had only one discordant episode. Detailed diagnostics show that five of the six
persistent failures never reached tolerance, while one reached it briefly and
lost the hold. The baseline trained with a far-target radius range while the
official task spans 6-20 cm, so coverage is a plausible but unproven contributor.
These are single-seed development measurements from one panel, not the official
assessment, and the unmeasured checkpoints remain unknown.

**Open questions:** It remains unresolved whether the persistent negative-angle
failures arise from insufficient training coverage, a learned representation
limitation, or another control limitation. It is also unknown whether the
97.0% peak generalizes beyond the development panel and whether broader,
sector-focused exposure changes the residual failures without creating failures
elsewhere.

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
