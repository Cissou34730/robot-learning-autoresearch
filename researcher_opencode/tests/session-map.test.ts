import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import {
  getEntry,
  mappingPath,
  mappingRejection,
  putEntry,
  readMapping,
  type SessionMappingEntry,
} from "../src/session-map.ts";

function entry(overrides: Partial<SessionMappingEntry> = {}): SessionMappingEntry {
  return {
    opencode_session_id: "ses_123",
    directory: "/work/tree",
    model: "opencode-go/gpt-5.6-luna",
    reasoning: "high",
    campaign_id: null,
    experiment: 1,
    phase: "proposal",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

test("a fresh worktree has no mapping", () => {
  const root = mkdtempSync(join(tmpdir(), "rl-map-"));
  assert.equal(getEntry(root, "harness-1"), null);
  assert.deepEqual(readMapping(root).sessions, {});
});

test("a mapping round-trips and is keyed by the harness session id", () => {
  const root = mkdtempSync(join(tmpdir(), "rl-map-"));
  putEntry(root, "harness-1", entry());
  assert.equal(getEntry(root, "harness-1")?.opencode_session_id, "ses_123");
  assert.equal(getEntry(root, "harness-2"), null);
});

test("the mapping lives under the ignored reports directory", () => {
  assert.equal(mappingPath("/work/tree").replace(/\\/g, "/"), "/work/tree/reports/opencode-sessions.json");
});

test("a resume may not cross worktrees, models or reasoning settings", () => {
  const expected = {
    directory: "/work/tree",
    model: "opencode-go/gpt-5.6-luna",
    reasoning: "high",
  };
  assert.equal(mappingRejection(entry(), expected), null);
  assert.match(mappingRejection(entry({ directory: "/work/other" }), expected) ?? "", /different worktree/);
  assert.match(mappingRejection(entry({ model: "opencode-go/kimi-k3" }), expected) ?? "", /model/);
  assert.match(mappingRejection(entry({ reasoning: "low" }), expected) ?? "", /reasoning/);
});

test("a resume with no recorded session policy is distinguishable", () => {
  const expected = {
    directory: "/work/tree",
    model: "opencode-go/gpt-5.6-luna",
    reasoning: "high",
  };
  assert.match(mappingRejection(entry({ reasoning: null }), expected) ?? "", /reasoning/);
});
