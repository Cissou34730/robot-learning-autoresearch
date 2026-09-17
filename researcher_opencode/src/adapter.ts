/**
 * One bounded Researcher session, executed through the official OpenCode
 * TypeScript SDK.
 *
 * The launcher owns the research protocol and decides whether a phase is
 * complete; this adapter owns only the OpenCode runtime: the server lifecycle,
 * session identity, the tool profile, the command policy, and what reaches the
 * console. Nothing printed here is read back as a scientific fact.
 *
 * It runs beside `researcher_copilot.py`, not instead of it. Both accept the same
 * argument list and speak the same console, so the launcher can choose a backend
 * per phase without either adapter knowing about the other.
 */

import { createOpencodeClient, createOpencodeServer } from "@opencode-ai/sdk";
import type { Event, OpencodeClient } from "@opencode-ai/sdk";

import {
  appendUsage,
  RUNTIME_ID,
  USAGE_SCHEMA_VERSION,
  type UsageRow,
} from "./accounting.ts";
import { REASONING_EFFORTS, splitModel, type AdapterArgs } from "./args.ts";
import type { Console, FileOperation } from "./console.ts";
import { changedSince, worktreeStatus } from "./git.ts";
import { commandDenial, permissionCommandText } from "./policy.ts";
import {
  getEntry,
  mappingRejection,
  putEntry,
  type SessionMappingEntry,
} from "./session-map.ts";

export const EXIT_OK = 0;
export const EXIT_SESSION_ERROR = 2;
export const EXIT_NOT_AUTHENTICATED = 3;
export const EXIT_MODEL_UNAVAILABLE = 4;
export const EXIT_TIMEOUT = 5;
export const EXIT_RUNTIME_FAILURE = 6;
export const EXIT_INTERRUPTED = 130;

/** Tools that would exceed the Researcher profile: delegation, the wider
 * network, and the session todo list. Disabling a name the server does not have
 * is harmless. */
const DISABLED_TOOLS: Record<string, boolean> = {
  task: false,
  webfetch: false,
  todowrite: false,
  todoread: false,
};

const POLICY = `<harness_policy>
This session runs inside the repository worktree the launcher selected. The
harness enforces the rules below at the tool boundary, so a rejected call fails
rather than succeeding silently. A rejection names the sanctioned alternative;
follow it instead of retrying the same command.

- The launcher executes experiments. Never invoke research/run_experiment.py,
  training, the viewer, or the final benchmark.
- Use research/brief.md and the campaign artifacts as the authoritative
  scientific context. Do not use Git history as scientific evidence or as a
  routine workspace-discovery step.
- The runner owns mutating Git operations, provenance and restoration.
  Read-only Git is available only when the current task specifically requires
  inspecting the experiment's current code state or delta. To revert this
  experiment's code, use the lineage proposal's "code" decision.
- Pytest execution belongs to the runner. Researcher-authored tests are not part
  of the scientific recipe and are not required for phase completion.
- Every tool call resends the whole conversation, so prefer one aggregation over
  the same command repeated per file, and read what you need rather than whole
  artifacts. Separate calls remain appropriate when the scientific question
  differs between artifacts or aggregation would make the analysis less clear.
  Context efficiency does not determine which scientific evidence is worth
  examining.
- Use targeted linting, parsing or lightweight analysis while developing the
  phase deliverable when they resolve uncertainty introduced by the work. Once
  the deliverable is complete, do not perform a separate final validation pass
  solely to reconfirm the deliverable or repository state; the Runner owns final
  contract and execution validation. The phase ends when its deliverable has
  been written.
</harness_policy>`;

/** Paths whose changes are the runtime's own bookkeeping, not research work. */
const IGNORED_CHANGE_PATTERNS = [
  /(^|\/)\.git\//,
  /(^|\/)node_modules\//,
  /(^|\/)__pycache__\//,
  /(^|\/)reports\/session_usage\//,
  /(^|\/)reports\/opencode-sessions\.json$/,
  /(^|\/)\.opencode\//,
];

/** How long to wait for the event stream to end once the server is closing. */
const DRAIN_TIMEOUT_MS = 3000;

/** An error that already knows which contract exit code it is. */
export class AdapterError extends Error {
  readonly exitCode: number;
  constructor(exitCode: number, message: string) {
    super(message);
    this.exitCode = exitCode;
  }
}

export type RunResult = {
  exitCode: number;
  runtimeSessionId: string | null;
  sawUsage: boolean;
};

