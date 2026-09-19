import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import {
  buildUsageRow,
  describeError,
  isIgnoredChange,
  lastMessageID,
  relativeTo,
  serverConfig,
  sessionLiveness,
  shutdownRuntime,
  watchStopRequest,
} from "../src/adapter.ts";
import type { OpencodeClient } from "@opencode-ai/sdk";
import { parseArgs } from "../src/args.ts";
import { Console } from "../src/console.ts";

/** A client that answers only the two reads liveness reconciliation performs. */
function fakeClient(parts: {
  status?: unknown;
  statusThrows?: boolean;
  messages?: unknown;
  messagesThrows?: boolean;
}): OpencodeClient {
  return {
    session: {
      status: async () => {
        if (parts.statusThrows) throw new Error("server unreachable");
        return { data: parts.status };
      },
      messages: async () => {
        if (parts.messagesThrows) throw new Error("server unreachable");
        return { data: parts.messages };
      },
    },
  } as unknown as OpencodeClient;
}

function message(id: string, role: "assistant" | "user", completed?: number): unknown {
  return {
    info: {
      id,
      role,
      time: completed === undefined ? { created: 1 } : { created: 1, completed },
    },
    parts: [],
  };
}

test("worktree-relative paths are resolved across separator styles", () => {
  assert.equal(relativeTo("C:\\work\\tree", "C:\\work\\tree\\a\\b.py"), "a/b.py");
  assert.equal(relativeTo("C:/work/tree", "C:/work/tree/a/b.py"), "a/b.py");
  assert.equal(relativeTo("C:/work/tree/", "C:/work/tree/a.py"), "a.py");
  assert.equal(relativeTo("C:/work/tree", "C:/work/other/a.py"), null);
  assert.equal(relativeTo("C:/work/tree", "C:/work/treehouse/a.py"), null);
});

test("runtime bookkeeping is not reported as research work", () => {
  assert.equal(isIgnoredChange(".git/index"), true);
  assert.equal(isIgnoredChange("node_modules/x/y.js"), true);
  assert.equal(isIgnoredChange("reports/session_usage/c.jsonl"), true);
  assert.equal(isIgnoredChange("reports/opencode-sessions.json"), true);
  assert.equal(isIgnoredChange("robot_learning/scenario/reward.py"), false);
  assert.equal(isIgnoredChange("reports/campaign-x.md"), false);
});

test("reasoning is expressed as a provider model option", () => {
  const config = serverConfig("opencode-go", "gpt-5.6-luna", "high") as any;
  assert.deepEqual(config.provider["opencode-go"].models["gpt-5.6-luna"].options, {
    reasoningEffort: "high",
  });
  assert.deepEqual(config.permission, { bash: "ask" });
});

test("runtime shutdown aborts the event stream before closing the server", async () => {
  const order: string[] = [];
  const eventAbort = new AbortController();
  let finishDrain!: () => void;
  const drain = new Promise<void>((resolve) => {
    finishDrain = resolve;
  });
  eventAbort.signal.addEventListener("abort", () => {
    order.push("abort");
    finishDrain();
  });

  await shutdownRuntime(eventAbort, () => order.push("close"), drain, 100);

  assert.equal(eventAbort.signal.aborted, true);
  assert.deepEqual(order, ["abort", "close"]);
});

test("a run-scoped stop request reaches the interrupt outcome", async () => {
  const directory = mkdtempSync(join(tmpdir(), "opencode-stop-"));
  const request = join(directory, "stop.request");
  let resolve!: () => void;
  const stopped = new Promise<void>((done) => {
    resolve = done;
  });
  const close = watchStopRequest(resolve, request, 5);

  try {
    writeFileSync(request, "");
    await Promise.race([
      stopped,
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("stop request was not observed")), 1000),
      ),
    ]);
  } finally {
    close();
    rmSync(directory, { recursive: true, force: true });
  }
});

test("errors are described from the shapes the SDK actually returns", () => {
  assert.equal(describeError({ data: { message: "boom" } }), "boom");
  assert.equal(describeError({ message: "boom" }), "boom");
  assert.equal(describeError({ name: "ProviderAuthError" }), "ProviderAuthError");
  assert.equal(describeError("plain"), "plain");
  assert.equal(describeError(undefined), "unknown session error");
});

