import assert from "node:assert/strict";
import { test } from "node:test";

import { Console } from "../src/console.ts";

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
