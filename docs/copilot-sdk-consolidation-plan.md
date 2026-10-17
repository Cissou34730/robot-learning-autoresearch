# Copilot SDK consolidation plan

## Status and decisions

This is a maintainer design plan, dated 2026-10-17. Approval of this plan
does not authorize implementation, model calls, or campaign execution.
The installed baseline is `github-copilot-sdk==1.0.19`.

Retain one agent runtime: the Copilot SDK and its native agent lifecycle.
Use GitHub Copilot and OpenCode Go as inference sources within that runtime.
OpenCode Go supplies inference; it does not supply a second agent runtime.

The approved workstreams are:

- Customize the actual PI system message.
- Add one PI-selected, named-sections context tool.
- Integrate OpenCode Go through SDK providers after the targeted
  custom-header investigation and integration-specific verification below.
- Retire the separate TypeScript OpenCode runtime after supported provider
  operation works.

Drop the previously proposed standalone, broad compatibility/probe phase.
The bounded header investigation belongs to provider integration, not to a
new general compatibility project.

G4's original proposal to split the OpenCode adapter is superseded by this
consolidation. Do not perform that refactor first. Do not edit the existing
G4 report or harness-experiment log as part of this documentation task.

## Existing integration boundaries

The existing adapter builds session options without `system_message` or
`providers` in `runner\copilot\copilot_adapter.py:409-453`. Client construction
around line 539 defaults to `copilot-cli`. The account-only
`get_auth_status` / `list_models` checks around lines 552-572 need
provider-aware treatment; a Copilot model listing alone cannot establish
that a Go route exists.

Keep native SDK tools, hooks, permissions, and agent lifecycle. Preserve
`submit_operation` and `scientific_coding`, exact child file bindings, and
the existing Runner boundary. Runner executes PI-authorized operations and
reports facts; it does not choose scientific intent, relevance, or repairs.
The preliminary analyst retains its own tools and publication permission,
without gaining scientific coding delegation.

No SDK or dependency upgrade has been established as necessary. Dependencies
remain human-owned. Later harness changes require a stopped campaign or an
isolated maintainer environment that cannot affect an active campaign.

## PI system-message customization

Use SDK system-message configuration, not an ordinary user message that
merely describes the desired persona. Maintain one canonical PI role source
and apply it consistently at session creation and resume. Do not maintain
divergent phase-specific copies of that role text.

The installed `SystemMessageConfig` definitions in
`.venv\Lib\site-packages\copilot\session.py:371-465` support `append`,
`replace`, and `customize`. Targetable sections include `preamble`,
the `identity` group, `code_change_rules`, `guidelines`, `safety`,
`tool_instructions`, `runtime_instructions`, and `last_instructions`.
The public [SDK system-message documentation][sdk-system] explains these
section semantics.

Prefer targeted `customize` changes to PI identity and relevant role wording.
Do not replace the whole system message: full `replace` removes SDK prompt
guardrails. Preserve SDK safety, tool and runtime instructions, permission
enforcement, and applicable code-change rules. Inspect group semantics before
overriding `identity`; do not remove technical instructions incidentally.

Keep shared technical contracts common while preserving distinct roles.
The main PI persona must not leak into the preliminary analyst, native
scientific coder, or reviewer. Those roles retain their own instructions.
Prompt changes do not establish scientific correctness or guarantee success.

Acceptance boundary: creation and resume use the same canonical PI role;
other roles remain distinct; SDK guardrails and harness authority are
unchanged. Evaluate scientific outcomes separately from prompt integration.

## One named-sections context tool

Provide one context tool through which the main PI or preliminary analyst
selects named sections from current authoritative contracts, the campaign
brief, the scientific model, and session context, as the current phase
permits. The caller selects sections; Runner does not choose scientific
relevance or silently substitute a summary.

Reuse existing invocation authorization and
`runner\copilot\path_policy.py`. A section name is not new read authority.
Resolve selections against current permitted sources and reject unavailable
or unauthorized content explicitly.

Return exact selected text with source identity and explicit pagination or
continuation. Never silently truncate. Keep complete selected content
retrievable. Do not create hidden scientific summaries or a duplicate,
potentially stale authority source.

Keep `view` for permitted scientific source inspection. Keep
`artifact_evidence_query` and `training_log_query` for measurement JSON and
training trajectories. Do not move those evidence paths into the context tool.
Do not expose this broad context reader to the coder or reviewer: their
exact request-bound reads and writes remain mechanically scoped.

Acceptance boundary: authorized selections return exact current source text;
phase restrictions and continuation are explicit; child bindings remain
unchanged. Measure calls, returned bytes, and latency, and token usage where
available. Do not assume batching saves tokens. Choose any sizing defaults
from evidence rather than inventing numerical limits in this plan.

## Targeted custom-header investigation

### Evidence established by read-only inspection

The installed Python SDK exposes custom provider headers:

- `ProviderConfig` starts at
  `.venv\Lib\site-packages\copilot\session.py:1578`; line 1598 declares
  `headers: dict[str, str]`.
- `NamedProviderConfig` starts at the same file's line 1627; line 1653
  declares `headers: dict[str, str]`.
- `ProviderModelConfig` starts at line 1663 and documents provider-qualified
  selection IDs. Named providers and models are explicitly experimental.

The installed client forwards configured headers into SDK-to-runtime
payloads, rather than dropping them during Python serialization:

- `.venv\Lib\site-packages\copilot\client.py:4447-4490` converts the
  singular provider; lines 4474-4475 copy its `headers` unchanged.
