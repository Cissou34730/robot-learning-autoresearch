# Independent prompt and instruction stack review

- **Date received:** 2026-10-05
- **Repository:** `Cissou34730/robot-learning-autoresearch`
- **Worktree reviewed:** `C:\Users\cyril.beurier\code\robot-learning-inquiry-centered-lifecycle`
- **Branch reviewed:** `inquiry-centered-lifecycle`
- **Context:** This independent, read-only review was requested after repeated
  concern that the PI-facing instruction stack could encourage early training,
  lose preliminary embodied-robotics reasoning at phase transitions, or turn
  scientific inquiries into preselected operations. The requested scope was
  the complete PI-facing prompt and instruction system, not a campaign audit
  or a persona-only review.
- **Preservation:** The review below is reproduced verbatim from the submitted
  response. It is retained as external analysis for maintainer discussion, not
  as an approved implementation plan or established causal result.
- **Source SHA-256:** `43E1DFCA809ABED3C62DD5DE542E814A8B1EAF5EFA63D60225BB52B6503CE391`

---

**1. Overall assessment**

The current instruction system is likely to produce a PI that takes scientific responsibility seriously but often organizes its work around producing and improving a learned policy. It contains substantial support for physical reasoning and question-driven inquiry. Its main weakness is that **the scientific reasoning developed during preparation is less directly represented in subsequent action selection than the operational state, candidate models, and training allocation**.

This is not an explicit training-first system. It says that “no operation is the default,” makes measurement and training peer instruments, and allows evidence to change the question. Those are meaningful counterweights. Nevertheless, the assembled prompts make it possible to select a plausible operation and subsequently explain its scientific relevance, particularly at startup. [contracts/program.md:86–106](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:86), [run_research.ps1:765–799](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:765)

The strongest elements are:

- Clear ownership of scientific judgment by the PI.
- A substantive preliminary physical-model prompt.
- Explicit separation of observations, interpretations, competing explanations, and claim limits.
- Durable scientific checkpoints across fresh sessions.
- Explicit warnings against interpreting policy success as causal confirmation or training collapse as method invalidation.

The principal weaknesses are:

- An incomplete handoff from the preliminary model into startup.
- A generic persona that independently imposes a learned-policy destination.
- Repeated operational instructions whose concrete content can outweigh broader scientific guidance.
- A lifecycle that requires goal review to produce an inquiry or official assessment, creating pressure to formalize a direction.
- Backend and context-routing inconsistencies that can produce avoidable repair work.

The current scenario legitimately requires a learned policy. That requirement should remain. The issue is its duplication in general PI identity and its potential interpretation as a reason to train early. **A required final artifact does not determine the first scientifically useful action.**

This review concerns the checked-out repository on `inquiry-centered-lifecycle`. No files were modified and no training or campaign operations were executed. Behavioral conclusions below are predictions from repository text and construction, not demonstrated causal effects. I did not use campaign outcomes to establish them. Repository-external model and SDK instructions were not reconstructed.

**2. Instruction architecture**

The launcher does not present every contract as one assembled document. It constructs a phase prompt, supplies selected state, and routes the PI to files. Consequently, the reading order of the full contracts is not guaranteed.

The preliminary prompt has this explicit order:

1. Human-goal summary.
2. PI persona.
3. Detailed scientific-model objective.
4. Instruction to use the scenario and human-authored implementation.
5. Required facts, consequences, and unknowns registers.
6. Instruction to write the model.

After preliminary publication, the launcher clears that backend-session identity. Startup therefore receives a new conversation rather than the preliminary conversation’s full reasoning. [run_research.ps1:839–881](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:839)

All ordinary scientific prompts use a different order:

1. PI persona.
2. Human-goal summary.
3. Evidence references and latest completed operation result.
4. Latest checkpoint’s scientific synthesis.
5. Latest checkpoint’s decision frontier.
6. Latest checkpoint’s goal gap.
7. Active inquiry, except during startup.
8. Phase objective.
9. Training allocation.
10. Validation correction, when applicable.
11. Scientific-model-use guidance.
12. Goal/evidence reminder.
13. Operation-selection or transition instructions.
14. Instruction to begin with the brief and latest record; consult other sources as required.

The model’s actual conclusions are not inserted here. [run_research.ps1:688–799](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:688)

