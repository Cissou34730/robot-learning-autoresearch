# Experiment log

| # | Operation / parent | Intervention | Checkpoint / panel results | Hypothesis assessment | Final decision |
|---:|---|---|---|---|---|
| 1 | Fresh baseline / parent fresh | Fresh baseline | 2 measured checkpoints; 21 unmeasured checkpoints; research_evaluation/research_evaluation: 2 measurements; task_reference/task-reference-v1: 2 measurements | Partially supported. The baseline established nontrivial learned task behavior and a clear training signal, but it did not establish a policy satisfying the human objective. The later training-proxy increase was not accompanied by higher measured task success, so proxy improvement is insufficient evidence of late policy progress. The small cross-panel advantage of `checkpoint-110592` supports selecting it as the current development lineage, but does not establish a meaningful causal or generalization superiority. | working checkpoint-110592; best known checkpoint-110592; code keep |
