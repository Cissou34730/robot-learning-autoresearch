# Copilot SDK consolidation plan

## Status and decisions

This is a maintainer design plan, dated 2026-10-17.
The maintainer separately approved the provider implementation and bounded SDK
checks. It is implemented with local transport/authority checks.
Remote OpenCode acceptance awaits a locally configured credential.
The other workstreams remain planned. No campaign execution is authorized here.
The installed baseline is `github-copilot-sdk==1.0.19`.

Retain one agent runtime: the Copilot SDK and its native agent lifecycle.
Use GitHub Copilot, OpenCode Zen and OpenCode Go as inference sources.
OpenCode supplies inference, not a second agent runtime.

The approved workstreams are:

- Customize the actual PI system message.
- Add one PI-selected, named-sections context tool.
- Integrate catalogue-selected OpenCode inference through SDK providers.
- Retire the separate TypeScript OpenCode runtime after supported provider
  operation works.

Drop the previously proposed standalone, broad compatibility/probe phase.
The bounded header investigation belongs to provider integration, not to a
new general compatibility project.

G4's original proposal to split the OpenCode adapter is superseded by this
consolidation. Do not perform that refactor first. Do not edit the existing
G4 report or harness-experiment log as part of this documentation task.

## Existing integration boundaries

The adapter now configures named SDK providers/models and provider-aware startup.
It does not customize `system_message`. Client construction still uses the
installed Copilot runtime. A Copilot account model list does not establish that
an OpenCode route exists.

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

Those were the planning-time findings.
Implementation checks now capture actual installed-runtime requests on loopback.
Reference identity headers reach Chat Completions, Responses and Anthropic
requests. Native coder/reviewer calls and resume preserve the selected route
and conversation identity. No remote OpenCode inference request was made.

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

The maintainer separately authorized implementation and bounded SDK checks.
Local checks establish request construction, not remote service acceptance.
Do not invent a proxy, assume an upgrade fixes a protocol mismatch, or claim
that another client's success establishes this client's remote behavior.

## Implemented OpenCode provider integration

Use the experimental named `providers` / `models` registry in the existing SDK.
The maintainer chooses provider and model at launch, not through a model picker
or separate role settings. Luna remains the default.
The OpenCode catalogue determines protocols, endpoints, limits and capabilities.
It refreshes after 24 hours and retains a valid stale cache with an explicit warning.
There is no single-model whitelist or silent model fallback.

Chat Completions, Responses and Anthropic pass installed-runtime loopback checks.
The SDK Anthropic transport appends `/v1/messages`, so its configured base removes
the catalogue's final `/v1`. Native Google transport is not exposed by SDK 1.0.19.
Incompatible catalogue entries remain listed with an explicit diagnostic.
No alternate Google-compatible route was tested or substituted.
External-only operation without a Copilot login remains unverified.

Reuse identity/header and catalogue behavior from the maintainer's working
`pi-harness\src\opencode` reference. Send its exact OpenCode CLI identity headers,
including stable session/project identities. Persist the identity per SDK session
without credentials. Zen credentials take precedence, with Go fallback for free
Zen routes.

Preserve provider-qualified selection IDs throughout configuration,
native-agent selection, validation, persistence, and resume.
`normalize_model` strips only the GitHub Copilot prefix.
Distinguish selection ID, provider connection, wire model, and capability
lookup model rather than conflating their purposes.

Make authentication and model checks provider-aware. Verify the selected
model, reasoning setting, protocol, and required native tool behavior for
each supported role/route. Reject unsupported selections explicitly; never
silently fall back to another provider, model, or reasoning level.

PI, coder and independent reviewer use the selected campaign model route.
Reviewer reasoning remains high when supported and is omitted otherwise.
The reviewer remains independent, read-only and retained for same-change repairs.

Every OpenCode inference request includes a tool named `read`, without porting
Pi's reader or glob implementation. The scoped UTF-8 reader reuses existing
path authorization. Explicit native-child tool selectors omit custom `read`
in the installed runtime. The approved adaptation inherits definitions while
hooks retain exact role/tool/file authority.
Chat Completions omits freeform `apply_patch`, so native SDK JSON `create` and
`edit` are available within the same coder and preliminary write boundaries.
Main PI and reviewer writes remain denied. Isolated native read/edit checks
confirm those boundaries without editing scientific sources.

Bind resume to the original provider/model identity and stable conversation
identity. Reconstruct and verify required configuration before continuing;
do not silently resume under a different inference source. Preserve
same-session error correction and existing recovery of pending/completed
Runner operations without duplicate submission.

Keep provider usage and cost units separate from Copilot AIU. Record source
and units when available. Mark unknown external charges as unavailable,
not zero; do not invent an AIU conversion or implied cost equivalence.

Acceptance boundary: local header, route, tool and resume checks pass while
permissions and Runner authority remain unchanged. Remote acceptance remains
pending a local credential and the separately authorized bounded model calls.
Campaign effectiveness remains unmeasured.

## Proposed delivery stages

These are future implementation stages, not execution permission.

1. Implement targeted PI system-message customization and verify the
   role-isolation and creation/resume boundaries above.
2. Implement the single named-sections context tool and verify exactness,
   authorization, continuation, and measured retrieval effects.
3. Provider integration is implemented ahead of the other workstreams.
   Complete remote acceptance before declaring service compatibility.
4. Only after supported provider operation works, retire the separate
   TypeScript OpenCode runtime, backend-selection path, and obsolete
   runtime-specific instructions. Update directly affected documentation
   to describe the single SDK runtime and supported inference choices.

Use proportional, maintainer-authorized validation of changed behavior.
Implementation checks do not authorize campaigns.

The transition is not a long-lived dual-runtime architecture. Do not add
old-session translation, campaign migration, history cleanup, or a generic
provider framework. Preserve existing campaign evidence and history.
Retirement is blocked until the supported replacement works; implementation
approval must remain separate from this planning approval.

[sdk-system]: https://github.com/github/copilot-sdk/blob/main/python/README.md#system-message-customization
[sdk-provider-e2e]: https://raw.githubusercontent.com/github/copilot-sdk/main/python/e2e/test_multi_provider_registry_e2e.py
[go-docs]: https://opencode.ai/v2/docs/console/go/
