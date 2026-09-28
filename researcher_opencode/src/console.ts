/**
 * Everything the human sees, and nothing the protocol reads back.
 *
 * A port of the console in `researcher_copilot.py`. The layout, gutter, markers,
 * PI messages, failures, denials and changed files are intentionally identical
 * so an OpenCode session reads the same as a Copilot one. Detailed accounting
 * remains in the durable usage log and is summarized by the Runner at strategic
 * lifecycle boundaries.
 */

import { isAbsolute, relative, resolve, win32 } from "node:path";
import { fileURLToPath } from "node:url";

const RESET = "\u001b[0m";
const DIM = "\u001b[90m";
/** The model's own words: one bright block behind a matching gutter, so a line
 * it writes is never mistaken for muted Runner output. */
const MESSAGE = "\u001b[1;96m";
const PLAIN_GUTTER = "  ";
const GUTTER = `${MESSAGE}${PLAIN_GUTTER}\u2502${RESET}${MESSAGE} `;
const UUID_PATTERN =
  /\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b/g;
const WINDOWS_PATH_PATTERN = /[A-Za-z]:[\\/](?:[^ \r\n:]+[\\/])*[^ \r\n:]+/g;
const UUID_SUFFIX_PATTERN = new RegExp(
  "(?<!\\w)(?:" +
    "[0-9a-fA-F]{1,8}|" +
    "[0-9a-fA-F]{8}-[0-9a-fA-F]{0,4}|" +
    "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{0,4}|" +
    "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{0,4}|" +
    "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-" +
    "[0-9a-fA-F]{4}-[0-9a-fA-F]{0,12}" +
    ")$",
);
const WINDOWS_PATH_SUFFIX_PATTERN = /[A-Za-z]:[\\/][^ \r\n:]*$/;
const WINDOWS_DRIVE_SUFFIX_PATTERN = /(?<!\w)[A-Za-z]:?$/;
const MAX_UNRESOLVED_CONSOLE_TOKEN = 512;
const ROOT = fileURLToPath(new URL("../..", import.meta.url));

const MARKER_COLORS: Record<string, string> = {
  ">": "\u001b[36m",
  x: "\u001b[1;91m",
  "+": "\u001b[32m",
  "-": "\u001b[31m",
  "~": "\u001b[36m",
  "!": "\u001b[1;91m",
  "--": "\u001b[1;96m",
  "[session]": "\u001b[95m",
};

export type FileOperation = "created" | "modified" | "deleted";

export function formatDuration(seconds: number): string {
  const total = Math.max(Math.floor(seconds), 0);
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  const hours = Math.floor(minutes / 60);
  if (hours > 0) {
    return `${hours}h${String(minutes % 60).padStart(2, "0")}m`;
  }
  if (minutes > 0) {
    return `${minutes}m${String(remainder).padStart(2, "0")}s`;
  }
  return `${remainder}s`;
}

function timestamp(): string {
  const now = new Date();
  const parts = [now.getHours(), now.getMinutes(), now.getSeconds()];
  return parts.map((part) => String(part).padStart(2, "0")).join(":");
}

export function formatConsoleLine(text: string): string {
  if (!process.stdout.isTTY) return text;
  const stripped = text.replace(/^\s+/, "");
  const indent = text.slice(0, text.length - stripped.length);
  const spaceIndex = stripped.indexOf(" ");
  const marker = spaceIndex === -1 ? stripped : stripped.slice(0, spaceIndex);
  const separator = spaceIndex === -1 ? "" : " ";
  const remainder = spaceIndex === -1 ? "" : stripped.slice(spaceIndex + 1);
  const color = MARKER_COLORS[marker] ?? "\u001b[36m";
  if (marker === "x" || marker === "!" || marker === "--") {
    return `${DIM}[${timestamp()}]${RESET} ${indent}${color}${stripped}${RESET}`;
  }
  return `${DIM}[${timestamp()}]${RESET} ${indent}${color}${marker}${RESET}${separator}${remainder}`;
}