type Deferred<T> = { promise: Promise<T>; resolve: (value: T) => void };

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((inner) => {
    resolve = inner;
  });
  return { promise, resolve };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export function describeError(error: unknown): string {
  if (error === null || error === undefined) return "unknown session error";
  if (typeof error === "string") return error;
  if (typeof error === "object") {
    const record = error as Record<string, unknown>;
    const data = record["data"];
    if (data && typeof data === "object") {
      const message = (data as Record<string, unknown>)["message"];
      if (typeof message === "string" && message.length > 0) return message;
    }
    const message = record["message"];
    if (typeof message === "string" && message.length > 0) return message;
    const name = record["name"];
    if (typeof name === "string" && name.length > 0) return name;
  }
  return String(error);
}

export function relativeTo(root: string, file: string): string | null {
  const normalizedRoot = root.replace(/\\/g, "/").replace(/\/+$/, "");
  const normalized = file.replace(/\\/g, "/");
  if (!normalized.startsWith(`${normalizedRoot}/`)) return null;
  return normalized.slice(normalizedRoot.length + 1);
}

/** Whether a changed path is the runtime's own bookkeeping. */
export function isIgnoredChange(path: string): boolean {
  return IGNORED_CHANGE_PATTERNS.some((pattern) => pattern.test(path));
}

/** Reasoning effort travels as a provider model option, not as a model name. */
export function serverConfig(
  providerID: string,
  modelID: string,
  reasoning: string,
): Record<string, unknown> {
  return {
    provider: {
      [providerID]: {
        models: {
          [modelID]: {
            options: { reasoningEffort: reasoning },
          },
        },
      },
    },
  };
}

async function resolveAgent(client: OpencodeClient): Promise<string | undefined> {
  try {
    const result = await client.app.agents();
    const agents = result.data ?? [];
    const primaries = agents.filter((agent) => agent.mode !== "subagent");
    const build = primaries.find((agent) => agent.name === "build");
    return (build ?? primaries[0])?.name;
  } catch {
    return undefined;
  }
}

async function assertModelAvailable(
  client: OpencodeClient,
  providerID: string,
  modelID: string,
  console: Console,
): Promise<void> {
  let result;
  try {
    result = await client.config.providers();
  } catch (error) {
    console.line(
      `  ! could not verify model availability: ${describeError(error)}`,
    );
    return;
  }
  const providers = result.data?.providers;
  if (!providers) {
    console.line("  ! could not verify model availability: no provider list");
    return;
  }
  const provider = providers.find((entry) => entry.id === providerID);
  const models = provider?.models ?? {};
  if (!provider || !Object.prototype.hasOwnProperty.call(models, modelID)) {
    const available = Object.keys(models).sort().slice(0, 40).join(", ");
    throw new AdapterError(
      EXIT_MODEL_UNAVAILABLE,
      `Model '${providerID}/${modelID}' is not available to OpenCode. ` +
        `Available for '${providerID}': ${available || "(none)"}`,
    );
  }
}

/** Open a new session, or prove the recorded one may be resumed. */
async function resolveSession(
  client: OpencodeClient,
  args: AdapterArgs,
  root: string,
): Promise<string> {
  const expected = {
    directory: root,
    model: args.model,
    reasoning: args.reasoning,
  };
  const existing = getEntry(root, args.sessionId);

  if (args.resume) {
    if (!existing) {
      throw new AdapterError(
        EXIT_RUNTIME_FAILURE,
        `no OpenCode session is recorded for harness session ${args.sessionId}; ` +
          `refusing to guess which session to continue`,
      );
    }
    const rejection = mappingRejection(existing, expected);
    if (rejection) {
      throw new AdapterError(EXIT_RUNTIME_FAILURE, rejection);
    }
    const result = await client.session.get({
      path: { id: existing.opencode_session_id },
    });
    if (result.error || !result.data) {
      throw new AdapterError(
        EXIT_RUNTIME_FAILURE,
        `the recorded OpenCode session ${existing.opencode_session_id} could not ` +
          `be loaded: ${describeError(result.error)}`,
      );
    }
    return existing.opencode_session_id;
  }

  if (existing) {
    throw new AdapterError(
      EXIT_RUNTIME_FAILURE,
      `harness session ${args.sessionId} is already mapped to OpenCode session ` +
        `${existing.opencode_session_id}; a fresh invocation must not adopt it`,
    );
  }

  const title = args.phase
    ? `researcher ${args.phase}${args.experiment === null ? "" : ` e${args.experiment}`}`
    : "researcher session";
  const created = await client.session.create({ body: { title } });
  if (created.error || !created.data) {
    throw new AdapterError(
      EXIT_RUNTIME_FAILURE,
      `could not create an OpenCode session: ${describeError(created.error)}`,
    );
  }
  const entry: SessionMappingEntry = {
    opencode_session_id: created.data.id,
    directory: root,
    model: args.model,
    reasoning: args.reasoning,
    campaign_id: args.campaignId,
    experiment: args.experiment,
    phase: args.phase,
    created_at: new Date().toISOString(),
  };
  putEntry(root, args.sessionId, entry);
  return created.data.id;
}

