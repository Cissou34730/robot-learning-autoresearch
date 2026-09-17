import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildUsageRow,
  describeError,
  isIgnoredChange,
  relativeTo,
  serverConfig,
  shutdownRuntime,
} from "../src/adapter.ts";
import { parseArgs } from "../src/args.ts";
import { Console } from "../src/console.ts";

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

test("errors are described from the shapes the SDK actually returns", () => {
  assert.equal(describeError({ data: { message: "boom" } }), "boom");
  assert.equal(describeError({ message: "boom" }), "boom");
  assert.equal(describeError({ name: "ProviderAuthError" }), "ProviderAuthError");
  assert.equal(describeError("plain"), "plain");
  assert.equal(describeError(undefined), "unknown session error");
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
