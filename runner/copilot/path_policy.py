"""Existing repository path, read, write and coding-scope policy."""

from __future__ import annotations

import fnmatch
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]


MAIN_WRITE_DENIAL = (
    "Ordinary PI sessions have no file-write tools. Use submit_operation for actions. "
    "Use scientific_coding for bounded scientific source changes."
)


CODING_SCOPE_DENIAL = "This action is outside this coding session's exact file scope."


CODING_PERMISSION_DENIAL = (
    "Harness authorization failure: the permission request has no matching active "
    "native-child or main-PI identity. No file access was authorized."
)


FILE_EDIT_DENIAL = (
    "This path is outside the editable scientific surface defined in AGENTS.md."
)


FILE_READ_DENIAL = (
    "Reserved harness, maintainer, and protected scientific files are unavailable "
    "for inspection in this phase."
)


RESERVED_SCRIPT_NAMES = (
    "run_experiment.py",
    "assessment.py",
    "final_benchmark.py",
    "migrate_policy_runtime.py",
    "reset_campaign.py",
    "run_research.ps1",
    "reset_research.ps1",
)


RESERVED_SCRIPT_PATHS = (
    "robot_learning/evaluate.py",
    "robot_learning/play.py",
    "robot_learning/train.py",
    "runner",
    "runner/*",
    "benchmark",
    "benchmark/*",
    "runner/build_brief.py",
    "runner/query_training_log.py",
    "researcher_*.py",
    "researcher_*.ps1",
    "tools",
    "tools/campaign_report.py",
    "docs",
    "docs/*",
    "tests",
    "tests/*",
)


RESERVED_MODULES = (
    "runner.run_experiment",
    "runner.assessment",
    "runner.migrate_policy_runtime",
    "runner.reset_campaign",
    "robot_learning.evaluate",
    "robot_learning.train",
    "robot_learning.play",
    "benchmark.final_benchmark",
    "benchmark.adapters.final_benchmark",
)


def _repository_relative_target(target: str) -> str | None:
    if not isinstance(target, str) or not target.strip():
        return None
    path = Path(target.strip())
    if not path.is_absolute():
        path = ROOT / path
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix().casefold()
    except ValueError:
        return None


def is_pi_writable_path(target: str, *, preliminary: bool = False) -> bool:
    relative = _repository_relative_target(target)
    if relative is None:
        return False
    protected_scenario = {
        "robot_learning/scenario/__init__.py",
        "benchmark/adapters/final_benchmark.py",
        "benchmark/adapters/task_reference.py",
    }
    if relative in protected_scenario:
        return False
    if preliminary:
        return relative == "pi_workspace/scientific_model.md"
    return relative in {
        "robot_learning/train.py",
        "robot_learning/evaluate.py",
        "robot_learning/play.py",
        "robot_learning/training/current_params.json",
        "pi_workspace/operation_request.json",
    } or relative.startswith(
        (
            "robot_learning/scenario/",
            "robot_learning/training/",
            "robot_learning/lab/",
        )
    )


def file_edit_denial(target: str, *, preliminary: bool = False) -> str | None:
    from runner.copilot.copilot_scoped_search import linked_path

    if not isinstance(target, str):
        return FILE_EDIT_DENIAL
    path = Path(target)
    if not path.is_absolute():
        path = ROOT / path
    if linked_path(ROOT, path) or ":" in str(path)[len(path.anchor) :]:
        return FILE_EDIT_DENIAL
    if is_pi_writable_path(target, preliminary=preliminary):
        return None
    return FILE_EDIT_DENIAL


def scoped_edit_denial(
    target: str,
    *,
    preliminary: bool = False,
    coding_paths: frozenset[str] | None = None,
) -> str | None:
    relative = _repository_relative_target(target)
    if coding_paths is not None:
        if relative not in coding_paths or file_edit_denial(target):
            return CODING_SCOPE_DENIAL
        return None
    if preliminary:
        return file_edit_denial(target, preliminary=True)
    return MAIN_WRITE_DENIAL


def file_read_denial(target: str, *, preliminary: bool = False) -> str | None:
    from runner.copilot.copilot_scoped_search import linked_path

    relative = _repository_relative_target(target)
    path = Path(target) if isinstance(target, str) else ROOT.parent
    if not path.is_absolute():
        path = ROOT / path
    if (
        relative is None
        or linked_path(ROOT, path)
        or ":" in str(path)[len(path.anchor) :]
        or relative.split("/", 1)[0] in {".git", ".venv", ".github"}
        or relative == ".copilot"
        or (
            relative.startswith(".copilot/")
            and not relative.startswith(".copilot/large-output/")
        )
    ):
        return FILE_READ_DENIAL
    if preliminary:
        if relative is not None and relative.startswith("robot_learning/"):
            return None
    if is_pi_writable_path(target):
        return None
    if is_reserved_execution(target):
        return FILE_READ_DENIAL
    return None


def is_reserved_execution(target: str | None) -> bool:
    if not target:
        return False
    relative = _repository_relative_target(target)
    normalized = (relative or target).replace("\\", "/").lstrip("./").lower()
    if Path(normalized).name in RESERVED_SCRIPT_NAMES:
        return True
    if any(
        fnmatch.fnmatchcase(normalized, path) or normalized.endswith("/" + path)
        for path in RESERVED_SCRIPT_PATHS
    ):
        return True
    return normalized in RESERVED_MODULES


def coding_file_scope(paths: list[str], *, writable: bool) -> frozenset[str]:
    result = set()
    for target in paths:
        path = PureWindowsPath(target)
        rejection = (
            f"Coding {'write' if writable else 'read'} scope rejected {target!r}: "
        )
        if (
            not target.strip()
            or path.drive
            or path.root
            or ".." in path.parts
            or any(character in target for character in "*?[]:")
        ):
            raise ValueError(
                rejection + "use an exact repository-relative file path, "
                "without absolute paths, parent traversal, wildcards or streams."
            )
        relative = _repository_relative_target(target)
        if relative is None:
            raise ValueError(rejection + "the path is outside the repository.")
        if (ROOT / relative).is_dir():
            raise ValueError(
                rejection + "directories are not file scopes; select exact files. "
                "New writable files do not require an existing parent directory."
            )
        if writable:
            if relative == "pi_workspace/operation_request.json":
                raise ValueError(
                    rejection
                    + "operation requests are Runner exchange, not coding output."
                )
            reason = file_edit_denial(target)
            if reason:
                raise ValueError(rejection + reason)
        else:
            reason = file_read_denial(target)
            if reason:
                raise ValueError(rejection + reason)
            if not (
                relative.startswith(("robot_learning/", "contracts/"))
                or relative in {"agents.md", "pi_workspace/scientific_model.md"}
            ):
                raise ValueError(
                    rejection + "read_paths permits scientific sources, contracts, "
                    "AGENTS.md and the frozen scientific model only; select other "
                    "relevant context through source_context."
                )
        result.add(relative)
    return frozenset(result)
