import { existsSync, statSync } from "node:fs";
import { isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Which shell invocations this harness refuses.
 *
 * A faithful port of the policy in `researcher_copilot.py`, so both PI
 * backends enforce the same rules with the same wording. Only what a segment
 * actually executes is judged, never what it merely names: reading or grepping a
 * protected path is ordinary research.
 *
 * This is a guardrail against the failures that have broken research runs, not a
 * sandbox. Inline code can still do anything the researcher could.
 */

export const GIT_DENIAL =
  "Denied by the harness: the runner owns mutating Git operations and " +
  "restoration. Read-only git is available for code provenance and code " +
  "inspection when the current task requires it. Request schema-6 " +
  "restore_recipe when a saved candidate recipe must be restored.";

export const EXECUTION_DENIAL =
  "Denied by the harness: the Runner executes schema-6 operations, not the PI. " +
  "Write one operation to research/operation_request.json for the Runner.";

export const SUITE_DENIAL =
  "Denied by the harness: a repository-wide pytest run belongs to the runner. " +
  "Use targeted linting, parsing or lightweight analysis for scientific changes.";

export const DEPENDENCY_DENIAL =
  "Denied by the harness: the project dependency set is human-owned. Use the " +
  "installed environment without installing, removing, syncing or locking packages.";

const RESERVED_SCRIPT_NAMES = new Set([
  "run_experiment.py",
  "runner_assessment.py",
  "migrate_research_state.py",
  "final_benchmark.py",
  "migrate_policy_runtime.py",
  "reset_campaign.py",
  "run_research.ps1",
  "reset_research.ps1",
]);

const RESERVED_SCRIPT_PATHS = [
  "robot_learning/evaluate.py",
  "robot_learning/play.py",
  "robot_learning/train.py",
];

const RESERVED_MODULES = new Set([
  "research.run_experiment",
  "research.runner_assessment",
  "research.migrate_policy_runtime",
  "research.reset_campaign",
  "robot_learning.evaluate",
  "robot_learning.train",
  "robot_learning.play",
  "robot_learning.benchmark.final_benchmark",
]);

const READ_ONLY_GIT = new Set([
  "status",
  "diff",
  "log",
  "show",
  "rev-parse",
  "ls-files",
  "ls-tree",
  "cat-file",
  "describe",
  "blame",
  "shortlog",
]);

/** Commands that only ever read. Naming a protected path to one of these is
 * research, not execution. */
const READER_COMMANDS = new Set([
  "get-content",
  "gc",
  "cat",
  "type",
  "rg",
  "select-string",
  "sls",
  "findstr",
  "head",
  "tail",
  "more",
  "less",
  "get-childitem",
  "ls",
  "dir",
]);

const INTERPRETERS = new Set(["python", "python.exe", "python3", "py", "py.exe"]);
const POWERSHELL_HOSTS = new Set(["powershell", "powershell.exe", "pwsh", "pwsh.exe"]);
const GIT_GLOBAL_VALUE_OPTIONS = new Set([
  "-c",
  "-C",
  "--config-env",
  "--exec-path",
  "--git-dir",
  "--namespace",
  "--super-prefix",
  "--work-tree",
]);
const UV_RUN_FLAG_OPTIONS = new Set([
  "-U",
  "-h",
  "-m",
  "-n",
  "-q",
  "-s",
  "-v",
  "--active",
  "--all-extras",
  "--all-groups",
  "--all-packages",
  "--compile-bytecode",
  "--exact",
  "--frozen",
  "--gui-script",
  "--help",
  "--isolated",
  "--locked",
  "--managed-python",
  "--module",
  "--no-binary",
  "--no-build",
  "--no-build-isolation",
  "--no-cache",
  "--no-config",
  "--no-default-groups",
  "--no-dev",
  "--no-editable",
  "--no-env-file",
  "--no-index",
  "--no-managed-python",
  "--no-progress",
  "--no-project",
  "--no-python-downloads",
  "--no-sources",
  "--no-sync",
  "--offline",
  "--only-dev",
  "--quiet",
  "--refresh",
  "--reinstall",
  "--script",
  "--system-certs",
  "--upgrade",
  "--verbose",
]);
const ROOT = fileURLToPath(new URL("../..", import.meta.url));

const SEPARATORS = [";", "&&", "||", "|", "\n", "\r"];

function splitWhitespace(text: string): string[] {
  const tokens: string[] = [];
  let token = "";
  let quote = "";
  for (const character of text) {
    if (quote) {
      if (character === quote) quote = "";
      else token += character;
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
    } else if (/\s/.test(character)) {
      if (token) {
        tokens.push(token);
        token = "";
      }
    } else {
      token += character;
    }
  }
  if (token) tokens.push(token);
  return tokens;
}

/** Split a command line on shell separators, so each segment can be judged. */
export function commandSegments(command: string): string[][] {
  let text = command;
  for (const separator of SEPARATORS) {
    text = text.split(separator).join("\u0000");
  }
  return text
    .split("\u0000")
    .map((segment) => splitWhitespace(segment))
    .filter((tokens) => tokens.length > 0);
}

/** Basename of a possibly Windows-style path. */
function baseName(value: string): string {
  const normalized = value.replace(/\\/g, "/");
  const index = normalized.lastIndexOf("/");
  return index === -1 ? normalized : normalized.slice(index + 1);
}

function stripEdgePunctuation(value: string): string {
  return value.replace(/^[&.]+/, "").replace(/[&.]+$/, "");
}

function uvOptionSpan(token: string): number {
  const option = token.split("=", 1)[0]!;
  if (token.includes("=") || UV_RUN_FLAG_OPTIONS.has(option)) return 1;
  if (token.startsWith("--")) return 2;
  for (let position = 1; position < token.length; position += 1) {
    if (UV_RUN_FLAG_OPTIONS.has(`-${token[position]}`)) continue;
    return position + 1 < token.length ? 1 : 2;
  }
  return 1;
}

/** Drop a leading `uv [global flags] run [run flags]` by option arity. */
export function stripLauncherPrefix(tokens: string[]): string[] {
  if (tokens.length === 0) return tokens;
  const head = tokens[0]!.toLowerCase();
  if (head !== "uv") return tokens;
  let index = 1;
  while (index < tokens.length && tokens[index]!.toLowerCase() !== "run") {
    if (!tokens[index]!.startsWith("-") || tokens[index] === "--") return tokens;
    index += uvOptionSpan(tokens[index]!);
  }
  if (index >= tokens.length) return tokens;
  index += 1;
  while (index < tokens.length && tokens[index]!.startsWith("-")) {
    if (tokens[index] === "--") {
      index += 1;
      break;
    }
    index += uvOptionSpan(tokens[index]!);
  }
  return tokens.slice(index);
}

/** What this segment would actually run, ignoring anything it merely names. */
export function executionTarget(tokens: string[]): string | null {
  while (tokens[0] === "&") tokens = tokens.slice(1);
  if (tokens.length === 0) return null;
  if (READER_COMMANDS.has(stripEdgePunctuation(tokens[0]!.toLowerCase()))) {
    return null;
  }
  const stripped = stripLauncherPrefix(tokens);
  if (stripped.length === 0) return null;
  const first = stripped[0]!;
  const executable = baseName(first).toLowerCase();
  if (POWERSHELL_HOSTS.has(executable)) {
    const args = stripped.slice(1);
    for (let index = 0; index < args.length; index += 1) {
      const argument = args[index]!.toLowerCase();
      if ((argument === "-file" || argument === "-f") && index + 1 < args.length) {
        return args[index + 1]!;
      }
      if (argument === "-command" || argument === "-c") return null;
    }
    return first;
  }
  if (!INTERPRETERS.has(executable)) return first;
  const args = stripped.slice(1);
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index]!;
    if (argument === "-m" && index + 1 < args.length) {
      return args[index + 1]!;
    }
    if (argument === "-c" || argument === "--command") {
      // Inline code names no target; the guardrail stops here by design.
      return null;
    }
    if (argument.startsWith("-")) continue;
    return argument;
  }
  return null;
}

