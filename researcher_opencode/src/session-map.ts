/**
 * The harness session UUID to OpenCode session mapping.
 *
 * The launcher owns the phase identity and reuses its UUID on retry, but
 * OpenCode assigns its own session IDs, so the two must be recorded together.
 * The mapping also pins the worktree, model configuration and campaign/phase
 * identity, which makes a cross-worktree or cross-configuration resume an
 * explicit failure rather than a silent surprise.
 *
 * It lives under the ignored `reports/` directory: it holds no scientific
 * evidence, is never injected into Researcher context, and is never committed.
 */

import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const MAPPING_VERSION = 1;
/** Bounded so a long-lived worktree never accumulates an unbounded file. */
const MAX_ENTRIES = 100;

export type SessionMappingEntry = {
  opencode_session_id: string;
  directory: string;
  model: string;
  reasoning: string | null;
  campaign_id: string | null;
  experiment: number | null;
  phase: string | null;
  created_at: string;
};

type SessionMappingFile = {
  version: number;
  sessions: Record<string, SessionMappingEntry>;
};

export function mappingPath(root: string): string {
  return join(root, "reports", "opencode-sessions.json");
}

export function readMapping(root: string): SessionMappingFile {
  const path = mappingPath(root);
  try {
    const parsed = JSON.parse(readFileSync(path, "utf8")) as Partial<SessionMappingFile>;
    if (parsed && typeof parsed === "object" && parsed.sessions) {
      return { version: MAPPING_VERSION, sessions: parsed.sessions };
    }
  } catch {
    // A missing or unreadable mapping is not itself an error: a fresh phase has
    // none, and this file is regenerated. Only a resume needs it to exist.
  }
  return { version: MAPPING_VERSION, sessions: {} };
}

export function getEntry(
  root: string,
  harnessSessionId: string,
): SessionMappingEntry | null {
  return readMapping(root).sessions[harnessSessionId] ?? null;
}

/** Record a mapping, pruning the oldest entries beyond the bound. */
export function putEntry(
  root: string,
  harnessSessionId: string,
  entry: SessionMappingEntry,
): void {
  const mapping = readMapping(root);
  mapping.sessions[harnessSessionId] = entry;
  const entries = Object.entries(mapping.sessions).sort((a, b) =>
    a[1].created_at < b[1].created_at ? 1 : -1,
  );
  mapping.sessions = Object.fromEntries(entries.slice(0, MAX_ENTRIES));
  const path = mappingPath(root);
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(mapping, null, 2)}\n`, "utf8");
  renameSync(temporary, path);
}

export function removeEntry(root: string, harnessSessionId: string): void {
  const mapping = readMapping(root);
  if (!(harnessSessionId in mapping.sessions)) return;
  delete mapping.sessions[harnessSessionId];
  const path = mappingPath(root);
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(mapping, null, 2)}\n`, "utf8");
  renameSync(temporary, path);
}

/** Why this recorded mapping cannot be resumed, or null when it can. */
export function mappingRejection(
  entry: SessionMappingEntry,
  expected: { directory: string; model: string; reasoning: string | null },
): string | null {
  if (entry.directory !== expected.directory) {
    return (
      `the recorded session belongs to a different worktree ` +
      `(${entry.directory}); refusing to resume it here`
    );
  }
  if (entry.model !== expected.model) {
    return (
      `the recorded session used model '${entry.model}' but this invocation ` +
      `requests '${expected.model}'; a model change starts a new session`
    );
  }
  if (entry.reasoning !== expected.reasoning) {
    return (
      `the recorded session used reasoning '${entry.reasoning ?? "unset"}' but ` +
      `this invocation requests '${expected.reasoning ?? "unset"}'; a reasoning ` +
      `change starts a new session`
    );
  }
  return null;
}
