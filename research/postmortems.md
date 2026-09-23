# Research postmortems

## f332c079-6021-457e-be60-1f0804528d76 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned a useful reach-and-hold
policy, but its measured success plateaued at 94.5% (378/400) on two disjoint
research panels. The working lineage's 22 failures split evenly between never
entering tolerance and entering tolerance but holding for fewer than 25 steps;
failure rates were not confined to the shortest target-radius bin.

**Lessons and limits:** The late proxy peak was independently reproduced, while
the reward-peak alternative tied it and the final checkpoint declined to 93.75%
pooled. The baseline reward therefore supports useful reach behavior but does
not establish reliable uninterrupted holding or the 98% objective. These are
development measurements under `research_evaluation`; the failure split, target
geometry summaries, and 94.5% estimate remain limited evidence rather than an
official result or a causal explanation.

**Open questions:** Whether explicitly penalizing exits from tolerance reduces
brief hold failures without increasing reach failures or reducing coverage
across the official target distribution remains unresolved. The contribution
of the never-reached failures to the remaining performance gap is also
uncertain.

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