test("session liveness is read from the server, not from the event stream", async () => {
  assert.equal(
    await sessionLiveness(fakeClient({ status: { ses_1: { type: "idle" } } }), "ses_1"),
    "done",
  );
  assert.equal(
    await sessionLiveness(fakeClient({ status: { ses_1: { type: "busy" } } }), "ses_1"),
    "working",
  );
  assert.equal(
    await sessionLiveness(
      fakeClient({ status: { ses_1: { type: "retry", attempt: 2, message: "busy", next: 5 } } }),
      "ses_1",
    ),
    "working",
  );
});

test("a still-busy session is never reported as complete", async () => {
  // A resumed session already holds a completed answer. It must not be read as
  // this run's answer while the session is demonstrably still working.
  const client = fakeClient({
    status: { ses_1: { type: "busy" } },
    messages: [message("msg_old", "assistant", 1700000000000)],
  });
  assert.equal(await sessionLiveness(client, "ses_1", "msg_old"), "working");
});

test("only an answer newer than the pre-run baseline proves completion", async () => {
  const newer = fakeClient({
    status: {},
    messages: [message("msg_old", "assistant", 1), message("msg_new", "assistant", 2)],
  });
  assert.equal(await sessionLiveness(newer, "ses_1", "msg_old"), "done");

  // Without that baseline the completed answer is an earlier turn's, and proves
  // nothing about the run whose stream was lost.
  const stale = fakeClient({ status: {}, messages: [message("msg_old", "assistant", 1)] });
  assert.equal(await sessionLiveness(stale, "ses_1", "msg_old"), "unknown");

  const userTurn = fakeClient({ status: {}, messages: [message("msg_1", "user")] });
  assert.equal(await sessionLiveness(userTurn, "ses_1", null), "unknown");
});

test("an unreadable session state is unknown, never complete", async () => {
  const client = fakeClient({ statusThrows: true, messagesThrows: true });
  assert.equal(await sessionLiveness(client, "ses_1", null), "unknown");
});

test("the pre-run baseline is the newest message the session already holds", async () => {
  const existing = fakeClient({
    messages: [message("msg_old", "assistant", 1), message("msg_new", "user")],
  });
  assert.equal(await lastMessageID(existing, "ses_1"), "msg_new");
  assert.equal(await lastMessageID(fakeClient({ messages: [] }), "ses_1"), null);
  assert.equal(await lastMessageID(fakeClient({ messagesThrows: true }), "ses_1"), null);
});

test("usage records nulls rather than inventing zero when nothing was reported", () => {
  const args = parseArgs([
    "--session-id",
    "11111111-2222-3333-4444-555555555555",
    "--campaign-id",
    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "--model",
    "opencode-go/gpt-5.6-luna",
    "prompt",
  ]);
  const console = new Console();

  const missing = buildUsageRow(
    args,
    console,
    { exitCode: 0, runtimeSessionId: "ses_1", sawUsage: false },
    1.5,
  );
  assert.equal(missing.input_tokens, null);
  assert.equal(missing.output_tokens, null);
  assert.equal(missing.reported_cost_usd, null);
  assert.equal(missing.aiu, null);
  assert.equal(missing.runtime, "opencode");
  assert.equal(missing.runtime_session_id, "ses_1");
  assert.equal(missing.session_id, args.sessionId);

  console.promptTokens = 1000;
  console.cacheReadTokens = 800;
  console.outputTokens = 20;
  console.cost = 0.25;
  const reported = buildUsageRow(
    args,
    console,
    { exitCode: 0, runtimeSessionId: "ses_1", sawUsage: true },
    2,
  );
  assert.equal(reported.input_tokens, 1000);
  assert.equal(reported.cache_read_tokens, 800);
  assert.equal(reported.output_tokens, 20);
  assert.equal(reported.reported_cost_usd, 0.25);
  // AIU stays null: OpenCode cost is a runtime estimate, not Copilot billing.
  assert.equal(reported.aiu, null);
});
