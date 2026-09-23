# Research postmortems

## f332c079-6021-457e-be60-1f0804528d76 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned a useful reach-and-hold
policy, but its measured success plateaued below the human objective. The
proxy-peak checkpoint-100352 achieved 94.5% on each of two disjoint
200-episode research panels (378/400 pooled), and checkpoint-110592 tied it on
the later panel. The final checkpoint-120832 was lower at 93.75% pooled.

**Lessons and limits:** Training proxies identified the late learned regime but
did not establish the 98% task objective. The independent panel confirmed that
checkpoint-100352 was not merely selected by its first-panel score, while the
near-tie with checkpoint-110592 leaves no meaningful behavioral advantage for
the reward peak. Continued training past the proxy peak was not beneficial in
this run. These are development measurements under
`research_evaluation`, not the official benchmark; residual failure geometry
and the generalization of the 94.5% estimate remain open.

**Open questions:** Which learning-condition change can convert the remaining
roughly 5.5% failures into uninterrupted 2-second holds without sacrificing
coverage across the official target distribution?

## f332c079-6021-457e-be60-1f0804528d76 / Experiment 1

**Result:** The fresh baseline produced a strong but sub-target policy. The
best-supported checkpoint was checkpoint-100352 at 94.5% on both disjoint
research panels; checkpoint-110592 tied it on the second panel, while the final
checkpoint declined to 93.75% pooled.

**Observed behavior:** Checkpoint-100352 succeeded on 189/200 episodes for
seeds 4200 and 4400, for 378/400 distinct executions. Checkpoint-110592
succeeded on 189/200 episodes on seed 4400. Checkpoint-120832 succeeded on
188/200 and 187/200 on seeds 4200 and 4400. On the shared seed-4400 panel,
checkpoint-100352 and checkpoint-110592 had equal outcomes; checkpoint-100352
had a small advantage over checkpoint-120832 in pooled paired comparisons.
The training proxy rose through the late run but did not track a policy meeting
the 98% objective.

**Hypothesis assessment:** Partially supported. The baseline established
substantial learned task performance and a defensible late-run checkpoint, but
the measured policies remained below the objective of at least 196 successes
in 200 official episodes. The disjoint panel supports checkpoint-100352 as a
reliable development leader, not as independent proof of official success.

**Interpretation:** Checkpoint-100352 is the appropriate working and
best-known lineage because it has the strongest independent coverage and ties
the only tested reward-peak alternative. The unchanged scientific recipe
should be kept for provenance, checkpoint-110592 should remain available as a
late-run alternative, and further training or intervention should be treated
as a new experiment rather than inferred from this closure.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`; `research/results.jsonl`;
`research/checkpoints/challengers/f332c079-6021-457e-be60-1f0804528d76/experiment-1/inventory.json`;
the six evaluation artifacts under
`research/evaluations/f332c079-6021-457e-be60-1f0804528d76/`.