| Phase | Available information and communicated objective | Required output or decision | Likely behavioral effect |
|---|---|---|---|
| **Preliminary scientific model** | Goal first; persona next; extensive physical-analysis instructions; scenario and accessible implementation available through inspection. | A compact model separating established facts, physical consequences, and unknowns. | Strong encouragement to reason physically before intervening. The deliverable boundary can also make this feel like completed preparation. |
| **Startup** | New conversation; common prompt; model available by reference; no previous checkpoint synthesis or frontier. Objective: establish a credible direction, perform useful scientific work, potentially build tools or methods, and choose an action. | Legal operations include measurement, training, roles, restoration, and checkpoint. Startup ends with a scientific record. | Freedom to act usefully immediately, but also freedom to establish a method before clearly expressing the scientific uncertainty. No learned-policy baseline is explicitly required. |
| **Goal review** | Current evidence, checkpoint synthesis/frontier/gap, and model-use guidance. Objective: reassess direction and choose official assessment or an inquiry. Measurements are available beforehand. | Assessment request, or inquiry opening followed by checkpoint. | Supports reconsideration, but makes a formal campaign decision the session’s destination. |
| **Inquiry creation** | PI supplies question, goal connection, closure condition, and rationale. | Open inquiry, then checkpoint; further work occurs in a fresh session. | Establishes a question and durable boundary. The free-text fields also permit an operation-shaped question. |
| **Operation request** | Current scientific context, legal capabilities, and instrument schemas. Guidance begins “Choose the operation…” then says to relate it to the unresolved distinction. | One operation request. | Encourages decision relevance, but leaves room for choosing an operation first and rationalizing it afterward. |
| **Inquiry continuation** | Same backend conversation within the bounded session; common prompt repeated; latest operation result supplied; latest durable checkpoint remains the persistent synthesis. | Another operation, checkpoint, reframe, or closure as appropriate. | Preserves local context, but recent results and repeated operational instructions can sustain the existing direction unless the PI deliberately reassesses it. |
| **Inquiry closure or reframe** | Explicit transition objective replaces the normal objective. Only checkpoint may follow. | Record decision, evidence, remaining gap, and next direction; then start a fresh session. | Strong protection against silently changing questions. Scientific quality of the closure still depends on the PI’s record. |
| **Retry and recovery** | Preliminary retry repeats goal/persona and deliverable correction. Invalid-operation retry reconstructs the scientific prompt with validation feedback. Execution failure appends diagnosis/repair-or-replace guidance. | Correct model/request, repair implementation, or choose another permitted action. | Preserves valid work and permits reconsideration, but emphasizes producing an acceptable action or repairing implementation. |

Sources: [startup objective](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:75), [phase objectives](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:1082), [operation permissions](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/instruments.md:21), [transition prompts](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:610), [recovery prompts](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:899), [validation retry](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:1170).

The generated brief presents: human goal → best evidence → goal gap → inquiry → latest checkpoint → current session and operation kinds → candidate registry → completed operations → artifact inventories → failed execution history. It does **not** contain a scientific-model section or an automatic link to the model or program contract. This matters because the launcher instructs the PI to begin there. [runner/build_brief.py:482–528](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/build_brief.py:482)

The Copilot adapter sends the launcher prompt without adding a repository-defined scientific system message in its session options. OpenCode adds a separate system-context string. Thus, the two backends do not have identical repository-controlled instruction surfaces. [runner/copilot_adapter.py:1396–1420](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/copilot_adapter.py:1396), [researcher_opencode/src/adapter.ts:751–758](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/researcher_opencode/src/adapter.ts:751)

**3. Prompt and instruction findings**

**F1. The scientific identity is broad in expertise but narrower in its stated destination. — Context-dependent**

**Textual evidence.** The persona opens:

> “You are the Principal Investigator responsible for leading this campaign toward a learned policy that satisfies the human goal…”

It then lists robotics, reinforcement learning, control, simulation, system identification, experimental design, and scientific software. The program contract similarly grants broad scientific responsibility. [run_research.ps1:66–69](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:66), [contracts/program.md:5–15](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:5)

The scenario itself requires a learned policy achieving at least 98% episode success. [contracts/scenario.md:9–20](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/scenario.md:9)

**Interpretation.** For this scenario, learned-policy development is correctly part of the destination. However, the general persona independently fixes that destination before the scenario is presented in ordinary sessions. It can make the broader disciplines appear to support policy production rather than define scientific questions in their own right.

This privileges learned-policy development more clearly than it privileges reinforcement learning specifically. Nothing in these instructions requires a particular RL algorithm or a learned-policy baseline as the first experiment.

**Interaction.** The fixed SB3/Gymnasium stack, training artifacts, and candidate roles reinforce the policy-development interpretation. The explicit multidisciplinary identity and “no operation is the default” wording counteract it. [AGENTS.md:12–19](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/AGENTS.md:12)

