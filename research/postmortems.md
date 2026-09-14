# Research postmortems

## 045ec01f-613e-4cd7-9cac-4b3c512b0f94 / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success, or 196/200
episodes, on the official full-range reach-and-hold task. Unchanged fresh PPO
produced a useful but below-objective policy: its best measured development
checkpoint reached 97.0% (194/200) at step 100352, while the later step-120832
checkpoint reached 96.5%. A fresh replication of the same recipe reached only
29.5% and 44.5% at those two positions, so the near-objective result is not a
reliable estimate of the recipe's typical outcome. The experiment-1
checkpoint-100352 policy remains the strongest measured lineage.

**Lessons and limits:** Task success on the fixed 200-episode development panel,
not training reward or training success, supports policy-progress claims. The
best unchanged policy's six failures cluster at negative target angles from
-122.1 to -145.4 degrees, but the evidence does not identify whether coverage,
representation, or control causes them. The training distribution covers only
14-20 cm although the official task covers 6-20 cm. Focused transfer toward the
negative-angle sector recovered five of those six episode seeds but regressed
many other cases, reaching 84.5% at the corresponding checkpoint; its rising
training proxies therefore did not establish task progress. The full-angle
policy I/O and task mechanics are shared across these comparisons, while
training-distribution changes and fresh-seed effects remain confounded with
learning dynamics. Measurements cover only selected checkpoints and one fixed
200-episode development panel.

**Open questions:** It remains unresolved how much of the result variance comes
from initialization and whether another training design can address the
negative-angle failures without broad regression. Experiment 4 did not improve
the unchanged-task panel after exposing the transfer policy to the full
official radius range, and the unchanged failure set includes both short and
long radii. No development policy has reached the official objective because
the strongest result is 194/200 on a development panel rather than the
terminal assessment.

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

## 045ec01f-613e-4cd7-9cac-4b3c512b0f94 / Experiment 4

**Result:** Expanding the training target-radius range from 14-20 cm to the
official 6-20 cm range did not produce measured task progress. The working
experiment-1 checkpoint remains the strongest measured policy, so experiment 4
is not selected and the parent scientific recipe is restored.

**Observed behavior:** Training completed 120,832 steps against a requested
120,000. Training proxies were high at the comparable checkpoint: training
success was 0.99 and mean episode reward was 113.72 at step 100,352. At the
endpoint they declined to 0.94 and 110.99. Research evaluation on 200 episodes
measured 97.0% (194/200) at both experiment-4 checkpoints 100,352 and 120,832,
matching the working policy's 97.0% on the same panel. Both challengers had zero
paired wins and zero losses against working. All three policies failed the same
six episode seeds (11, 25, 111, 167, 171, and 188), and all six failures
truncated at 500 steps. The failure targets covered radii from 6.00 to 16.63
cm and angles from -122.1 to -145.4 degrees. Diagnostics showed small changes
in approach behavior for some failures, including brief tolerance entry for
seeds 111 and 188 under experiment 4, but no binary task successes were
recovered. The remaining 22 experiment-4 checkpoints were not measured.

**Hypothesis assessment:** Weakened. The exploratory question predicted that
full-radius training could improve the parent without the broad regression of
the angle-focused transfer. Neither measured challenger improved over the
97.0% parent, and the identical failure set does not support radial coverage
as a sufficient explanation for the residual failures. The result does not
prove that radius coverage cannot help under another training design or
initialization. It also does not establish that the negative-angle pattern is
caused by angle coverage alone, because this run changed training distribution
and continued from the parent.

**Interpretation:** The measured policy outcome is unchanged despite strong
training proxies, reinforcing that those proxies cannot select a policy.
Failures at both the shortest and longer target radii within the negative-angle
cluster weaken a radius-only account, while the unchanged panel result gives no
evidence that this transfer intervention advances the human objective. The
working policy remains useful for further development but is below the 98%
objective and is not ready for terminal assessment.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`, `research/research_state.json`,
`research/evaluations/045ec01f-613e-4cd7-9cac-4b3c512b0f94/evaluation-045ec01f-613e-4cd7-9cac-4b3c512b0f94-experiment-4-checkpoint-100352-200ep-seed0-ffdccdbf3357.json`,
`research/evaluations/045ec01f-613e-4cd7-9cac-4b3c512b0f94/evaluation-045ec01f-613e-4cd7-9cac-4b3c512b0f94-experiment-4-checkpoint-120832-200ep-seed0-ffdccdbf3357.json`,
and `research/evaluations/045ec01f-613e-4cd7-9cac-4b3c512b0f94/evaluation-045ec01f-613e-4cd7-9cac-4b3c512b0f94-experiment-4-working-200ep-seed0-ffdccdbf3357.json`.
