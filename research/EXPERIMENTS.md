# Experiment log

| # | Date | Change | Hypothesis | Candidate success | Seeds passed | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-08-31 | Fresh baseline | Establish the initial baseline for the human-defined objective. | 66.5 | - | measured as requested; awaiting researcher analysis |
| 2 | 2026-08-31 | Bias the training target-radius sampler toward the difficult outer workspace: sample 14-20 cm targets 70% of the time and sample the full configured range 30% of the time, while preserving the same angle sampling and official task behavior. | The baseline's outer-workspace reach failures are caused by insufficient learning exposure to 14-20 cm targets, not by an inability to hold once the target is reached. A plausible alternative is that the failures are primarily angle- or optimizer-dependent; comparing outer-radius reach and hold diagnostics against the fresh baseline will distinguish these explanations. | 21.75 | - | measured as requested; awaiting researcher analysis |
