# Research postmortems

## f592bc9d-cc2f-47de-a506-a4882760818c / Experiment 1

**Result:** Fresh PPO baseline reached 66.0% (132/200) on the research evaluation at checkpoint-120832 and 55.0% (110/200) on task-reference-v1, far below the 98% objective.
**Observed behavior:** On the identical research panel, checkpoint-120832 improved only 1.5 percentage points over checkpoint-86016 (66.0% versus 64.5%); final-checkpoint successes reached and held the target in about 13 steps, while all 68 research-panel failures targeted radii from 14–20 cm.
**Interpretation:** The baseline reliably solves shorter reaches but has a systematic long-range workspace failure; additional training to 120,832 steps produced only a marginal gain and does not justify an official benchmark request.
**Evidence inspected:** `research/evaluations/f592bc9d-cc2f-47de-a506-a4882760818c/evaluation-f592bc9d-cc2f-47de-a506-a4882760818c-experiment-1-checkpoint-86016-200ep-seed1000-41299d1f0507.json`, `research/evaluations/f592bc9d-cc2f-47de-a506-a4882760818c/evaluation-f592bc9d-cc2f-47de-a506-a4882760818c-experiment-1-checkpoint-120832-200ep-seed1000-41299d1f0507.json`, `research/evaluations/f592bc9d-cc2f-47de-a506-a4882760818c/task-reference-f592bc9d-cc2f-47de-a506-a4882760818c-experiment-1-checkpoint-120832-task-reference-v1.json`