/**
 * Apply the command policy to one permission request.
 *
 * This is internal plumbing, not a user workflow: every request is answered
 * automatically, so an unattended session never waits for a human. A permitted
 * operation is approved once rather than remembered, so a broad approval can
 * never bypass a later command check.
 */
async function answerPermission(
  client: OpencodeClient,
  sessionID: string,
  console: Console,
  permission: {
    id: string;
    type?: string;
    title?: string;
    pattern?: string | string[];
    metadata?: Record<string, unknown>;
    callID?: string;
  },
): Promise<void> {
  const commandText = permissionCommandText(permission);
  const reason = commandText ? commandDenial(commandText) : null;
  if (reason) {
    console.denied(reason, permission.callID ?? null);
  }
  const result = await client.postSessionIdPermissionsPermissionId({
    path: { id: sessionID, permissionID: permission.id },
    body: { response: reason ? "reject" : "once" },
  });
  if (result.error) {
    console.line(
      `  ! could not answer permission ${permission.id}: ${describeError(result.error)}`,
    );
  }
}

export async function run(args: AdapterArgs, console: Console): Promise<RunResult> {
  const root = process.cwd();
  const { providerID, modelID } = splitModel(args.model);

  if (!REASONING_EFFORTS.has(args.reasoning)) {
    throw new AdapterError(
      EXIT_RUNTIME_FAILURE,
      `OpenCode has no '${args.reasoning}' reasoning effort for this model; ` +
        `use one of ${[...REASONING_EFFORTS].join(", ")}`,
    );
  }

  const server = await createOpencodeServer({
    hostname: "127.0.0.1",
    // 0 prefers the conventional port and otherwise takes a free one, so two
    // worktrees never silently share a server.
    port: 0,
    timeout: 30_000,
    config: serverConfig(providerID, modelID, args.reasoning),
  });

  // The stream ends when the closing server drops it; bounded below so a stuck
  // socket can never hold the launcher open after the summary.
  let drain: Promise<void> = Promise.resolve();
  try {
    const client = createOpencodeClient({ baseUrl: server.url, directory: root });
    await assertModelAvailable(client, providerID, modelID, console);

    const sessionID = await resolveSession(client, args, root);
    const agent = await resolveAgent(client);
    const before = worktreeStatus(root);
    const started = performance.now();

    const subscription = await client.event.subscribe();
    const idle = deferred<void>();
    const interrupted = deferred<void>();
    const onSigint = (): void => interrupted.resolve();
    process.once("SIGINT", onSigint);

    const muted = { value: false };
    const printedChars = new Map<string, number>();
    const announcedTools = new Set<string>();
    let latestModelID = modelID;
    let sawUsage = false;

    drain = (async (): Promise<void> => {
      for await (const event of subscription.stream as AsyncGenerator<Event>) {
        if (muted.value) break;
        handleEvent(event);
      }
    })().catch((error: unknown) => {
      if (!muted.value) console.line(`  ! event stream ended: ${describeError(error)}`);
    });

    function handleEvent(event: Event): void {
      switch (event.type) {
        case "message.updated": {
          const info = event.properties.info;
          if (info.role === "assistant") latestModelID = info.modelID;
          return;
        }
        case "message.part.updated": {
          const part = event.properties.part;
          if (part.sessionID !== sessionID) return;
          switch (part.type) {
            case "text": {
              // Deltas are streamed, but a part may also arrive as a whole
              // snapshot. Tracking what was already printed makes the two
              // idempotent, so no text is lost and none is printed twice.
              const emitted = printedChars.get(part.id) ?? 0;
              if (part.text.length > emitted) {
                console.delta(part.text.slice(emitted));
                printedChars.set(part.id, part.text.length);
              }
              return;
            }
            case "tool": {
              const state = part.state;
              // A short tool can reach a terminal state without a visible
              // running update, so announce on first sight of the call ID.
              if (!announcedTools.has(part.callID)) {
                announcedTools.add(part.callID);
                console.tool(part.tool, state.input, part.callID);
              }
              // A call this harness already rejected reported its own reason.
              if (state.status === "error" && !console.deniedCalls.has(part.callID)) {
                console.toolFailed(state.error, part.tool, state.input);
              }
              return;
            }
            case "step-start": {
              console.turnStart(latestModelID);
              return;
            }
            case "step-finish": {
              console.turnEnd();
              sawUsage = true;
              console.promptTokens += part.tokens.input;
              console.cacheReadTokens += part.tokens.cache.read;
              console.cacheWriteTokens += part.tokens.cache.write;
              console.outputTokens += part.tokens.output;
              console.reasoningTokens += part.tokens.reasoning;
              console.cost += part.cost;
              return;
            }
            default:
              return;
          }
        }
        case "permission.updated": {
          const permission = event.properties;
          if (permission.sessionID !== sessionID) return;
          void answerPermission(client, sessionID, console, permission);
          return;
        }
        case "file.watcher.updated": {
          const file = relativeTo(root, event.properties.file);
          if (!file || isIgnoredChange(file)) return;
          const raw = event.properties.event;
          const operation: FileOperation =
            raw === "add" ? "created" : raw === "unlink" ? "deleted" : "modified";
          console.fileChanged(operation, file);
          return;
        }
        case "session.status": {
          if (event.properties.sessionID !== sessionID) return;
          if (event.properties.status.type === "retry") {
            console.line("  ~ provider retry in progress");
          }
          return;
        }
        case "session.error": {
          if (event.properties.sessionID && event.properties.sessionID !== sessionID) {
            return;
          }
          console.error(describeError(event.properties.error));
          return;
        }
        case "session.idle": {
          if (event.properties.sessionID !== sessionID) return;
          console.turnEnd();
          idle.resolve();
          return;
        }
        default:
          return;
      }
    }

    const timeoutHandle = { id: undefined as NodeJS.Timeout | undefined };
    const timedOut = new Promise<"timeout">((resolve) => {
      timeoutHandle.id = setTimeout(() => resolve("timeout"), args.timeout * 1000);
    });

    let outcome: "idle" | "timeout" | "interrupt" = "idle";
    try {
      const prompt = await client.session.promptAsync({
        path: { id: sessionID },
        body: {
          model: { providerID, modelID },
          ...(agent ? { agent } : {}),
          system: POLICY,
          tools: DISABLED_TOOLS,
          parts: [{ type: "text", text: args.prompt }],
        },
      });
      if (prompt.error) {
        throw new AdapterError(
          EXIT_RUNTIME_FAILURE,
          `could not submit the prompt: ${describeError(prompt.error)}`,
        );
      }

      outcome = await Promise.race([
        idle.promise.then(() => "idle" as const),
        interrupted.promise.then(() => "interrupt" as const),
        timedOut,
      ]);
    } finally {
      if (timeoutHandle.id) clearTimeout(timeoutHandle.id);
      process.removeListener("SIGINT", onSigint);
    }

    if (outcome !== "idle") {
      try {
        await client.session.abort({ path: { id: sessionID } });
      } catch (error) {
        console.line(`  ! could not abort the session: ${describeError(error)}`);
      }
      console.line(
        outcome === "timeout"
          ? `  ! session timed out after ${args.timeout}s`
          : "  ! session interrupted",
      );
    }

    // Everything the human sees has been decided; stop streaming so no late
    // event lands after the summary.
    muted.value = true;
    console.summary(
      args.sessionId,
      changedSince(root, before),
      (performance.now() - started) / 1000,
    );

    if (outcome === "timeout") {
      return { exitCode: EXIT_TIMEOUT, runtimeSessionId: sessionID, sawUsage };
    }
    if (outcome === "interrupt") {
      return { exitCode: EXIT_INTERRUPTED, runtimeSessionId: sessionID, sawUsage };
    }
    return {
      exitCode: console.sessionError ? EXIT_SESSION_ERROR : EXIT_OK,
      runtimeSessionId: sessionID,
      sawUsage,
    };
  } finally {
    // Only this invocation's server is closed; persisted OpenCode history stays.
    server.close();
    await Promise.race([drain, delay(DRAIN_TIMEOUT_MS)]);
  }
}