- The same file's lines 4493-4523 convert named providers;
  lines 4514-4515 copy their `headers` unchanged.
- Session creation uses these converters at lines 2813-2824; resume uses
  them at lines 3608-3617.

The public upstream [multi-provider E2E source][sdk-provider-e2e], inspected
on 2026-10-17 from the moving `main` branch, configures provider `headers`.
Its `_assert_routing` helper asserts both the expected wire model and a
captured `x-provider` header on a routed request. This is upstream test
coverage in source, not a test executed here or proof about this installed
CLI. The upstream capture harness is not a proposed project proxy.

The public [OpenCode Go documentation][go-docs] asks coding clients to
identify themselves with a client-specific `User-Agent`, rather than a
generic SDK/library name, and to send a stable `x-opencode-session` for each
conversation. It also expects typical coding-agent traffic.

Conclusion: SDK type support and Python serialization support exist in the
installed package, and upstream source exercises header routing. Actual
installed CLI/runtime delivery of Go's required headers, and OpenCode Go's
acceptance of this integration, remain unverified. No credentials were read,
no model request was sent, and no live header behavior was tested here.

### Remaining integration-specific verification

Before accepting the Go route, verify on the actual installed runtime:

- Both required header values reach Go on the supported request path;
  runtime or transport defaults do not overwrite the client-specific
  `User-Agent`.
- Session identity is stable across turns, resume, retries, and same-session
  error correction, and is not reused for unrelated conversations.
- Define the native-child conversation/correlation policy, then verify
  headers on child requests and any auxiliary requests sent to Go.
- Header configuration is reapplied correctly on resume alongside the
  provider/model registry, without logging credentials.
- The intended scientific agent traffic is acceptable under Go's documented
  coding-agent usage expectations.

These checks require separate implementation/validation authorization. If
the direct SDK path fails them, report the specific blocker before changing
the design. Do not invent a proxy, assume an upgrade fixes it, or claim that
Go's support for other clients proves this client's behavior.

## OpenCode Go provider integration

Use the experimental named `providers` / `models` registry, additive to
Copilot authentication, to allow mixed model routes across native agents.
Do not use the singular whole-session BYOK mode as a substitute for this
mixed setup. Copilot authentication is still required.

The initial intended Go route is `deepseek-v4.1-flash`, with provider type
`openai`, `wire_api` set to `completions`, and base URL
`https://opencode.ai/inference/go/openai/v1`. Go GPT models require
`responses`; do not assume one wire protocol serves every Go model.
Document only routes actually verified, not blanket Go model support.

Preserve provider-qualified selection IDs throughout configuration,
native-agent selection, validation, persistence, and resume.
`runner\copilot\coding_contracts.py:39-41` currently strips the provider
prefix in `normalize_model`; that behavior is incompatible with named BYOK
route identity and must not remain on provider-qualified paths.
Distinguish selection ID, provider connection, wire model, and capability
lookup model rather than conflating their purposes.

Make authentication and model checks provider-aware. Verify the selected
model, reasoning setting, protocol, and required native tool behavior for
each supported role/route. Reject unsupported selections explicitly; never
silently fall back to another provider, model, or reasoning level.

By default, the scientific coder inherits the PI's selected route.
The independent reviewer stays on Copilot `gpt-6-luna` with high reasoning
unless the maintainer separately approves a change. Mixed routing must not
change reviewer independence or the native same-coder/same-reviewer
correction loop.

Bind resume to the original provider/model identity and stable conversation
identity. Reconstruct and verify required configuration before continuing;
do not silently resume under a different inference source. Preserve
same-session error correction and existing recovery of pending/completed
Runner operations without duplicate submission.

Keep provider usage and cost units separate from Copilot AIU. Record source
and units when available. Mark unknown external charges as unavailable,
not zero; do not invent an AIU conversion or implied cost equivalence.

Acceptance boundary: the explicitly supported Go route passes the header,
model/reasoning, tool, resume, and correction checks above; the mixed Copilot
reviewer still works; permissions and Runner authority are unchanged.
Failure of any required check blocks declaring that route supported.

## Proposed delivery stages

These are future implementation stages, not execution permission.

1. Implement targeted PI system-message customization and verify the
   role-isolation and creation/resume boundaries above.
2. Implement the single named-sections context tool and verify exactness,
   authorization, continuation, and measured retrieval effects.
3. Integrate the selected Go provider route using the header evidence above.
   Complete the remaining route-specific verification before declaring
   support. Do not insert a standalone broad compatibility phase.
4. Only after supported provider operation works, retire the separate
   TypeScript OpenCode runtime, backend-selection path, and obsolete
   runtime-specific instructions. Update directly affected documentation
   to describe the single SDK runtime and supported inference choices.

Use proportional, maintainer-authorized validation of changed behavior.
This documentation task runs no tests, campaigns, or inference.

The transition is not a long-lived dual-runtime architecture. Do not add
old-session translation, campaign migration, history cleanup, or a generic
provider framework. Preserve existing campaign evidence and history.
Retirement is blocked until the supported replacement works; implementation
approval must remain separate from this planning approval.

[sdk-system]: https://github.com/github/copilot-sdk/blob/main/python/README.md#system-message-customization
[sdk-provider-e2e]: https://raw.githubusercontent.com/github/copilot-sdk/main/python/e2e/test_multi_provider_registry_e2e.py
[go-docs]: https://opencode.ai/v2/docs/console/go/
