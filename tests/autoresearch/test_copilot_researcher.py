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
        # An unfamiliar verb is refused rather than assumed harmless.
        "git switcheroo",
    ],
)
def test_mutating_git_is_refused_and_names_the_lineage_decision(command):
    reason = adapter.command_denial(command)

    assert reason == adapter.GIT_DENIAL
    assert "revert" in reason
    assert "code provenance and code inspection" in reason
    assert "when the current task requires it" in reason
    for read_command in ("status", "diff", "log", "show", "rev-parse", "ls-files"):
        assert read_command not in reason


@pytest.mark.parametrize(
    "command",
    [
        "git status --short",
        "git diff --name-only",
        "git log --oneline -5",
        "git show HEAD:robot_learning/scenario/reward.py",
        "git rev-parse HEAD",
        "git ls-files",
    ],
)
def test_read_only_git_stays_available(command):
    assert adapter.command_denial(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "uv run python research/run_experiment.py",
        "uv run python research/run_experiment.py --evaluate-pending",
        "uv run python -m robot_learning.train",
        "uv run python -m robot_learning.evaluate --official-benchmark --model x.zip",
        "uv run python robot_learning/evaluate.py --task-reference --model x.zip",
        "uv run python robot_learning/play.py",
    ],
)
def test_execution_belongs_to_the_launcher(command):
    assert adapter.command_denial(command) == adapter.EXECUTION_DENIAL


def test_a_repository_wide_test_run_is_refused_but_a_suite_is_not():
    assert adapter.command_denial("uv run pytest") == adapter.SUITE_DENIAL
    assert adapter.command_denial("uv run pytest -q") == adapter.SUITE_DENIAL
    assert adapter.command_denial("uv run pytest tests/scenario") is None
    assert adapter.command_denial("uv run pytest -q tests/training") is None


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


def test_uv_run_uses_the_fixed_environment_without_being_obstructed():
    assert adapter.command_denial("uv run python analysis.py") is None
    assert adapter.command_denial("uv run pytest tests/scenario") is None


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
        "rg request_final_benchmark research/runner_protocol.py",
        "Select-String -Path research/program.md -Pattern final_benchmark",
        "python -c \"print(proposal['request_final_benchmark'])\"",
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
    assert resolve(["uv", "run", "python", "-m", "robot_learning.train"]) == (
        "robot_learning.train"
    )
    assert resolve(["uv", "run", "pytest", "tests/scenario"]) == "pytest"
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


# --- what the console shows -------------------------------------------------


@pytest.mark.parametrize(
    ("tool", "arguments", "target"),
    [
        ("view", {"path": "research/brief.md"}, "research/brief.md"),
        ("view", {"filePath": "research/brief.md"}, "research/brief.md"),
        ("rg", {"pattern": "success_percent", "path": "research"}, "success_percent"),
        ("rg", {"query": "held_steps"}, "held_steps"),
        (
            "glob",
            {"pattern": "research/evaluations/**/*.json"},
            "research/evaluations/**/*.json",
        ),
        (
            "apply_patch",
            {"path": "reward.py", "content": "not for display"},
            "reward.py",
        ),
        ("read_powershell", {"shellId": "shell-1"}, "shell-1"),
        ("stop_powershell", {"shellId": "shell-1"}, "shell-1"),
        ("list_powershell", {}, ""),
    ],
)
def test_diagnostic_tool_starts_show_a_compact_target(capsys, tool, arguments, target):
    console = adapter.Console()

    console.tool(tool, arguments)

    suffix = f": {target}" if target else ""
    assert capsys.readouterr().out == f"  > {tool}{suffix}\n"
    assert console.tool_calls == 1


@pytest.mark.parametrize("argument_key", ["input", "patch", None])
def test_patch_starts_show_file_targets_without_patch_contents(capsys, argument_key):
    patch = (
        "*** Begin Patch\n*** Update File: reward.py\n@@\n"
        "+large payload that must remain hidden\n"
        "*** Add File: diagnostic.py\n+another payload\n*** End Patch"
    )
    arguments = {argument_key: patch} if argument_key else patch

    adapter.Console().tool("apply_patch", arguments)

    assert capsys.readouterr().out == "  > apply_patch: reward.py, diagnostic.py\n"