export function isReservedExecution(target: string | null): boolean {
  if (!target) return false;
  const normalized = target.replace(/\\/g, "/").replace(/^\.\//, "").toLowerCase();
  const name = baseName(normalized);
  if (RESERVED_SCRIPT_NAMES.has(name)) return true;
  if (RESERVED_SCRIPT_PATHS.some((path) => normalized.endsWith(path))) return true;
  return RESERVED_MODULES.has(normalized);
}

/** The subcommand when it is not a read-only one, so unknown verbs deny. */
export function deniedGitSubcommand(tokens: string[]): string | null {
  const executableIndex = tokens.findIndex(
    (token) => baseName(stripEdgePunctuation(token)).toLowerCase().replace(/\.exe$/, "") === "git",
  );
  if (executableIndex === -1) return null;
  let index = executableIndex + 1;
  while (index < tokens.length) {
    const token = tokens[index]!;
    const option = token.split("=", 1)[0]!;
    if (GIT_GLOBAL_VALUE_OPTIONS.has(option)) {
      index += token.includes("=") ? 1 : 2;
      continue;
    }
    if (token.startsWith("-")) {
      index += 1;
      continue;
    }
    const subcommand = baseName(token).toLowerCase().replace(/\.exe$/, "");
    return READ_ONLY_GIT.has(subcommand) ? null : subcommand;
  }
  return "git";
}

function namesTargetedTestFile(token: string): boolean {
  const selector = token.split("::", 1)[0]!;
  const path = isAbsolute(selector) ? resolve(selector) : resolve(ROOT, selector);
  const withinRoot = relative(ROOT, path);
  return (
    withinRoot !== "" &&
    !withinRoot.startsWith("..") &&
    !isAbsolute(withinRoot) &&
    existsSync(path) &&
    statSync(path).isFile()
  );
}

const PYTEST_FLAG_OPTIONS = new Set([
  "-V",
  "-h",
  "-l",
  "-q",
  "-s",
  "-v",
  "-x",
  "--cache-clear",
  "--co",
  "--collect-in-virtualenv",
  "--collect-only",
  "--collectonly",
  "--continue-on-collection-errors",
  "--disable-plugin-autoload",
  "--disable-pytest-warnings",
  "--disable-warnings",
  "--doctest-continue-on-failure",
  "--doctest-ignore-import-errors",
  "--doctest-modules",
  "--exitfirst",
  "--failed-first",
  "--ff",
  "--fixtures",
  "--fixtures-per-test",
  "--force-short-summary",
  "--full-trace",
  "--fulltrace",
  "--funcargs",
  "--help",
  "--keep-duplicates",
  "--keepduplicates",
  "--last-failed",
  "--lf",
  "--lsof",
  "--markers",
  "--new-first",
  "--nf",
  "--no-fold-skipped",
  "--no-header",
  "--no-showlocals",
  "--no-summary",
  "--noconftest",
  "--pdb",
  "--pyargs",
  "--quiet",
  "--runxfail",
  "--setup-only",
  "--setup-plan",
  "--setup-show",
  "--setuponly",
  "--setupplan",
  "--setupshow",
  "--showlocals",
  "--stepwise",
  "--stepwise-reset",
  "--stepwise-skip",
  "--strict-config",
  "--strict-markers",
  "--strict",
  "--sw",
  "--sw-reset",
  "--sw-skip",
  "--trace",
  "--trace-config",
  "--traceconfig",
  "--verbose",
  "--version",
  "--xfail-tb",
]);

function shortOptionSpan(token: string): number {
  for (let position = 1; position < token.length; position += 1) {
    if (PYTEST_FLAG_OPTIONS.has(`-${token[position]}`)) continue;
    return position + 1 < token.length ? 1 : 2;
  }
  return 1;
}

function isRepositoryWidePytest(tokens: string[]): boolean {
  const index = tokens.findIndex(
    (token) => baseName(token).toLowerCase().replace(/\.exe$/, "") === "pytest",
  );
  if (index === -1) return false;
  const rest = tokens.slice(index + 1);
  let position = 0;
  let positionalOnly = false;
  while (position < rest.length) {
    const token = rest[position]!;
    if (positionalOnly) {
      if (namesTargetedTestFile(token)) return false;
      position += 1;
      continue;
    }
    if (token === "--") {
      positionalOnly = true;
      position += 1;
      continue;
    }
    if (token.startsWith("--")) {
      position += token.includes("=") || PYTEST_FLAG_OPTIONS.has(token) ? 1 : 2;
      continue;
    }
    if (token.startsWith("-") && token.length > 1) {
      position += shortOptionSpan(token);
      continue;
    }
    if (namesTargetedTestFile(token)) return false;
    position += 1;
  }
  return true;
}

/** Whether a command changes or extends the fixed project dependency set. */
export function isDependencyManagement(tokens: string[]): boolean {
  if (tokens.length === 0) return false;
  const lowered = tokens.map((token) => token.toLowerCase());
  const executable = baseName(stripEdgePunctuation(lowered[0]!))
    .toLowerCase()
    .replace(/\.exe$/, "");
  if (executable === "uvx") return true;
  if (executable === "uv") {
    if (lowered.length < 2) return false;
    const operation = lowered[1]!;
    if (["add", "remove", "sync", "lock", "pip", "tool"].includes(operation)) {
      return true;
    }
    if (operation === "run") {
      if (lowered.slice(2).some((token) => token.startsWith("--with"))) return true;
      return isDependencyManagement(stripLauncherPrefix(tokens));
    }
  }
  if (["pip", "pip3", "pipx"].includes(executable)) {
    return lowered.slice(1).some((token) => token === "install" || token === "uninstall");
  }
  if (INTERPRETERS.has(executable)) {
    const moduleIndex = lowered.indexOf("-m");
    if (moduleIndex !== -1 && lowered[moduleIndex + 1] === "pip") {
      return lowered
        .slice(moduleIndex + 2)
        .some((token) => token === "install" || token === "uninstall");
    }
  }
  return executable === "install-module" || executable === "install-package";
}

/** The reason this command is refused, or null when it may run. */
export function commandDenial(command: string): string | null {
  for (const tokens of commandSegments(command)) {
    if (isDependencyManagement(tokens)) return DEPENDENCY_DENIAL;
    const target = executionTarget(tokens);
    if (!target) continue;
    const name = baseName(target).toLowerCase().replace(/\.exe$/, "");
    if (isReservedExecution(target)) return EXECUTION_DENIAL;
    if (name === "git" && deniedGitSubcommand(tokens)) return GIT_DENIAL;
    if (name === "pytest" && isRepositoryWidePytest(tokens)) return SUITE_DENIAL;
  }
  return null;
}

export type PermissionLike = {
  type?: string;
  title?: string;
  pattern?: string | string[];
  metadata?: Record<string, unknown>;
};

const SHELL_PERMISSION_TYPES = /bash|shell|command|exec|terminal|process/i;

function collectStrings(value: unknown, into: string[]): void {
  if (typeof value === "string") {
    if (value.length > 0) into.push(value);
    return;
  }
  if (Array.isArray(value)) {
    for (const entry of value) collectStrings(entry, into);
  }
}

/**
 * The command text a permission request is about, or "" when the request is not
 * a shell invocation.
 *
 * The policy judges what a command *executes*, so applying it to a non-shell
 * permission would be wrong: an edit of `robot_learning/train.py` merely names a
 * reserved script and is ordinary research. Only an explicit command field, or a
 * shell-shaped permission type, produces text to judge.
 */
export function permissionCommandText(permission: PermissionLike): string {
  const metadata = permission.metadata ?? {};
  const explicit: string[] = [];
  for (const key of ["command", "commandLine", "script", "cmd"]) {
    collectStrings(metadata[key], explicit);
  }
  collectStrings(metadata["commands"], explicit);
  if (explicit.length > 0) return explicit.join("\n");

  const looksLikeShell =
    SHELL_PERMISSION_TYPES.test(permission.type ?? "") ||
    SHELL_PERMISSION_TYPES.test(String(metadata["tool"] ?? ""));
  if (!looksLikeShell) return "";

  const fallback: string[] = [];
  collectStrings(metadata["pattern"], fallback);
  collectStrings(metadata["args"], fallback);
  collectStrings(permission.pattern, fallback);
  collectStrings(permission.title, fallback);
  return fallback.join("\n");
}
