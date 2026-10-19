# OI-015: experimental realization in campaign 1ae27a27

Date: 2026-10-09. Campaign: `1ae27a27-6880-4ca6-9d50-e6498e771cb7`.
Focus: T16/I14/M27 and T17/I15/M28, with E59-E64 interpretation and handoff.
Status: independent RCA and proposed harness adjustment; no repair implemented.

## Recommendation

Add a mechanical report of exact saved-component matches and a short contract clarification about the evidence needed to interpret an intended experimental change. Preserve existing artifact-integrity fingerprints. Let the PI decide whether the match requires investigation, qualifies a conclusion, or is expected for the question being studied.

The artifacts establish exact equality of saved learned state at all 24 corresponding checkpoints and equality of recorded evaluation behavior. They do not establish the physical or software cause of that equality. In particular, this audit cannot conclude that the intervention gate never activated, that every training observation was identical, or that delivery problems are excluded.

The specific scientific gap is that I15 proceeded from a changed intended controller to a negative controller conclusion without accounting for its exact recorded equivalence to I14. The measured candidate's failure to improve complete success is supported. Whether the intended controller distinction was exercised remains unresolved.

## Evidence and access

The campaign has been removed from the current checkout by a later campaign reset. Its completed records and artifact blobs remain in repository history. This audit read them directly from Git objects without restoring files or changing campaign state:

- `ef7ae3e656408cb9f604c595002e00de0aa71f02`: completed T17 training and archived candidates.
- `daf0741332450a9b5679ac000c976cf96be358c8`: completed M28, including both T16/T17 candidate archives and M27/M28 artifacts.
- `021ff566c1f99d72d82aa9044499fc403b0421cc`: completed E64 checkpoint, including E59-E64.
- Scientific snapshots: T16 `ba2e90f974e04d84050145a73c027d6a2be94393`; T17 `9988ffc29a16b3a02efa13c3f6cbc5528299ad9b`.

These are accesses to preserved campaign records and artifacts. Commit chronology alone is not scientific evidence. The current harness was read only to identify proposal locations.

Comparisons used inline standard-library analysis through `uv run --no-sync`. Model ZIP members were compared as bytes; JSON measurement records were compared as parsed values. Pickle opcodes were inspected for function-name strings without unpickling or executing the saved runtime. No training, policy inference, simulation, or evaluation was run. No script file was created.

## Confirmed facts

### The intended treatments differed

Both training operations transferred from `T3:checkpoint-120832`, used seed 0, requested 120,000 steps, and completed 120,832 steps. Their recorded scientific sources differ in `robot_learning/scenario/policy_io.py`.

| Controller element | T16 | T17 |
|---|---|---|
| Distance window | 0.01 < distance <= 0.055 m | 0.012 < distance <= 0.050 m |
| Target-angle gate | -165 to -105 degrees | -155 to -125 degrees |
| Velocity condition | Inward radial speed exceeds 0.05 m/s | Inward speed exceeds a distance-derived envelope |
| Correction | Fixed-gain radial damping | Velocity excess, terminal taper and overshoot weighting |

The environment clips the mapped action before applying motor control. A source-level correction can therefore differ without necessarily changing the applied action. This is a concrete remaining possibility, not a finding that clipping caused this case.

### The saved state matches at every archived checkpoint

At all 24 corresponding step counts, these byte comparisons returned equality:

- Uncompressed `model.zip` member `policy.pth`.
- Uncompressed member `policy.optimizer.pth`.
- Uncompressed member `pytorch_variables.pth`.
- The saved `vecnormalize.pkl` file.

All 24 recorded training-success and mean-reward values also match exactly. The terminal policy member has SHA-256:

`40c2850ab162140b54cf1f0a8a186acfd59872005b3b037ffadd74a018863de0`

The terminal normalization file has SHA-256:

`14f25a95dfa8f1537e25763d07be43ea51379f74c32df305a6e49527a44a0c4d`

The full ZIP files and executable-runtime files differ. The respective terminal runtime hashes are:

- T16: `d8b11440938d32e5215315103dfe95d282778415690e364ad02591738e3ed8b4`.
- T17: `66f2bb60c78dbe2f3a2b6c7b1f70f9762f107f1db2377c930b7c4e1eaa37d505`.

