# Research postmortems

## aceb9fe8-b43f-4f58-b5ff-dab4ce7434b7 / Scientific strategy

**Direction:** Freeze the strongest measured baseline checkpoint and use the official benchmark to resolve whether the campaign objective is met. No intervention or mechanism has been tested yet, so no scientific mechanism has been eliminated.

**Lessons and limits:** The fresh PPO baseline learned substantial task behavior: its training proxy rose from 0 at 5,120 steps to 0.97 at 100,352 steps, but this proxy is not task evidence (`research/results.jsonl`, `research/brief.md`). On the fixed 200-episode task-reference panel, `checkpoint-100352` achieved 196/200 (98.0%), while the final `checkpoint-120832` achieved 194/200 (97.0%) (`research/evaluations/aceb9fe8-b43f-4f58-b5ff-dab4ce7434b7/task-reference-aceb9fe8-b43f-4f58-b5ff-dab4ce7434b7-experiment-1-checkpoint-100352-task-reference-v1.json`, `research/evaluations/aceb9fe8-b43f-4f58-b5ff-dab4ce7434b7/task-reference-aceb9fe8-b43f-4f58-b5ff-dab4ce7434b7-experiment-1-checkpoint-120832-task-reference-v1.json`). On this panel, the peak checkpoint's four failures all had radii below 10 cm and angles from -116 to -128 degrees; the final checkpoint retained those failures and added two more. This is descriptive finite-panel evidence, not a causal explanation or a population guarantee. The task-reference panel is development evidence and is not the official benchmark.

**Open questions:** Whether `checkpoint-100352` reaches the 98% objective under the official benchmark; whether the late-training drop from 98.0% to 97.0% is repeatable; and whether the small-radius, negative-angle failures persist outside this panel.

**Conditional next steps:** No further development measurement is justified before resolving the objective with the frozen `checkpoint-100352`; request the terminal official benchmark. Do not treat the training proxy or this development panel as the official result.

## aceb9fe8-b43f-4f58-b5ff-dab4ce7434b7 / Experiment 1

**Result:** The baseline produced a strong development candidate at 100,352 steps, but the final checkpoint was slightly worse on the same task-reference panel; the best measured candidate is checkpoint-100352.

**Observed behavior:** This automatic baseline has no researcher-authored `expected_observation` or `contradicting_observation`; its recorded hypothesis was only to establish an initial baseline (`research/results.jsonl`). Training completed 120,832 steps, with a training proxy of 0.97 at 100,352 steps and 0.95 at the final checkpoint (`research/brief.md`, `research/results.jsonl`). On the identical 200-episode task-reference panel, checkpoint-100352 scored 196 successes (98.0%) and checkpoint-120832 scored 194 successes (97.0%). The peak checkpoint failed episodes 0, 10, 84, and 102; all four targets were below 10 cm radius and between -116 and -128 degrees. The final checkpoint failed those same four episodes plus episodes 121 and 152. Both measurements are development task-reference measurements, not official benchmark results.

**Hypothesis assessment:** Supported for the limited baseline-establishment purpose: the run produced a measurable policy with near-threshold task performance. The absence of proposal-level expected and contradicting observations is an automatic-baseline protocol property, not evidence for or against a mechanism. The measured policy progress is partially supported by task-reference performance, but the human objective remains unverified because the panel is finite and non-official. The peak-versus-final difference is an observed within-run checkpoint comparison; it does not establish that additional training caused the regression.

**Interpretation:** The baseline is sufficiently promising to freeze its best measured checkpoint for terminal assessment. The shared failure pattern suggests a useful diagnostic lead around short-radius targets at negative angles, while the two additional final-checkpoint failures indicate that later training did not improve this measured panel. Neither pattern supports a causal claim about the failure mechanism.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/evaluations/aceb9fe8-b43f-4f58-b5ff-dab4ce7434b7/task-reference-aceb9fe8-b43f-4f58-b5ff-dab4ce7434b7-experiment-1-checkpoint-100352-task-reference-v1.json`; `research/evaluations/aceb9fe8-b43f-4f58-b5ff-dab4ce7434b7/task-reference-aceb9fe8-b43f-4f58-b5ff-dab4ce7434b7-experiment-1-checkpoint-120832-task-reference-v1.json`; `research/scenario.md`.
