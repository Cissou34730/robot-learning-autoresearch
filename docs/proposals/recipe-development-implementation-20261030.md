# Recipe Development Implementation

Maintainer implementation plan, 30 October 2026. Development is approved.
This document records the integrated implementation, validation evidence and
remaining local commit. It does not authorize campaign execution or campaign writes.

## Scope and safeguards

Before this documentation edit, a read-only check confirmed all ten campaign
locks were free. The check covered `campaign-1` through `campaign-5` under both
`robot-learning-campaigns` and `robot-learning-campaigns-norecipe`.
It used the launcher's canonical path and mutex naming. This documentation
worker edits only this plan. It does not stage files, commit, create branches or push.

This branch is local only. Never push it. The main agent owns integration and
separate local stage commits. This plan does not authorize automatic campaign
writes, resets or archival actions. Campaign folders, dependencies and other
harness checkouts remain outside this documentation task.

Pre-existing dirty editor settings, the experiment backlog and the HTML report
remain uncommitted and preserved. They are excluded from implementation commits.
Preserve the skeleton repository's pre-existing, uncommitted `current_params.json`.
No harness or skeleton changes were pushed.

Editor Mypy caused the source-cache writes that triggered the ownership
rejection. Editor Mypy was removed and workspace settings were cleaned before
the main implementation stages. That cleanup is pre-existing work, not part of
the three stage commits below. This documentation task does not change settings.

## Agreed lifecycle

The fresh lifecycle is analyst, recipe development, original startup, then
goal review and inquiries. The analyst builds the physical and scientific model
and proposes a first reward and distinct methods. The PI decides which proposals
to implement and which method to select.

Recipe development uses measured variant comparisons to accelerate later
inquiries. It can contain several comparisons. It ends when the remaining
scientific work primarily develops the selected method rather than chooses among
competing methods. The selection preserves measured differences, unresolved
alternatives and the next investigation. It has no score threshold, fixed number
of comparisons or additional training-step cap.

A variant implements a distinct proposed method. Its differences follow from
the scientific question, with freedom across PI-owned source code and parameters.
The first reward is a design proposal, not a required common base. Training
length follows the next variant decision and observed learning. Further training
is selective, with each variant's own learned state preserved where appropriate.

Startup retains its original purpose: establish the initial scientific
direction, develop useful tools and choose the first useful investigation.
It receives the scientific model and the complete recipe-development record.
Its first reference is the selected recipe, not the inherited scaffold.
The relevant original startup text was checked with `git show 511c9cfe4`.
Later goal-review and inquiry guidance remains in place.

## Stages and actual status

| Stage | Owner | Status |
|---|---|---|
| Lifecycle, instructions and prompt rendering | Runtime and wording owners | Committed locally as `d618312cf` (19 files), core quality review clean |
| Independent per-variant parents and documentation | Parent owner | Committed locally as `74d6fb697` (6 files), 114 passed, independently reviewed |
| TUI and legacy reports | TUI and report owners | Committed locally as `356c8a47c` (7 files), TUI 125 passed, report 3 passed |
| Recipe CLI required training timesteps | Integrator | Separate skeleton repository: local commit `79e671a`, local tag `skeleton-v4` created |
| Combined lifecycle and instructions focused gate | Test worker and main agent | 315 passed in 50.74 seconds |
| Independent durability audit | Independent reviewer | Complete, no concrete bug found |
| Related fixture, brief and report repairs | Respective owners | Complete, owner checks 63 passed and 9 passed, final regression passed |
| Final notification and brief compatibility repairs | Respective owners | Complete and validated, local follow-up commit pending |
| Final full required gate and remaining completion checks | Integrator | Complete: 964 passed, 1 skipped, zero failures in 182.85 seconds |
| Final follow-up commit | Integrator | PENDING, local only, no push |

The wording implementation adds only the missing variant term and the new
recipe-development session term. It updates phase permissions, record meaning,
analyst proposal ownership and the analyst's training-instrument reference.
The runtime uses `prompts.RECIPE_DEVELOPMENT_OBJECTIVE` for the new phase.
Startup renders the complete phase record unchanged, including in a continued
conversation. No authority, coding or measurement excerpt boundary changed.
No wording tests or new test infrastructure were added.

The repair code worker completed phase ordering, the cap-zero boundary after
both phases, strict state invariants and immutable handoff and recovery.
The lifecycle core quality review was clean. The independent durability audit
found no concrete bug. The final full required gate also passed.
The parent stage passed its independent review and 114 targeted tests.

The recipe CLI stage is complete in the separate skeleton repository.
Commit `79e671a` changes only the required training-timesteps argument.
The local `skeleton-v4` tag exists. The user's existing `current_params.json`
remains uncommitted and preserved. The isolated argparse check passed outside
the harness. Neither the skeleton commit nor its tag may be pushed.

Final repairs cover brief compatibility, the notification's own replacement text
and fixture updates. The final follow-up commit also includes formatting of two
Python files and this document. These changes are complete and validated but
remain uncommitted, separate from the three harness stage commits.
The original startup text is restored. The agreed PI definition of done is
unchanged. No new training cap, score threshold or fixed comparison count was
added. Cost accounting remains token-only. No new tool was added.
No new code files or test cases were needed.

## Frozen runtime interface

