# Research postmortems

## dba19098-4f5e-4745-8212-dc17e14d5d84 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned a strong reach-and-hold
policy late in training. Checkpoint-100352 is the leading candidate: it achieved
196/200 (98.00%) on the disjoint research panel and 98.00% on the permanently
reused task-reference panel. The disjoint panel is the independent evidence for
this selection; the task-reference score is not independent confirmation.
Checkpoint-120832 is a close alternative at 194/200 (97.00%) on the same
disjoint panel. Neither development measurement is the official result.

**Lessons and limits:** Training proxies identify the useful late-training
region but do not rank the final policies reliably: 100352 and 120832 both
scored 94.375% on the first research panel despite different proxy values.
The selected policy usually reaches the target quickly and completes the
100-step hold, but the disjoint-panel failures include both failure to reach and
hold interruptions. The current evidence supports preserving the 100352
checkpoint and retaining 120832 as a reusable control, while the official
200-episode assessment remains necessary to determine whether the human
objective is met.

**Open questions:** Whether checkpoint-100352 reaches at least 196 successes on
the official frozen panel remains unknown. The residual failures' dependence on
target geometry and whether additional training improves or degrades the
late-training policy are also unresolved.

## dba19098-4f5e-4745-8212-dc17e14d5d84 / Experiment 1

**Result:** The fresh PPO baseline produced a learned policy that reaches the
campaign target level on a disjoint 200-episode development panel, with
checkpoint-100352 performing best among the measured late checkpoints.

**Observed behavior:** Checkpoint-100352 scored 151/160 (94.375%) on the first
research panel and 196/200 (98.00%) on the disjoint episodes 5200-5399. Its
pooled research result was 347/360 (96.39%). The fixed task-reference panel
returned 196/200 (98.00%), but that panel was reused and cannot independently
confirm a model selected using it. Checkpoint-120832 scored 151/160 and 194/200
(97.00%) on the corresponding panels, with only two discordant wins favoring
100352 across the 360 paired research episodes. The 100352 disjoint-panel
failures include both episodes that never reached a successful hold and episodes
whose hold was interrupted; successful episodes generally completed the
100-step hold in roughly 105-120 control steps.

**Hypothesis assessment:** The baseline question was to establish an initial
reference rather than test a causal intervention. It is partially supported:
the run establishes a strong learned-policy reference and a late checkpoint
selection, but it does not establish official objective attainment or explain
the residual failures.

**Expected observation disposition:** not tested - This fresh baseline recorded
no frozen expected observation; the measurements instead established the
late-checkpoint performance and remaining uncertainty.

**Interpretation:** Checkpoint-100352 is the best-supported working and
best-known policy available from this experiment. Its 98.00% disjoint
development result is encouraging and independently addresses the selection
concern, but it is not a final benchmark result. The unchanged scientific
recipe should be kept, checkpoint-120832 should remain available as a close
alternative, and the next campaign decision should separately determine whether
to submit checkpoint-100352 for official assessment or run another experiment.

**Evidence inspected:** research/brief.md;
research/checkpoints/challengers/dba19098-4f5e-4745-8212-dc17e14d5d84/experiment-1/inventory.json;
research/evaluations/dba19098-4f5e-4745-8212-dc17e14d5d84/evaluation-dba19098-4f5e-4745-8212-dc17e14d5d84-experiment-1-checkpoint-100352-200ep-seed5200-f48545f83637.json;
research/evaluations/dba19098-4f5e-4745-8212-dc17e14d5d84/evaluation-dba19098-4f5e-4745-8212-dc17e14d5d84-experiment-1-checkpoint-120832-200ep-seed5200-f48545f83637.json;
research/evaluations/dba19098-4f5e-4745-8212-dc17e14d5d84/task-reference-dba19098-4f5e-4745-8212-dc17e14d5d84-experiment-1-checkpoint-100352-task-reference-v1.json;
research/research_state.json