@pytest.mark.parametrize("arguments", [None, {"path": {"content": "hidden"}}])
def test_missing_or_structured_targets_do_not_dump_arguments(capsys, arguments):
    adapter.Console().tool("view", arguments)

    assert capsys.readouterr().out == "  > view\n"


@pytest.mark.parametrize(
    "tool,key", [("powershell", "command"), ("view", "path"), ("rg", "pattern")]
)
def test_long_tool_targets_stay_on_one_truncated_line(capsys, tool, key):
    adapter.Console().tool(tool, {key: "x" * 200 + "\nhidden tail"})

    assert capsys.readouterr().out == f"  > {tool}: {'x' * 107}...\n"


def test_a_shell_command_is_one_trimmed_line(capsys):
    console = adapter.Console()

    console.tool("powershell", {"command": "uv run ruff check  reward.py"})

    assert capsys.readouterr().out == "  > powershell: uv run ruff check reward.py\n"


def test_changed_files_are_reported_once_each(capsys):
    console = adapter.Console()

    console.file_changed("modified", "research/proposal.json")
    console.file_changed("modified", "research/proposal.json")
    console.file_changed("created", "research/postmortems.md")

    out = capsys.readouterr().out
    assert out == "  ~ research/proposal.json\n  + research/postmortems.md\n"
    assert len(console.changed_files) == 2


def test_a_refusal_is_reported_once_not_twice(capsys):
    console = adapter.Console()

    console.denied(adapter.GIT_DENIAL, "call-1")

    assert "call-1" in console.denied_calls
    assert console.denials == 1
    assert capsys.readouterr().out.count("Denied by the harness") == 1


def test_streamed_text_is_not_repeated_by_the_final_message(capsys):
    console = adapter.Console()

    console.delta("partial ")
    console.delta("answer")
    console.message("partial answer")

    assert capsys.readouterr().out == "partial answer"


def test_the_final_message_is_shown_when_nothing_streamed(capsys):
    console = adapter.Console()

    console.message("complete answer")

    assert capsys.readouterr().out == "complete answer\n"


def test_the_summary_reports_work_not_a_verdict(capsys):
    console = adapter.Console()
    console.prompt_tokens, console.output_tokens = 9000, 120
    console.nano_aiu = 356_660_000

    console.summary("fdb8162a-19eb-45ee-9835-9b22f70f4a80", ["research/proposal.json"])

    out = capsys.readouterr().out
    assert "1 file(s) changed" in out
    assert "0.36 AIU" in out
    for verdict in ("success", "complete", "valid", "failed"):
        assert verdict not in out.lower()


def test_cost_separates_cached_prompt_tokens_from_fresh_ones():
    console = adapter.Console()
    console.prompt_tokens = 400_000
    console.cache_read_tokens = 360_000
    console.output_tokens = 9_000
    console.nano_aiu = 2_500_000_000

    usage = console.usage()

    # A single token total would price a cached read like a fresh one.
    assert "2.50 AIU" in usage
    assert "prompt 400k (90% cached)" in usage


def test_cost_names_which_kind_of_token_dominated():
    console = adapter.Console()
    console.nano_aiu = 2_290_000_000
    console.nano_aiu_by_type = {
        "input": 60_000_000,
        "cache_write": 1_060_000_000,
        "cache_read": 600_000_000,
        "output": 600_000_000,
    }

    # Fresh and cached-write tokens are both new context, so they read as one cost.
    assert console.cost_split() == " (new 1.12 / read 0.60 / out 0.60)"


def test_the_cost_split_is_absent_until_the_runtime_prices_a_turn():
    assert adapter.Console().cost_split() == ""


