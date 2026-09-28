"""The Copilot adapter is a runtime boundary, not a scientific authority.

It decides what may run and what the console shows. It never decides whether a
bounded research phase succeeded, and none of these tests start a real session.
"""

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

import researcher_copilot as adapter

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "researcher_copilot.py").read_text(encoding="utf-8")


# --- model identity ---------------------------------------------------------


def test_the_provider_prefix_is_stripped_from_the_model():
    assert adapter.normalize_model("github-copilot/gpt-5.6-luna") == "gpt-5.6-luna"
    assert adapter.normalize_model("gpt-5.6-luna") == "gpt-5.6-luna"


# --- the command policy -----------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x",
        "git add -A",
        "git push origin HEAD",
        "git checkout main",
        "git reset --hard",
        "git restore --source HEAD -- file.py",
        "git stash",
        "git rebase main",
        "git clean -fd",
        "git.exe commit -m x",
        r'"C:\Program Files\Git\cmd\git.exe" push origin HEAD',
        r'"C:\Program Files\Git\cmd\git.exe" -C . reset --hard',
        # An unfamiliar verb is refused rather than assumed harmless.
        "git switcheroo",
    ],
)
def test_mutating_git_is_refused(command):
    reason = adapter.command_denial(command)

    assert reason == adapter.GIT_DENIAL


@pytest.mark.parametrize(
    "command",
    [
        "git status --short",
        "git diff --name-only",
        "git log --oneline -5",
        "git show HEAD:robot_learning/scenario/reward.py",
        "git rev-parse HEAD",
        "git ls-files",
        "git.exe status --short",
        r'"C:\Program Files\Git\cmd\git.exe" -C . log -1',
    ],
)
def test_read_only_git_stays_available(command):
    assert adapter.command_denial(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "uv run python research/run_experiment.py",
        "uv run python -m research.run_experiment --check-operation",
        "uv run python research/run_experiment.py --execute-pending",
        "uv run python research/run_experiment.py --run-official-assessment",
        "uv run python research/migrate_policy_runtime.py --help",
        "uv run python -m research.migrate_policy_runtime --help",
        "uv run python research/reset_campaign.py --mode fresh",
        "uv run python -m research.reset_campaign --mode fresh",
        "uv run python -m robot_learning.train",
        "uv run python -m robot_learning.evaluate --official-benchmark --model x.zip",
        "uv run python robot_learning/evaluate.py --task-reference --model x.zip",
        "uv run python robot_learning/play.py",
        r".\run_research.ps1",
        r"& .\run_research.ps1",
        r".\reset_research.ps1 -Mode Fresh",
        "pwsh -File run_research.ps1",
        "powershell.exe -File reset_research.ps1 -Mode Fresh",
    ],
)
def test_execution_belongs_to_the_launcher(command):
    assert adapter.command_denial(command) == adapter.EXECUTION_DENIAL


def test_a_repository_wide_test_run_is_refused():
    existing = "tests/autoresearch/test_copilot_researcher.py"
    assert adapter.command_denial("uv run pytest") == adapter.SUITE_DENIAL
    assert adapter.command_denial("uv run pytest -q") == adapter.SUITE_DENIAL
    assert adapter.command_denial("uv run pytest -k foo") == adapter.SUITE_DENIAL
    assert adapter.command_denial("pytest.exe -k foo") == adapter.SUITE_DENIAL
    # A flag-only option alone still selects nothing.
    assert adapter.command_denial("uv run pytest --strict") == adapter.SUITE_DENIAL
    # A directory runs the whole tree, not a targeted selection.
    assert adapter.command_denial("uv run pytest tests") == adapter.SUITE_DENIAL
    # A value-taking option is not a test selector, whatever its name, so an
    # option-only invocation still runs everything.
    assert adapter.command_denial("uv run pytest --color no") == adapter.SUITE_DENIAL
    assert (
        adapter.command_denial("uv run pytest --durations-min 1")
        == adapter.SUITE_DENIAL
    )
    assert (
        adapter.command_denial("uv run pytest --code-highlight yes")
        == adapter.SUITE_DENIAL
    )
    # A path used only as an option value is not a selector either, even when a
    # value-less option precedes the value-taking one.
    assert (
        adapter.command_denial("uv run pytest --rootdir tests") == adapter.SUITE_DENIAL
    )
    assert (
        adapter.command_denial(f"uv run pytest --strict --rootdir {existing}")
        == adapter.SUITE_DENIAL
    )
    assert (
        adapter.command_denial(
            "uv run pytest --rootdir tests/autoresearch/test_copilot_researcher.py"
        )
        == adapter.SUITE_DENIAL
    )
    # An inline option value is not a selector, so the run stays repository-wide.
    assert (
        adapter.command_denial("uv run pytest --rootdir=tests") == adapter.SUITE_DENIAL
    )


