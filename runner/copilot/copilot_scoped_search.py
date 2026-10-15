"""Trusted rg/glob overrides that prune unreadable descendants before searching."""

from __future__ import annotations

import asyncio
import fnmatch
import os
import re
import stat
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_OUTPUT_BYTES = 60_000
MAX_FILES = 50_000


class GlobParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pattern: str = Field(min_length=1, max_length=4096)
    paths: str | list[str] | None = Field(
        default=None,
        description=(
            "Readable search roots. Use paths, not path. "
            "Omit for the repository root."
        ),
    )


class RgParams(GlobParams):
    output_mode: Literal["content", "files_with_matches", "count"] = "files_with_matches"
    glob: str | None = None
    type: str | None = None
    ignore_case: bool = Field(default=False, alias="-i")
    after: int = Field(default=0, ge=0, le=100, alias="-A")
    before: int = Field(default=0, ge=0, le=100, alias="-B")
    context: int = Field(default=0, ge=0, le=100, alias="-C")
    line_numbers: bool = Field(default=False, alias="-n")
    head_limit: int = Field(default=200, ge=1, le=20_000)
    multiline: bool = False


def linked_path(root: Path, path: Path) -> bool:
    """Reject hard links and reparse points, including linked parent segments."""
    try:
        relative = path.absolute().relative_to(root.absolute())
        current = root
        for part in relative.parts:
            current /= part
            try:
                info = current.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or (
                getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            ) or (stat.S_ISREG(info.st_mode) and info.st_nlink > 1):
                return True
        return False
    except (OSError, ValueError):
        return True


def glob_expression(pattern: str) -> re.Pattern:
    """Path-aware glob syntax, including ** and small brace alternatives."""
    pattern = pattern.replace("\\", "/")
    if len(pattern) > 4096:
        raise ValueError("Glob pattern is too long.")
    alternatives = [pattern]
    for _ in range(8):
        expanded = []
        changed = False
        for item in alternatives:
            match = re.search(r"\{([^{}]+)\}", item)
            if match:
                changed = True
                expanded.extend(
                    item[:match.start()] + option + item[match.end():]
                    for option in match.group(1).split(",")
                )
            else:
                expanded.append(item)
        if len(expanded) > 64:
            raise ValueError("Glob pattern has too many alternatives.")
        alternatives = expanded
        if not changed:
            break
    expressions = []
    for item in alternatives:
        parts = item.split("/")
        expression = ""
        for index, part in enumerate(parts):
            if part == "**":
                expression += "(?:[^/]+/)*" if index < len(parts) - 1 else ".*"
            else:
                position = 0
                while position < len(part):
                    character = part[position]
                    if character == "*":
                        expression += "[^/]*"
                    elif character == "?":
                        expression += "[^/]"
                    elif character == "[" and "]" in part[position + 1:]:
                        end = part.index("]", position + 1)
                        translated = fnmatch.translate(part[position:end + 1])
                        expression += translated.removeprefix("(?s:").removesuffix(")\\Z")
                        position = end
                    else:
                        expression += re.escape(character)
                    position += 1
                if index < len(parts) - 1:
                    expression += "/"
        expressions.append(expression)
    return re.compile("(?:" + "|".join(expressions) + ")\\Z", re.IGNORECASE)


