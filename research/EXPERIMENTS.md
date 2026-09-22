# Experiment log

| # | Operation / parent | Intervention | Checkpoint / panel results | Hypothesis assessment | Final decision |
|---:|---|---|---|---|---|
| 1 | Fresh baseline / parent fresh | Fresh baseline | 3 measured checkpoints; 21 unmeasured checkpoints; research_evaluation/research_evaluation: 3 measurements; task_reference/task-reference-v1: 3 measurements | The baseline measurement hypothesis was partially supported. The late high-training-success checkpoint (`checkpoint-100352`) performed better than the earlier proxy-peak checkpoint and the final checkpoint on both measured panels, while continued training to `checkpoint-120832` weakened task-reference performance. The conclusion is limited because the task-reference panel was reused for selection and the research evaluation covered only 100 episodes; neither is the official 200-episode benchmark. | working checkpoint-100352; best known checkpoint-100352; code keep |
