# Research postmortems

No experiments recorded.

## 5d4e159f-7fae-4a25-b885-b127042e894e / Scientific strategy

**Direction:** Establish a reliable baseline for the reach-and-hold objective, then improve robustness from the strongest measured checkpoint rather than selecting by training reward alone.

**Lessons and limits:** The fresh baseline learned the task late in training, reaching 97.0% on the research panel and 98.0% on the fixed task-reference panel at 100,352 steps. The later 120,832-step checkpoint declined to 96.5% and 97.0% on those same panels, so the measured peak is preferable to the final checkpoint. On the task-reference panel, the 100,352-step failures were concentrated at near-base targets with angles from about -116 to -128 degrees; this is a useful failure-mode clue, not evidence that all such targets fail. The research evaluation exposes no target geometry, and both panels are development evidence rather than the official verdict.

**Open questions:** Whether the 100,352-step checkpoint reaches the 98% objective on the official panel remains unknown. It is also unresolved whether the persistent negative-angle failures reflect a systematic control/coverage weakness or ordinary policy and panel variation, and whether additional training would improve them or reproduce the late-training decline.

**Conditional next steps:** If the official result is below target, investigate robustness for the near-base, negative-angle region and prefer the 100,352-step lineage as the starting point; compare any later checkpoint against it rather than assuming more steps help. If a subsequent run changes the method, preserve this checkpoint as the baseline for development comparisons.

## 5d4e159f-7fae-4a25-b885-b127042e894e / Experiment 1

**Result:** The fresh baseline produced a strong but not yet officially validated policy. Checkpoint 100,352 is the measured peak and is selected for continued work.

**Observed behavior:** Training success rose from 0 through the first 70,656 steps, reached 0.97 at 100,352 steps, and was 0.95 at 120,832 steps. On the same 200-episode research panel, checkpoint 100,352 succeeded on 194 episodes (97.0%) and checkpoint 120,832 on 193 (96.5%); the later checkpoint added one failure and did not recover any of the earlier failures. On the fixed task-reference panel, the checkpoints achieved 98.0% and 97.0%, respectively. The earlier checkpoint had four failures, all truncated at 500 steps with target angles between -116 and -128 degrees and target radii between 6.7 and 9.9 cm. The later checkpoint retained those four failures and added two more. Neither result is the official benchmark.

**Hypothesis assessment:** The baseline expectation of establishing a competent initial policy was supported: learning was substantial and the best checkpoint approached the objective. The contradicting observation is that the completed 120,000-step run did not improve monotonically and both development results remained below the objective on at least one panel. Because this was a baseline with no intervention, the evidence does not attribute the outcome to a method change or establish reproducibility.

**Interpretation:** The decline after the 100,352-step peak makes checkpoint selection consequential and argues against continuing from the final checkpoint by default. The paired research-panel comparison favors 100,352 by one episode, while the task-reference comparison favors it by two; together these are sufficient to choose the earlier policy for lineage, but not to claim generalization or explain causality. The persistent task-reference failures suggest a targeted angular/near-base robustness question for future training.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/evaluations/5d4e159f-7fae-4a25-b885-b127042e894e/evaluation-5d4e159f-7fae-4a25-b885-b127042e894e-experiment-1-checkpoint-100352-200ep-seed0-d72ec900e7de.json`; `research/evaluations/5d4e159f-7fae-4a25-b885-b127042e894e/evaluation-5d4e159f-7fae-4a25-b885-b127042e894e-experiment-1-checkpoint-120832-200ep-seed0-d72ec900e7de.json`; `research/evaluations/5d4e159f-7fae-4a25-b885-b127042e894e/task-reference-5d4e159f-7fae-4a25-b885-b127042e894e-experiment-1-checkpoint-100352-task-reference-v1.json`; `research/evaluations/5d4e159f-7fae-4a25-b885-b127042e894e/task-reference-5d4e159f-7fae-4a25-b885-b127042e894e-experiment-1-checkpoint-120832-task-reference-v1.json`.
