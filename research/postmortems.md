# Research postmortems

## 7ab511e1-b514-43a0-891b-e3e4cdaff4d8 / Scientific strategy

**Direction:** The baseline establishes a near-target policy, so the next
investigation should address its measured short-radius blind spot rather than
replace the method speculatively. The strongest current lead is to broaden or
reweight training targets below 14 cm, with attention to the negative-angle
sector where the selected policy failed. The measurements do not establish that
the training distribution caused the failures, and they do not support a causal
claim about late training degradation.

**Lessons and limits:** The selected checkpoint-100352 reached 98% (196/200) on
the protected development task-reference panel, while checkpoint-95232 reached
96% and checkpoint-120832 reached 97%
(`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/task-reference-7ab511e1-b514-43a0-891b-e3e4cdaff4d8-experiment-1-checkpoint-100352-task-reference-v1.json`,
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/task-reference-7ab511e1-b514-43a0-891b-e3e4cdaff4d8-experiment-1-checkpoint-95232-task-reference-v1.json`, and
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/task-reference-7ab511e1-b514-43a0-891b-e3e4cdaff4d8-experiment-1-checkpoint-120832-task-reference-v1.json`). This is
development evidence, not the official result. The baseline proposal snapshot
did not state explicit expected or contradicting observations; its implicit
expectation was that the highest training-success checkpoint would be the
strongest measurement candidate. That expectation was partially supported:
checkpoint-100352 was the best of the three measured checkpoints, but the
training proxy did not establish task success and the later checkpoint scored
lower on the same panel. On checkpoint-100352, all four failures truncated at
500 steps and had radii 6.7-9.9 cm and angles -116 to -128 degrees. The training
environment samples radii 14-20 cm while the protected task samples 6-20 cm
(`robot_learning/scenario/environment.py` and
`robot_learning/benchmark/final_contract.py`), so the radius mismatch is a
testable explanation, not an established cause.

**Open questions:** Does including 6–14 cm targets improve the short-radius
failures without reducing performance elsewhere? Is the negative-angle
cluster a genuine geometry-dependent weakness or a small-panel artifact? Does
the selected checkpoint meet the 98% threshold on the separate official panel?

**Conditional next steps:** Close this baseline with checkpoint-100352 as the
working and best-known lineage, then make the next training experiment target
the observed short-radius gap, preferably by changing the training target
distribution while keeping the protected task unchanged. If a subsequent
development measurement still misses 98% with the same geometry pattern,
increase targeted coverage of the failing radius/angle region; if it reaches
the target without a material residual gap, request terminal assessment rather
than treating another proxy increase as progress.

## 7ab511e1-b514-43a0-891b-e3e4cdaff4d8 / Experiment 1

**Result:** The fresh PPO baseline produced a near-target policy. The measured
checkpoint-100352 is the best available candidate at 98% on the protected
development panel, but the experiment does not itself establish the official
objective.

**Observed behavior:** Training success rose from 0 through 70,656 steps to
0.93 at 95,232 and 0.97 at 100,352, then ended at 0.95 at 120,832
(`research/results.jsonl` and
`research/training_logs/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-1-attempt-1.log`).
The task-reference measurements scored checkpoint-95232 at 96% (192/200),
checkpoint-100352 at 98% (196/200), and checkpoint-120832 at 97% (194/200).
The four checkpoint-100352 failures were episodes 0, 10, 84, and 102; their
target radii were 6.7, 7.2, 9.9, and 9.4 cm and their target angles were
-116.4, -125.4, -122.9, and -127.9 degrees. All four truncated rather than
completing the hold. The later checkpoint retained those four failures and
added failures at approximately -132.4 and 169.1 degrees.

**Hypothesis assessment:** Partially supported. The baseline's implicit
expected observation—that the highest training-proxy checkpoint would be a
strong task candidate—matched the ranking of the three measured checkpoints,
and that checkpoint reached the 98% development-panel threshold. The
contradicting signal is that the final checkpoint fell to 97% despite similar
training success, and that four failures remained clustered in a short-radius
sector. These results show checkpoint selection and a near-target outcome, not
that the proxy caused task progress, that late training caused the decline, or
that the policy reaches 98% on the official panel.

**Interpretation:** The baseline demonstrates substantial learned reach-and-hold
behavior and identifies checkpoint-100352 as the practical parent for the next
investigation. The residual failures are consistent with insufficient training
coverage below 14 cm and with a geometry-specific weakness, but the fixed
200-episode panel and single training run cannot distinguish those explanations
or support causal attribution.

**Evidence inspected:** `research/results.jsonl`;
`research/training_logs/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-1-attempt-1.log`;
`research/checkpoints/challengers/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-1/inventory.json`;
the three task-reference artifacts under
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/`; and
`robot_learning/scenario/environment.py`.