**F2. Embodied reasoning is prominent and substantive during preparation, but its detailed scope is phase-local. — Helpful initially; weaker continuity afterward**

**Textual evidence.** The preliminary objective explicitly covers morphology, workspace, joint constraints, actuation, timing, damping, inertia, control authority, initial state, task geometry, observability, alternative physical configurations, failure classes, and meaningful physical quantities. It rejects a component inventory or repository summary. [run_research.ps1:78–97](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:78)

**Interpretation.** Weak embodied focus is not plausibly explained by an absence of physical instructions. This is one of the strongest parts of the system.

Contacts, compliance, friction, latency, and sensing noise are not individually named. They are covered only by the open-ended instructions about materially relevant dynamics and sensing. That is a generality limitation, not evidence that they matter to the current arm or that the PI must study every such property.

**Interaction.** Later prompts retain the shorter instruction to use physical consequences and unknowns to form competing explanations. They do not repeat the detailed scope or carry selected conclusions forward automatically. The vulnerability is retention of relevance, not initial exposure.

**F3. Startup lacks a concrete handoff of the preliminary model’s consequential conclusions. — Harmful risk; strongest architectural finding**

**Textual evidence.**

- The preliminary conversation is ended and its session identifier cleared.
- Startup’s synthesis and frontier come from `pi_checkpoint`; when absent, the prompt says no durable synthesis or frontier has been recorded.
- Model-use guidance is included, but model content is not.
- The final routing instruction says to consult the scientific model “only as the scientific question requires.”
- The brief contains neither a model section nor its source link.

[run_research.ps1:714–724](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:714), [run_research.ps1:783–799](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:783), [run_research.ps1:880–881](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:880), [runner/build_brief.py:482–528](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/build_brief.py:482)

**Interpretation.** The model is available and its use is explicitly requested. Nevertheless, startup must reconstruct which conclusions matter while simultaneously establishing the question and choosing work. “Consult … as the scientific question requires” permits selecting the question before retrieving the physical reasoning that should help determine it.

This does not guarantee forgetting. A careful PI can read the model and perform the intended synthesis. It makes continuity dependent on voluntary reconstruction at exactly the boundary where no checkpoint yet supplies it.

**Interaction.** The next startup checkpoint can preserve a strong synthesis. It can equally preserve a prematurely operational framing, which subsequent sessions then receive as their starting context.

**F4. The human goal is stable, but its repeated summary emphasizes success more than task physics. — Context-dependent**

**Textual evidence.** The program defines the human goal as the only campaign objective and places inquiries, sessions, and operations below it. [contracts/program.md:19–33](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:19)

The launcher uses a stored goal summary or extracts only the scenario’s `Success criterion` section. The brief uses the same fallback strategy. [run_research.ps1:473–487](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:473), [runner/build_brief.py:31–42](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/build_brief.py:31)

**Interpretation.** This preserves the achievement criterion but does not automatically preserve the target distribution, spatial tolerance, hold duration, or episode horizon from other scenario sections. Those remain available in the full contract.

A scalar success gap can consequently become more immediately visible than the physical capability or uncertainty responsible for it. This is a compression effect, not a changed human goal.

The distinction between campaign objective and temporary scientific objective is otherwise clear. The phrase “only objective” should not be interpreted as requiring every scientifically useful action to improve policy performance immediately.

**F5. Startup combines direction-setting with implementation and operation selection. — Context-dependent**

**Textual evidence.** Startup must establish direction, use scientific work to refine it, potentially build reusable tools and methods, choose the first useful action, and preserve its work. [run_research.ps1:75–76](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:75)

The ordinary action guidance says:

> “Choose the operation whose result would most improve the next decision toward the human goal.”

It then says to relate the selected operation to the unresolved scientific distinction or method-development need. [run_research.ps1:765–772](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:765)

**Interpretation.** This correctly allows genuine scientific work during startup; startup is not merely a planning exercise. However, it does not clearly separate establishing the decision-relevant uncertainty from selecting an intervention. Its wording can support either question-first reasoning or retrospective justification of an attractive operation.

Tool construction is qualified by “where needed,” so it is not mandatory. Its explicit mention still makes building infrastructure a salient interpretation of useful startup work.

**F6. Goal review supports reconsideration but requires a formal decision that can encourage operation-shaped inquiries. — Context-dependent**

