/**
 * Invocation accounting.
 *
 * One row per Researcher invocation, appended to the same campaign-scoped
 * location the Copilot adapter uses, so a single report covers both runtimes.
 * The record holds aggregate usage only: never conversation text, commands,
 * credentials or tool arguments.
 *
 * Copilot rows report `aiu`. OpenCode has no AIU concept, so it leaves `aiu`
 * null and records its own runtime cost estimate under separate, explicitly
 * named fields. The two units are never conflated.
 */

import { mkdirSync, appendFileSync } from "node:fs";
import { join } from "node:path";

/** The runner's own row contract. Bumped when the field meaning changes. */
export const USAGE_SCHEMA_VERSION = 2;
export const RUNTIME_ID = "opencode";

const UUID_PATTERN =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

export type UsageRow = {
  campaign_id: string;
  experiment: number | null;
  phase: string | null;
  attempt: number;
  session_id: string;
  recorded_at: string;
  model: string;
  reasoning: string;
  duration_seconds: number;
  exit_code: number;
  input_tokens: number | null;
  cache_read_tokens: number | null;
  output_tokens: number | null;
  aiu: null;
  tool_calls: number;
  tools_by_name: Record<string, number>;
  runtime: string;
  runtime_session_id: string | null;
  usage_schema_version: number;
  cache_write_tokens: number | null;
  reasoning_tokens: number | null;
  reported_cost_usd: number | null;
};

export function usageDirectory(root: string): string {
  return join(root, "reports", "session_usage");
}

/**
 * Append one row. A campaign id is a path component, so it is validated rather
 * than trusted. Accounting failure must never invalidate a scientific
 * deliverable, so callers treat a throw as a warning.
 */
export function appendUsage(root: string, row: UsageRow): void {
  if (!UUID_PATTERN.test(row.campaign_id)) {
    throw new Error(`campaign id is not a UUID: ${row.campaign_id}`);
  }
  const directory = usageDirectory(root);
  mkdirSync(directory, { recursive: true });
  appendFileSync(
    join(directory, `${row.campaign_id}.jsonl`),
    `${JSON.stringify(row)}\n`,
    "utf8",
  );
}
