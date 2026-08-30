# Experiment log

| # | Date | Change | Hypothesis | Candidate success | Seeds passed | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-08-30 | Fresh baseline | Establish the initial baseline for the human-defined objective. | 66.5 | - | measured as requested; awaiting researcher analysis |
| 2 | 2026-08-30 | Keep the training radius range at 6-20 cm and retain uniform angle sampling, but sample the radius as min_radius + sqrt(U) * (max_radius - min_radius) so outer targets are presented more frequently while preserving the full task distribution support. | The baseline's large-target reachability failure is primarily caused by insufficient learning coverage of the outer workspace: uniform-radius sampling provides much less experience at 17-20 cm than at easier inner radii, so PPO does not learn reliable outer-target motions within the fixed budget. | 97.0 | - | measured as requested; awaiting researcher analysis |
