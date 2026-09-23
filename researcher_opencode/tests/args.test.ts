import assert from "node:assert/strict";
import { test } from "node:test";

import { parseArgs, REASONING_EFFORTS, splitModel, UsageError } from "../src/args.ts";

const BASE = ["--session-id", "abc", "do the thing"];

test("parses the launcher's argument list", () => {
  const args = parseArgs([
    "--session-id",
    "11111111-2222-3333-4444-555555555555",
    "--model",
    "opencode-go/gpt-5.6-luna",
    "--reasoning",
    "high",
    "--server-url",
    "http://127.0.0.1:4096",
    "--experiment",
    "7",
    "--phase",
    "proposal",
    "--attempt",
    "2",
    "--campaign-id",
    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "--resume",
    "--preliminary",
    "the prompt text",
  ]);
  assert.equal(args.sessionId, "11111111-2222-3333-4444-555555555555");
  assert.equal(args.model, "opencode-go/gpt-5.6-luna");
  assert.equal(args.reasoning, "high");
  assert.equal(args.serverUrl, "http://127.0.0.1:4096");
  assert.equal(args.experiment, 7);
  assert.equal(args.phase, "proposal");
  assert.equal(args.attempt, 2);
  assert.equal(args.campaignId, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
  assert.equal(args.resume, true);
  assert.equal(args.preliminary, true);
  assert.equal(args.prompt, "the prompt text");
});

test("the prompt is the only positional and may appear last", () => {
  const args = parseArgs(["a prompt with spaces", "--session-id", "abc"]);
  assert.equal(args.prompt, "a prompt with spaces");
});

test("defaults match the adapter contract", () => {
  const args = parseArgs(BASE);
  assert.equal(args.resume, false);
  assert.equal(args.preliminary, false);
  assert.equal(args.attempt, 1);
  assert.equal(args.timeout, 1800);
  assert.equal(args.experiment, null);
  assert.equal(args.phase, null);
  assert.equal(args.campaignId, null);
  assert.equal(args.serverUrl, null);
  assert.equal(args.model, "opencode-go/deepseek-v4.1-flash");
});

test("a missing session id is a usage error", () => {
  assert.throws(() => parseArgs(["just a prompt"]), UsageError);
});

test("an unknown flag is a usage error rather than being ignored", () => {
  assert.throws(() => parseArgs([...BASE, "--wat"]), UsageError);
});

test("an unsupported reasoning value is rejected, never ignored", () => {
  assert.throws(() => parseArgs([...BASE, "--reasoning", "extreme"]), UsageError);
});

test("a non-integer experiment is a usage error", () => {
  assert.throws(() => parseArgs([...BASE, "--experiment", "x"]), UsageError);
});

test("model must be provider-qualified", () => {
  assert.deepEqual(splitModel("opencode-go/gpt-5.6-luna"), {
    providerID: "opencode-go",
    modelID: "gpt-5.6-luna",
  });
  assert.throws(() => splitModel("gpt-5.6-luna"), UsageError);
  assert.throws(() => splitModel("/leading"), UsageError);
  assert.throws(() => splitModel("trailing/"), UsageError);
});

test("'max' is not an OpenCode reasoning effort", () => {
  // Copilot accepts it; OpenCode has no such effort for these models, and the
  // adapter must say so rather than silently substituting one.
  assert.equal(REASONING_EFFORTS.has("max"), false);
  assert.equal(REASONING_EFFORTS.has("xhigh"), true);
});