**Textual evidence.** Goal review explicitly says “Reassess the scientific direction” and permits measurements before committing to an inquiry. It must nevertheless choose assessment or inquiry opening. A goal-review checkpoint is unavailable until an inquiry has been opened. [run_research.ps1:1098–1099](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:1098), [contracts/instruments.md:23–26](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/instruments.md:23)

An inquiry is a “temporary question or obstacle,” and closure can occur when it produces the “actionable result for which it was opened.” [contracts/program.md:86–94](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:86), [contracts/program.md:120–123](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:120)

**Interpretation.** “Obstacle” legitimately includes method-development problems. But it also accommodates an inquiry organized around implementing or running a method already selected.

The inquiry schema distinguishes question, goal connection, closure condition, and rationale. It does not explain at the schema location how to distinguish a scientific question from an operation. The program provides stronger semantics elsewhere. [contracts/instruments.md:33–66](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/instruments.md:33)

The Runner’s acceptance of nonempty fields is appropriate mechanical validation. The remedy is clearer PI-facing meaning, not Runner judgment of whether the question is sufficiently scientific.

**F7. Continuity mechanisms are strong after checkpointing, but they depend on what the PI chooses to preserve. — Mostly helpful**

**Textual evidence.** The session record must preserve synthesis, evidence, gap, frontier, and direction. The program explicitly requires competing explanations, contradictory evidence, claim limits, and discriminating evidence. [contracts/program.md:127–150](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:127)

The prompt inserts the latest checkpoint’s synthesis/frontier, plus the latest completed operation result. Within a session, the backend conversation is resumed. [run_research.ps1:714–724](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:714), [run_research.ps1:490–594](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:490), [runner/copilot_adapter.py:1423–1437](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/copilot_adapter.py:1423)

**Interpretation.** It would be inaccurate to describe continuation as merely “keep executing.” Scientific state is prominently preserved, and reframe/closure boundaries prevent silent question changes.

Remaining weaknesses are narrower:

- The checkpoint is a selected synthesis, so omitted preliminary consequences can remain omitted.
- Within a session, its durable synthesis predates new results until another checkpoint.
- The repeated latest-result summary can emphasize the newest operational outcome.
- There is no explicit distinction between source-established physical facts and operation-derived evidence in the evidence-reference interface.

The last point does not prohibit discussing source facts in narrative fields. It makes their durable provenance less explicit than completed-operation provenance. [contracts/instruments.md:260–264](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/instruments.md:260)

**F8. Instruments influence action selection despite disclaiming recommendations. — Context-dependent**

**Textual evidence.** The instrument document says it “does not recommend when or whether to use an instrument.” Measurement precedes training, and general `python_module` measurement has no candidate field. The first two measurement interfaces, however, are candidate-based evaluations. [contracts/instruments.md:3–6](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/instruments.md:3), [contracts/instruments.md:86–134](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/instruments.md:86)

Training allocation is inserted into every ordinary prompt, including goal review and checkpoint-only transitions, where training is unavailable. [run_research.ps1:776–794](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:776)

**Interpretation.** Training does not dominate through document position or exclusive availability. Its salience comes from repeated allocation, explicit candidate production, model roles, and the final assessment destination.

Conversely, a candidate-free physical experiment is exposed as the generic technical interface `python_module`. Its scientific breadth is less apparent from its name than policy evaluation is from the two named evaluation instruments.

Non-training work is explicitly genuine science in the program. It can nevertheless look like preparation for obtaining or improving candidates when viewed through the operation and artifact interfaces.

**Interaction.** Startup permits shorter training runs; inquiry training must use the full allocation. This may make startup especially attractive for a small baseline or pilot run. That can be useful, but the allocation rule is not scientific evidence that such a run should come first. [contracts/instruments.md:211–230](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/instruments.md:211)

**F9. Negative results are treated well; execution failures and campaign stopping are less nuanced. — Mixed**

**Textual evidence.** The program says:

> “A useful policy does not establish its proposed cause. A negative recipe result or training collapse does not by itself invalidate the broader method.”

[contracts/program.md:157–160](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:157)

Recovery says:

> “Diagnose and correct the scientific implementation, or choose a different action if the failure changes the scientific decision.”

[run_research.ps1:920–921](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:920)

AGENTS classifies failed operations as execution history rather than evidence. Only official assessment can produce a campaign conclusion; scientific exhaustion is not a supported ending. The inquiry cap pauses without asserting a scientific conclusion. [AGENTS.md:161–164](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/AGENTS.md:161), [contracts/program.md:170–173](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:170), [contracts/program.md:77–82](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:77)

