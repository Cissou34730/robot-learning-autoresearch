/**
 * Everything the human sees, and nothing the protocol reads back.
 *
 * A port of the console in `researcher_copilot.py`. The layout, gutter, markers,
 * turn banners and summary line are intentionally identical so an OpenCode
 * session reads the same as a Copilot one. The one deliberate difference is
 * accounting: OpenCode reports a monetary cost estimate and token components
 * rather than Copilot AIU, so cost is labelled as a runtime estimate.
 */

const RESET = "\u001b[0m";
const DIM = "\u001b[90m";
/** The model's own words: one block behind a gutter, so a line it writes is
 * never mistaken for something the harness reported. */
const MESSAGE = "\u001b[1;97m";
const PLAIN_GUTTER = "  ";
const GUTTER = `${DIM}${PLAIN_GUTTER}\u2502${RESET}${MESSAGE} `;

const MARKER_COLORS: Record<string, string> = {
  ">": "\u001b[36m",
  x: "\u001b[31m",
  "+": "\u001b[32m",
  "-": "\u001b[31m",
  "~": "\u001b[36m",
  "!": "\u001b[33m",
  "--": "\u001b[36m",
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
  return `${DIM}[${timestamp()}]${RESET} ${indent}${color}${marker}${RESET}${separator}${remainder}`;
}

export function thousands(count: number): string {
  return count >= 1000 ? `${Math.round(count / 1000)}k` : String(count);
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
  private turn = 0;
  private turnStartedAt: number | null = null;
  private turnModel = "";
  private turnTools = 0;
  private turnFiles = 0;
  private turnPromptAtStart = 0;
  private turnCacheReadAtStart = 0;
  private turnOutputAtStart = 0;
  private silentTools: Set<string> = new Set();

  constructor(label = "") {
    this.label = label;
  }

  tagged(text: string): string {
    return this.label ? `[${this.label}] ${text}` : text;
  }

  line(text: string): void {
    this.closeMessage();
    process.stdout.write(`${formatConsoleLine(text)}\n`);
  }

  /** Mark where the model's next stretch of work begins. */
  turnStart(model?: string | null): void {
    this.turn += 1;
    this.turnStartedAt = performance.now();
    this.turnModel = model ?? "";
    this.turnTools = 0;
    this.turnFiles = 0;
    this.turnPromptAtStart = this.promptTokens;
    this.turnCacheReadAtStart = this.cacheReadTokens;
    this.turnOutputAtStart = this.outputTokens;
    const modelNote = this.turnModel ? ` \u00b7 ${this.turnModel}` : "";
    this.line(`-- ${this.tagged(`turn ${this.turn}`)}${modelNote}`);
  }

  /** Report what one turn cost, rather than leaving it to the summary. */
  turnEnd(): void {
    if (this.turnStartedAt === null) return;
    const elapsed = Math.floor((performance.now() - this.turnStartedAt) / 1000);
    this.turnStartedAt = null;
    const parts: string[] = [];
    parts.push(`${this.turnTools} tool${this.turnTools === 1 ? "" : "s"}`);
    if (this.turnFiles > 0) {
      parts.push(`${this.turnFiles} file${this.turnFiles === 1 ? "" : "s"}`);
    }
    parts.push(formatDuration(elapsed));
    const output = this.outputTokens - this.turnOutputAtStart;
    if (output > 0) parts.push(`out ${thousands(output)}`);
    const prompt = this.promptTokens - this.turnPromptAtStart;
    if (prompt > 0) {
      const cached = this.cacheReadTokens - this.turnCacheReadAtStart;
      const share = cached > 0 ? ` (${Math.round((100 * cached) / prompt)}% cached)` : "";
      parts.push(`prompt ${thousands(prompt)}${share}`);
    }
    this.line(`-- ${this.tagged(`turn ${this.turn}`)} \u00b7 ${parts.join(" \u00b7 ")}`);
  }

  private closeMessage(): void {
    if (!this.midStream) return;
    if (process.stdout.isTTY) process.stdout.write(RESET);
    if (!this.atLineStart) process.stdout.write("\n");
    this.midStream = false;
    this.atLineStart = true;
  }

  delta(text: string): void {
    if (!text) return;
    if (!this.midStream) {
      this.midStream = true;
      this.atLineStart = true;
      if (process.stdout.isTTY) process.stdout.write(MESSAGE);
    }
    const pieces = text.split("\n");
    for (let index = 0; index < pieces.length; index += 1) {
      if (index > 0) {
        process.stdout.write("\n");
        this.atLineStart = true;
      }
      const piece = pieces[index]!;
      if (!piece) continue;
      if (this.atLineStart) {
        // Every line of the message carries the gutter, including the bare
        // ones, so none of them reads as harness output.
        process.stdout.write(process.stdout.isTTY ? GUTTER : PLAIN_GUTTER);
        this.atLineStart = false;
      }
      process.stdout.write(piece);
    }
  }

  message(text: string): void {
    if (this.midStream || !text) return;
    this.delta(text);
    this.closeMessage();
  }

  tool(name: string, input: unknown, callID?: string | null): void {
    this.toolCalls += 1;
    this.toolCounts.set(name, (this.toolCounts.get(name) ?? 0) + 1);
    this.turnTools += 1;
    if (callID) this.activeTools.set(callID, name);
    if (this.silentTools.has(name)) return;
    let detail = this.describe(name, input);
    detail = detail.split(/\s+/).filter(Boolean).join(" ");
    if (detail.length > 110) detail = `${detail.slice(0, 107)}...`;
    this.line(detail ? `  > ${name}: ${detail}` : `  > ${name}`);
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
    const target = this.describe(name, input);
    const shortTarget = target.length > 100 ? `${target.slice(0, 97)}...` : target;
    let reason = typeof error === "string" ? error : String(error ?? "");
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
    const marker =
      operation === "created" ? "+" : operation === "deleted" ? "-" : "~";
    if (this.changedFiles.get(path) !== marker) {
      this.changedFiles.set(path, marker);
      this.turnFiles += 1;
      this.line(`  ${marker} ${path}`);
    }
  }

  error(message: string): void {
    this.sessionError = message;
    this.line(`  ! session error: ${message}`);
  }

  /** The session's own end, labelled so a phase boundary is visible. */
  summary(sessionID: string, changed: string[], elapsedSeconds: number): void {
    for (const path of changed) {
      if (!this.changedFiles.has(path)) this.line(`  ~ ${path}`);
    }
    const files = `${changed.length} file(s) changed`;
    const denials = this.denials > 0 ? `, ${this.denials} denied` : "";
    this.line(
      `[session] ${sessionID.slice(0, 8)} \u00b7 ${formatDuration(elapsedSeconds)} \u00b7 ` +
        `${files}, ${this.usage()}, ${this.work()}${denials}`,
    );
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
