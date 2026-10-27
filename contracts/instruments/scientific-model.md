# Scientific instruments: scientific model

This file is a part of the instrument contract. `contracts/instruments.md` lists
all parts.

## Scientific-model publication

Before other campaign work, `pi_workspace/scientific_model.md` must contain
four registers with content: `Established facts`, `Physical consequences`,
`Unknowns` and `Decision-relevant synthesis`. Each register is a level-two
heading (`##`) with its content under it. Topics in a register use level-three
headings (`###`).

The analyst writes the scientific model. The scientific model states physical
consequences and the evidence that separates them. It does not choose changes.

The synthesis is the last register. It selects the consequences and the
unknowns that are most likely to change the first decisions of the campaign.
For each selected item, it keeps the effect on decisions, the assumptions, the
source references and the evidence that separates the possibilities. The
startup session receives this register as the handoff. The PI also reads the
full scientific model at startup and selects the first direction.

After acceptance, the scientific model does not change for the campaign. Later
session records keep or change its important conclusions. The Runner checks
only that the file exists and that each required register is present and not
empty. It does not check the scientific quality. The PI judges the quality when
it uses the scientific model.
