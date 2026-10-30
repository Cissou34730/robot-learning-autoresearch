# Glossary

The campaign texts use each term below with one meaning only. In text that
addresses the PI, "you" means the PI. Field names, operation names and file
names in code format are technical names. They keep their exact spelling.

## Roles

| Term | Meaning | Do not use |
|---|---|---|
| PI | The principal investigator. The PI is the only scientific decision-maker of the campaign. | researcher |
| analyst | The agent that writes the scientific model before the first PI session. | preliminary analyst |
| coder | The agent that changes PI-owned source files for one `scientific_coding` request. | coding child, child |
| reviewer | The agent that checks the change of a coder. | — |
| Runner | The harness program that validates operations, executes them and records their results. | trusted controller |

## Task and policy

| Term | Meaning | Do not use |
|---|---|---|
| task | Everything that `contracts/scenario.md` and the robot contracts fix: the robot, the physics, the episode start, the targets, the success criterion and the official assessment. You cannot change the task. | scenario |
| goal | At least 196 successful episodes out of 200 in the official assessment. | human goal, objective, human objective, campaign objective |
| episode | One attempt to reach and hold one target, with at most 500 control steps. | — |
| episode outcome | The success or the failure of one episode. | — |
| policy | A trained neural network together with its saved runtime. | learned policy, learned model, learned candidate |
| saved runtime | The code that is saved with a policy. It builds the observation of the network and turns the network output into the motor command. | policy io, policy i/o |
| observation | The input that the saved runtime gives to the network at each control step. | — |
| robot model | A model of the kinematics or the dynamics of the robot, in any form. You can use a robot model as a tool. The fixed transformation from the network output to the motor command cannot contain one; `contracts/scenario.md` gives this limit. | — |
| candidate | A policy that a training run saved and that you can measure. Its identity has the form `T<n>:checkpoint-<steps>`, or `T<n>:<label>-checkpoint-<steps>` for a training variant. | model, saved artifact |
| training checkpoint | A candidate that a training run saved at a given step count. | checkpoint, policy checkpoint |
| role | A label that you give to a candidate: working, best-known, or a retained label. The operation is `model_role`. | model role |
| best-known candidate | The candidate with the strongest measured evidence. It does not need to reach the goal. | best-known model |

## Method and source code

| Term | Meaning | Do not use |
|---|---|---|
| method | How you make a policy: the observation, the transformation of the network output into the motor command, the network, the algorithm, the reward, the training targets and the training length. | approach, learning method |
| change | One modification of the method or of a tool. | — |
| intervention | A change that you make to test its causal effect on the behavior of the policy. | — |
| recipe | The source files and the parameters that implement a method. Each candidate records its recipe. | scientific recipe |
| variant | A recipe that tests a proposed method. During recipe development, quick tests of variants guide the first recipe. Differences between variants follow from the scientific question. A variant can change any PI-owned source file and any parameter. | — |
| inherited recipe | The recipe that the campaign contains when it starts. `contracts/scenario.md` describes it. | current recipe, baseline recipe |
| source code | Any code. | — |
| implementation | The source code that realizes a method, a tool or an instrument. | — |
| PI-owned path | A path whose content you decide. `contracts/authority.md` lists these paths. | — |
| human-owned path | A path that no campaign role can change. | — |

## Evidence

| Term | Meaning | Do not use |
|---|---|---|
| operation | One action that the Runner executes for you. Only operations change the campaign. | instrument operation |
| measurement | An operation that runs one or more instruments: `research_evaluation`, `task_reference` or `python_module`. | — |
| research evaluation | The instrument `research_evaluation`. It runs episodes in the PI-owned research environment, on the episode seeds that you select. | — |
| task-reference evaluation | The instrument `task_reference`. It runs a candidate on a fixed protected panel through the saved runtime, as the official assessment does. | — |
| panel | A fixed set of episode seeds. | — |
| development panel | The `research_evaluation` panel with seed 100000 and 400 episodes. | — |
| development measurement | Any measurement before the official assessment. | — |
| official assessment | The protected evaluation of the best-known candidate on 200 episodes. Its result ends the campaign. The operation is `campaign_conclusion`. | final assessment, assessment, campaign conclusion |
| artifact | A file that an operation writes. | — |
| result | The facts that a completed operation returns. | — |
| finding | A fact or an interpretation that evidence supports. | — |
| evidence | Completed results and their artifacts. Only completed operations give evidence. | — |
| fact | A value or a statement that you read directly in the task definitions, in the source code or in evidence. It is not an inference. | — |
| interpretation | What you infer from facts. It is provisional: new evidence can revise it. | — |
| conclusion | An interpretation that you state as the answer to a question, with its limits. | — |
| mechanism | The causal chain that produces a behavior of the policy: the dynamics of the robot, the saved runtime, the network and the training process. | — |
| explanation | A proposed mechanism for a behavior of the policy. | — |
| hypothesis | An explanation stated so that evidence can test it. One test can support or weaken it; one test alone does not establish it. | — |
| discriminating evidence | Evidence that can distinguish competing explanations, because they predict different results for it. | — |
| mechanism test | A comparison that shows whether an explanation accounts for where the policy fails and for where it succeeds in comparable conditions. | explanation test |
| causal research map | The relations among observations, interpretations, competing explanations, unresolved distinctions and discriminating evidence that `current_synthesis` and `decision_frontier` record. | — |
| reference | The basis of a comparison. In a paired comparison, it is the candidate that the other candidate is compared with. | first reference |

