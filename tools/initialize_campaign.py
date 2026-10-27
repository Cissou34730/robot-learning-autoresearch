"""Create an independent, local-only campaign repository from a recipe ref."""

from __future__ import annotations

import argparse
import io
import json
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

from runner import paths
from runner.reset_campaign import (
    TASK_COMPATIBILITY_PATHS,
    TASK_CONTRACT_PATH,
    task_contract,
    task_file_fingerprint,
)

CAMPAIGN_GITIGNORE = (
    "__pycache__/\n*.py[cod]\n.venv/\n.copilot/\nreports/\nmodels/\n"
    "campaigns/evaluations/\ncampaigns/training_logs/\ncampaigns/brief.md\n"
    "runner/state/last_train_summary.md\nrunner/state/last_evaluation.json\n"
    "runner/state/GOAL_REACHED\nrunner/state/RECOVERY_PENDING\n"
    "runner/state/RESTART_PENDING\npi_workspace/operation_request.json\n"
)


def source_git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def trust_folder(root: Path) -> None:
    # Git refuses folders it considers owned by another account unless listed here.
    safe = root.as_posix()
    listed = subprocess.run(
        ["git", "config", "--global", "--get-all", "safe.directory"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    if safe not in listed:
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", safe], check=True
        )


def initialize(root: Path, source: Path, reference: str) -> None:
    root = root.resolve()
    source = source.resolve()
    if root.exists():
        raise ValueError(f"Campaign destination already exists: {root}")
    if root == paths.HARNESS_ROOT or root.is_relative_to(paths.HARNESS_ROOT):
        raise ValueError("Campaign repository must be outside the harness repository")
    source_git(source, "check-ref-format", f"refs/tags/{reference}")
    revision = (
        source_git(source, "rev-parse", "--verify", f"{reference}^{{commit}}")
        .decode()
        .strip()
    )
    files = (
        source_git(source, "ls-tree", "-r", "--name-only", revision)
        .decode()
        .splitlines()
    )
    contract = task_contract()
    if TASK_CONTRACT_PATH in files:
        recorded = json.loads(
            source_git(source, "show", f"{revision}:{TASK_CONTRACT_PATH}")
        )
    else:
        recorded = {
            "schema_version": 1,
            "files": {
                relative: task_file_fingerprint(
                    source_git(source, "show", f"{revision}:{relative}")
                )
                for relative in TASK_COMPATIBILITY_PATHS
            },
        }
    if recorded != contract:
        raise ValueError("Source recipe belongs to a different human-defined task")
    archive = source_git(
        source, "archive", "--format=zip", revision, "--", "robot_learning"
    )
    with zipfile.ZipFile(io.BytesIO(archive)) as contents:
        for member in contents.infolist():
            name = Path(member.filename)
            if (
                name.is_absolute()
                or ".." in name.parts
                or not name.parts
                or name.parts[0] != "robot_learning"
                or stat.S_ISLNK(member.external_attr >> 16)
            ):
                raise ValueError(f"Unsafe recipe archive member: {member.filename}")
        root.mkdir(parents=True)
        contents.extractall(root)
    metadata = root / TASK_CONTRACT_PATH
    metadata.parent.mkdir(parents=True)
    metadata.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    (root / ".gitignore").write_text(CAMPAIGN_GITIGNORE, encoding="utf-8")
    trust_folder(root)
    source_git(root, "init", "-b", "campaign")
    source_git(root, "add", "--", ".")
    source_git(
        root, "commit", "-m", f"Import scientific recipe from {reference} ({revision})"
    )
    source_git(root, "tag", reference)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "runner.reset_campaign",
            "--mode",
            "fresh",
            "--recipe-ref",
            reference,
        ],
        cwd=paths.HARNESS_ROOT,
        env=paths.python_environment(root),
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Campaign repository was created at {root}, but its initial reset failed. "
            "Inspect the error before retrying the reset; do not rerun initialization."
        )
    print(f"Local campaign repository: {root}")
    print("No remotes configured. No training or PI session started.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--source-repository", type=Path, default=paths.HARNESS_ROOT)
    parser.add_argument("--recipe-ref", default="baseline-distinct-episodes-v3")
    args = parser.parse_args()
    try:
        initialize(args.campaign_root, args.source_repository, args.recipe_ref)
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as error:
        print(f"Initialization failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
