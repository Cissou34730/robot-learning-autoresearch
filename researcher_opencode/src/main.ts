/**
 * Entry point for one bounded Researcher session on the OpenCode runtime.
 *
 * Mirrors `researcher_copilot.py`: the same exit codes, the same console label,
 * and accounting recorded in the same place, so the PowerShell launcher treats
 * both backends identically.
 */

import { pathToFileURL } from "node:url";

import { appendUsage } from "./accounting.ts";
import {
  AdapterError,
  buildUsageRow,
  describeError,
  EXIT_INTERRUPTED,
  EXIT_RUNTIME_FAILURE,
  run,
  type RunResult,
} from "./adapter.ts";
import { Console } from "./console.ts";
import { parseArgs, UsageError, type AdapterArgs } from "./args.ts";

/** The experiment and phase a session belongs to, for the console only. */
export function consoleLabel(args: AdapterArgs): string {
  const parts: string[] = [];
  if (args.experiment !== null) parts.push(`e${args.experiment}`);
  if (args.phase) parts.push(args.phase);
  return parts.join("\u00b7");
}

function recordUsage(
  args: AdapterArgs,
  console: Console,
  result: RunResult,
  elapsedSeconds: number,
): void {
  // Standalone invocations are not attributed to an arbitrary campaign.
  if (!args.campaignId) return;
  appendUsage(process.cwd(), buildUsageRow(args, console, result, elapsedSeconds));
}

export async function main(argv: string[] = process.argv.slice(2)): Promise<number> {
  let args: AdapterArgs;
  try {
    args = parseArgs(argv);
  } catch (error) {
    if (error instanceof UsageError) {
      process.stderr.write(`researcher_opencode: ${error.message}\n`);
      return 2;
    }
    throw error;
  }

  const console = new Console(consoleLabel(args));
  const started = performance.now();
  let exitCode = EXIT_RUNTIME_FAILURE;
  let result: RunResult = {
    exitCode: EXIT_RUNTIME_FAILURE,
    runtimeSessionId: null,
    sawUsage: false,
  };

  try {
    result = await run(args, console);
    exitCode = result.exitCode;
  } catch (error) {
    if (error instanceof AdapterError) {
      process.stderr.write(`${error.message}\n`);
      exitCode = error.exitCode;
    } else if (
      error instanceof Error &&
      (error.name === "AbortError" || error.name === "InterruptedError")
    ) {
      exitCode = EXIT_INTERRUPTED;
    } else {
      // The launcher needs a code, not a traceback.
      process.stderr.write(`OpenCode runtime failure: ${describeError(error)}\n`);
      exitCode = EXIT_RUNTIME_FAILURE;
    }
    result = { ...result, exitCode };
  } finally {
    try {
      recordUsage(args, console, result, (performance.now() - started) / 1000);
    } catch (error) {
      // Accounting failure must not invalidate a scientific deliverable.
      process.stderr.write(`Session usage could not be recorded: ${describeError(error)}\n`);
    }
  }

  return exitCode;
}

// Only run when invoked directly, so the module stays importable for tests and
// for a launcher smoke check.
const isEntryPoint =
  process.argv[1] !== undefined &&
  import.meta.url === pathToFileURL(process.argv[1]).href;
if (isEntryPoint) {
  process.exitCode = await main();
}