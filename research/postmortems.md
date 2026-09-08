# Research postmortems

## e37e91cd-4511-480f-9dd4-48082d9757c3 / Scientific strategy

**Direction:** Improve robustness on the official 6-20 cm target distribution by
extending training coverage to the inner-radius targets, while using
`checkpoint-100352` as the current parent.

**Lessons and limits:** The fresh PPO baseline learned a strong reach-and-hold
policy: its training proxy rose from 0 to 0.97 by 100,352 steps. The
research-evaluation panels pooled to 98.0% for `checkpoint-100352`, and the
independent protected development panel reached 98.0% (196/200). The later
`checkpoint-120832` regressed to 97.33% and 97.0% respectively. The training
environment samples 14-20 cm, whereas the official task samples 6-20 cm; five
of the six protected-panel failures for `checkpoint-100352` were inner-radius
targets between 6.7 and 10.0 cm. These are development-panel observations,
not an official verdict or causal evidence for the distribution gap.

**Open questions:** Whether exposing the learner to the full official radius
range improves the inner-radius failures without reducing outer-radius
performance; whether the remaining failures reflect a narrow angular
generalization gap; and whether the 98.0% development result has enough margin
to generalize beyond the fixed panel.

**Conditional next steps:** Continue from `checkpoint-100352` with a changed
training target distribution covering the official 6-20 cm range, then
remeasure both the research evaluator and the protected task-reference panel.
Use a terminal benchmark only after development evidence provides a stronger
margin or no more useful policy improvement is identified.

## e37e91cd-4511-480f-9dd4-48082d9757c3 / Experiment 1

**Result:** The fresh baseline produced a useful policy, with
`checkpoint-100352` outperforming the final checkpoint and meeting 98.0% on
both pooled research evaluation and the protected development panel. It is
selected as the working and best-known lineage for continued development.

**Observed behavior:** The training proxy improved from 0 at 5,120 steps to
0.97 at 100,352 steps, then ended at 0.95 after 120,832 steps. On identical
research-evaluation semantics, `checkpoint-100352` scored 97.0% on the
200-episode seed-0 panel and 98.5% on the 400-episode seed-200 panel
(98.0% pooled), while `checkpoint-120832` scored 96.5% and 97.75%
(97.33% pooled). On the fixed protected task-reference panel, the scores were
98.0% and 97.0%. The six `checkpoint-100352` task-reference failures were
truncated episodes; five had target radii from 6.7 to 10.0 cm and negative
angles near -116 to -132 degrees, and one was an outer-radius target at about
17.9 cm and 169 degrees.

**Hypothesis assessment:** This automatic baseline had no
intervention-specific `expected_observation` or `contradicting_observation`;
the result is therefore a reference rather than a test of a changed recipe.
It supports the feasibility of learning the task and supports policy progress
toward the 98% objective, but the protected score is only a fixed
development-panel result and does not establish the official objective.
Checkpoint selection is supported by the consistent advantage of
`checkpoint-100352` over the later checkpoint; no causal claim about why the
regression occurred is warranted.

**Interpretation:** The best measured checkpoint should be preserved, but the
near-threshold result and concentration of failures below the training
radius range make full-radius training the most useful next intervention.
Repeated measurement of the same development panels would add less value than
testing that changed recipe.

**Evidence inspected:** `research/brief.md`,
`research/results.jsonl`, `research/training_logs/e37e91cd-4511-480f-9dd4-48082d9757c3/experiment-1-attempt-1.log`,
the four research-evaluation artifacts and two task-reference artifacts under
`research/evaluations/e37e91cd-4511-480f-9dd4-48082d9757c3/`,
`robot_learning/scenario/environment.py`,
`robot_learning/scenario/evaluation.py`, and
`robot_learning/benchmark/reference_evaluation.py`.