@pytest.mark.parametrize(
    "flag", ["--locked", "--frozen", "--offline", "--no-sync", "--no-project"]
)
def test_uv_run_value_less_flags_do_not_hide_denied_commands(flag):
    assert (
        adapter.command_denial(f"uv run {flag} git commit -m x") == adapter.GIT_DENIAL
    )
    assert adapter.command_denial(f"uv run {flag} pytest") == adapter.SUITE_DENIAL


def test_uv_run_value_options_consume_only_their_values():
    assert (
        adapter.command_denial("uv run --project . git commit -m x")
        == adapter.GIT_DENIAL
    )
    assert adapter.command_denial("uv run --python 3.12 pytest") == adapter.SUITE_DENIAL


def test_a_targeted_test_run_remains_permitted():
    # AGENTS.md and research/instruments.md allow targeted tests and focused
    # checks, so the command layer refuses only repository-wide runs.
    existing = "tests/autoresearch/test_copilot_researcher.py"
    assert adapter.command_denial(f"uv run pytest {existing}") is None
    assert adapter.command_denial(f"uv run pytest {existing}::test_x") is None
    assert adapter.command_denial(f"uv run pytest --maxfail 1 {existing}") is None
    # A flag-only option consumes nothing and must not hide the selector.
    assert adapter.command_denial(f"uv run pytest -q {existing}") is None
    # The value-less options pytest itself declares are recognised, including
    # ones a hand-maintained list omitted.
    for flag in ("--strict", "--disable-plugin-autoload", "--trace-config"):
        assert adapter.command_denial(f"uv run pytest {flag} {existing}") is None
    for flag in (
        "--markers",
        "--no-showlocals",
        "--stepwise-reset",
        "--traceconfig",
        "--fulltrace",
        "-h",
        "-V",
    ):
        assert adapter.command_denial(f"uv run pytest {flag} {existing}") is None
    # Repeated and combined short flags consume nothing either.
    assert adapter.command_denial(f"uv run pytest -q -q {existing}") is None
    assert adapter.command_denial(f"uv run pytest -qq {existing}") is None
    assert adapter.command_denial(f"uv run pytest -qx {existing}") is None
    # An inline option value likewise leaves the selector visible.
    assert adapter.command_denial(f"uv run pytest --maxfail=1 {existing}") is None


@pytest.mark.parametrize(
    "command",
    [
        "uv add sb3-contrib",
        "uv remove stable-baselines3",
        "uv sync",
        "uv lock",
        "uv pip install sb3-contrib",
        "uv run --with sb3-contrib python analysis.py",
        "uv run --with-requirements requirements.txt python analysis.py",
        "uv run pip install sb3-contrib",
        "uv run python -m pip install sb3-contrib",
        "uv tool install ruff",
        "uvx ruff check .",
        "pip install sb3-contrib",
        "pipx install ruff",
        "python -m pip uninstall stable-baselines3",
        "Install-Package example",
    ],
)
def test_dependency_management_is_refused(command):
    assert adapter.command_denial(command) == adapter.DEPENDENCY_DENIAL


@pytest.mark.parametrize(
    "command",
    [
        "uv --offline add numpy",
        "uv -n add numpy",
        "uv --project . sync",
        "uv --project=. lock",
        "uv --offline run --with requests python -c pass",
        "uv --offline run --with=requests python -c pass",
        "uv --offline run -w requests python -c pass",
        "uv --offline run -w=requests python -c pass",
        "uv run -wrequests python -c pass",
        "uv --offline run -wrequests python -c pass",
        r"C:\Tools\uv.exe --offline add numpy",
        r'"C:\Program Files\uv\uv.exe" --project=. sync',
        r'& "C:\Program Files\uv\uv.exe" --offline add numpy',
    ],
)
def test_uv_global_options_cannot_hide_dependency_management(command):
    assert adapter.command_denial(command) == adapter.DEPENDENCY_DENIAL