def test_the_session_reports_the_work_that_drove_its_cost(capsys):
    console = adapter.Console()
    for _ in range(12):
        console.tool("view", {})

    console.summary("session-id", [], offloaded=(3, 174_080))

    out = capsys.readouterr().out
    # Each invocation counts once, regardless of its display detail.
    assert "tools 12" in out
    assert "offloaded 3 (170 KB)" in out


def test_an_unused_offload_is_not_reported_as_work(capsys):
    console = adapter.Console()

    console.summary("session-id", [])

    out = capsys.readouterr().out
    assert "tools 0" in out
    assert "offloaded" not in out


def test_offloaded_output_is_counted_only_for_this_session(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "LARGE_OUTPUT_DIR", tmp_path)
    (tmp_path / "earlier.txt").write_bytes(b"x" * 100)
    before = adapter.offload_snapshot()
    (tmp_path / "during.txt").write_bytes(b"y" * 2048)

    assert before == {"earlier.txt"}
    assert adapter.offloaded_since(before) == (1, 2048)


def test_a_missing_offload_directory_reports_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "LARGE_OUTPUT_DIR", tmp_path / "absent")

    assert adapter.offload_snapshot() == set()
    assert adapter.offloaded_since(set()) == (0, 0)


def test_usage_reports_cleanly_before_any_model_call():
    assert "0.00 AIU" in adapter.Console().usage()


def test_a_file_written_outside_the_edit_tools_is_still_reported(capsys):
    console = adapter.Console()

    # The runtime emitted no change event, because the shell wrote the file.
    console.summary("session-id", ["research/postmortems.md", "research/proposal.json"])

    out = capsys.readouterr().out
    assert "  ~ research/postmortems.md" in out
    assert "  ~ research/proposal.json" in out
    assert "2 file(s) changed" in out


def test_a_file_already_announced_is_not_listed_twice(capsys):
    console = adapter.Console()
    console.file_changed("modified", "research/proposal.json")

    console.summary("session-id", ["research/proposal.json"])

    assert capsys.readouterr().out.count("research/proposal.json") == 1


def test_the_changed_set_comes_from_the_worktree_not_the_runtime(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "worktree_status",
        lambda: {"research/proposal.json": "M", "new.py": "??"},
    )

    changed = adapter.changed_since({"research/proposal.json": "M", "gone.py": "??"})

    assert changed == ["gone.py", "new.py"]


# --- event routing ----------------------------------------------------------


def test_only_meaningful_events_reach_the_console(capsys):
    events = pytest.importorskip("copilot.session_events")
    console = adapter.Console()
    finished = asyncio.Event()
    on_event, _ = adapter.build_handlers(console, finished)

    def emit(data):
        on_event(SimpleNamespace(data=data))

    emit(
        events.AssistantReasoningDeltaData(
            delta_content="hidden thinking", reasoning_id="r1"
        )
    )
    emit(events.AssistantMessageDeltaData(delta_content="visible", message_id="m1"))
    emit(events.SessionWorkspaceFileChangedData(operation="modified", path="a.py"))
    emit(events.SessionIdleData())

    out = capsys.readouterr().out
    assert "hidden thinking" not in out
    assert "visible" in out
    assert "  ~ a.py" in out
    assert finished.is_set()


def test_a_refused_call_does_not_also_report_a_tool_failure(capsys):
    events = pytest.importorskip("copilot.session_events")
    console = adapter.Console()
    on_event, _ = adapter.build_handlers(console, asyncio.Event())

    console.denied(adapter.GIT_DENIAL, "call-1")
    capsys.readouterr()
    on_event(
        SimpleNamespace(
            data=events.ToolExecutionCompleteData(
                success=False, tool_call_id="call-1", error="rejected"
            )
        )
    )

    assert capsys.readouterr().out == ""


def test_a_genuine_tool_failure_is_still_reported(capsys):
    events = pytest.importorskip("copilot.session_events")
    console = adapter.Console()
    on_event, _ = adapter.build_handlers(console, asyncio.Event())

    on_event(
        SimpleNamespace(
            data=events.ToolExecutionCompleteData(
                success=False, tool_call_id="call-2", error="ruff exited 1"
            )
        )
    )

    assert "ruff exited 1" in capsys.readouterr().out


