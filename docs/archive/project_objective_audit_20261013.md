# Objective audit of the autonomous robot-research harness

Date: 13 October 2026. Source snapshot: ef12ebeaa3c0ce9c96d610fcccfe42c98a4aca4d.

This revision replaces the earlier report after the maintainer identified a scope error. The earlier report gave too much weight to improving the arm's learning recipe and recommended a task-specific controller baseline. Those recommendations did not answer the project's central question. They are withdrawn from this harness assessment.

## 1. What the project is actually trying to build

The product is an autonomous scientific worker operating through a reliable harness. A human supplies a robot, its physical and interaction contracts, a task, and protected success criteria. The model must understand that setup, choose a scientific direction, implement learning methods and measurement tools, request execution, interpret evidence, and revise its direction until the campaign reaches its permitted ending.

The harness supplies authority boundaries, access to sources and installed APIs, coding delegation, instruments, evidence access, persistence, context transitions, resource controls, and final assessment. It must support this work without embedding the scientific answer.

The test arm is an instance of the problem, not the product. A maintainer-authored arm controller, reward, curriculum, or preferred experiment sequence would not establish that the model can investigate unfamiliar robots. Likewise, adopting the best known arm recipe as a compulsory starting point would change what the test measures.

This intention is explicit in contracts/program.md: scientific direction, tool construction, implementation, experimental design, and interpretation belong to the PI; Runner performs factual execution. Training and measurement are peer instruments. Existing scientific code has no privileged status.

The inquiry lifecycle is also deliberate. An inquiry bounds a consequential question; a scientific session preserves coherent work; an operation produces a particular action or record. The current contract does not define a campaign as a succession of prescribed training adjustments.

## 2. Overall assessment

The architecture is coherent for this objective. It separates the immutable problem from a mutable scientific implementation, gives the model substantial scientific freedom, and preserves a factual record independently of the model's interpretation. There is no source evidence here that the entire approach should be replaced by a fixed optimizer or a task-specific control procedure.

The implementation has important mechanical and informational defects. More importantly, the available observations do not establish that the resulting model reliably exercises the scientific competence the architecture asks of it.

These are distinct conclusions:

| Question | Assessment |
|---|---|
| Does the design represent a plausible autonomous robotics research setup? | Yes: the division of problem definition, scientific work, execution, and independent assessment is credible. |
| Does the current harness mechanically implement every part correctly? | No: concrete defects and inconsistencies remain. |
| Do the tools make the intended scientific work possible? | Substantially yes, with demonstrated interface friction and gaps in verification coverage. |
| Does successful tool execution establish sound scientific judgment? | No. The contracts explicitly acknowledge that limit. |
| Do campaign failures identify the harness as the sole cause? | No. They mix model reasoning, generated science code, interfaces, runtime incidents, and task outcomes. |
| Is task generality demonstrated? | No. A second task is needed to observe it, but task-specific code in the scenario is not itself a generality defect. |

The strongest project-level concern is the incomplete connection between an intended scientific method, its actual implementation, the measurement that exercises it, and the conclusion used for the next decision. The harness records these objects, but recording them does not establish that their meanings agree.

## 3. Comparison with real robotics research

The setup resembles a researcher working from a physical specification, a simulator, instrumentation, code, and an experimental budget. Human ownership of the task and physics is appropriate. Scientific freedom to change reward, observations, algorithms, diagnostic tools, and training conditions is also appropriate.

