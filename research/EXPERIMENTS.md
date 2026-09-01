# Experiment log

| # | Date | Change | Hypothesis | Candidate success | Seeds passed | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-09-01 | Fresh baseline | Establish the initial baseline for the human-defined objective. | 66.0 | - | measured as requested; awaiting researcher analysis |
| 2 | 2026-09-01 | Set HOLD_EXIT_FORFEIT_FRACTION to 0.5 so leaving the tolerance band forfeits half of the accumulated hold-progress reward. | With no forfeiture when leaving the tolerance band, PPO can abandon an almost-complete hold without losing the accumulated hold reward, limiting reliable reach-and-hold behavior. | 76.0 | - | measured as requested; awaiting researcher analysis |
