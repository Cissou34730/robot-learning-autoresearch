/**
 * Which shell invocations this harness refuses.
 *
 * A faithful port of the policy in `researcher_copilot.py`, so both Researcher
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
  "inspection when the current task requires it. To " +
  'revert this experiment\'s code, set "code": {"action": "revert", ' +
  '"reason": "..."} in the lineage proposal and the runner restores it.';

export const EXECUTION_DENIAL =
  "Denied by the harness: the launcher executes experiments, not the " +
  "researcher. Write this phase's deliverable and the launcher will validate " +
  "and run it.";

export const SUITE_DENIAL =
  "Denied by the harness: a repository-wide pytest run belongs to the runner. " +
  "Use targeted linting, parsing or lightweight analysis for scientific changes.";

export const DEPENDENCY_DENIAL =
  "Denied by the harness: the project dependency set is human-owned. Use the " +
  "installed environment without installing, removing, syncing or locking packages.";

const RESERVED_SCRIPT_NAMES = new Set([
  "run_experiment.py",
  "migrate_research_state.py",
  "final_benchmark.py",
  "migrate_policy_runtime.py",
  "reset_campaign.py",
]);

const RESERVED_SCRIPT_PATHS = [
  "robot_learning/evaluate.py",
  "robot_learning/play.py",
  "robot_learning/train.py",
];

const RESERVED_MODULES = new Set([
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

const SEPARATORS = [";", "&&", "||", "|", "\n", "\r"];

function splitWhitespace(text: string): string[] {
  return text.split(/\s+/).filter((token) => token.length > 0);
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

/** Drop a leading `uv run [--flag value]` so the real invocation is visible. */
export function stripLauncherPrefix(tokens: string[]): string[] {
  if (tokens.length === 0) return tokens;
  const head = tokens[0]!.toLowerCase();
  if (head !== "uv" && head !== "uvx") return tokens;
  let index = 1;
  if (index < tokens.length && tokens[index]!.toLowerCase() === "run") {
    index += 1;
  }
  while (index < tokens.length && tokens[index]!.startsWith("-")) {
    index += 1;
    if (index < tokens.length && !tokens[index]!.startsWith("-")) {
      index += 1;
    }
  }
  return tokens.slice(index);
}

/** What this segment would actually run, ignoring anything it merely names. */
export function executionTarget(tokens: string[]): string | null {
  if (tokens.length === 0) return null;
  if (READER_COMMANDS.has(stripEdgePunctuation(tokens[0]!.toLowerCase()))) {
    return null;
  }
  const stripped = stripLauncherPrefix(tokens);
  if (stripped.length === 0) return null;
  const first = stripped[0]!;
  if (!INTERPRETERS.has(baseName(first).toLowerCase())) return first;
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
  const index = tokens.indexOf("git");
  if (index === -1) return null;
  for (const token of tokens.slice(index + 1)) {
    if (token.startsWith("-")) continue;
    return READ_ONLY_GIT.has(token) ? null : token;
  }
  return "git";
}

function isRepositoryWidePytest(tokens: string[]): boolean {
  const index = tokens.indexOf("pytest");
  if (index === -1) return false;
  return !tokens.slice(index + 1).some((token) => !token.startsWith("-"));
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