**Interpretation.** These instructions discourage premature abandonment and false causal claims. But the recovery wording initially attributes failure to scientific implementation, even though a request, environment, tool, or publication failure may be responsible.

“Not evidence” is appropriately strict about incomplete scientific results, but too broad if read as saying failure provides no diagnostic information. The brief does preserve failures separately, which partially resolves this.

The conclusion structure encourages persistence. It can also sustain inquiries when the PI cannot currently justify a credible route. This is a lifecycle limitation; wording alone cannot create a missing pause or escalation operation.

**F10. Authority is correctly broad, but permission to replace is more emphatic than the rationale for retaining. — Context-dependent**

**Textual evidence.** AGENTS says:

> “Nothing is sacred, preferred, required to remain recognizable, or exempt from replacement.”

The persona calls existing code, architecture, metrics, hypotheses, and decisions provisional; ordinary prompts repeat permission to inspect, modify, or replace implementations. [AGENTS.md:129–132](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/AGENTS.md:129), [run_research.ps1:68–69](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:68), [run_research.ps1:767](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:767)

**Interpretation.** This usefully prevents accidental deference to inherited implementation. The persona also says redesign should occur “when the evidence warrants it,” so arbitrary rewriting is not explicitly endorsed.

Nevertheless, replacement permission appears repeatedly and forcefully. Retaining an adequate implementation receives no equivalent scientific framing. A model inclined toward implementation work may interpret broad authority as an expectation to exercise it.

The needed balance is evidence-based scope selection, not a blanket preference for small changes.

**F11. Some routing and legality descriptions conflict with the actual phase context. — Harmful, primarily operational**

**Textual evidence.**

- The program says the brief’s source references route to the scenario, model, instruments, records, and AGENTS; the brief renderer does not generate most of those links. [contracts/program.md:175–188](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:175), [runner/build_brief.py:482–528](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/build_brief.py:482)
- The brief displays “Available operation kinds” from the session-kind matrix rather than applying transition restrictions. It can advertise checkpoint before goal-review opening, or broader operations during checkpoint-only transitions. [runner/build_brief.py:330–350](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/build_brief.py:330), [runner/protocol.py:658–668](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/protocol.py:658)
- Candidate metadata is routed to `runner/state/research_state.json`, although Runner state is described as hidden from the PI. [runner/build_brief.py:383–386](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/build_brief.py:383), [AGENTS.md:49–50](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/AGENTS.md:49)
- The preliminary contract references assessment implementation, while protected evaluators are hidden. The accessible source for assessment semantics is not identified precisely there. [contracts/program.md:37–40](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:37), [AGENTS.md:47–48](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/AGENTS.md:47)

**Interpretation.** These inconsistencies can trigger navigation failures and retries that interrupt scientific work. They do not independently explain training-first behavior, but weaken the claimed reliability of context routing.

The “causal research map” is also invoked without a clear named representation. It should be tied explicitly to the existing synthesis and decision frontier. [contracts/program.md:96](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:96)

**F12. OpenCode has definite instruction drift, distinct from the main scientific-framing issue. — Harmful if that backend is used**

**Textual evidence.** Its injected system context points to `research/brief.md`, `research/scenario.md`, and `research/instruments.md`. Its write policy permits `research/scientific_model.md` during preparation and older request/lab paths afterward. The launcher requires `pi_workspace/scientific_model.md` and uses the current `contracts/` and `campaigns/` layout. [researcher_opencode/src/adapter.ts:78–96](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/researcher_opencode/src/adapter.ts:78), [researcher_opencode/src/policy.ts:191–215](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/researcher_opencode/src/policy.ts:191), [researcher_session.ps1:163–190](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/researcher_session.ps1:163)

Its test-denial message suggests targeted checks, whereas current AGENTS prohibits direct execution of the human-owned tests. [researcher_opencode/src/policy.ts:24–26](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/researcher_opencode/src/policy.ts:24)

**Interpretation.** These are concrete inconsistencies, not speculative prompt effects. They can obstruct compliant execution or send the PI toward obsolete locations.

They cannot explain behavior under the default Copilot backend merely by existing. Their relevance depends on which backend was used. The launcher defaults to Copilot. [run_research.ps1:3–5](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:3)

The Copilot repository instructions separately contain maintainer-engineering rules, but explicitly state that those rules do not narrow PI authority. They should therefore not be interpreted as a blanket small-change requirement for scientific sessions. [ .github/copilot-instructions.md:9–26](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/.github/copilot-instructions.md:9)

**4. Principal diagnosis**