def test_uv_run_uses_the_fixed_environment_without_being_obstructed():
    for command in (
        "uv run python analysis.py",
        "uv run pytest -W error tests/autoresearch/test_copilot_researcher.py",
        "uv run python analysis.py -w 5",
        "uv --offline run python analysis.py",
        "uv -n run python analysis.py",
        "uv --project . run python analysis.py",
        "uv --project=. run ruff check robot_learning/scenario/reward.py",
        r"C:\Tools\uv.exe --offline run python analysis.py",
    ):
        assert adapter.command_denial(command) is None


def test_ordinary_research_commands_are_not_obstructed():
    for command in (
        "uv run ruff check robot_learning/scenario/reward.py",
        "uv run python -c \"import json; print('ok')\"",
        "Get-Content research/brief.md",
    ):
        assert adapter.command_denial(command) is None


@pytest.mark.parametrize(
    "command",
    [
        # Naming a protected path is research; only running it is execution.
        "Get-Content research/run_experiment.py",
        "rg request_official_assessment research/runner_protocol.py",
        "Select-String -Path research/program.md -Pattern official_assessment",
        "python -c \"print(operation['campaign_conclusion'])\"",
        "cat robot_learning/train.py",
    ],
)
def test_reading_about_a_protected_path_is_not_running_it(command):
    assert adapter.command_denial(command) is None


def test_the_execution_target_is_resolved_through_the_launcher_prefix():
    resolve = adapter.execution_target

    assert resolve(["uv", "run", "python", "research/run_experiment.py"]) == (
        "research/run_experiment.py"
    )
    assert resolve(["uv", "run", "--group", "researcher", "python", "x.py"]) == "x.py"
    assert resolve(["uv", "run", "--locked", "git", "commit"]) == "git"
    assert resolve(["uv", "--offline", "run", "--project", ".", "pytest"]) == "pytest"
    assert resolve(["uv", "run", "--", "pytest"]) == "pytest"
    assert resolve(["uv", "run", "python", "-m", "robot_learning.train"]) == (
        "robot_learning.train"
    )
    assert resolve(["uv", "run", "pytest", "tests/autoresearch/test.py"]) == "pytest"
    # Inline code names no target, which the guardrail accepts knowingly.
    assert resolve(["python", "-c", "code"]) is None
    assert resolve(["Get-Content", "anything"]) is None


@pytest.mark.parametrize(
    "command",
    [
        "git status; git push",
        "git status && git commit -m x",
        "Get-Content x.txt | git apply",
    ],
)
def test_a_refused_command_cannot_hide_behind_an_allowed_one(command):
    assert adapter.command_denial(command) is not None


def test_the_shell_request_is_read_from_every_segment_it_reports():
    request = SimpleNamespace(
        full_command_text="git status",
        command_segments=[SimpleNamespace(full_command_text="git push")],
    )

    assert adapter.command_denial(adapter.shell_command_text(request)) is not None


def test_a_refused_shell_call_answers_with_a_rejection(capsys):
    pytest.importorskip("copilot")
    from copilot.rpc import PermissionDecisionReject
    from copilot.session_events import PermissionRequestShell

    console = adapter.Console()
    _, on_permission = adapter.build_handlers(console, asyncio.Event())
    request = PermissionRequestShell(
        can_offer_session_approval=False,
        commands=[],
        full_command_text="git push",
        has_write_file_redirection=False,
        intention="publish",
        possible_paths=[],
        possible_urls=[],
        tool_call_id="call-3",
    )

    decision = on_permission(request, {})

    assert isinstance(decision, PermissionDecisionReject)
    assert decision.feedback == adapter.GIT_DENIAL
    assert "call-3" in console.denied_calls
    capsys.readouterr()


def test_write_permissions_enforce_the_pi_owned_surface(capsys):
    pytest.importorskip("copilot")
    from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject
    from copilot.session_events import PermissionRequestWrite

    console = adapter.Console()
    _, on_permission = adapter.build_handlers(console, asyncio.Event())

    allowed = PermissionRequestWrite(
        can_offer_session_approval=False,
        diff="",
        file_name="robot_learning/training/algorithms.py",
        intention="scientific edit",
        tool_call_id="write-allowed",
    )
    denied = PermissionRequestWrite(
        can_offer_session_approval=False,
        diff="",
        file_name="research/run_experiment.py",
        intention="runner edit",
        tool_call_id="write-denied",
    )

    assert isinstance(on_permission(allowed, {}), PermissionDecisionApproveOnce)
    decision = on_permission(denied, {})
    assert isinstance(decision, PermissionDecisionReject)
    assert decision.feedback == adapter.FILE_EDIT_DENIAL
    assert "write-denied" in console.denied_calls
    capsys.readouterr()


