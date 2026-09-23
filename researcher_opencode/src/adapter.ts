/**
 * One bounded Researcher session, executed through the official OpenCode
 * TypeScript SDK.
 *
 * The launcher owns the research protocol and decides whether a phase is
 * complete; this adapter owns only the OpenCode session runtime: session
 * identity, the event stream that witnesses it, the tool profile, the
 * command policy, and what reaches the console. Nothing printed here is read
 * back as a scientific fact.
 *
 * The event stream is a witness, not the authority. It can end or lose a
 * connection while the session is still working, and the server cannot be asked
 * to replay what was missed, so a stream that stops being trustworthy is
 * settled against the session's own state instead of being waited out.
 *
 * It runs beside `researcher_copilot.py`, not instead of it. Both accept the same
 * argument list and speak the same console, so the launcher can choose a backend
 * per phase without either adapter knowing about the other.
 */

import { createOpencodeClient, createOpencodeServer } from "@opencode-ai/sdk";
import type { Event, OpencodeClient } from "@opencode-ai/sdk";
import { existsSync } from "node:fs";

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
const STOP_REQUEST_ENV = "ROBOT_RESEARCH_STOP_REQUEST";
const STOP_POLL_MS = 100;

export function watchStopRequest(
  onStop: () => void,
  requestPath = process.env[STOP_REQUEST_ENV],
  pollMs = STOP_POLL_MS,
): () => void {
  if (!requestPath) return () => undefined;

  const poll = (): void => {
    if (existsSync(requestPath)) onStop();
  };
  poll();
  const timer = setInterval(poll, pollMs);
  timer.unref();
  return () => clearInterval(timer);
}

/** Tools that would exceed the Researcher profile: delegation, the wider
 * network, and the session todo list. Disabling a name the server does not have
 * is harmless. */
const DISABLED_TOOLS: Record<string, boolean> = {
  task: false,
  webfetch: false,
  todowrite: false,
  todoread: false,
};

const CAMPAIGN_CONTEXT_GUIDANCE = `- Use research/brief.md and the campaign artifacts as the authoritative
  scientific context. Do not use Git history as scientific evidence or as a
  routine workspace-discovery step.`;
const PRELIMINARY_CONTEXT_GUIDANCE = `- In the preliminary scientific-model phase, use only the human-authored
  robot and task specification, not research/brief.md or campaign artifacts.
  Do not use Git history as scientific evidence or routine workspace discovery.`;