export function thousands(count: number): string {
  return count >= 1000 ? `${Math.round(count / 1000)}k` : String(count);
}

export function compactConsolePath(target: string): string {
  const value = target.trim();
  if (win32.isAbsolute(value)) {
    const normalized = win32.normalize(value);
    const root = win32.normalize(ROOT);
    const withinRoot = win32.relative(root, normalized);
    if (
      withinRoot !== "" &&
      !withinRoot.startsWith(`..${win32.sep}`) &&
      !win32.isAbsolute(withinRoot)
    ) {
      return withinRoot.replace(/\\/g, "/");
    }
    const parts = normalized.split(/[\\/]/).filter(Boolean);
    return `.../${parts.slice(-2).join("/")}`;
  }
  if (isAbsolute(value)) {
    const normalized = resolve(value);
    const withinRoot = relative(ROOT, normalized);
    if (
      withinRoot !== "" &&
      !withinRoot.startsWith("..") &&
      !isAbsolute(withinRoot)
    ) {
      return withinRoot.replace(/\\/g, "/");
    }
    const parts = normalized.split(/[\\/]/).filter(Boolean);
    return `.../${parts.slice(-2).join("/")}`;
  }
  return value.replace(/\\/g, "/");
}

export function compactText(text: string): string {
  return text
    .replace(UUID_PATTERN, "<id>")
    .replace(WINDOWS_PATH_PATTERN, (path) => compactConsolePath(path));
}

function unresolvedConsoleSuffixStart(text: string): number {
  let start = text.length;
  for (const pattern of [
    UUID_SUFFIX_PATTERN,
    WINDOWS_PATH_SUFFIX_PATTERN,
    WINDOWS_DRIVE_SUFFIX_PATTERN,
  ]) {
    const match = pattern.exec(text);
    if (match?.index !== undefined) start = Math.min(start, match.index);
  }
  return start;
}

export class Console {
  label: string;
  changedFiles: Map<string, string> = new Map();
  promptTokens = 0;
  cacheReadTokens = 0;
  cacheWriteTokens = 0;
  outputTokens = 0;
  reasoningTokens = 0;
  cost = 0;
  sessionError: string | null = null;
  denials = 0;
  toolCalls = 0;
  toolCounts: Map<string, number> = new Map();
  deniedCalls: Set<string> = new Set();
  activeTools: Map<string, string> = new Map();

  private midStream = false;
  private atLineStart = true;
  private readonly messageWidth: number;
  private compactBuffer = "";
  private messageBuffer = "";
  private messageSpacing = "";
  private messageColumn = 0;
  private messageContinuesWord = false;
  private turn = 0;
  private turnStartedAt: number | null = null;
  private turnModel = "";
  private turnTools = 0;
  private turnFiles = 0;
  private turnPromptAtStart = 0;
  private turnCacheReadAtStart = 0;
  private turnOutputAtStart = 0;
  constructor(label = "", columns = process.stdout.columns ?? 100) {
    this.label = label;
    this.messageWidth = Math.max(columns - 4, 20);
  }

  tagged(text: string): string {
    return this.label ? `[${this.label}] ${text}` : text;
  }

  line(text: string): void {
    this.closeMessage();
    process.stdout.write(`${formatConsoleLine(text)}\n`);
  }

  /** Mark the next PI turn and start its compact accounting. */
  turnStart(model?: string | null): void {
    this.turn += 1;
    this.turnStartedAt = performance.now();
    this.turnModel = model ?? "";
    this.turnTools = 0;
    this.turnFiles = 0;
    this.turnPromptAtStart = this.promptTokens;
    this.turnCacheReadAtStart = this.cacheReadTokens;
    this.turnOutputAtStart = this.outputTokens;
    process.stdout.write("\n");
    const modelNote = this.turnModel ? ` | ${this.turnModel}` : "";
    this.line(`-- ${this.tagged(`PI turn ${this.turn}`)}${modelNote}`);
  }

