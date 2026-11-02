# Scientific instruments: scientific model

This file is a part of the instrument contract. `contracts/instruments.md` lists
all parts.

## Scientific-model publication

Before other campaign work, `pi_workspace/scientific_model.md` must contain
four substantive registers: `Established facts`, `Physical consequences`,
`Unknowns` and `Decision-relevant synthesis`. Each register is a level-two
heading (`##`) with its content under it. Topics in a register use level-three
headings (`###`).

The analyst writes the scientific model. It states physical consequences,
learning hypotheses and the evidence that can distinguish them.
The analyst analyzes the starting recipe that `contracts/scenario.md` describes.
Recipe design choices are not properties of the robot.

The synthesis is the last register. It selects the consequences and the
unknowns that are most likely to change the first decisions of the campaign.
These decisions include the design and the interpretation of the first
measurements. For each selected item, it keeps the decision relevance, the
assumptions, the source references and the discriminating evidence.

The synthesis includes `### Proposed first reward` and
`### Proposed design variants`. The reward proposal gives each term's formula
and weight, its available inputs and its relation to complete task behavior.
It accounts for the discount factor and episode-end conditions.
For each term, the analyst states the behavior that it encourages, the behavior
that it makes cheapest and the reason for its weight. The analyst states the
observations in the first training runs that can show that the reward is wrong.

Each variant proposal states its question, source and parameter changes,
physical or learning reason, expected behavior and discriminating observations.
A variant can change any PI-owned source file and any parameter.

The proposals are hypotheses, not established facts.
The PI decides which proposals to implement and can revise them.
The synthesis proposes a recipe-development question when that phase is
included, or an initial scientific question for startup when it is skipped.

The synthesis also includes the invariances of the definitions. For each
invariance, it states which outcomes the invariance predicts to be equal when
the episode start and the target are transformed the same way. A measured difference between such
outcomes, beyond sampling variation, is evidence about the policy, not about
the task.

When the campaign includes a recipe-development session, that session receives
the synthesis, the proposals and the full scientific model. The PI selects the interventions
and creates further variants from the test results.
The PI develops a recipe that learns and supports startup.
The recipe uses knowledge across all tested variants.
The PI combines design choices supported by the results.
The PI measures the resulting recipe to demonstrate learning progress.

The startup session receives the unchanged scientific model and the recipe in
`robot_learning/`. When the campaign includes recipe development, this recipe
is the delivered recipe. Startup also receives `current_synthesis`,
`next_direction_or_closure` and `next_question` from recipe development, word for word.
The PI also reads the full scientific model in the startup session and selects
the initial direction.

After acceptance, the scientific model stays fixed for the campaign. Later
session records preserve or revise its consequential conclusions. The Runner
checks only that the file exists and that each required register is present
and not empty. It does not check scientific adequacy. The PI judges the
soundness of the scientific model when the PI uses it.
