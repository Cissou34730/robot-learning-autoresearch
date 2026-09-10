# Experiment log

| # | Operation / parent | Intervention | Checkpoint / panel results | Hypothesis assessment | Final decision |
|---:|---|---|---|---|---|
| 1 | Fresh baseline / parent fresh | Fresh baseline | 2 measured checkpoints; 22 unmeasured checkpoints; task_reference/task-reference-v1: 2 measurements | Partially supported. The baseline hypothesis was only to establish an initial baseline, and that objective was met: the recipe learned a policy with 98% measured task-reference success. The measurement does not show robust attainment of the human objective because the final checkpoint scored 97%, the best score is exactly at the threshold, and both measurements use the same development panel. Since this was not an intervention, the result does not support a causal claim about PPO settings, reward terms, or the training-range mismatch. | working checkpoint-100352; best known checkpoint-100352; code keep |
