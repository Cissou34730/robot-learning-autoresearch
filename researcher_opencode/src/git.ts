/**
 * Worktree observation, independent of the runtime's own change events.
 *
 * The same meaning as the Copilot adapter's: this compares Git status before and
 * after, so a file written by any means is still observed. It detects status
 * changes, not every content change to a file already modified before the
 * invocation.
 */

import { execFileSync } from "node:child_process";

export function worktreeStatus(root: string): Map<string, string> {
  const entries = new Map<string, string>();
  try {
    const stdout = execFileSync(
      "git",
      ["status", "--porcelain", "--untracked-files=all"],
      { cwd: root, timeout: 30_000, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
    );
    for (const line of stdout.split("\n")) {
      if (line.length > 3) {
        const path = line.slice(3).trim().replace(/^"(.*)"$/, "$1");
        entries.set(path, line.slice(0, 2).trim());
      }
    }
  } catch {
    // A missing or failing Git is not a session error; it only removes one
    // observation channel.
  }
  return entries;
}

export function changedSince(root: string, before: Map<string, string>): string[] {
  const after = worktreeStatus(root);
  const changed: string[] = [];
  for (const path of new Set([...before.keys(), ...after.keys()])) {
    if (before.get(path) !== after.get(path)) changed.push(path);
  }
  return changed.sort();
}