The dominant prompt-level mechanism is **an incomplete transition from scientific understanding to action selection**.

The system explicitly asks for the right scientific reasoning. The weakness is how that reasoning becomes the concrete basis of subsequent decisions:

1. Preparation creates a substantive model in a separate conversation.
2. Startup receives that model by reference, while its synthesis and frontier fields are empty.
3. The prompt immediately supplies a policy-oriented identity, training allocation, implementation authority, and operation-selection instructions.
4. The first checkpoint then becomes the synthesis repeatedly carried forward.
5. If startup framed the problem around a method or operation, the continuity machinery can preserve that framing very effectively.

This is more explanatory than attributing the behavior to one persona sentence. Removing “reinforcement learning” from the expertise list would leave the handoff and operational framing intact. Equally, simply adding another general instruction to use the model would largely repeat guidance already present.

The dominant mechanism has two interacting parts: **missing concrete scientific carry-forward** and **concrete operational framing at the decision point**. Static inspection cannot isolate their relative behavioral contribution. They operate together in the same prompt. A controlled comparison would be needed to establish causality or effect size.

Secondary contributors are:

| Concern | Most relevant prompt features |
|---|---|
| **Early training** | Learned-policy persona; training allocation in every prompt; startup’s shorter-run permission; candidate-based named evaluations. |
| **Method-first reasoning** | Operation selection preceding its explanatory relation; method-building startup language; inquiries permitted to concern an “obstacle.” |
| **Loss of continuity** | Fresh preliminary/startup boundary; model absent from brief; selective checkpoint synthesis; source facts less explicitly referenced than operation evidence. |
| **Weak embodied focus later** | Detailed physical scope concentrated in preliminary phase; repeated goal summary compresses task physics; policy statistics immediately visible. |
| **Operational rushing** | Every invocation must produce a deliverable/request; goal review must reach assessment or inquiry opening; retries emphasize acceptable action production. |
| **Unnecessary implementation changes** | Repeated replacement authority; explicit startup tool-building; recovery initially framed as implementation correction. |

These are tendencies, not instructions to behave badly. Strong counter-instructions exist for every major concern. Model-default preferences for familiar RL workflows or coding tasks could amplify these effects, but that is a hypothesis about the model, not repository evidence.

**5. Effective elements to preserve**

- **PI ownership and Runner restraint.** The explicit denial of scientific authority to the Runner is unusually clear. Preserve it without adding adequacy checks, required hypothesis counts, or mandatory preliminary measurements. [contracts/program.md:5–15](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:5)

- **Physical-model construction.** Its emphasis on coupled dynamics, observability, geometry, and physical consequences is substantially stronger than a file inventory. Improve its handoff rather than replacing it with a shorter persona statement.

- **Consequential uncertainty.** The model-use guidance asks for discriminating evidence when a mechanism could change direction and allows irrelevant unknowns to be set aside. This avoids requiring exhaustive physical investigation. It already appears in ordinary prompts, giving it meaningful influence. [run_research.ps1:71–74](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1:71)

- **Scientific checkpoint semantics.** The distinction between synthesis, decision frontier, and chosen action is sound. These fields can support the proposed improvements without proliferating new schemas.

- **Training as an instrument.** Preserve “measurement and training are peer instruments,” no default operation, no mandatory successor, and no implicit model promotion. Their influence would improve if concrete prompt construction matched them more consistently. [contracts/program.md:96–106](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:96), [contracts/program.md:162–168](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/contracts/program.md:162)

- **Scientific treatment of negative results.** Preserve the distinction between recipe outcome, causal explanation, and broader method validity. Place a short reminder in recovery and closure contexts, where it is most useful.

- **Explicit inquiry transitions.** Mandatory records after opening, reframing, and closing support continuity without asking the Runner to interpret the science.

- **Resource cap as an administrative pause.** The cap does not manufacture scientific exhaustion or force assessment. That distinction should remain.

**6. Recommended changes, ordered by expected influence**

**R1. Make the preliminary-to-startup handoff explicit, and carry forward PI-selected physical implications.**

**Problem and surfaces:** F3 and F7; preliminary objective, startup objective, common prompt, checkpoint guidance, and brief routing.

Add this wording to the preliminary objective:

> “For each consequential physical implication or unknown, explain which possible research decisions it could change and the assumptions on which that relevance depends. Do not select a method merely to complete this document. Preserve source references so later sessions can recover the reasoning.”

Replace the beginning of the startup objective with:

> “Read the initial scientific model before selecting the first action. Identify the physical consequences and unknowns that currently matter most to the human goal. State the scientific distinction or capability question that should determine the initial direction, then choose the work that can resolve or advance it. Existing reasoning may already justify action; no additional measurement is required merely because this is startup.”

Add to checkpoint guidance:

> “Preserve the model conclusions that remain consequential, the evidence that has revised them, and any consequential unknown deliberately deferred. The initial model remains a fixed historical reference; current synthesis records the campaign’s updated understanding.”

The brief should always link to the initial model and the program contract. Subsequent prompts should reproduce the PI’s selected synthesis rather than asking the Runner to select important physical conclusions.

**Why:** This directly addresses the missing handoff while retaining the existing record structure.

**Preserves:** PI choice of question, method, amount of analysis, and whether training is immediately justified.

**Possible new bias:** Excessive deference to the initial model or repeated lengthy summaries. Counter this by explicitly allowing revision and limiting carry-forward to consequential conclusions.

**R2. Present the human task and scientific state before operational options; remove the generic policy destination.**

**Problem and surfaces:** F1, F4, F8; `$piPersona`, `Get-HumanGoalSummary`, `New-ScientificSessionPrompt`, and brief ordering.

Replace the persona’s opening with:

> “You are the Principal Investigator responsible for scientific direction toward the human goal defined in contracts/scenario.md. Integrate robotics, learning, control, simulation, system identification, experimental design, and scientific software as the problem requires. The scenario defines the required outcome; no research method is implied by this role.”

Keep the current scenario’s learned-policy requirement unchanged.

Use this prompt order:

1. Human goal, essential task conditions, and protected boundaries.
2. PI role and Human/PI/Runner responsibilities.
3. Relevant physical understanding and current synthesis.
4. Completed evidence and its interpretive limits.
5. Goal gap and decision frontier.
6. Active inquiry and phase objective.
7. Decision guidance.
8. Currently legal operations and applicable resource limits.
9. Source routing and submission mechanics.

Preserve essential physical task conditions through a human-authored compact summary or the scenario text, rather than asking the Runner to infer scientific relevance.

Show training allocation when training is legal, in the resource section. Do not repeat it during goal review or checkpoint-only transitions.

**Why:** The information needed to define the scientific problem becomes the basis for interpreting the available actions.

**Preserves:** Human control of the goal and budget; all existing legal instruments.

**Possible new bias:** Longer prompts or overemphasis on physical analysis. Keep the task context compact and permit learning or implementation questions when those are consequential.

**R3. Define inquiries and action selection by the decision they can change.**

**Problem and surfaces:** F5 and F6; program inquiry definition, goal-review objective, instrument field explanations, common action guidance.

Replace the operation-selection opening with:

> “Identify the unresolved distinction or capability question that matters to the next decision. State what different findings would change. Then select the supported action best suited to that question. A method-development inquiry may concern whether a proposed construction can provide a needed capability; explain why that capability matters and how its usefulness will be assessed.”

Clarify inquiry fields near their schema:

> “The question states what is unresolved, rather than naming an operation to execute. The rationale connects that uncertainty to existing understanding and the human goal. The closure condition states what answer, bounded conclusion, or redirection would make the inquiry complete; completing an operation is sufficient only when its result answers that question.”

For closure:

> “Distinguish the operation’s outcome, the answer supported for this inquiry, remaining uncertainty, and the implication for the campaign. These conclusions may differ.”

**Why:** It makes retrospective operation justification less natural and preserves the distinction between evidence production and scientific conclusion.

**Preserves:** Exploratory work, method development, legitimate operation-specific questions, and the PI’s judgment of closure.

**Possible new bias:** Artificial hypotheses or forced binary alternatives. Explicitly allow descriptive characterization and open uncertainty; do not require multiple explanations when none are scientifically credible.

**R4. Make continuation and recovery explicitly reconsider the current interpretation.**

**Problem and surfaces:** F7 and F9; common continuation prompt, failure prompt, closure guidance, and program evidence semantics.

Add:

> “Interpret the new result against the current question and consequential physical explanations. State what changed, what remains unresolved, and whether the current question or selected method still warrants continuation. The previous next action is provisional.”

Replace the execution-failure instruction with:

> “Identify whether the failure concerns the request, execution environment, implementation, or publication. Preserve valid completed evidence. Repair or replace the action according to what the diagnosis changes about the scientific decision; an execution failure alone does not establish a scientific negative result.”

Clarify “failed operations are not evidence”:

