/**
 * Command-line parity with `researcher_copilot.py`.
 *
 * The PowerShell launcher builds one argument list and both adapters accept it,
 * so a phase can switch backend without the launcher changing shape.
 */

export class UsageError extends Error {}

export type AdapterArgs = {
  prompt: string;
  sessionId: string;
  model: string;
  reasoning: string;
  resume: boolean;
  timeout: number;
  serverUrl: string | null;
  campaignId: string | null;
  experiment: number | null;
  phase: string | null;
  attempt: number;
};

const REASONING_CHOICES = ["low", "medium", "high", "xhigh", "max"];
const VALUE_FLAGS = new Set([
  "--session-id",
  "--model",
  "--reasoning",
  "--timeout",
  "--server-url",
  "--campaign-id",
  "--experiment",
  "--phase",
  "--attempt",
]);
const SWITCH_FLAGS = new Set(["--resume"]);

function integer(flag: string, value: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed)) {
    throw new UsageError(`${flag} expects an integer, received '${value}'`);
  }
  return parsed;
}

export function parseArgs(
  argv: string[] = process.argv.slice(2),
  defaults: { model: string; timeout: number } = {
    model: "opencode-go/deepseek-v4.1-flash",
    timeout: 1800,
  },
): AdapterArgs {
  const flags = new Map<string, string>();
  const positionals: string[] = [];
  let resume = false;

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index]!;
    if (SWITCH_FLAGS.has(token)) {
      resume = true;
      continue;
    }
    if (token.startsWith("--")) {
      if (!VALUE_FLAGS.has(token)) {
        throw new UsageError(`unrecognized argument: ${token}`);
      }
      const value = argv[index + 1];
      if (value === undefined) {
        throw new UsageError(`${token} expects a value`);
      }
      flags.set(token, value);
      index += 1;
      continue;
    }
    positionals.push(token);
  }

  if (positionals.length === 0) {
    throw new UsageError("the prompt is required");
  }
  if (positionals.length > 1) {
    throw new UsageError(
      `expected a single prompt, received ${positionals.length} positional arguments`,
    );
  }

  const sessionId = flags.get("--session-id");
  if (!sessionId) {
    throw new UsageError("--session-id is required");
  }

  const reasoning = flags.get("--reasoning") ?? "high";
  if (!REASONING_CHOICES.includes(reasoning)) {
    throw new UsageError(
      `--reasoning must be one of ${REASONING_CHOICES.join(", ")}, received '${reasoning}'`,
    );
  }

  const timeoutValue = flags.get("--timeout");
  const timeout = timeoutValue === undefined ? defaults.timeout : Number(timeoutValue);
  if (!Number.isFinite(timeout) || timeout <= 0) {
    throw new UsageError(`--timeout expects a positive number, received '${timeoutValue}'`);
  }

  const experimentValue = flags.get("--experiment");
  const attemptValue = flags.get("--attempt");

  return {
    prompt: positionals[0]!,
    sessionId,
    model: flags.get("--model") ?? defaults.model,
    reasoning,
    resume,
    timeout,
    serverUrl: flags.get("--server-url") ?? null,
    campaignId: flags.get("--campaign-id") ?? null,
    experiment: experimentValue === undefined ? null : integer("--experiment", experimentValue),
    phase: flags.get("--phase") ?? null,
    attempt: attemptValue === undefined ? 1 : integer("--attempt", attemptValue),
  };
}

/** Split a provider-qualified model into the parts OpenCode expects. */
export function splitModel(model: string): { providerID: string; modelID: string } {
  const index = model.indexOf("/");
  if (index <= 0 || index === model.length - 1) {
    throw new UsageError(
      `OpenCode needs a provider-qualified model such as ` +
        `'opencode-go/deepseek-v4.1-flash', received '${model}'`,
    );
  }
  return { providerID: model.slice(0, index), modelID: model.slice(index + 1) };
}

export const REASONING_EFFORTS = new Set(["low", "medium", "high", "xhigh"]);
