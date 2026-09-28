import assert from "node:assert/strict";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  compactConsolePath,
  compactText,
  Console,
} from "../src/console.ts";

const ROOT = fileURLToPath(new URL("../..", import.meta.url));

function captureOutput(action: () => void): string {
  const written: string[] = [];
  const original = process.stdout.write;
  process.stdout.write = ((chunk: string | Uint8Array) => {
    written.push(String(chunk));
    return true;
  }) as typeof process.stdout.write;
  try {
    action();
  } finally {
    process.stdout.write = original;
  }
  return written.join("");
}

test("routine tools stay hidden while failures remain visible", () => {
  const output = captureOutput(() => {
    const console = new Console();
    console.tool("view", { path: "research/brief.md" }, "call-1");
    console.toolFailed("missing", "view", { path: "research/missing.md" });
  });

  assert.match(output, /view \(research\/missing\.md\) failed: missing/);
  assert.doesNotMatch(output, /research\/brief\.md/);
});

test("operation request changes are exposed immediately", () => {
  const output = captureOutput(() => {
    new Console().fileChanged("modified", "research/operation_request.json");
  });

  assert.match(output, /research\/operation_request\.json/);
  assert.match(output, /PI operation request updated/);
});

test("separate PI messages each start with their own gutter", () => {
  const output = captureOutput(() => {
    const console = new Console();
    console.message("first answer");
    console.message("second answer");
  });

  assert.equal(output, "  first answer\n  second answer\n");
});

test("PI turns are visible without token narration", () => {
  const output = captureOutput(() => {
    const console = new Console("S3 inquiry");
    console.turnStart("model");
    console.tool("view", { path: "research/brief.md" }, "call-1");
    console.turnEnd();
  });

  assert.match(output, /PI turn 1 \| model/);
  assert.match(output, /PI turn 1 complete \| 1 tool/);
  assert.doesNotMatch(output, /prompt|cache|token/);
});

test("backend UUIDs and absolute Windows paths are compacted in PI messages", () => {
  const output = captureOutput(() => {
    new Console().message(
      "Inspect C:\\work\\repo\\research\\brief.md for " +
        "11111111-1111-1111-1111-111111111111",
    );
  });

  assert.match(output, /\.\.\.\/research\/brief\.md/);
  assert.match(output, /<id>/);
  assert.doesNotMatch(output, /C:\\work\\repo/);
});

test("streamed compaction buffers split UUIDs and Windows paths", () => {
  const message =
    "Use 11111111-1111-1111-1111-111111111111 at " +
    "C:\\work\\repo\\research\\brief.md";
  const output = captureOutput(() => {
    const console = new Console();
    console.delta("Use 11111111-1111");
    console.delta("-1111-1111-111111111111");
    console.delta(" at C:\\work");
    console.delta("\\repo\\research");
    console.delta("\\brief.md");
    console.message(message);
  });

  assert.equal(output, "  Use <id> at .../research/brief.md");
});

test("repository and external path compaction matches the Copilot console", () => {
  const repositoryPath = join(ROOT, "research", "brief.md");
  const externalPath = join(ROOT, "..", "private", "trace.log");

  assert.equal(compactConsolePath(repositoryPath), "research/brief.md");
  assert.equal(compactConsolePath(externalPath), ".../private/trace.log");
  assert.equal(compactConsolePath("research\\brief.md"), "research/brief.md");
  assert.equal(
    compactText(`Read ${repositoryPath} after ${externalPath}`),
    "Read research/brief.md after .../private/trace.log",
  );
});

test("long PI prose wraps with a continuation gutter without losing words", () => {
  const message =
    "Choose the measurement whose result would most improve the next " +
    "decision toward the human goal.";
  const output = captureOutput(() => {
    new Console("", 36).message(message);
  });

  const lines = output.trimEnd().split("\n");
  assert.ok(lines.length > 1);
  assert.ok(lines.every((line) => line.startsWith("  ") && line.length <= 36));
  assert.equal(
    lines.map((line) => line.slice(2)).join(" "),
    message,
  );
});