> “Failed operations do not establish completed scientific results. Their recorded errors remain diagnostic execution history. Any scientific claim suggested by a failure requires appropriate completed evidence.”

**Why:** This gives reconsideration a concrete place after results and prevents automatic implementation replacement.

**Preserves:** Same-session continuation, recovery options, and completed-evidence requirements.

**Possible new bias:** Reconsidering settled decisions after every routine result. Ask only for changes material to the next decision.

The absence of a PI-requested unresolved pause is a separate lifecycle question. Do not conceal it with wording that tells the PI to stop when no such operation exists, or make the Runner decide that further work lacks scientific value.

**R5. Explain candidate-free instruments by their capability, without prescribing their use.**

**Problem and surfaces:** F8; instrument overview and `python_module` description.

Add near the operation overview:

> “A measurement may characterize the embodied system or another scientific quantity without a learned candidate. The python_module instrument supports PI-defined experiments and analyses. Candidate evaluation and training are other available capabilities; their availability establishes no preferred sequence.”

Present a compact capability overview before detailed schemas, distinguishing candidate evaluation, general experiments/analysis, training, recordkeeping, and role management.

**Why:** It makes non-training scientific work visible without requiring it.

**Preserves:** Mechanical instrument contracts and unrestricted PI selection.

**Possible new bias:** Measurement-first behavior or unnecessary diagnostic tooling. State explicitly that an operation should be chosen for its decision value and that existing analysis may be sufficient.

**R6. Keep full implementation authority while making change scope a scientific decision.**

**Problem and surfaces:** F10; AGENTS authority paragraph and repeated persona/action language.

Replace the emphatic replacement passage with:

> “Within the PI-owned surface, the PI may retain, modify, combine, replace, or remove any implementation. Choose the scope of change from the scientific question, current evidence, and requirements of the proposed method. Existing architecture has no scientific authority, and replacement is not itself scientific progress. Explain consequential changes and preserve enough provenance to interpret their effects.”

**Why:** It gives retention and replacement equal standing while retaining unrestricted authority.

**Preserves:** Complete redesign when scientifically justified; no human approval requirement for ordinary PI-owned scientific work.

**Possible new bias:** Conservatism or an implied minimal-diff rule. Avoid “smallest change” language for scientific sessions.

**R7. Align routing, availability descriptions, and backend guidance with the actual contracts.**

**Problem and surfaces:** F11 and F12; brief renderer, OpenCode injected context and denial text, associated path policies, and preliminary source guidance.

Recommended changes:

- Replace obsolete `research/...` references with the current contract, campaign, and exchange paths.
- Align OpenCode’s writable-path policy with the launcher’s current ownership surface.
- Display operations legal in the current transition state, or label the broader list as phase-level capabilities with explicit current restrictions.
- Route candidate metadata through PI-readable published artifacts.
- Identify accessible task and assessment semantics without directing the PI toward protected evaluators.
- Define “causal research map” as the relationships already recorded in synthesis and decision frontier.
- Remove PI-facing test examples that appear to authorize direct test execution.

**Why:** These are direct sources of contradictory instructions and unnecessary recovery.

**Preserves:** Existing protected boundaries; no new scientific gate.

**Possible new bias:** Overly restrictive routing could hide useful context. Keep source references broad within the permitted surface and distinguish visibility from write authority.

For an OpenCode deployment, correcting its path mismatch is an immediate prerequisite. It is ranked here only because it does not explain the default backend’s scientific tendencies.

**R8. Reduce repetition by assigning each instruction a clear location and purpose.**

**Problem and surfaces:** Repeated persona, replacement authority, training allocation, model-use instructions, and distributed field semantics.

Keep durable definitions in `contracts/program.md`, mechanical interfaces in `contracts/instruments.md`, ownership in AGENTS, and phase-specific decisions in the launcher. Repeat only the short scientific decision sequence and the state needed to apply it.

Preserve the full physical-model objective during preparation. Move negative-result and failure distinctions into the continuation/recovery locations where they affect a decision. Keep explicit reminders that scientific acceptance is the PI’s responsibility: the existing model-deliverable check establishes file presence and nonempty content, not model adequacy. [runner/run_experiment.py:1782–1793](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/run_experiment.py:1782)

**Why:** The system already contains most of the necessary scientific principles. Better placement and concrete carry-forward are more likely to help than additional repeated declarations.

**Preserves:** The separation between PI scientific judgment and Runner mechanical validation.

**Possible new bias:** Excessive deduplication can make fresh sessions miss critical instructions. Retain compact role boundaries and decision semantics in every fresh scientific-session prompt.
