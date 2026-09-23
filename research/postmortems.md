# Research postmortems

## c17f2d19-015e-4182-96af-e2b91cb5e92e / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned a strong reach-and-hold
policy. Checkpoint-100352 is the best-supported candidate: it achieved 199/200
successes across two disjoint research-evaluation panels and 98% on the fixed
task-reference panel. The latter panel was used during selection and is not
independent confirmation, but the disjoint research panel preserved the
candidate's near-objective behavior. The official benchmark is therefore
warranted for checkpoint-100352; development measurements do not themselves
establish the human objective.

**Lessons and limits:** Training reward and proxy success identified learning
progress but did not rank the final policies reliably: the reward peak at
checkpoint-86016 measured 92% on research evaluation and 94% on task reference,
whereas checkpoint-100352 was stronger. Continuing to checkpoint-120832 did not
improve the selected policy: it measured 197/200 on the two research panels and
97% on the fixed task-reference panel. The paired research comparison favored
checkpoint-100352 by 2-0 discordant outcomes over 200 distinct episodes.
These results establish saved-policy behavior under the recorded development
instruments, not causal attribution or an official result.

**Open questions:** The fixed official 200-episode assessment remains unresolved.
The few observed failures and the extent of any residual sensitivity to target
geometry are not sufficient to diagnose a further intervention before that
assessment.

## c17f2d19-015e-4182-96af-e2b91cb5e92e / Experiment 2

**Result:** The baseline produced a near-objective policy; checkpoint-100352 was
selected as working and best-known, with checkpoint-120832 retained as a
measured alternative, and the unchanged recipe was kept.

**Observed behavior:** Of 24 candidates, three were measured. Checkpoint-86016
scored 92/100 on research evaluation and 94% on the fixed task-reference panel.
Checkpoint-100352 scored 99/100 and then 100/100 on disjoint research panels,
plus 98% on the fixed task-reference panel. Checkpoint-120832 scored 97/100
and then 100/100 on the same research panels, plus 97% on task reference.
The pooled research results were 199/200 for checkpoint-100352 and 197/200 for
checkpoint-120832; the latest checkpoint-100352 artifact records 100 successful
holds with no hold interruptions.

**Hypothesis assessment:** Supported as a baseline establishment, within the
scope of the unchanged recipe and development measurements. The evidence shows
substantial progress toward the human objective and supports selecting a saved
policy, but it does not by itself establish the official 98% result or provide
causal evidence about why the baseline learned.

**Interpretation:** Checkpoint-100352 is the strongest available policy because
it meets the development threshold on the reused task-reference panel and
retains 100% success on a disjoint research panel, while checkpoint-120832 is
slightly weaker in pooled development evidence. The task-reference score cannot
serve as independent confirmation because it informed selection; the disjoint
research result is the independent persistence check available in this
campaign. The evidence is sufficient to freeze checkpoint-100352 for terminal
assessment, not to claim that the objective has already been reached.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/c17f2d19-015e-4182-96af-e2b91cb5e92e/experiment-2/inventory.json`;
`research/evaluations/c17f2d19-015e-4182-96af-e2b91cb5e92e/evaluation-c17f2d19-015e-4182-96af-e2b91cb5e92e-experiment-2-checkpoint-100352-100ep-seed10100-f48545f83637.json`;
`research/evaluations/c17f2d19-015e-4182-96af-e2b91cb5e92e/evaluation-c17f2d19-015e-4182-96af-e2b91cb5e92e-experiment-2-checkpoint-120832-100ep-seed10100-f48545f83637.json`.