  /** Close the visible PI turn without reproducing token accounting. */
  turnEnd(): void {
    if (this.turnStartedAt === null) return;
    const elapsed = formatDuration((performance.now() - this.turnStartedAt) / 1000);
    this.turnStartedAt = null;
    const tools = `${this.turnTools} tool${this.turnTools === 1 ? "" : "s"}`;
    const files =
      this.turnFiles > 0
        ? ` | ${this.turnFiles} file${this.turnFiles === 1 ? "" : "s"}`
        : "";
    this.line(
      `-- ${this.tagged(`PI turn ${this.turn} complete`)} | ${tools}${files} | ${elapsed}`,
    );
    process.stdout.write("\n");
  }

  private closeMessage(): void {
    if (!this.midStream) return;
    this.bufferConsoleText("", true);
    this.flushMessage(true);
    if (process.stdout.isTTY) process.stdout.write(RESET);
    if (!this.atLineStart) process.stdout.write("\n");
    this.midStream = false;
    this.atLineStart = true;
    this.compactBuffer = "";
    this.messageBuffer = "";
    this.messageSpacing = "";
    this.messageColumn = 0;
    this.messageContinuesWord = false;
  }

  private messageNewline(): void {
    process.stdout.write("\n");
    this.atLineStart = true;
    this.messageSpacing = "";
    this.messageColumn = 0;
    this.messageContinuesWord = false;
  }

  private writeMessageWord(word: string): void {
    let spacing = this.messageSpacing;
    if (
      !this.atLineStart &&
      this.messageColumn + spacing.length + word.length > this.messageWidth
    ) {
      this.messageNewline();
      spacing = "";
    }
    if (this.atLineStart) {
      process.stdout.write(process.stdout.isTTY ? GUTTER : PLAIN_GUTTER);
      this.atLineStart = false;
    } else if (spacing) {
      process.stdout.write(spacing);
      this.messageColumn += spacing.length;
    }
    process.stdout.write(word);
    this.messageColumn += word.length;
    this.messageSpacing = "";
  }

  private flushMessage(final: boolean): void {
    const tokens = this.messageBuffer.match(/\n|[^\S\n]+|\S+/g) ?? [];
    for (const token of tokens) {
      if (token === "\n") {
        this.messageNewline();
      } else if (/^\s+$/.test(token)) {
        this.messageSpacing += token;
        this.messageContinuesWord = false;
      } else if (this.messageContinuesWord && !this.messageSpacing) {
        process.stdout.write(token);
        this.messageColumn += token.length;
      } else {
        this.writeMessageWord(token);
        this.messageContinuesWord = true;
      }
    }
    this.messageBuffer = "";
    if (final && this.messageSpacing && !this.atLineStart) {
      process.stdout.write(this.messageSpacing);
      this.messageColumn += this.messageSpacing.length;
      this.messageSpacing = "";
    }
  }

  private bufferConsoleText(text: string, final: boolean): void {
    this.compactBuffer += text;
    let splitAt = final
      ? this.compactBuffer.length
      : unresolvedConsoleSuffixStart(this.compactBuffer);
    if (
      !final &&
      this.compactBuffer.length - splitAt > MAX_UNRESOLVED_CONSOLE_TOKEN
    ) {
      splitAt = this.compactBuffer.length;
    }
    if (splitAt === 0) return;
    const ready = this.compactBuffer.slice(0, splitAt);
    this.compactBuffer = this.compactBuffer.slice(splitAt);
    this.messageBuffer += compactText(ready);
  }

  delta(text: string): void {
    if (!text) return;
    if (!this.midStream) {
      this.midStream = true;
      this.atLineStart = true;
      if (process.stdout.isTTY) process.stdout.write(MESSAGE);
    }
    this.bufferConsoleText(text, false);
    this.flushMessage(false);
  }

  message(text: string): void {
    if (this.midStream) {
      this.bufferConsoleText("", true);
      this.flushMessage(true);
      return;
    }
    if (!text) return;
    this.delta(text);
    this.closeMessage();
  }