def test_a_silent_tool_failure_identifies_the_tool_and_target(capsys, monkeypatch):
    # Visibility can be reduced after the diagnostic campaign without losing errors.
    monkeypatch.setattr(adapter, "SILENT_TOOLS", frozenset({"view"}))
    events = pytest.importorskip("copilot.session_events")
    console = adapter.Console()
    on_event, _ = adapter.build_handlers(console, asyncio.Event())

    on_event(
        SimpleNamespace(
            data=events.ToolExecutionStartData(
                tool_call_id="call-3",
                tool_name="view",
                arguments={"path": "research/missing.json"},
            )
        )
    )
    assert capsys.readouterr().out == ""

    on_event(
        SimpleNamespace(
            data=events.ToolExecutionCompleteData(
                success=False, tool_call_id="call-3", error="Path does not exist"
            )
        )
    )

    output = capsys.readouterr().out
    assert "view" in output
    assert "research/missing.json" in output
    assert "Path does not exist" in output


def test_successful_tool_output_is_not_dumped_or_counted_again(capsys):
    events = pytest.importorskip("copilot.session_events")
    console = adapter.Console()
    on_event, _ = adapter.build_handlers(console, asyncio.Event())
    on_event(
        SimpleNamespace(
            data=events.ToolExecutionStartData(
                tool_call_id="read-1",
                tool_name="view",
                arguments={"path": "reward.py"},
            )
        )
    )
    capsys.readouterr()
    on_event(
        SimpleNamespace(
            data=events.ToolExecutionCompleteData(
                tool_call_id="read-1",
                success=True,
                result={"content": "large scientific output"},
            )
        )
    )

    assert capsys.readouterr().out == ""
    assert console.tool_calls == 1
    assert console.active_tools == {}


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
    assert "revert" in decision.feedback
    assert "call-3" in console.denied_calls
    capsys.readouterr()


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


def test_the_researcher_is_told_that_round_trips_resend_the_conversation():
    pytest.importorskip("copilot")
    args = adapter.parse_args(["p", "--session-id", "s"])

    content = adapter.session_options(args, adapter.Console(), asyncio.Event())[
        "system_message"
    ]["content"]

    assert "resends the whole conversation" in content
    normalized = " ".join(content.split())
    assert "one aggregated tool call when practical" in normalized
    assert "when the combined result remains compact" in normalized
    assert "Separate calls remain appropriate" in normalized
    assert (
        "Use targeted tests, linting, parsing or analysis while developing"
        in normalized
    )
    assert "when they resolve uncertainty introduced by the work" in normalized
    assert "do not perform a separate final validation pass solely" in normalized
    assert "the Runner owns final contract and execution validation" in normalized


def test_the_repository_policy_is_stated_to_the_model_as_well_as_enforced():
    pytest.importorskip("copilot")
    args = adapter.parse_args(["p", "--session-id", "s"])

    message = adapter.session_options(args, adapter.Console(), asyncio.Event())[
        "system_message"
    ]
    content = " ".join(message["content"].split())

    assert message["mode"] == "append"
    assert str(ROOT) in content
    assert "run_experiment.py" in content
    assert "research/brief.md and the campaign artifacts" in content
    assert "authoritative scientific context" in content
    assert "Do not use Git history as scientific evidence" in content
    assert "current code state or delta" in content
    assert "routine workspace-discovery step" in content


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
    for deliverable in (
        "proposal.json",
        "evaluation_request.json",
        "postmortems.md",
        "results.jsonl",
        "research_state.json",
    ):
        assert deliverable not in SOURCE


def test_the_copilot_runtime_loads_only_where_it_is_used():
    header = SOURCE.split("ROOT = Path", 1)[0]

    assert "import copilot" not in header
    assert "from copilot" not in header
    # Every other module keeps importing the adapter's policy without the SDK.
    assert "from copilot" in SOURCE
