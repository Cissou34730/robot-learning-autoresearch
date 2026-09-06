# Experiment log

| # | Date | Operation | Hypothesis | Candidate success | Seeds passed | Verdict |
|---:|---|---|---|---:|---:|---|
| 1 | 2026-09-04 | Fresh baseline | Establish the initial baseline for the human-defined objective. | 97.0 | - | researcher selected checkpoint-100352 |
| 2 | 2026-09-06 | Modify the researcher-owned training environment to draw half of training targets from the observed -150 to -110 degree sector and half uniformly over the full angular range, while leaving the official evaluation distribution and the 14-20 cm training radius unchanged. | Oversampling the observed -150 to -110 degree failure sector during training, while retaining uniform samples over the full angular range, will improve negative-angle reach reliability and raise the transferred policy above the 97.0% baseline without reducing hold stability elsewhere. | - | - | researcher selected working as working |