export function buildUsageRow(
  args: AdapterArgs,
  console: Console,
  result: RunResult,
  elapsedSeconds: number,
): UsageRow {
  return {
    campaign_id: args.campaignId ?? "",
    experiment: args.experiment,
    phase: args.phase,
    attempt: args.attempt,
    session_id: args.sessionId,
    recorded_at: new Date().toISOString(),
    model: args.model,
    reasoning: args.reasoning,
    duration_seconds: Number(elapsedSeconds.toFixed(3)),
    exit_code: result.exitCode,
    input_tokens: result.sawUsage ? console.promptTokens : null,
    cache_read_tokens: result.sawUsage ? console.cacheReadTokens : null,
    output_tokens: result.sawUsage ? console.outputTokens : null,
    aiu: null,
    tool_calls: console.toolCalls,
    tools_by_name: Object.fromEntries(console.toolCounts),
    runtime: RUNTIME_ID,
    runtime_session_id: result.runtimeSessionId,
    usage_schema_version: USAGE_SCHEMA_VERSION,
    cache_write_tokens: result.sawUsage ? console.cacheWriteTokens : null,
    reasoning_tokens: result.sawUsage ? console.reasoningTokens : null,
    reported_cost_usd: result.sawUsage ? Number(console.cost.toFixed(6)) : null,
  };
}

export { appendUsage };