The T16 serialized runtime contains `action_with_prearrival_damping`; T17 contains `action_with_prearrival_velocity_shaping`. This supports export of the respective controller code. It does not prove that the training environment invoked the changed branch or that the branch changed applied actions.

### The recorded development behavior also matches

Across M27/T16 and M28/T17, parsed equality holds for:

- All 160 episode-result records, including rewards and episode lengths.
- The complete `research_evidence` diagnostic objects.
- All 160 recorded arrival-state rows in the diagnostic artifacts.
- The residual-case records.

Both candidates recorded 153 complete holds, 157 first reaches and eight hold interruptions. Their T3 controls recorded 153 complete holds, 157 first reaches and four interruptions.

This is equality of the recorded quantities on the sampled panel. It is not a complete per-step trajectory comparison or proof of equivalent behavior everywhere.

### The scientific handoff did not account for that equivalence

E60 carried the negative T16 result into a proposed different controller. E61 explicitly described I15 as changing the controller design. E63 then rejected the distance-envelope/overshoot-risk controller after M28, and E64 selected a different terminal-state or plant-control representation.

The record supports rejecting T17 as an improvement on that panel. It leaves unanswered whether T17 adds a distinct effective test of the intended control law. The difference between those statements matters when evidence is used to select the next scientific direction.

## RCA and limits of causal attribution

**Observed failure:** a distinct intended intervention received a scientific interpretation without resolving a striking equivalence in the available evidence.

**Interpretation gap:** the recorded transition from intended change to tested mechanism was not substantiated. Candidate performance was measured, while realization of the specific experimental distinction remained uncertain.

**Harness observability gap:** current completion feedback exposes source provenance, archived candidates and learning metrics, but not an explicit comparison of saved components with prior candidates. `runner/repository.py:2307` hashes whole artifact files for integrity. `runner/run_experiment.py:1419` assembles training results; `run_research.ps1:581` and `runner/build_brief.py:222` present them. None of these inspected paths supplies the exact component-match observation.

The existing fingerprint is correct for its integrity purpose: different executable runtime files should yield different complete-artifact fingerprints. It is not designed to answer whether learned-state components match. Replacing it with a narrower digest would lose an important guarantee.

**Contract gap:** current OI-003/OI-004 guidance concerns evidence selection and interpretation of outcome versus mechanism diagnostics. It does not explicitly distinguish a proposed implementation from evidence that the intended experimental difference was exercised. This is a plausible place to clarify evidential scope, but the campaign does not isolate prompt wording as the cause of the PI's omission.

**Implementation cause remains unknown.** The following explanations remain possible:

| Explanation | What would distinguish it |
|---|---|
| Relevant controller conditions were not encountered | Evidence of which conditions occurred on the relevant states |
| A correction was computed but neutralized before plant input | Evidence comparing intended correction with applied control |
| Training and exported runtime used different effective behavior | Evidence connecting the actual execution path to the intended implementation |
| Different implementations were equivalent on the sampled work | Evidence showing the distinction's domain and whether this experiment covered it |

These are possible discriminators, not required measurements or a prescribed PI workflow. The PI retains the choice of whether and how to resolve them.

Equal normalization statistics do not identify the original observation sequence: aggregate statistics can match for different sequences. Equal saved weights and optimizer state also do not reconstruct every intervening update. Conversely, an inference-controller change can be scientifically meaningful while leaving learned weights untouched. Thus component equality alone is not sufficient evidence of an inert intervention.

## Proposed harness adjustment

### 1. Add an optional, factual component-comparison result

At candidate archival, retain the existing complete-artifact fingerprint and additionally record versioned hashes for identifiable saved components. For the present SB3 ZIP format, the useful components are the uncompressed policy, optimizer and additional tensor-state members, plus normalization. Keep runtime-file equality as a separate observation.

Describe the comparison as **exact serialized-component equality**. It is not a semantic policy fingerprint or proof of identical computation. A serialization difference can hide equal numerical values; no match therefore establishes nothing about scientific difference. Unknown formats or missing optional components should have explicit unsupported/unavailable status, not be treated as matching or rejected solely by this comparison feature.