This is a broader ambition than an LLM reward tuner. Eureka provides evidence that models can improve reward code across tasks and morphologies. It does not establish reliable autonomous diagnosis, experimental design, and method development across arbitrary robots. The project is testing that broader competence. [Eureka](https://arxiv.org/abs/2310.12931).

Real researchers also make implementation mistakes and use provisional measurements. The relevant distinction is how effectively the worker detects those mistakes, limits the claims they support, and chooses informative subsequent work. A long sequence of valid operations can still be scientifically ineffective.

Physical deployment adds sensing, calibration, latency, safety, reset, and model-mismatch requirements. Those requirements belong in the supplied robot/task setup and its instruments when the project reaches hardware. Their absence from a deliberately bounded simulator test does not invalidate the current harness design. [Real robot RL lessons](https://arxiv.org/abs/2102.02915).

The present audit therefore does not recommend introducing hardware concerns, a different arm reward, or an IK controller to make this test pass. The question is whether the model can derive and investigate the relevant scientific issues from the supplied contracts.

## 4. What “generic” means in this repository

Generality belongs at the boundary between the reusable harness and the supplied scientific setup.

Arm-specific dynamics, observations, success conditions, and protected evaluation are expected in the scenario and robot/task contracts. The earlier report incorrectly treated those facts as broad evidence against harness generality.

A focused source search found no PPO selection, radius, hold-duration, or folded-branch science in the reviewed reusable operation, execution, adapter, and brief modules. Runner receives the official adapter's generic goal_reached verdict. Laboratory evidence can carry arbitrary researcher-owned fields. These are positive signs of scientific separation.

There is one concrete remaining robot coupling: runner/protocol.py explicitly lists contracts/robots/two_joint_arm.py and two_joint_arm.xml in TRUSTED_RUNTIME_PATHS. Another robot's protected dependencies would need an accurate trust definition. A task-supplied manifest could express that mechanically without teaching Runner the robot's science.

The fixed Python stack is a declared environmental boundary. It does not mean that the harness must embed PPO forever: the PI owns the trainer and loader sources. Conversely, a JSON algorithm label cannot be assumed to replace their implementation.

A valid generality demonstration would show that a new supplied robot/task changes its contracts, scientific setup, and assessment adapter while leaving scientific decision rules in the reusable harness unchanged. It would not require a universal observation vector, reward template, controller, or policy.

## 5. Where the setup is strong

The scientific authority boundary is clear. Coding delegation assists implementation; it does not transfer scientific direction to the child or Runner. The main PI receives changes and proposed checks and retains review responsibility.

Frozen policy I/O and normalization protect candidate meaning when current scientific sources change. This is particularly important in a system that permits representation changes.

Explicit candidate roles avoid treating a freshly trained or terminal checkpoint as automatically best. Development evidence remains separate from official certification.

The operation ledger distinguishes completed scientific evidence from failed execution. Artifacts have content identities. The selected ten artifacts checked in this audit matched their recorded fingerprints.

Scoped evidence readers support deeper inspection rather than forcing the model to rely on reduced summaries. Current contracts explicitly distinguish uninspected data from absent data.

Durable scientific records carry interpretation and unresolved questions across fresh contexts. The current prompts explicitly make inherited judgments revisable; it would be incorrect to claim that the initial physical model or a previous synthesis mechanically fixes subsequent scientific belief.

These mechanisms address real problems. Their existence is not evidence that the model uses them well, but removing them without understanding the failure would discard useful protections.

## 6. What the campaign evidence establishes about the harness

The latest campaign produced a strong learned artifact and an official failure at 195/200. Earlier preserved states contain official passes at 196/200 and 197/200. This establishes that successful task artifacts have been produced. It does not establish reliable autonomous scientific behavior.

In the latest campaign:

- Four training operations completed, producing 96 checkpoints.
- Twenty-one measurement operations completed; five failed.
- Four distinct checkpoints received research evaluation.
- Recorded usage was 102.595910 AIU, including preparation, PI work, and coding.

These numbers describe activity and cost. They do not establish that 21 measurements were unnecessary, that four trainings were enough, or that the model should have followed a predetermined recipe. The relevant question is what decision each result supported and whether it tested the intended proposition.

Three consecutive measurement failures, M23–M25, came from passing a candidate directory to an interface expecting a model file. A prior tooling RCA records ten failures arising from one malformed filename. These are strong examples of generic interface friction and incorrect diagnosis propagating through a repair loop. They do not reveal a defective robot-learning method.

M22's controlled verification preceded those failures but replaced the actual loader. This demonstrates that a check can pass while the immediately relevant integration remains untested.

The campaign also selected a very early T4 checkpoint for evaluation. That is not automatically a selection error. It limits the conclusion to that artifact; it cannot establish a result for every checkpoint or for the broader scientific method. The issue for the harness is whether the PI preserves this distinction in subsequent reasoning, not whether Runner mandates particular checkpoints.

Seventy-three usage files and nine recoverable terminal states were inspected or indexed. They do not constitute a complete census of hundreds of campaigns. No lifetime success rate or causal effect of a harness revision is established.

## 7. Confirmed defects and their relevance to the product

### A. Scientific measurements can be internally inconsistent

The existing M26 trace labels joint, Cartesian, and acceleration quantities as synchronized, but records them across different MuJoCo instants. Independent reconstruction of tip position from 43,150 stored joint states found a maximum disagreement of 5.924 mm with the Cartesian position in the same row. One stored endpoint changed tolerance classification under that reconstruction.

This is an error in generated scientific instrumentation, not a reason to put an arm-specific rule in Runner. It is evidence that proposed verification and PI review did not establish the claimed synchronization.

A generic harness should make checked and unchecked integration scope clear, retain actual source and proposed checks, and make independent checks possible. The scientific worker must decide and implement the appropriate physical validation. Mechanical evidence integrity cannot certify physical correctness.

Any change to protected timing semantics requires human ownership and versioning. This audit does not reinterpret historical verdicts.

### B. Verification can exercise substitutes for the integration it claims to check

The trace check replaces the loader, environment factory, simulator stepping, and branch classifier. Controlled fixtures are useful for bookkeeping; they cannot establish the actual artifact-loading or simulation behavior they replace.

The current check documents part of that limitation. Nevertheless, its success preceded real loading failures. The model's review needs to evaluate what the check actually exercised.

The correction is an accurate verification boundary and access to small executable integration checks through existing Runner instruments. It is not a mandatory scenario-specific diagnostic list.

### C. Model identities are not consistently available across instruments

Candidate identity works for training and ordinary evaluation. Custom laboratory measurements have identity-bound JSON inputs, but model inputs still use raw arguments and paths. The worker must manually cross that representation boundary.

Extending the existing selected-input mechanism to model artifacts would remove a clerical burden without choosing evidence or directing science. Runner should resolve the exact selected identity and verify its components, then report factual errors.

### D. Declared configuration can differ from actual implementation

Transfer training restores saved policy settings while recording requested settings as effective. Fresh and transfer paths therefore do not have equivalent configuration semantics.

The latest architecture settings did not change, so this is not an explanation of its score. It is a concrete risk to autonomous experimental claims: the worker can believe an intervention ran when it did not.

The generic requirement is that requested, inherited, and applied settings be distinguishable and inspectable. The PI still decides whether a transfer or migration is scientifically appropriate.

### E. Training completion metadata is unsafe after exceptions

The trainer saves in finally and marks completion based on a flag that catches keyboard interruption but not ordinary training exceptions. A partially trained artifact can consequently say completed.

Normal process failure is detected, and normal reacceptance creates a new operation identity. The remaining source-established risk concerns interruption before Runner records the child failure: original-operation recovery can trust the misleading completion metadata without checking actual completed steps against the allocation.

This interleaving was not executed or observed in the audit. Correct completion facts and recovery checks are mechanical harness responsibilities.

### F. Current-state views can present historical judgment as current fact

The brief reports official failure but retains a goal-gap sentence saying the result is unknown. It also labels a transfer-local step count as accumulated training. Historical scientific records should remain intact; a current view should mark their time and later superseding facts.

An inherited “43-episode-equivalent gap” is another example of invalid quantitative interpretation surviving a mechanically valid checkpoint. Runner should not silently repair scientific interpretation. It should present denominators and factual measurements clearly enough for the PI to check it.

### G. The terminal verdict has weaker retained evidence

The official path retains status, model identity/fingerprint, a formatted summary, and time. It does not persist a detailed, sealed episode record comparable with development evidence.

This limits maintainer postmortems of the product. A complete protected assessment artifact can be retained without revealing held-out details to the PI during development.

### H. Authority definitions are duplicated

Lifecycle requirements and path ownership are repeated across protocol, launcher/controller, adapter, and brief. Runner's broad robot_learning ownership prefix differs from the adapter's narrower scientific scopes.

Shared factual definitions would reduce contradictory decisions. Enforcement should remain at each boundary. This does not authorize Runner to evaluate scientific adequacy.

The large adapter and repository modules also concentrate several changing responsibilities. This is maintenance risk rather than proof that their size caused a campaign failure.

## 8. Why repeated adjustments have not settled the problem

The project has addressed real individual failures, but its history does not provide controlled evidence that each adjustment improved autonomous research.

Several changes concern mechanical interfaces and can be assessed with bounded, robot-neutral reproductions. Others concern model attention, interpretation, continuation, and commitment. Those are behavioral hypotheses. Passing implementation checks cannot establish their effectiveness.

A documented failure can motivate a prompt change, but another campaign after that change does not isolate its effect. Scientific implementation, model behavior, runtime, selected artifacts, and encountered evidence all change along the way.

The resulting loop can be expensive: observe a failure, add guidance, observe a different failure, add more guidance. A larger instruction stack can explain more expected behavior without supplying stronger evidence that the worker can perform it.

The decisive issue is not how detailed the research procedure sounds. It is whether the model reliably:

1. distinguishes an observation from an interpretation;
2. notices when its implementation does not realize its intended method;
3. checks consequential assumptions independently;
4. retrieves the evidence its next decision requires;
5. changes its direction in response to that evidence;
6. limits negative conclusions to what actually ran.

Those obligations are already substantially present in the contracts. Further wording should be justified by a specific failure of delivery or interpretation, not by assuming that every failure means the principle is absent.

Coding separation addresses authorship and authority. It does not automatically provide independent validation: the child can implement the same mistaken assumption and a check embodying it, while the PI accepts both. The evidence shows that this remains an important failure mode. It does not establish that adding another agent is the remedy.

Provider/runtime incidents form a separate category. The historical post-handoff 400 error does not diagnose the robot learning or scientific model. Its upstream cause remains uncertain. Model-call retries, where configured, must be assessed separately from Runner-operation recovery and should not be confused with resubmitting scientific work.

## 9. What a justified improvement program would examine

The report recommends improvements to the worker's environment and to evaluation of the harness. It does not prescribe a scientific strategy for the arm.

First, repair concrete mechanical contradictions: actual completion, actual configuration, identity resolution, current-state presentation, retained assessment facts, and shared authority definitions. These can be reviewed without solving any particular robot.

Second, establish behavioral evidence from existing saved incidents. Examples include a malformed selected identity, a proposed check that mocks its claimed integration, an interpretation unsupported by inspected artifact fields, or an implementation that omits a stated intervention. A bounded replay can examine whether the model detects and handles the issue using the tools and context it actually receives.

A replay does not need a hand-coded solution to the robot task. It tests the research worker's handling of evidence, interfaces, and scientific claims. It must preserve the original information available at the decision boundary; retrospective access to the answer would invalidate the comparison.

Third, compare a specific harness change under fixed conditions, separating mechanical success from model behavior. A prompt correction should be compared with the previous prompt on the same decision problems. A tool improvement should be tested for whether it removes the observed burden without changing scientific authority.

Full campaigns remain necessary to observe integrated scientific capability, but they should test a defined harness hypothesis. A different final robot score by itself is insufficient attribution.

Finally, use another supplied robot/task to challenge portability. The test should examine whether core Runner or generic instructions need task-specific scientific changes. The model may choose entirely different methods and measurements; that is intended behavior.

Appropriate project measurements include:

- identity and evidence retrieval errors;
- completed work recovered accurately after interruption;
- agreement between declared and actual interventions;
- useful detection of verification omissions;
- unsupported claims propagated across sessions;
- repeated repair attempts based on the same wrong premise;
- cost and time to decision-relevant evidence;
- task success, with the recipe and resource context preserved.

These measurements need not become new mandatory scientific fields or new lifecycle phases. They can be maintainer evaluation of the existing behavior.

## 10. Limits of the conclusions

The audit identifies a coherent setup, specific mechanical defects, demonstrated generated-code/review failures, and inadequate causal evidence for many historical harness adjustments.

It does not establish that the current language model can satisfy the broad scientific role reliably, that another model would do better at equal cost, or that a particular lifecycle simplification would improve results. Those remain product-level hypotheses.

The current scenario's successful and unsuccessful policies are evidence about the artifacts and the scientific work that produced them. They cannot alone determine which portion of the harness is correct or how well it will support a new robot.

The correction to the earlier report is substantive: the project should be assessed as an autonomous scientific system. Making the supplied arm pass through maintainer-authored science would bypass the capability the project is intended to develop and measure.

## Evidence references

Current contracts: [program](../contracts/program.md), [instruments](../contracts/instruments.md), [scenario](../contracts/scenario.md).

Reusable implementation: [protocol](../runner/protocol.py), [operation execution](../runner/run_experiment.py), [execution utilities](../runner/execution.py), [adapter](../runner/copilot_adapter.py), [brief](../runner/build_brief.py), and [launcher](../run_research.ps1).

Scientific evidence: [current ledger](../campaigns/results.jsonl), [current state](../runner/state/research_state.json), [trainer](../robot_learning/train.py), [trace](../robot_learning/lab/folded_residual_trace.py), and [trace check](../robot_learning/lab/folded_residual_trace_check.py).

Historical context: [tooling RCA](copilot_tools_combined_rca_20261012.md), [complexity review](reusable-infrastructure-complexity-review-20261012.md), [change narrative](harness-change-narrative.md), and [provider incident](RCA-copilot-400-2026-10-13.md). Historical design plans are context, not current command authority.

The original audit verified M5, M8, M10, M13, M15, both M18 artifacts, both M21 artifacts, and M26 against their recorded hashes. M26's SHA-256 is ec5ced0275a4cd3c80863448387609013675ec1903c32cbfa3c95481156c716b. Its geometric consistency calculation used the XML link lengths and existing stored states; it did not execute simulation or recompute an official verdict.

No campaign operations, dependency changes, implementation changes, or protected-test inspection were performed for this revision. The revision uses the evidence already collected plus focused reads of the intended architecture. Only this report was changed.

