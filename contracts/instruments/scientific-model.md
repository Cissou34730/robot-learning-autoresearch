# Scientific instruments: scientific model

Part of the instrument contract indexed in `contracts/instruments.md`.

## Scientific-model publication

Before other campaign work, `pi_workspace/scientific_model.md` must contain
substantive `Established facts`, `Physical consequences`, `Unknowns`, and
`Decision-relevant synthesis` registers.
Each register is a level-two heading (`##`) with its content under it. Topics
inside a register use level-three headings (`###`).
The preliminary analyst writes the model. The model states physical
consequences and the evidence that discriminates between them. It selects no
intervention.
The synthesis is the final register. It selects the consequences and unknowns
most likely to change the first campaign decisions. For each selected item, it
keeps the decision relevance, the assumptions, the source references, and the
discriminating evidence. Startup receives this register as the handoff. The PI
also reads the whole model at startup and selects the initial direction.
After acceptance, the model remains fixed for the campaign.
Later checkpoints preserve or revise its consequential conclusions.
The Runner checks only that the file exists and that each required register
section is present and non-empty. It does not check scientific adequacy; the
PI judges the model's soundness when using it.
