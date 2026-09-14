# Research postmortems

## f571cc16-ae35-4a96-9bb1-e618052af336 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned the reach-and-hold behavior late in training. The best measured checkpoint, `checkpoint-100352`, achieved 98.0% on both the researcher evaluator and the independent protected task-reference panel. Later training did not preserve that level, so checkpoint selection matters more than the final training step for this run.

**Lessons and limits:** Training proxies and reward identified the onset of useful behavior but did not establish task success: the reward peak at step 86,016 measured 95.5% and 94.0% on the two development panels, while the proxy peak near steps 97,280-100,352 coincided with 98.0% measured success. The evidence is limited to one training run and 200-episode development panels; it does not establish the official 200-episode result or explain the remaining failures. Sources: `research/results.jsonl`, `research/evaluations/f571cc16-ae35-4a96-9bb1-e618052af336/`, and the queried experiment-1 training log.

**Open questions:** Whether the selected checkpoint reaches the human objective on the distinct official panel, and whether its residual failures are systematic outside the measured development panels, remain unresolved.

## f571cc16-ae35-4a96-9bb1-e618052af336 / Experiment 1

**Result:** The baseline produced a strong candidate, with the best measured development performance at the objective level.

**Observed behavior:** Training completed 120,832 steps. The logged mean episode reward rose from -24.5 at step 5,120 to 163.9 at step 86,016, then declined to 117.3 at step 100,352 and 112.0 at the final checkpoint. The training success proxy rose from 0 to 0.97 by steps 97,280-100,352 and was 0.95 at step 120,832. Research evaluation success was 95.5% at checkpoint 86,016, 98.0% at checkpoint 100,352, and 96.5% at checkpoint 120,832. Protected task-reference success was respectively 94.0%, 98.0%, and 97.0%. At checkpoint 100,352, the researcher evaluator had four failures, each missing the complete hold; the task-reference panel had four failures, all reaching the 500-step limit, with target angles from -127.9 to -116.4 degrees and radii from 6.73 to 9.91 cm.

**Hypothesis assessment:** Supported as a baseline-establishment result, and partially supported as evidence of progress toward the human objective: one saved checkpoint reached 98.0% on both development instruments, but the later checkpoint regressed and no development panel is the official assessment. The baseline does not establish that the objective is met on the official panel.

**Interpretation:** Measured task performance, rather than the reward or training proxy alone, identifies checkpoint 100352 as the most useful artifact from this run. The agreement between the researcher evaluator and protected task-reference panel supports freezing that checkpoint for official assessment, while the late-training regression argues against selecting the final checkpoint. The failure concentration is a diagnostic signal, not evidence that all official-task failures have the same cause.

**Evidence inspected:** `research/results.jsonl`; `research/evaluations/f571cc16-ae35-4a96-9bb1-e618052af336/evaluation-f571cc16-ae35-4a96-9bb1-e618052af336-experiment-1-checkpoint-86016-200ep-seed1729-6ba3ba6d7654.json`; `research/evaluations/f571cc16-ae35-4a96-9bb1-e618052af336/evaluation-f571cc16-ae35-4a96-9bb1-e618052af336-experiment-1-checkpoint-100352-200ep-seed1729-6ba3ba6d7654.json`; `research/evaluations/f571cc16-ae35-4a96-9bb1-e618052af336/evaluation-f571cc16-ae35-4a96-9bb1-e618052af336-experiment-1-checkpoint-120832-200ep-seed1729-6ba3ba6d7654.json`; the three corresponding `task-reference-...json` artifacts; and the experiment-1 training log queried for steps 5,120-120,832.