const POLICY = `<harness_policy>
This session runs inside the repository worktree the launcher selected. The
harness enforces the rules below at the tool boundary, so a rejected call fails
rather than succeeding silently. A rejection names the sanctioned alternative;
follow it instead of retrying the same command.

- The launcher executes experiments. Never invoke research/run_experiment.py,
  training, the viewer, or the final benchmark.
${CAMPAIGN_CONTEXT_GUIDANCE}
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

export function policyForContext(preliminary: boolean): string {
  return preliminary
    ? POLICY.replace(CAMPAIGN_CONTEXT_GUIDANCE, PRELIMINARY_CONTEXT_GUIDANCE)
    : POLICY;
}

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

/** How many times a stream that ended while the session's outcome was still
 * unknown is re-established before the run is reported as unobservable. */
const STREAM_RECONNECT_ATTEMPTS = 3;

/** Delay before the first reconnect; doubled for each further attempt. */
const STREAM_RECONNECT_DELAY_MS = 500;

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

type PermissionAskedEvent = {
  type: "permission.asked";
  properties: {
    id: string;
    sessionID: string;
    permission: string;
    patterns: string[];
    metadata: Record<string, unknown>;
    tool?: { callID: string };
  };
};

type RuntimeEvent = Event | PermissionAskedEvent;

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

/** Release every runtime handle before returning control to the launcher. */
export async function shutdownRuntime(
  eventAbort: AbortController,
  closeServer: () => void,
  drain: Promise<void>,
  drainTimeoutMs: number = DRAIN_TIMEOUT_MS,
): Promise<void> {
  // Do not rely on server shutdown to wake a blocked SSE read. On Windows the
  // server may already be gone while the fetch stream still retains handles,
  // which prevents Node from exiting and leaves the launcher waiting forever.
  eventAbort.abort();
  closeServer();
  await Promise.race([drain, delay(drainTimeoutMs)]);
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
    permission: { bash: "ask" },
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

/**
 * What the server, rather than the event stream, says about a session.
 *
 * `working` is deliberately distinct from `unknown`: a busy session must never
 * be reported as complete, while an unreadable one must never be reported as
 * either.
 */
export type SessionLiveness = "done" | "working" | "unknown";

/** The newest message in a session, captured before a run's prompt so an
 * earlier turn's completed answer can never be read as this run's. */
export async function lastMessageID(
  client: OpencodeClient,
  sessionID: string,
): Promise<string | null> {
  try {
    const result = await client.session.messages({ path: { id: sessionID } });
    const list = result.data ?? [];
    return list[list.length - 1]?.info.id ?? null;
  } catch {
    return null;
  }
}

/**
 * Ask the server what a session is doing.
 *
 * The status map is trusted when it answers; when it is silent the last message
 * is consulted instead. Exactly one prompt is submitted per invocation, so a
 * completed assistant message newer than the pre-run baseline is that prompt's
 * answer.
 */
export async function sessionLiveness(
  client: OpencodeClient,
  sessionID: string,
  baselineMessageID: string | null = null,
): Promise<SessionLiveness> {
  try {
    const status = await client.session.status();
    const entry = status.data?.[sessionID];
    if (entry?.type === "idle") return "done";
    // Busy or retrying: the session is demonstrably still working.
    if (entry) return "working";
  } catch {
    // Unreachable server; the message check below may still answer.
  }
  try {
    const result = await client.session.messages({ path: { id: sessionID } });
    const list = result.data ?? [];
    const last = list[list.length - 1]?.info;
    if (last?.role === "assistant" && last.time.completed && last.id !== baselineMessageID) {
      return "done";
    }
  } catch {
    // Fall through: an unreadable state is unknown, never complete.
  }
  return "unknown";
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

  const ownedServer = args.serverUrl
    ? null
    : await createOpencodeServer({
        hostname: "127.0.0.1",
        port: 0,
        timeout: 30_000,
        config: serverConfig(providerID, modelID, args.reasoning),
      });
  const serverUrl = args.serverUrl ?? ownedServer!.url;
  const eventAbort = new AbortController();

  // The stream ends when the closing server drops it; bounded below so a stuck
  // socket can never hold the launcher open after the summary.
  let drain: Promise<void> = Promise.resolve();
  try {
    const client = createOpencodeClient({ baseUrl: serverUrl, directory: root });
    await assertModelAvailable(client, providerID, modelID, console);

    const sessionID = await resolveSession(client, args, root);
    const agent = await resolveAgent(client);
    const before = worktreeStatus(root);
    const started = performance.now();

    const idle = deferred<void>();
    const interrupted = deferred<void>();
    /** The session's outcome could not be established from either the stream or
     * the server. This is a distinct ending from a timeout. */
    const unobservable = deferred<void>();
    const onSigint = (): void => interrupted.resolve();
    process.once("SIGINT", onSigint);
    const stopWatching = watchStopRequest(() => interrupted.resolve());

    const muted = { value: false };
    // Set once the run has an outcome, so supervision stops second-guessing it.
    const decided = { value: false };
    // Set once this run's prompt exists, so no earlier state is read as its answer.
    const submitted = { value: false };
    let baseline: string | null = null;
    const printedChars = new Map<string, number>();
    const announcedTools = new Set<string>();
    let latestModelID = modelID;
    let sawUsage = false;
    let reportedLoss = false;
    let reconciling = false;

    /**
     * Settle the run against the session's own state.
     *
     * Used whenever the event stream stops being a reliable witness. Events
     * emitted while the stream was down are never re-delivered, so the stream
     * cannot be relied on to deliver the completion it witnessed; the server is
     * asked instead, rather than waiting for the invocation timeout and then
     * aborting work that may already be finished.
     */
    async function reconcile(): Promise<SessionLiveness> {
      if (!submitted.value) return "unknown";
      const liveness = await sessionLiveness(client, sessionID, baseline);
      if (liveness === "done" && !muted.value && !decided.value) {
        console.line(
          "  ! session completion confirmed from the server, not from the event stream; " +
            "usage may omit work the stream never delivered",
        );
        idle.resolve();
      }
      return liveness;
    }

    /**
     * Open the event stream.
     *
     * The SDK retries a failed connection by itself, so connection churn is
     * otherwise invisible; the first failure is reported and reconciled because
     * the gap it opens can swallow the session's completion.
     */
    async function subscribe(): Promise<AsyncGenerator<RuntimeEvent>> {
      const subscription = await client.event.subscribe({
        signal: eventAbort.signal,
        onSseError: (error: unknown): void => {
          if (muted.value || decided.value || eventAbort.signal.aborted || reconciling) return;
          if (!reportedLoss) {
            reportedLoss = true;
            console.line(`  ! event stream connection failed: ${describeError(error)}`);
          }
          reconciling = true;
          void reconcile()
            .catch((failure: unknown) => {
              console.line(`  ! could not read the session state: ${describeError(failure)}`);
            })
            .finally(() => {
              reconciling = false;
            });
        },
      });
      return subscription.stream as AsyncGenerator<RuntimeEvent>;
    }

    async function consume(stream: AsyncGenerator<RuntimeEvent>): Promise<void> {
      for await (const event of stream) {
        if (muted.value) return;
        handleEvent(event);
      }
    }

    // Subscribed before the prompt, because the server cannot subsequently be
    // asked to replay what a late subscription missed.
    let stream: AsyncGenerator<RuntimeEvent> | null = await subscribe();

    drain = (async (): Promise<void> => {
      for (let attempt = 0; ; attempt += 1) {
        if (stream) {
          try {
            await consume(stream);
          } catch (error) {
            if (!muted.value) {
              console.line(`  ! event stream ended: ${describeError(error)}`);
            }
          }
        }
        if (muted.value || decided.value || eventAbort.signal.aborted) return;
        // The stream is over. Unless the session is provably finished, the
        // runtime has lost its only witness and must not guess.
        if ((await reconcile()) === "done") return;
        if (attempt >= STREAM_RECONNECT_ATTEMPTS) {
          unobservable.resolve();
          return;
        }
        console.line(
          "  ! event stream ended with the session's outcome still unknown; " +
            `reconnecting (attempt ${attempt + 1} of ${STREAM_RECONNECT_ATTEMPTS})`,
        );
        await delay(STREAM_RECONNECT_DELAY_MS * 2 ** attempt);
        if (muted.value || decided.value || eventAbort.signal.aborted) return;
        stream = null;
        try {
          stream = await subscribe();
        } catch (error) {
          if (!muted.value) {
            console.line(`  ! could not reopen the event stream: ${describeError(error)}`);
          }
        }
      }
    })().catch((error: unknown) => {
      if (!muted.value) console.line(`  ! event supervision failed: ${describeError(error)}`);
    });

    function handleEvent(event: RuntimeEvent): void {
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
        case "permission.asked": {
          const permission = event.properties;
          if (permission.sessionID !== sessionID) return;
          void answerPermission(client, sessionID, console, {
            id: permission.id,
            type: permission.permission,
            pattern: permission.patterns,
            metadata: permission.metadata,
            callID: permission.tool?.callID,
          });
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

    let outcome: "idle" | "timeout" | "interrupt" | "unobservable" = "idle";
    try {
      // Where the session stood before this prompt. A resumed session already
      // holds a completed answer, and only a message past this point is this
      // run's.
      baseline = await lastMessageID(client, sessionID);
      const prompt = await client.session.promptAsync({
        path: { id: sessionID },
        body: {
          model: { providerID, modelID },
          ...(agent ? { agent } : {}),
          system: policyForContext(args.preliminary),
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
      submitted.value = true;

      outcome = await Promise.race([
        idle.promise.then(() => "idle" as const),
        interrupted.promise.then(() => "interrupt" as const),
        unobservable.promise.then(() => "unobservable" as const),
        timedOut,
      ]);
    } finally {
      // The outcome is settled; supervision must not reopen anything now.
      decided.value = true;
      if (timeoutHandle.id) clearTimeout(timeoutHandle.id);
      process.removeListener("SIGINT", onSigint);
      stopWatching();
    }

    if (outcome !== "idle") {
      try {
        await client.session.abort({ path: { id: sessionID } });
      } catch (error) {
        console.line(`  ! could not abort the session: ${describeError(error)}`);
      }
      if (outcome === "timeout") {
        console.line(`  ! session timed out after ${args.timeout}s`);
      } else if (outcome === "interrupt") {
        console.line("  ! session interrupted");
      } else {
        console.line(
          "  ! the event stream could not be re-established and the server did not " +
            "confirm the session finished",
        );
      }
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
    if (outcome === "unobservable") {
      // Not a timeout: the invocation is ending because the runtime lost the
      // ability to tell whether the session finished, and reports neither answer.
      return { exitCode: EXIT_RUNTIME_FAILURE, runtimeSessionId: sessionID, sawUsage };
    }
    return {
      exitCode: console.sessionError ? EXIT_SESSION_ERROR : EXIT_OK,
      runtimeSessionId: sessionID,
      sawUsage,
    };
  } finally {
    await shutdownRuntime(eventAbort, () => ownedServer?.close(), drain);
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
