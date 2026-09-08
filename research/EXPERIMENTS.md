# Experiment log

| # | Operation / parent | Intervention | Checkpoint / panel results | Hypothesis assessment | Final decision |
|---:|---|---|---|---|---|
| 1 | Fresh baseline / parent fresh | Fresh baseline | 3 measured checkpoints; 21 unmeasured checkpoints; research_evaluation/research_evaluation: 3 measurements | The baseline objective was partially supported: learning produced a policy at the 98% development threshold, but the result does not establish performance on the official task distribution. The repeated failures indicate a stable residual blind spot on this development panel, while their exact repetition across checkpoints limits what can be inferred about broader-distribution failure modes. The training trajectory also does not show continued improvement after the proxy peak. The evidence is sufficient to choose a candidate and request the authoritative benchmark, but not to claim official success. | working checkpoint-100352; best known checkpoint-100352; code keep |
