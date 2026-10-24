"""Existing repository path, read, write and coding-scope policy."""

from __future__ import annotations

import fnmatch
from pathlib import Path, PureWindowsPath

from runner import paths

ROOT = paths.ROOT


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
    "This path is outside the PI-owned paths defined in contracts/authority.md."
)


FILE_READ_DENIAL = (
    "Reserved harness, maintainer, and protected scientific files are unavailable "
    "for inspection in this phase."
)


RESULTS_READ_DENIAL = (
    "Read campaign results through artifact_evidence_query, not this file: "
    "action=operations lists operations (filter with where/select); "
    "action=metadata with operation_id and path=/record returns one complete record."
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
    "agents.md",
    "readme.md",
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
    try:
        path = physical_target(target)
        if paths.SPLIT:
            if path.resolve() in {ROOT.resolve(), paths.HARNESS_ROOT.resolve()}:
                return "."
            return paths.logical_path(path).casefold()
        return path.resolve().relative_to(ROOT.resolve()).as_posix().casefold()
    except ValueError:
        return None


def physical_target(target: str) -> Path:
    path = Path(target.strip())
    if path.is_absolute():
        return path
    if paths.SPLIT:
        return ROOT if target.strip() in {".", ""} else paths.locate(target.strip())
    return ROOT / path


def read_target(target: str) -> Path:
    """Resolve absent campaign-root aliases without accepting shadow files."""
    from runner.copilot.copilot_scoped_search import linked_path

    path = physical_target(target)
    if paths.SPLIT and path.is_relative_to(paths.HARNESS_ROOT):
        relative = path.relative_to(paths.HARNESS_ROOT)
        if ".." in relative.parts:
            raise ValueError("Read paths must not contain parent traversal.")
        # Contract reads resolve into the harness; campaign files live elsewhere.
        if paths.is_campaign_owned(relative) and not linked_path(
            paths.HARNESS_ROOT, path
        ):
            return paths.locate(relative)
    if paths.SPLIT and path.is_relative_to(ROOT):
        relative = path.relative_to(ROOT)
        if ".." in relative.parts:
            raise ValueError("Read paths must not contain parent traversal.")
        if (
            relative != Path(".")
            and not paths.is_campaign_owned(relative)
            and not path.exists()
            and not linked_path(ROOT, path)
        ):
            return paths.locate(relative)
    return path


def target_root(path: Path) -> Path:
    if paths.SPLIT and path.resolve().is_relative_to(paths.HARNESS_ROOT.resolve()):
        return paths.HARNESS_ROOT
    return ROOT


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
    try:
        path = physical_target(target)
    except ValueError:
        return FILE_EDIT_DENIAL
    if linked_path(target_root(path), path) or ":" in str(path)[len(path.anchor) :]:
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
    try:
        path = physical_target(target) if isinstance(target, str) else ROOT.parent
    except ValueError:
        return FILE_READ_DENIAL
    if (
        relative is None
        or linked_path(target_root(path), path)
        or ":" in str(path)[len(path.anchor) :]
        or relative.split("/", 1)[0] in {".git", ".venv", ".github"}
        or relative == ".copilot"
        or (
            relative.startswith(".copilot/")
            and not relative.startswith(".copilot/large-output/")
        )
    ):
        return FILE_READ_DENIAL
    if relative == "campaigns/results.jsonl":
        return RESULTS_READ_DENIAL
    if relative.startswith("reports/tui_observations/"):
        return FILE_READ_DENIAL
    if preliminary and relative.startswith("robot_learning/"):
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
        if physical_target(target).is_dir():
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
                or relative == "pi_workspace/scientific_model.md"
            ):
                raise ValueError(
                    rejection + "read_paths permits scientific sources, contracts "
                    "and the frozen scientific model only; select other "
                    "relevant context through source_context."
                )
        result.add(relative)
    return frozenset(result)