Schema 7 adds `campaign_phase`, with `recipe_development`, `startup` and
`research` as its values. It adds `recipe_development`, which is null or the
complete completed phase checkpoint record. Fresh campaigns start in
`recipe_development`. Read-only compatibility normalization preserves the
legacy schema 6 startup path rather than restarting scientific work.
New campaigns from a schema 6 Prepared Baseline intentionally use the
compatibility startup path. They do not enter recipe development.

The recipe-development checkpoint preserves its full record and moves to
startup. The startup checkpoint moves to research. Session identities retain
the `S<n>` format. Recipe development permits the startup-like scientific
operations and checkpoint, with no inquiry or official assessment.
For fresh schema 7 campaigns, the maintainer `--max-inquiries 0` boundary applies
after both recipe development and original startup. Compatibility campaigns
retain the original startup-only boundary. The cap and its remaining count
stay absent from campaign-facing text.

Strict invariants enforce phase ordering. The completed recipe-development
record remains immutable through startup handoff and recovery. Later inquiry
checkpoints must not replace that record.

Per-variant parent continuation is implemented and documented in `74d6fb697`:

- Fresh training rejects every parent, at both operation root and variant level.
- Transfer training uses each variant's explicit parent instead of the root
  parent. A variant without an explicit parent inherits the root parent.
- The root parent may be omitted only when every variant supplies its own
  parent. Without a root parent, all variants must have explicit parents.
- Acceptance freezes the resolved parent mapping for each variant. Resume uses
  that frozen mapping rather than resolving the parents again.
- Legacy accepted operations without a per-variant mapping use their frozen
  root parent as the fallback.
- Variants within one operation still share training steps and seed. Independent
  parents add no fixed training-step cap or comparison-count cap.

## Validation record

- The combined focused gate passed: 315 tests in 50.74 seconds.
  The gate includes targeted TUI coverage. It is not the full required suite.
- Lifecycle core and campaign text passed quality review. The repair work
  completed phase ordering, cap-zero handling, invariants and immutable
  handoff and recovery. The independent durability audit found no concrete bug.
- Independent parent continuation passed 114 tests and independent review.
- The TUI gate passed 125 tests. The legacy report gate passed 3 tests.
- The completed final full required gate passed: 964 passed, 1 skipped and
  zero failures in 182.85 seconds. The command was:

  ```text
  uv run --all-groups pytest tests/autoresearch tests/benchmark -q -p no:cacheprovider --tb=short
  ```

- Earlier full, partial and interrupted failures are historical results, not
  current blockers. The completed final gate supersedes those results.
- Touched-file Ruff lint passed for 31 Python files. The formatting check passed
  for the same 31 files. The Git diff whitespace check passed.
- The isolated required-timesteps argparse test passed outside the harness.
  The skeleton stage now also has its local commit and tag.

Final wording checks distinguish rendered text from whole-file findings:

- The new rendered session blocks passed STE with zero errors.
- Two phrases in the changed brief were repaired. The changed brief and the
  notification replacement each passed STE with zero errors and zero warnings.
  The final brief contains two sentences. These repairs remain uncommitted.
- Whole-file checks retain five inherited hard errors in `contracts/program.md`,
  one in `runner/copilot/system_prompt.py` and 24 in
  `runner/launcher/prompts.py`. The last count includes a raw-source parser
  artifact. The new analyst text has the same six hard errors as its baseline.
  These results do not certify the full text.
- Ten synthetic fresh, continued and legacy prompt renders passed. A required
  checkpoint transition also rendered successfully.
- The startup handoff decoded to the full input record. Prompt construction
  did not mutate the input state. The analyst reference included the training
  instrument.
- Both wording-stage Python modules parsed and imported successfully. Ruff
  formatted only these two files. Targeted Ruff lint, formatting verification
  and tracked wording whitespace checks passed. No campaign was launched or reset.

Whole-file STE is not clean. The rendered result does not remove inherited
findings or the Python-source parser artifact. Review those findings separately
from the new rendered prose. This record does not claim full STE conformance.

## Completion status and remaining commit

The lifecycle, independent-parent, TUI/report and skeleton CLI stages have local
commits and focused validation. The final full required gate and completion
checks passed. Only the local follow-up commit remains pending.

Integration validation covered schema 6 normalization, fresh phase selection,
both checkpoint transitions, operation permissions and interrupted or continued
conversations. It also covered frozen per-variant parents, TUI and legacy
reports, and both fresh and compatibility cap-zero boundaries.
These checks did not execute campaigns.

Completion status:

1. Complete: the confirmed final regression result is recorded above.
2. Complete: touched-file formatting, lint and whitespace checks passed.
   Whole-file STE findings remain separate from rendered prose and are disclosed above.
3. Complete: startup retains its original purpose and receives the full immutable
   phase record and scientific model. Its first reference is the selected recipe.
   Later inquiry checkpoints do not replace the phase record.
4. Complete: campaign text review checked for examples, numeric pilot anchors,
   fixed reward assumptions and maintainer guardrail leaks.
5. Pending: record the validated follow-up changes in a local commit only.
   Exclude the pre-existing settings, backlog and HTML report changes.
   Preserve the skeleton's uncommitted `current_params.json`.
   Never push this branch or the skeleton.

Campaign execution remains NOT performed. No live training validated the new
flow. Its scientific effect remains unmeasured. Automated validation does not
establish a scientific benefit.

These requirements preserve the scientific purpose of recipe development and
the original startup phase. They do not authorize campaign writes, resets,
archival actions or campaign execution.
