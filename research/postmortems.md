# Research postmortems

## 045ec01f-613e-4cd7-9cac-4b3c512b0f94 / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success, or 196/200
episodes, on the official full-range reach-and-hold task. The unchanged fresh PPO
recipe learned a useful policy whose best measured development checkpoint reached
97.0% (194/200) at step 100352, but the later step-120832 checkpoint reached
96.5%. The transfer recipe that added 25% focused exposure to the -150 to -115
degree sector did not improve unchanged-task success: its measured checkpoints
were 88.0%, 84.5%, and 83.5%. The experiment-1 checkpoint-100352 policy remains
the strongest measured lineage.

**Lessons and limits:** Task success on the fixed 200-episode development panel,
not training reward or training success, supports policy-progress claims. The
baseline's six failures at step 100352 form a negative-angle cluster from
-122.1 to -145.4 degrees; five never entered tolerance and one held for only one
step. The step-120832 baseline retained that cluster and added a brief failure at
102.7 degrees. The focused transfer run recovered five of those six episode
seeds, but created many failures across other angles and had only 84.5% success
at the corresponding step. Its training success rose to 0.91 while measured task
success fell, so the proxy did not establish task progress. The baseline uses a
14-20 cm training-radius range while the official task spans 6-20 cm, making
coverage plausible but unproven. The evidence is single-seed for the unchanged
recipe, the target-geometry diagnostics do not establish a causal mechanism, and
unmeasured checkpoints remain unknown.

**Open questions:** It remains unresolved whether the residual negative-angle
failures reflect insufficient coverage, a learned representation limitation, or
another control limitation. The reproducibility and seed variance of the
near-objective unchanged PPO result are also unknown, as is whether another
training seed can reach or exceed the objective without the broad regression
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

## 045ec01f-613e-4cd7-9cac-4b3c512b0f94 / Experiment 3

**Result:** The fresh replication did not reproduce the near-objective
unchanged PPO policy. Its challenger checkpoints are not selected; the
experiment-1 `checkpoint-100352` policy remains the working and best-known
lineage, and the unchanged scientific recipe is kept for future development.

**Observed behavior:** Training completed 120,832 steps against a requested
120,000. The raw log's training success stayed at zero through 90,112 steps,
then reached 0.04 at 100,352 and 0.13 at 120,832; mean episode reward rose
from -7.3 at 1,024 steps to 107.4 at 120,832. On the same 200-episode
research-evaluation semantics, checkpoint-100352 achieved 29.5% (59/200) and
checkpoint-120832 achieved 44.5% (89/200). The later checkpoint therefore
improved on this development measurement, but both remained far below
experiment 1's 97.0% at the corresponding peak and 96.5% at its final
checkpoint. At the shared episode seeds, the replication recovered only seed
25 from experiment 1's failures at each corresponding checkpoint while losing
most of experiment 1's successes; the measured replication failures were
predominantly 500-step truncations. The other 22 checkpoints were not measured.

**Hypothesis assessment:** Contradicted for this replication. The confirmatory
hypothesis predicted that at least one measured checkpoint would reach 97%;
neither did, and the independent run was materially worse at both measured
positions. This supports the proposed seed-specific or unstable alternative
and weakens treating experiment 1's failure pattern as representative of the
unchanged recipe. One independent seed and two measured checkpoints do not
estimate the recipe's full variance or prove that another seed cannot reach the
objective.

**Interpretation:** The result is evidence of substantial seed sensitivity under
the tested unchanged recipe, not evidence that the task is unlearnable. The
late increase in training reward and training success did not correspond to
near-objective task success, reinforcing that proxy metrics cannot select a
policy. Because this was a fresh replication with no scientific code or
parameter intervention, the evidence does not identify a causal component
behind the variance. The experiment-1 policy remains the strongest measured
development artifact, but its 97.0% result is still below the 98% objective
and is not an official assessment.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`, `research/research_state.json`,
`research/training_logs/045ec01f-613e-4cd7-9cac-4b3c512b0f94/experiment-3-attempt-1.log`,
`research/evaluations/045ec01f-613e-4cd7-9cac-4b3c512b0f94/evaluation-045ec01f-613e-4cd7-9cac-4b3c512b0f94-experiment-3-checkpoint-100352-200ep-seed0-6ba3ba6d7654.json`,
`research/evaluations/045ec01f-613e-4cd7-9cac-4b3c512b0f94/evaluation-045ec01f-613e-4cd7-9cac-4b3c512b0f94-experiment-3-checkpoint-120832-200ep-seed0-6ba3ba6d7654.json`,
and the corresponding experiment-1 evaluation artifacts.
