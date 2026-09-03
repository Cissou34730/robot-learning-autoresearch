import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_reset_persists_a_canonical_accepted_artifact(tmp_path):
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell is unavailable")
    root = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    research_dir = root / "research"
    research_dir.mkdir(parents=True)
    shutil.copy2(
        Path(__file__).resolve().parents[2] / "reset_research.ps1",
        root / "reset_research.ps1",
    )
    (research_dir / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-b", "test", str(root)], check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Runner"], cwd=root, check=True
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=root, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)], cwd=root, check=True
    )

    subprocess.run(
        [pwsh, "-NoProfile", "-File", str(root / "reset_research.ps1"), "-Force"],
        cwd=root,
        check=True,
    )

    state = json.loads(
        (research_dir / "research_state.json").read_text(encoding="utf-8-sig")
    )
    assert state["accepted_artifact"] == "research/checkpoints/accepted"