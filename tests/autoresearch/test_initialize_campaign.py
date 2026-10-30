"""Recipe initialization imports only code and optional scientific analysis."""

from __future__ import annotations

import io
import json
import shutil
import stat
import subprocess
import sys
import zipfile

import pytest

from runner import paths, repository, reset_campaign
from tools import initialize_campaign

ANALYSIS_PATH = "pi_workspace/scientific_model.md"
ANALYSIS = (
    "## Established facts\r\nThe robot has joint position limits.\r\n"
    "## Physical consequences\r\nJoint limits bound the reachable workspace.\r\n"
    "## Unknowns\r\nThe learned policy accuracy is not measured.\r\n"
    "## Decision-relevant synthesis\r\nMeasure policy accuracy: caf\u00e9.\r\n"
).encode("utf-8")
REFERENCE = "prepared-recipe"
REVISION = "a" * 40


@pytest.fixture
def recipe_source(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    root = tmp_path / "new-campaign"
    contract = {"schema_version": 1, "files": {"controlled-task": "fingerprint"}}
    monkeypatch.setattr(initialize_campaign, "task_contract", lambda: contract)
    files = {
        "robot_learning/train.py": b"VALUE = 1\n",
        initialize_campaign.TASK_CONTRACT_PATH: json.dumps(contract).encode("utf-8"),
    }
    git_calls = []
    resets = []

    def source_git(folder, *arguments):
        git_calls.append((folder, arguments))
        if folder != source:
            assert folder == root
            assert arguments[0] in {"init", "add", "commit", "tag"}
            return b""
        if arguments[0] == "check-ref-format":
            return b""
        if arguments[0] == "rev-parse":
            return REVISION.encode("ascii")
        if arguments[0] == "ls-tree":
            return "\n".join(files).encode("utf-8")
        if arguments[0] == "show":
            return files[arguments[1].split(":", 1)[1]]
        assert arguments[:4] == ("archive", "--format=zip", REVISION, "--")
        selected = arguments[4:]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            if ANALYSIS_PATH in selected:
                archive.writestr("pi_workspace/", b"")
            for relative, content in files.items():
                if any(
                    relative == prefix or relative.startswith(prefix + "/")
                    for prefix in selected
                ):
                    archive.writestr(relative, content.replace(b"\r\n", b"\n"))
        return buffer.getvalue()

    def reset(command, *, cwd, env, check):
        assert command == [
            sys.executable,
            "-m",
            "runner.reset_campaign",
            "--mode",
            "fresh",
            "--recipe-ref",
            REFERENCE,
        ]
        assert cwd == paths.HARNESS_ROOT
        assert env[paths.CAMPAIGN_ROOT_ENV] == str(root)
        assert not check
        assert (root, ("tag", REFERENCE)) in git_calls
        resets.append(
            {
                target.relative_to(root).as_posix(): target.read_bytes()
                for target in root.rglob("*")
                if target.is_file()
            }
        )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(initialize_campaign, "source_git", source_git)
    monkeypatch.setattr(initialize_campaign, "trust_folder", lambda _root: None)
    monkeypatch.setattr(initialize_campaign.subprocess, "run", reset)
    return source, root, files, git_calls, resets


def test_prepared_recipe_imports_only_code_and_exact_analysis_bytes(recipe_source):
    source, root, files, git_calls, resets = recipe_source
    files[ANALYSIS_PATH] = ANALYSIS
    excluded = (
        "pi_workspace/operation_request.json",
        "pi_workspace/notes.md",
        "runner/state/research_state.json",
        "campaigns/EXPERIMENTS.md",
        "campaigns/checkpoints/candidates/old/model.zip",
        "models/candidates/old/model.zip",
        ".copilot/session.json",
    )
    files.update(dict.fromkeys(excluded, b"prior campaign data"))

    initialize_campaign.initialize(root, source, REFERENCE)

    imported = resets[0]
    assert set(imported) == {
        "robot_learning/train.py",
        ANALYSIS_PATH,
        initialize_campaign.TASK_CONTRACT_PATH,
        ".gitignore",
    }
    assert imported["robot_learning/train.py"] == files["robot_learning/train.py"]
    assert imported[ANALYSIS_PATH] == ANALYSIS
    assert json.loads(imported[initialize_campaign.TASK_CONTRACT_PATH]) == (
        initialize_campaign.task_contract()
    )
    assert imported[".gitignore"].decode("utf-8").splitlines() == (
        initialize_campaign.CAMPAIGN_GITIGNORE.splitlines()
    )
    assert (root / ANALYSIS_PATH).read_bytes() == ANALYSIS
    assert (root, ("add", "--", ".")) in git_calls
    assert any(
        folder == root and arguments[0] == "commit" for folder, arguments in git_calls
    )
    assert (
        source,
        ("archive", "--format=zip", REVISION, "--", "robot_learning", ANALYSIS_PATH),
    ) in git_calls


@pytest.mark.parametrize("analysis", [b"", b"## Established facts\nLimits.\n", b"\xff"])
def test_invalid_analysis_rejects_before_destination_creation(recipe_source, analysis):
    source, root, files, git_calls, resets = recipe_source
    files[ANALYSIS_PATH] = analysis

    with pytest.raises(ValueError):
        initialize_campaign.initialize(root, source, REFERENCE)

    assert not root.exists()
    assert not resets
    assert not any(arguments[0] == "archive" for _, arguments in git_calls)


def test_real_git_prepared_recipe_initializes_and_publishes_fresh_campaign(
    tmp_path, monkeypatch
):
    if shutil.which("git") is None:
        pytest.skip("Git is not installed")
    source = tmp_path / "source"
    root = tmp_path / "destination"
    settings = {
        "core.autocrlf": "false",
        "core.hooksPath": str(tmp_path / "hooks"),
        "commit.gpgsign": "false",
        "safe.directory": str(source),
    }
    monkeypatch.setenv("GIT_CONFIG_COUNT", str(len(settings) + 1))
    for index, (name, value) in enumerate(settings.items()):
        monkeypatch.setenv(f"GIT_CONFIG_KEY_{index}", name)
        monkeypatch.setenv(f"GIT_CONFIG_VALUE_{index}", value)
    monkeypatch.setenv(f"GIT_CONFIG_KEY_{len(settings)}", "safe.directory")
    monkeypatch.setenv(f"GIT_CONFIG_VALUE_{len(settings)}", str(root))
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Initializer test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "initializer@example.invalid")
    monkeypatch.setattr(paths, "SPLIT", True)
    for name, relative in {
        "ROOT": ".",
        "CAMPAIGNS_DIR": "campaigns",
        "RUNNER_STATE_DIR": "runner/state",
        "PI_WORKSPACE_DIR": "pi_workspace",
        "RESEARCH_DIR": "campaigns",
        "LOG_PATH": "campaigns/EXPERIMENTS.md",
        "RESULTS_PATH": "campaigns/results.jsonl",
        "OPERATION_REQUEST_PATH": "pi_workspace/operation_request.json",
        "STATE_PATH": "runner/state/research_state.json",
        "TRAINING_LOG_DIR": "campaigns/training_logs",
        "SCIENTIFIC_MODEL_PATH": ANALYSIS_PATH,
        "GOAL_PATH": "runner/state/GOAL_REACHED",
        "RECOVERY_PENDING_PATH": "runner/state/RECOVERY_PENDING",
        "RESTART_PENDING_PATH": "runner/state/RESTART_PENDING",
        "CANDIDATE_ROOT": "models/candidates",
        "EVALUATION_DIR": "campaigns/evaluations",
    }.items():
        monkeypatch.setattr(paths, name, root / relative)
    contract = initialize_campaign.task_contract()
    excluded = (
        "pi_workspace/notes.md",
        "pi_workspace/operation_request.json",
        "runner/state/research_state.json",
        "campaigns/EXPERIMENTS.md",
        "campaigns/results.jsonl",
        "campaigns/checkpoints/candidates/old/model.zip",
        "models/candidates/old/model.zip",
        ".copilot/session.json",
    )
    files = {
        "robot_learning/train.py": b"VALUE = 1\n",
        "robot_learning/training/current_params.json": b'{"algorithm":{"name":"ppo"}}\n',
        initialize_campaign.TASK_CONTRACT_PATH: json.dumps(contract).encode("utf-8"),
        ANALYSIS_PATH: ANALYSIS,
        **dict.fromkeys(excluded, b"prior campaign data"),
    }
    for relative, content in files.items():
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    initialize_campaign.source_git(source, "init", "-b", "source")
    initialize_campaign.source_git(source, "add", "--", ".")
    initialize_campaign.source_git(source, "commit", "-m", "Prepared source recipe")
    initialize_campaign.source_git(source, "tag", REFERENCE)
    source_revision = initialize_campaign.source_git(
        source, "rev-parse", "HEAD"
    ).strip()
    run = subprocess.run

    def dispatch_reset(command, **kwargs):
        if command[:3] != [sys.executable, "-m", "runner.reset_campaign"]:
            return run(command, **kwargs)
        assert kwargs["cwd"] == paths.HARNESS_ROOT
        assert kwargs["env"][paths.CAMPAIGN_ROOT_ENV] == str(root)
        with monkeypatch.context() as reset_context:
            reset_context.setattr(sys, "argv", ["runner.reset_campaign", *command[3:]])
            return subprocess.CompletedProcess(command, reset_campaign.main())

    monkeypatch.setattr(initialize_campaign, "trust_folder", lambda _root: None)
    monkeypatch.setattr(reset_campaign, "validate_restored_recipe", lambda: None)
    monkeypatch.setattr(initialize_campaign.subprocess, "run", dispatch_reset)

    initialize_campaign.initialize(root, source, REFERENCE)

    local_revision = initialize_campaign.source_git(
        root, "rev-parse", f"{REFERENCE}^{{commit}}"
    ).strip()
    assert local_revision != source_revision
    assert (
        initialize_campaign.source_git(
            root, "show", f"{local_revision.decode()}:{ANALYSIS_PATH}"
        )
        == ANALYSIS
    )
    assert (root / ANALYSIS_PATH).read_bytes() == ANALYSIS
    assert initialize_campaign.source_git(root, "show", f"HEAD:{ANALYSIS_PATH}") == (
        ANALYSIS
    )
    state = repository.load_state()
    assert state["scientific_model"] == {
        "status": "ready",
        "path": ANALYSIS_PATH,
        "commit": local_revision.decode(),
    }
    assert state["campaign"]["recipe_source_commit"] == local_revision.decode()
    assert state["campaign_phase"] == "recipe_development"
    assert state["recipe_development"] is None
    assert state["counters"] == dict.fromkeys(
        ("inquiry", "session", "measurement", "training", "event"), 0
    )
    assert state["operation_events"] == []
    assert state["candidates"] == {}
    assert state["model_roles"] == {"working": None, "best_known": None, "retained": {}}
    for field in (
        "pending_operation",
        "active_inquiry",
        "pi_checkpoint",
        "scientific_session",
        "official_assessment",
        "terminal_state",
    ):
        assert state[field] is None
    assert (
        json.loads(
            initialize_campaign.source_git(
                root, "show", "HEAD:runner/state/research_state.json"
            )
        )
        == state
    )
    assert paths.RESULTS_PATH.read_bytes() == b""
    assert paths.LOG_PATH.read_text(
        encoding="utf-8"
    ) == repository.render_operation_log([])
    for relative in excluded:
        if relative not in {
            "runner/state/research_state.json",
            "campaigns/EXPERIMENTS.md",
            "campaigns/results.jsonl",
        }:
            assert not (root / relative).exists()
    assert not paths.reset_marker_path(root).exists()
    assert initialize_campaign.source_git(root, "status", "--porcelain") == b""
    assert initialize_campaign.source_git(root, "remote") == b""