def test_preliminary_write_permission_only_allows_the_scientific_model():
    assert (
        adapter.file_edit_denial("research/scientific_model.md", preliminary=True)
        is None
    )
    assert (
        adapter.file_edit_denial("research/operation_request.json", preliminary=True)
        == adapter.FILE_EDIT_DENIAL
    )
    assert adapter.file_edit_denial("research/operation_request.json") is None


# --- the session profile ----------------------------------------------------


def test_the_session_runs_a_trimmed_tool_profile_inside_the_worktree():
    pytest.importorskip("copilot")
    args = adapter.parse_args(["p", "--session-id", "s", "--reasoning", "medium"])

    options = adapter.session_options(args, adapter.Console(), asyncio.Event())

    assert options["model"] == "gpt-5.6-luna"
    assert options["reasoning_effort"] == "medium"
    assert options["working_directory"] == str(ROOT)
    assert options["streaming"] is True
    assert options["enable_file_change_tracking"] is True
    # Everything a robotics experiment cannot use stays out of the context.
    assert options["enable_skills"] is False
    assert options["enable_session_store"] is False
    assert options["enable_mcp_apps"] is False
    allowed = options["available_tools"].to_list()
    assert "builtin:view" in allowed
    assert "builtin:apply_patch" in allowed
    for absent in ("builtin:web_fetch", "builtin:sql", "builtin:task"):
        assert absent not in allowed


def test_oversized_tool_output_is_offloaded_instead_of_held_in_context():
    pytest.importorskip("copilot")
    args = adapter.parse_args(["p", "--session-id", "s"])

    large_output = adapter.session_options(args, adapter.Console(), asyncio.Event())[
        "large_output"
    ]

    assert large_output["enabled"] is True
    assert large_output["max_size_bytes"] == adapter.LARGE_OUTPUT_MAX_BYTES
    # Offloaded output stays readable but must never look like a research change.
    assert large_output["output_directory"] == str(adapter.LARGE_OUTPUT_DIR)
    assert adapter.LARGE_OUTPUT_DIR.is_relative_to(ROOT)
    assert ".copilot/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_campaign_artifacts_are_not_offloaded_out_of_the_session():
    # Evaluation panels run about 120 KiB; the threshold sits well above them so
    # the primary scientific evidence stays in the session by default.
    assert adapter.LARGE_OUTPUT_MAX_BYTES >= 256 * 1024


# --- session identity -------------------------------------------------------


class FakeSession:
    def __init__(self, session_id):
        self.session_id = session_id


class FakeClient:
    def __init__(self, *, authenticated=True, models=("gpt-5.6-luna",)):
        self.authenticated = authenticated
        self.models = models
        self.created = []
        self.resumed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_auth_status(self):
        return SimpleNamespace(isAuthenticated=self.authenticated)

    async def list_models(self):
        return [SimpleNamespace(id=name) for name in self.models]

    async def create_session(self, **kwargs):
        self.created.append(kwargs)
        return FakeSession(kwargs["session_id"])

    async def get_session_metadata(self, session_id):
        return None

    async def resume_session(self, session_id, **kwargs):
        self.resumed.append((session_id, kwargs))
        return FakeSession(session_id)


def test_a_first_attempt_creates_the_session_the_launcher_named():
    client = FakeClient()
    args = adapter.parse_args(["p", "--session-id", "phase-1"])

    session = asyncio.run(adapter.open_session(client, args, {}))

    assert client.created == [{"session_id": "phase-1"}]
    assert client.resumed == []
    assert session.session_id == "phase-1"


def test_a_retry_resumes_that_same_session_and_never_an_implicit_one():
    client = FakeClient()
    args = adapter.parse_args(["p", "--session-id", "phase-1", "--resume"])

    asyncio.run(adapter.open_session(client, args, {}))

    assert client.resumed == [("phase-1", {})]
    assert client.created == []


