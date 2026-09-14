# Research postmortems

## 045ec01f-613e-4cd7-9cac-4b3c512b0f94 / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success on the
official full-range reach-and-hold task. The fresh PPO baseline learned a useful
policy, but its strongest measured development checkpoint reached 97.0% (194/200)
at checkpoint-100352, below the objective. The transfer experiment that added
focused negative-angle exposure did not improve measured task success: its best
checkpoint reached 88.0% and its final checkpoint 83.5%. The original working
policy therefore remains the strongest measured lineage.

**Lessons and limits:** Measured task success, rather than training reward or
training success, supports claims of policy progress. On the shared 200-episode
development panel, checkpoint-100352 outperformed checkpoint-90112 (97.0% versus
93.0%) and checkpoint-120832 (97.0% versus 96.5%); the late paired comparison
had only one discordant episode. Detailed diagnostics show that five of the six
persistent failures never reached tolerance, while one reached it briefly and
lost the hold. The baseline trained with a far-target radius range while the
official task spans 6-20 cm, so coverage is a plausible but unproven contributor.
The focused transfer run recovered five of the six prior failure seeds on its
three measured checkpoints, but introduced many other failures and scored
84.5% at the checkpoint matching the baseline peak. Its training proxies did
not establish task progress: training success rose to 0.91 at the final
checkpoint while measured task success fell to 83.5%. These are single-seed
development measurements, the experiment-2 artifacts do not emit target
radius/angle breakdowns, and the unmeasured checkpoints remain unknown.

**Open questions:** It remains unresolved whether the persistent negative-angle
failures arise from insufficient training coverage, a learned representation
limitation, or another control limitation. It is also unknown whether the
97.0% peak generalizes beyond the development panel and which alternative
intervention could address the residual failures without the broad regression
seen under focused transfer training.

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

## 045ec01f-613e-4cd7-9cac-4b3c512b0f94 / Experiment 2

**Result:** The transfer experiment's focused target sampling did not yield
measured policy progress. Its challenger checkpoints are not selected; the
working lineage and best-known designation remain the experiment-1
`checkpoint-100352` policy, and the scientific recipe is restored to that
parent.

**Observed behavior:** Training completed 120,832 steps against a requested
120,000. Checkpoint metadata reported training success of 0.87, 0.88, and 0.91
at 90,112, 100,352, and 120,832 steps, with episode-reward means of 103.63,
107.01, and 111.85. Research evaluation on 200 episodes with seed 0 measured
88.0% (176/200), 84.5% (169/200), and 83.5% (167/200) at those checkpoints;
every recorded failure in these artifacts ran to the 500-step truncation. Using
the deterministic episode-seed labels, five of the six failure seeds that
persisted at the baseline peak were successful in all three experiment-2
measurements, while seed 11 remained a failure. The experiment-2 artifacts do
not include target radius or angle, so the location of the newly introduced
failures cannot be established from this round.

**Hypothesis assessment:** Weakened, with a partial local signal. The recovery
of five prior hard seeds is consistent with the exploratory expectation that
additional focused exposure could help those cases. However, the overall
unchanged-task success was substantially below the parent policy at every
measured checkpoint, including 84.5% at the corresponding 100,352-step
position versus the parent's 97.0% development result. The result supports
neither a net policy improvement nor the claim that this coverage change
preserves performance elsewhere; it does not prove that coverage cannot be
useful under another training design.

**Interpretation:** Under this transfer recipe, focused negative-angle sampling
changed behavior on several previously failing episode seeds but produced a
large regression across the measured panel. The increase in training proxies
did not translate into task success, so those proxies should not guide policy
acceptance. Because the measurement instrumentation omitted target geometry,
the result cannot distinguish failures inside and outside the focused sector
or establish a causal sector-level mechanism. The parent remains the most
useful saved policy for further development, but it remains below the human
objective and is not ready for irreversible official assessment.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`, `research/research_state.json`,
`robot_learning/scenario/environment.py`,
`research/evaluations/045ec01f-613e-4cd7-9cac-4b3c512b0f94/evaluation-045ec01f-613e-4cd7-9cac-4b3c512b0f94-experiment-2-checkpoint-90112-200ep-seed0-00d38a8dd674.json`,
`research/evaluations/045ec01f-613e-4cd7-9cac-4b3c512b0f94/evaluation-045ec01f-613e-4cd7-9cac-4b3c512b0f94-experiment-2-checkpoint-100352-200ep-seed0-00d38a8dd674.json`,
and `research/evaluations/045ec01f-613e-4cd7-9cac-4b3c512b0f94/evaluation-045ec01f-613e-4cd7-9cac-4b3c512b0f94-experiment-2-checkpoint-120832-200ep-seed0-00d38a8dd674.json`.
