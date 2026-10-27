# Scientific instruments: scientific model

This file is a part of the instrument contract. `contracts/instruments.md` lists
all parts.

## Scientific-model publication

Before other campaign work, `pi_workspace/scientific_model.md` must contain
four substantive registers: `Established facts`, `Physical consequences`,
`Unknowns` and `Decision-relevant synthesis`. Each register is a level-two
heading (`##`) with its content under it. Topics in a register use level-three
headings (`###`).

The analyst writes the scientific model. The scientific model states physical
consequences and the discriminating evidence between them. It selects no
intervention.

The synthesis is the last register. It selects the consequences and the
unknowns that are most likely to change the first decisions of the campaign.
These decisions include the design and the interpretation of the first
measurements. For each selected item, it keeps the decision relevance, the
assumptions, the source references and the discriminating evidence.

The synthesis also includes the invariances of the definitions. For each
invariance, it states which outcomes the invariance predicts to be equal when
the episode start and the target are transformed the same way. A measured difference between such
outcomes, beyond sampling variation, is evidence about the policy, not about
the task.

The startup session receives the synthesis as the handoff. The PI also reads
the full scientific model in the startup session and selects the initial
direction.

After acceptance, the scientific model stays fixed for the campaign. Later
session records preserve or revise its consequential conclusions. The Runner
checks only that the file exists and that each required register is present
and not empty. It does not check scientific adequacy. The PI judges the
soundness of the scientific model when the PI uses it.