class ScopedSearch:
    def __init__(
        self, root: Path, denial: Callable[[str], str | None],
        rg_executable: Path | None, authorize: Callable,
    ) -> None:
        self.root = root.resolve()
        self.denial = denial
        self.rg_executable = rg_executable
        self.authorize = authorize

    def target(self, target: str) -> Path:
        if not isinstance(target, str) or not target.strip():
            raise ValueError("Search paths must be nonempty strings.")
        raw = Path(target)
        if not raw.is_absolute():
            raw = self.root / raw
        # Reject alternate streams and device paths before canonicalization.
        if ":" in str(raw)[len(raw.anchor):] or linked_path(self.root, raw):
            raise ValueError("Linked or non-file path aliases are unavailable.")
        path = raw.resolve()
        if not path.is_relative_to(self.root) or self.denial(str(path)):
            raise ValueError("Search path is outside the readable repository surface.")
        return path

    def files(self, paths: str | list[str] | None) -> tuple[list[Path], bool]:
        targets = [paths] if isinstance(paths, str) else paths or [str(self.root)]
        if len(targets) > 64:
            raise ValueError("At most 64 search roots are supported.")
        roots = [self.target(target) for target in targets]
        files: set[Path] = set()
        pending = list(roots)
        while pending:
            path = pending.pop()
            if self.denial(str(path)) or linked_path(self.root, path):
                continue
            if path.is_file():
                files.add(path)
                if len(files) >= MAX_FILES:
                    return sorted(files), True
            elif path.is_dir():
                with os.scandir(path) as entries:
                    for entry in entries:
                        candidate = Path(entry.path)
                        if (
                            not entry.name.startswith(".")
                            and not self.denial(str(candidate))
                            and not linked_path(self.root, candidate)
                        ):
                            pending.append(candidate)
        return sorted(files), False

    def display(self, path: Path) -> str:
        return str(path.relative_to(self.root))

    def glob(self, params: GlobParams, invocation) -> str:
        self.authorize(invocation)
        expression = glob_expression(params.pattern)
        files, incomplete = self.files(params.paths)
        targets = [params.paths] if isinstance(params.paths, str) else params.paths or [str(self.root)]
        bases = [self.target(target) for target in targets]
        bases = [base if base.is_dir() else base.parent for base in bases]
        lines = []
        size = 0
        for path in files:
            if any(
                path.is_relative_to(base)
                and expression.fullmatch(path.relative_to(base).as_posix())
                for base in bases
            ):
                line = self.display(path)
                size += len(line.encode("utf-8")) + 1
                if size > MAX_OUTPUT_BYTES:
                    incomplete = True
                    break
                lines.append(line)
        return "\n".join(lines) + (
            "\n[Truncated: narrow pattern/paths to retrieve additional allowed files.]"
            if incomplete else ""
        )

    async def rg(self, params: RgParams, invocation) -> str:
        self.authorize(invocation)
        if self.rg_executable is None or not self.rg_executable.is_file():
            raise ValueError("The runtime's ripgrep executable is unavailable.")
        files, incomplete = self.files(params.paths)
        if params.glob:
            expression = glob_expression(params.glob)
            files = [
                path for path in files
                if expression.fullmatch(path.name)
                or expression.fullmatch(path.relative_to(self.root).as_posix())
            ]
        command = [str(self.rg_executable), "--no-config", "--color=never"]
        if params.output_mode == "content":
            command += [
                "--with-filename", "--max-columns=20000", "--max-columns-preview",
            ]
            if params.line_numbers:
                command.append("--line-number")
            for option, value in (("-A", params.after), ("-B", params.before), ("-C", params.context)):
                if value:
                    command += [option, str(value)]
        else:
            command += [
                "--files-with-matches" if params.output_mode == "files_with_matches"
                else "--count",
                "--with-filename",
            ]
        if params.ignore_case:
            command.append("--ignore-case")
        if params.multiline:
            command.append("--multiline")
        if params.type:
            command += ["--type", {"tsx": "ts", "jsx": "js"}.get(params.type, params.type)]
        command += ["--regexp", params.pattern, "--"]
        output = bytearray()
        output_capped = False
        # Never give rg a directory or a glob to traverse. Its operands are
        # exclusively files selected by the shared read policy above.
        for start in range(0, len(files), 64):
            self.authorize(invocation)
            selected = [
                ".\\" + self.display(path) for path in files[start:start + 64]
                if not self.denial(str(path)) and not linked_path(self.root, path)
            ]
            if not selected:
                continue
            process = await asyncio.create_subprocess_exec(
                *command, *selected, cwd=self.root,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            errors = asyncio.create_task(process.stderr.read(8192))
            try:
                async with asyncio.timeout(30):
                    while True:
                        chunk = await process.stdout.read(4096)
                        if not chunk:
                            break
                        remaining = MAX_OUTPUT_BYTES - len(output)
                        output.extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            output_capped = True
                            break
                        if len(output.splitlines()) > params.head_limit:
                            output_capped = True
                            break
                    if output_capped and process.returncode is None:
                        process.kill()
                    code = await process.wait()
                    error = await errors
                    if code not in (0, 1) and not output_capped:
                        raise ValueError(error.decode("utf-8", errors="replace"))
            finally:
                if process.returncode is None:
                    process.kill()
                await process.wait()
                errors.cancel()
                await asyncio.gather(errors, return_exceptions=True)
            if output_capped or len(output.splitlines()) >= params.head_limit:
                incomplete = incomplete or output_capped or start + 64 < len(files)
                break
        lines = output.decode("utf-8", errors="replace").splitlines()
        if len(lines) > params.head_limit:
            incomplete = True
            lines = lines[:params.head_limit]
        preview_marker = " [... omitted end of long line]"
        previewed = params.output_mode == "content" and any(
            line.endswith(preview_marker)
            and len(line.encode("utf-8")) >= 20_000 + len(preview_marker)
            for line in lines
        )
        return "\n".join(lines) + (
            "\n[Truncated: narrow pattern/paths or increase head_limit.]"
            if incomplete else ""
        ) + (
            "\n[Partial line preview: ripgrep shortened at least one line above "
            "20000 columns. Retrieve full content with view on the exact file "
            "and view_range; use forceReadLargeFiles if needed.]"
            if previewed else ""
        )

    def tools(self):
        from copilot import define_tool

        return [
            define_tool(
                "rg", description=(
                    "Search readable repository files with ripgrep. Reserved descendants "
                    "and linked paths are pruned BEFORE content is read. Root/default, "
                    "subdirectory and multiple paths are supported. Choose content, "
                    "matching filenames or counts, with glob/type/context selectors. "
                    "Output reports transport/traversal limits; narrow or repeat distinct "
                    "subsets when truncated. Coding children cannot use search."
                ), handler=self.rg, params_type=RgParams,
                overrides_built_in_tool=True, skip_permission=True,
            ),
            define_tool(
                "glob", description=(
                    "Find readable repository files by glob, including ** and brace "
                    "alternatives. Parameters are pattern and paths, not path. "
                    "Directory discovery uses this tool, not view. "
                    "Reserved descendants and linked paths are pruned "
                    "BEFORE filenames enter the result. paths accepts root/default, "
                    "subdirectory or several directories. Explicit truncation is not "
                    "a claim of complete retrieval. Coding children cannot use search."
                ), handler=self.glob, params_type=GlobParams,
                overrides_built_in_tool=True, skip_permission=True,
            ),
        ]