def test_bare_recipe_keeps_code_only_archive_and_pending_analysis(recipe_source):
    source, root, _files, git_calls, resets = recipe_source

    initialize_campaign.initialize(root, source, REFERENCE)

    assert resets
    assert ANALYSIS_PATH not in resets[0]
    assert not (root / "pi_workspace").exists()
    assert (
        source,
        ("archive", "--format=zip", REVISION, "--", "robot_learning"),
    ) in git_calls
    state = reset_campaign.empty_state(REVISION, REVISION)
    assert state["scientific_model"] == {
        "status": "pending",
        "path": ANALYSIS_PATH,
        "commit": None,
    }


@pytest.mark.parametrize(
    ("filename", "mode"),
    [
        ("pi_workspace/notes.md", stat.S_IFREG),
        ("pi_workspace", stat.S_IFREG),
        ("pi_workspace/../escape.md", stat.S_IFREG),
        ("/pi_workspace/scientific_model.md", stat.S_IFREG),
        (ANALYSIS_PATH, stat.S_IFLNK),
        ("pi_workspace/", stat.S_IFLNK),
    ],
)
def test_analysis_archive_rejects_other_workspace_paths_and_unsafe_entries(
    recipe_source, monkeypatch, filename, mode
):
    source, root, files, _git_calls, resets = recipe_source
    files[ANALYSIS_PATH] = ANALYSIS
    source_git = initialize_campaign.source_git

    def unsafe_archive(folder, *arguments):
        result = source_git(folder, *arguments)
        if arguments[0] != "archive":
            return result
        buffer = io.BytesIO()
        with (
            zipfile.ZipFile(io.BytesIO(result)) as original,
            zipfile.ZipFile(buffer, "w") as archive,
        ):
            for member in original.infolist():
                if member.filename != filename:
                    archive.writestr(member, original.read(member))
            entry = zipfile.ZipInfo(filename)
            entry.create_system = 3
            entry.external_attr = (mode | 0o644) << 16
            archive.writestr(entry, b"unexpected")
        return buffer.getvalue()

    monkeypatch.setattr(initialize_campaign, "source_git", unsafe_archive)

    with pytest.raises(ValueError, match="Unsafe recipe archive member"):
        initialize_campaign.initialize(root, source, REFERENCE)

    assert not root.exists()
    assert not resets