  tool(name: string, input: unknown, callID?: string | null): void {
    this.toolCalls += 1;
    this.toolCounts.set(name, (this.toolCounts.get(name) ?? 0) + 1);
    this.turnTools += 1;
    if (callID) this.activeTools.set(callID, name);
  }

  /** The most human-meaningful single argument for a tool call. */
  private describe(name: string, input: unknown): string {
    if (!input || typeof input !== "object") {
      return typeof input === "string" ? input : "";
    }
    const record = input as Record<string, unknown>;
    const keys =
      name === "grep" || name === "glob" || name === "rg"
        ? ["pattern", "query", "path", "include"]
        : [
            "command",
            "description",
            "filePath",
            "path",
            "file_path",
            "pattern",
            "query",
            "url",
          ];
    for (const key of keys) {
      const value = record[key];
      if (typeof value === "string" && value.length > 0) return value;
    }
    return "";
  }

  toolFailed(error: unknown, name = "tool", input?: unknown): void {
    const target = compactText(this.describe(name, input));
    const shortTarget = target.length > 100 ? `${target.slice(0, 97)}...` : target;
    let reason = compactText(typeof error === "string" ? error : String(error ?? ""));
    reason = reason.split(/\s+/).filter(Boolean).join(" ");
    if (reason.length > 160) reason = `${reason.slice(0, 157)}...`;
    const operation = shortTarget ? `${name} (${shortTarget})` : name;
    this.line(`  x ${operation} failed: ${reason}`);
  }

  denied(reason: string, callID?: string | null): void {
    this.denials += 1;
    if (callID) this.deniedCalls.add(callID);
    const firstLine = reason.split("\n")[0] ?? reason;
    this.line(`  x ${firstLine}`);
  }

  fileChanged(operation: FileOperation, path: string): void {
    path = compactConsolePath(path);
    const marker =
      operation === "created" ? "+" : operation === "deleted" ? "-" : "~";
    if (this.changedFiles.get(path) !== marker) {
      this.changedFiles.set(path, marker);
      this.turnFiles += 1;
      const suffix =
        path === "research/operation_request.json"
          ? " | PI operation request updated"
          : "";
      this.line(`  ${marker} ${path}${suffix}`);
    }
  }

  error(message: string): void {
    this.sessionError = message;
    this.line(`  ! session error: ${message}`);
  }

  /** Expose unannounced changes; lifecycle summaries come from the Runner. */
  summary(sessionID: string, changed: string[], elapsedSeconds: number): void {
    void sessionID;
    void elapsedSeconds;
    for (const path of changed) {
      const compact = compactConsolePath(path);
      if (!this.changedFiles.has(compact)) this.line(`  ~ ${compact}`);
    }
  }

  work(): string {
    return `tools ${this.toolCalls}`;
  }

  /** Cost as the runtime estimates it. Point-in-time and scoped to this
   * invocation; cached prompt tokens are a fraction of fresh ones, so the token
   * split says whether to shrink what enters the session or what it replies. */
  usage(): string {
    const prompt = `prompt ${thousands(this.promptTokens)}`;
    const share =
      this.promptTokens > 0
        ? ` (${Math.round((100 * this.cacheReadTokens) / this.promptTokens)}% cached)`
        : "";
    return `cost $${this.cost.toFixed(4)}, ${prompt}${share}`;
  }

  snapshot(): Record<string, number | string | null | Record<string, number>> {
    return {
      input_tokens: this.promptTokens,
      cache_read_tokens: this.cacheReadTokens,
      cache_write_tokens: this.cacheWriteTokens,
      output_tokens: this.outputTokens,
      reasoning_tokens: this.reasoningTokens,
      reported_cost_usd: Number(this.cost.toFixed(6)),
      tool_calls: this.toolCalls,
      tools_by_name: Object.fromEntries(this.toolCounts),
    };
  }
}