## Campaign and sessions

| Term | Meaning | Do not use |
|---|---|---|
| campaign | One attempt to reach the goal, from the analyst session to the result of the official assessment. | — |
| session | One conversation of the PI or of the analyst, for one purpose. | scientific session, bounded session, bounded scientific session |
| session objective | The purpose of the current session. | — |
| analyst session | The first session. The analyst writes the scientific model. | preliminary session, preliminary analyst session, campaign-start session |
| scientific model | The document `pi_workspace/scientific_model.md`: the initial physical model of the robot and the task, which the analyst derives from the definitions. It does not change during the campaign; your session records carry forward what the campaign learns. | — |
| decision-relevant synthesis | The last section of the scientific model. It gives the facts and the unknowns that are most likely to change your first decisions. | decision-relevant |
| recipe-development session | Your first session after the analyst session. You compare variants and select the method for later inquiries. Its kind is `recipe_development`. | — |
| startup session | The session after recipe development. You establish the initial scientific direction, the tools and the first useful investigation from the selected recipe. | — |
| goal-review session | A session in which you choose one of two actions: request the official assessment, or open one inquiry. You can measure before you choose. | goal review |
| inquiry | A question that you open in a goal-review session, with a closure condition. You work on it in inquiry sessions until you close it. | goal-linked inquiry |
| active inquiry | An inquiry that is open. | — |
| inquiry session | A session in which you work on the active inquiry. | — |
| session record | What the `checkpoint` operation saves: your synthesis, the goal gap, the open questions and the next step. It does not save a policy. | scientific session record |
| checkpoint operation | The operation `checkpoint`. It saves the session record. | — |

The campaign follows this cycle:

```text
analyst session -> recipe-development session -> startup session -> goal-review session
goal-review session -> open inquiry -> inquiry sessions -> close inquiry -> goal-review session
goal-review session -> official assessment -> end of the campaign
```

## Other terms

| Term | Meaning | Do not use |
|---|---|---|
| consequential | Able to change a decision. | — |
| session-sized deliverable | The part of an inquiry that one session completes. | — |
| decision frontier | The open questions, and the evidence that can answer each of them. The record field is `decision_frontier`. | — |

## Operations by session

| Operation | Recipe-development session | Startup session | Goal-review session | Inquiry session |
|---|---|---|---|---|
| `measurement` | yes | yes | yes | yes |
| `training` | yes | yes | no | yes |
| `model_role` | yes | yes | yes | yes |
| `restore_recipe` | yes | yes | no | yes |
| `inquiry` open | no | no | yes, when no inquiry is active | no |
| `inquiry` reframe or close | no | no | no | yes |
| `campaign_conclusion` | no | no | yes, when no inquiry is active | no |
| `checkpoint` | yes | yes | yes, after you open an inquiry | yes |

`contracts/instruments.md` gives the formats and the acceptance rules.

## Session record fields

| Field | Meaning |
|---|---|
| `human_goal_connection` | How the work of the session moves the campaign toward the goal. |
| `current_goal_gap` | The goal, the measured result of the best candidate, and the difference, in numbers. |
| `current_synthesis` | The facts, your conclusions, the explanations that you did not exclude, and the limits of your claims. |
| `evidence_references` | The completed operations that support the record. |
| `decision_frontier` | The open questions, and the evidence that can answer each of them. |
| `next_question` | The question for the next session. `contracts/instruments.md` gives the rule for each session. |
| `completed_operations` | The operations that you completed in this session. |
| `candidates_and_roles` | The candidates and their roles. |
| `next_direction_or_closure` | The next action or the closure decision, and why. |
| `cumulative_resource_use` | The training runs, the measurements and the other operations of the campaign so far. |