Compare with earlier completed candidates in the same campaign and report matched component names, candidate identities and checkpoint coverage. For a run-level statement such as 24/24, require a complete match of corresponding checkpoint step sets; distinguish a terminal-only match from a complete recorded trajectory match. Present parent, seed and allocation as comparison context. Do not infer scientific independence from them.

A compact observation for this case would be:

> T17 matches T16 in policy, optimizer, additional tensor state and normalization at all 24 corresponding saved checkpoints. Executable runtime files differ. This reports exact saved-component equality; realization of the intended intervention is not determined.

Persist the comparison in the completed training result and show it both in immediate result feedback and the durable brief. A difference in source or runtime makes this observation particularly relevant, but it must not turn into a rejection, automatic rerun, forced measurement or automatic scientific conclusion. A changed inference controller with fixed weights remains a valid experiment.

### 2. Clarify evidential scope in `contracts/program.md`

Proposed addition beside the existing mechanism-evidence guidance:

> Conclusions about an intended experimental distinction must be limited to completed evidence that it was exercised under the relevant conditions. When that remains unresolved, preserve the uncertainty in `current_synthesis` and `decision_frontier`. Matching saved state or measured outcomes does not by itself establish that the intended change was inactive, ineffective or equivalent.

This leaves candidate-performance conclusions valid at their measured scope. It imposes no mandatory activation counter, experiment sequence, or rule to abandon a method. Existing evidence may already establish realization; an additional operation is not automatically required.

The new factual observation should appear in result feedback rather than adding another standing research procedure to every session prompt.

### Implementation locations and compatibility

| Location | Proposed responsibility |
|---|---|
| `runner/repository.py`, candidate archival | Compute supported component hashes without executing policy artifacts; preserve integrity fingerprints |
| `runner/run_experiment.py`, completed training result | Associate exact matches with earlier completed candidates and checkpoint coverage |
| `runner/repository.py`, result/state validation | Accept and validate optional versioned comparison metadata while retaining old completed-record support |
| `run_research.ps1`, `Get-LatestSessionResult` training branch | Surface compact match facts immediately after completion |
| `runner/build_brief.py`, training summary | Preserve compact comparison facts and references across sessions |
| `contracts/instruments.md` | Document the added result metadata and its mechanical meaning |
| `contracts/program.md` | State the interpretation boundary above |

Compute or recover comparison metadata from the archived candidate set on both normal completion and interrupted-operation recovery. Persist it deterministically so a resumed publication cannot silently lose or change the observation. Historical campaign records should remain readable without rewriting them. The proposal does not change candidate IDs, operation acceptance, operation permissions or model-role assignment.

## Validation proposed for an implementation

The historical artifact check above establishes that the proposed exact-comparison signal can distinguish matching state components from differing complete artifacts in this case. It does not validate a future implementation.

Targeted checks should cover: this archived T16/T17 match; same components in differently packaged ZIP files; a changed component being reported separately; partial checkpoint coverage never rendered as a whole-run match; unsupported formats preserving normal operation; compatibility with older result records; and recovery producing the same durable comparison metadata.

A candidate with matching learned weights and a different runtime must remain accepted, with no automatic claim of ineffectiveness. A subsequent campaign can assess whether the PI preserves uncertainty about realization or resolves it before making a stronger controller conclusion. Counting fewer operations or forcing a different research direction is not the success criterion.

## Relationship to the existing OI-015 draft

`docs/oi015_rca_20261009.md` already proposes an additional component digest. That mechanical direction is useful, but this RCA qualifies its stronger claims:

- Identical normalization files do not prove identical observation streams.
- Exported changed code does not prove its changed branch affected training.
- Earlier runs responding to other source changes do not exclude a delivery problem in this pair.
- A complete fingerprint differing is expected when runtime behavior can differ; it should be preserved.
- The gate being inert, an independently effective experiment being absent, and the run being scientifically worthless are not established by the archived comparisons alone.

The recommended adjustment makes a consequential observation visible and preserves the limits of interpretation. The actual cause of T16/T17 equality remains an open scientific or implementation question.

## Deliverable boundary

Only this report was created in `docs/`. Existing reports were preserved. No harness, scientific implementation, PI workspace, campaign state or dependency file was modified. Analysis code ran inline; there are no temporary scripts to retain or remove.