def test_a_missing_persisted_session_fails_without_creating_a_replacement():
    class MissingSessionClient(FakeClient):
        async def resume_session(self, session_id, **kwargs):
            self.resumed.append((session_id, kwargs))
            raise LookupError("missing")

    client = MissingSessionClient()
    args = adapter.parse_args(["p", "--session-id", "campaign-pi", "--resume"])

    with pytest.raises(RuntimeError, match="refusing to create a replacement"):
        asyncio.run(adapter.open_session(client, args, {}))

    assert client.created == []


def test_first_invocation_recovery_creates_the_missing_persisted_session():
    client = FakeClient()
    args = adapter.parse_args(
        ["p", "--session-id", "campaign-pi", "--resume-or-create"]
    )

    session = asyncio.run(adapter.open_session(client, args, {}))

    assert client.resumed == []
    assert client.created == [{"session_id": "campaign-pi"}]
    assert session.session_id == "campaign-pi"


def test_first_invocation_recovery_resumes_an_existing_persisted_session():
    class ExistingSessionClient(FakeClient):
        async def get_session_metadata(self, session_id):
            return SimpleNamespace(session_id=session_id)

    client = ExistingSessionClient()
    args = adapter.parse_args(
        ["p", "--session-id", "campaign-pi", "--resume-or-create"]
    )

    session = asyncio.run(adapter.open_session(client, args, {}))

    assert client.resumed == [("campaign-pi", {})]
    assert client.created == []
    assert session.session_id == "campaign-pi"


def test_first_invocation_recovery_does_not_guess_when_lookup_fails():
    class FailingLookupClient(FakeClient):
        async def get_session_metadata(self, session_id):
            raise RuntimeError(f"lookup failed for {session_id}")

    client = FailingLookupClient()
    args = adapter.parse_args(
        ["p", "--session-id", "campaign-pi", "--resume-or-create"]
    )

    with pytest.raises(RuntimeError, match="lookup failed"):
        asyncio.run(adapter.open_session(client, args, {}))

    assert client.resumed == []
    assert client.created == []


def install_fake_sdk(monkeypatch, client):
    module = types.ModuleType("copilot")
    module.CopilotClient = lambda **kwargs: client
    monkeypatch.setitem(sys.modules, "copilot", module)


def test_a_missing_copilot_login_fails_without_starting_a_session(monkeypatch, capsys):
    client = FakeClient(authenticated=False)
    install_fake_sdk(monkeypatch, client)

    code = adapter.main(["p", "--session-id", "phase-1"])

    assert code == adapter.EXIT_NOT_AUTHENTICATED
    assert client.created == []
    assert "not authenticated" in capsys.readouterr().err


def test_an_unavailable_model_is_reported_instead_of_silently_replaced(
    monkeypatch, capsys
):
    client = FakeClient(models=("gpt-5.5", "claude-opus-5"))
    install_fake_sdk(monkeypatch, client)

    code = adapter.main(["p", "--session-id", "phase-1", "--model", "gpt-5.6-luna"])

    error = capsys.readouterr().err
    assert code == adapter.EXIT_MODEL_UNAVAILABLE
    assert client.created == []
    assert "gpt-5.6-luna" in error and "gpt-5.5" in error


def test_a_runtime_failure_becomes_an_exit_code_not_a_traceback(monkeypatch, capsys):
    module = types.ModuleType("copilot")

    def explode(**kwargs):
        raise RuntimeError("runtime binary is missing")

    module.CopilotClient = explode
    monkeypatch.setitem(sys.modules, "copilot", module)

    code = adapter.main(["p", "--session-id", "phase-1"])

    assert code == adapter.EXIT_RUNTIME_FAILURE
    assert "runtime binary is missing" in capsys.readouterr().err


# --- the boundary with the science ------------------------------------------


def test_the_adapter_never_judges_a_research_deliverable():
    assert "runner_protocol" not in SOURCE
    assert "validate_operation_request" not in SOURCE
    assert "json.load" not in SOURCE


def test_the_copilot_runtime_loads_only_where_it_is_used():
    header = SOURCE.split("ROOT = Path", 1)[0]

    assert "import copilot" not in header
    assert "from copilot" not in header
    # Every other module keeps importing the adapter's policy without the SDK.
    assert "from copilot" in SOURCE
