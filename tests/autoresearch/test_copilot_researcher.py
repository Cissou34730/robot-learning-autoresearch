"""The Copilot adapter is a runtime boundary, not a scientific authority.

It decides what may run and what the console shows. It never decides whether a
bounded research phase succeeded, and none of these tests start a real session.
"""

import asyncio
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import runner.copilot.copilot_adapter as adapter

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "runner/copilot/copilot_adapter.py").read_text(encoding="utf-8")


# --- model identity ---------------------------------------------------------


def test_the_provider_prefix_is_stripped_from_the_model():
    assert adapter.normalize_model("github-copilot/gpt-5.6-luna") == "gpt-5.6-luna"
    assert adapter.normalize_model("gpt-5.6-luna") == "gpt-5.6-luna"
    assert adapter.normalize_model("opencode/other-model") == "opencode/other-model"
    assert (
        adapter.normalize_model("opencode-go/other-model") == "opencode-go/other-model"
    )


def provider_catalog():
    limits = {"context": 200000, "output": 32000}
    models = {
        "free-model": {
            "reasoning": True,
            "tool_call": True,
            "cost": {"input": 0, "output": 0},
            "limit": limits,
        },
        "luna": {
            "reasoning": True,
            "limit": limits,
            "provider": {
                "npm": "@ai-sdk/openai",
                "api": "https://opencode.ai/inference/openai/v1",
            },
        },
        "claude": {
            "reasoning": True,
            "limit": limits,
            "provider": {
                "npm": "@ai-sdk/anthropic",
                "api": "https://opencode.ai/inference/anthropic/v1",
            },
        },
        "plain-model": {"reasoning": False, "limit": limits},
    }
    return {
        provider: {
            "npm": "@ai-sdk/openai-compatible",
            "api": f"https://opencode.ai/inference/{prefix}openai/v1",
            "models": models,
        }
        for provider, prefix in (("opencode", ""), ("opencode-go", "go/"))
    }


def test_provider_selection_is_a_launch_option_with_per_provider_defaults():
    from runner.copilot.opencode_provider import DEFAULT_MODEL, OPENCODE_DEFAULT_MODEL

    assert DEFAULT_MODEL == "gpt-6-luna"
    assert adapter.parse_args(["p", "--session-id", "s"]).model == DEFAULT_MODEL
    for provider in ("opencode", "opencode-go"):
        args = adapter.parse_args(["p", "--session-id", "s", "--provider", provider])
        assert args.model == OPENCODE_DEFAULT_MODEL
        assert (
            adapter.parse_args(
                ["p", "--session-id", "s", "--model", f"{provider}/any-model"]
            ).model
            == f"{provider}/any-model"
        )
    with pytest.raises(SystemExit):
        adapter.parse_args(
            [
                "p",
                "--session-id",
                "s",
                "--provider",
                "opencode",
                "--model",
                "opencode-go/luna",
            ]
        )


@pytest.mark.parametrize(
    ("selection", "sdk_type", "wire_api", "endpoint"),
    [
        (
            "opencode/free-model",
            "openai",
            "completions",
            "https://opencode.ai/inference/openai/v1",
        ),
        (
            "opencode/luna",
            "openai",
            "responses",
            "https://opencode.ai/inference/openai/v1",
        ),
        (
            "opencode/claude",
            "anthropic",
            "completions",
            "https://opencode.ai/inference/anthropic/v1",
        ),
        (
            "opencode-go/plain-model",
            "openai",
            "completions",
            "https://opencode.ai/inference/go/openai/v1",
        ),
    ],
)
def test_provider_routes_use_catalog_protocol_and_limits(
    selection, sdk_type, wire_api, endpoint
):
    from runner.copilot.opencode_provider import resolve_model

    model = resolve_model(selection, provider_catalog())
    assert (model.sdk_type, model.wire_api, model.base_url) == (
        sdk_type,
        wire_api,
        endpoint,
    )
    options = model.session_options(
        "ses_0123456789abABCDEFGHIJKLMN", "local-key", "project"
    )
    expected_base = (
        endpoint.removesuffix("/v1") if sdk_type == "anthropic" else endpoint
    )
    assert options["providers"][0]["base_url"] == expected_base
    assert options["model"] == selection
    assert options["providers"][0]["api_key"] == "local-key"
    assert options["models"][0]["wire_model"] == selection.split("/", 1)[1]
    assert options["models"][0]["max_context_window_tokens"] == 200000
    assert options["models"][0]["max_output_tokens"] == 32000
    assert options["models"][0]["max_prompt_tokens"] == 168000


def test_provider_identity_is_restored_without_changing_model(tmp_path, monkeypatch):
    from runner.copilot import opencode_provider as provider

    monkeypatch.setattr(provider, "STATE_DIRECTORY", tmp_path)
    first = provider.session_identity("sdk-one", "opencode/free-model")
    assert (
        provider.session_identity("sdk-one", "opencode/free-model", resume=True)
        == first
    )
    assert provider.session_identity("sdk-two", "opencode/free-model") != first
    headers = provider.identity_headers(first, "project")
    assert headers["User-Agent"].startswith("opencode/latest/")
    assert headers["x-opencode-client"] == "cli"
    for name in (
        "x-opencode-session",
        "x-opencode-session-id",
        "x-session-affinity",
        "x-session-id",
    ):
        assert headers[name] == first
    assert headers["x-opencode-project"] == "project"
    with pytest.raises(ValueError, match="another model route"):
        provider.session_identity("sdk-one", "opencode/luna", resume=True)
    with pytest.raises(ValueError, match="persisted session identity"):
        provider.session_identity("missing", "opencode/free-model", resume=True)


def test_provider_credential_is_one_opencode_key(monkeypatch):
    from runner.copilot.opencode_provider import api_key

    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENCODE_API_KEY"):
        api_key()
    monkeypatch.setenv("OPENCODE_API_KEY", "local-key")
    assert api_key() == "local-key"


def test_provider_catalog_refresh_keeps_choices_and_reports_stale_cache(
    tmp_path, monkeypatch
):
    from io import StringIO
    from urllib.error import URLError

    from runner.copilot import opencode_provider as provider

    catalog = provider_catalog()
    monkeypatch.setattr(provider, "STATE_DIRECTORY", tmp_path)

    def fetch(_request, **_kwargs):
        return StringIO(json.dumps(catalog))

    monkeypatch.setattr(provider, "urlopen", fetch)
    assert provider.load_catalog() == catalog

    def unavailable(*_args, **_kwargs):
        raise URLError("offline")

    monkeypatch.setattr(provider, "urlopen", unavailable)
    assert provider.load_catalog() == catalog
    monkeypatch.setattr(provider, "CATALOG_REFRESH_SECONDS", -1)
    with pytest.warns(UserWarning, match="using the saved catalog"):
        assert provider.load_catalog() == catalog


def test_provider_native_read_is_preloaded_and_preserves_file_scope(
    tmp_path, monkeypatch
):
    from copilot import ToolInvocation

    from runner.copilot import path_policy
    from runner.copilot.opencode_provider import resolve_model

    monkeypatch.setattr(adapter, "ROOT", tmp_path)
    monkeypatch.setattr(path_policy, "ROOT", tmp_path)
    source = tmp_path / "robot_learning" / "training" / "fixture.txt"
    source.parent.mkdir(parents=True)
    source.write_text("first\nsecond\nthird\n", encoding="utf-8")
    args = adapter.parse_args(
        ["p", "--session-id", "s", "--model", "opencode/free-model"]
    )
    args.provider_model = resolve_model(args.model, provider_catalog())
    args.provider_identity = "ses_0123456789abABCDEFGHIJKLMN"
    args.provider_project = "project"
    monkeypatch.setenv("OPENCODE_API_KEY", "local-key")
    options = adapter.session_options(args, adapter.Console(), asyncio.Event())
    read = next(tool for tool in options["tools"] if tool.name == "read")
    assert read.defer == "never"
    assert "custom:read" in options["available_tools"].to_list()
    result = asyncio.run(
        read.handler(
            ToolInvocation(
                session_id="s", arguments={"path": str(source), "view_range": [2, 2]}
            )
        )
    )
    assert result.result_type == "success"
    assert result.text_result_for_llm == "second\n"
    denied = asyncio.run(
        read.handler(ToolInvocation(session_id="s", arguments={"path": "tests"}))
    )
    assert denied.result_type == "failure"
    denied = asyncio.run(
        read.handler(
            ToolInvocation(
                session_id="s",
                agent_id="unknown-child",
                arguments={"path": str(source)},
            )
        )
    )
    assert denied.result_type == "failure"


def test_provider_native_roles_stay_on_copilot_with_role_tools(monkeypatch):
    from runner.copilot.coding_contracts import CODING_TOOLS, REVIEW_TOOLS
    from runner.copilot.coding_session import ScientificCoding
    from runner.copilot.opencode_provider import DEFAULT_MODEL, resolve_model

    args = adapter.parse_args(
        ["p", "--session-id", "s", "--model", "opencode/plain-model"]
    )
    args.provider_model = resolve_model(args.model, provider_catalog())
    coding = ScientificCoding(None, args, adapter.Console())
    for agent in (coding.agent(), coding.reviewer_agent()):
        assert agent["model"] == DEFAULT_MODEL
        assert agent["reasoning_effort"] == "high"
    assert coding.agent()["tools"] == CODING_TOOLS
    assert coding.reviewer_agent()["tools"] == REVIEW_TOOLS
    main_read = {
        "sessionId": "s",
        "toolName": "read",
        "toolArgs": {"path": "robot_learning/training/environment.py"},
    }
    assert coding.pre_tool_use(main_read, {"session_id": "s"}) is None
    coding.busy = True
    coding.active_handle = "authorized-child"
    coding.binding = {
        "allowed_paths": [],
        "read_paths": ["robot_learning/training/environment.py"],
    }
    allowed = {
        "sessionId": "authorized-child",
        "toolName": "view",
        "toolArgs": {"path": "robot_learning/training/environment.py"},
    }
    assert coding.pre_tool_use(allowed, {"session_id": "s"}) is None
    denied = {**allowed, "toolArgs": {"path": "AGENTS.md"}}
    assert (
        coding.pre_tool_use(denied, {"session_id": "s"})["permissionDecision"] == "deny"
    )
    coding.binding["allowed_paths"] = coding.binding["read_paths"]
    for tool in (
        "read",
        "create",
        "edit",
        "scientific_coding",
        "submit_operation",
        "artifact_evidence_query",
        "training_log_query",
        "powershell",
        "rg",
        "glob",
    ):
        denied = {**allowed, "toolName": tool}
        assert (
            coding.pre_tool_use(denied, {"session_id": "s"})["permissionDecision"]
            == "deny"
        )


def test_provider_native_json_editors_keep_main_and_preliminary_boundaries():
    from runner.copilot.coding_session import scoped_tool_hook

    for tool in ("create", "edit"):
        request = {
            "toolName": tool,
            "toolArgs": {"path": "pi_workspace/scientific_model.md"},
        }
        main = scoped_tool_hook(json_editors=True)
        assert main(request, {})["permissionDecision"] == "deny"
        preliminary = scoped_tool_hook(preliminary=True, json_editors=True)
        assert preliminary(request, {}) is None
        request["toolArgs"] = {"path": "robot_learning/training/environment.py"}
        assert preliminary(request, {})["permissionDecision"] == "deny"


def test_provider_usage_preserves_units_and_does_not_invent_external_aiu(
    tmp_path, monkeypatch
):
    from runner.copilot import copilot_console
    from runner.copilot.opencode_provider import resolve_model

    monkeypatch.setattr(copilot_console, "ROOT", tmp_path)
    args = adapter.parse_args(
        [
            "p",
            "--session-id",
            "s",
            "--model",
            "opencode/free-model",
            "--campaign-id",
            "00000000-0000-0000-0000-000000000001",
        ]
    )
    args.provider_model = resolve_model(args.model, provider_catalog())
    args.effective_reasoning = "high"
    console = adapter.Console()
    console.provider = "opencode"
    console.reported_usage = {"aiu", "input_tokens"}
    console.prompt_tokens = 100
    copilot_console.record_usage(args, console, 1.0, 0)
    path = next((tmp_path / "reports" / "session_usage").glob("*.jsonl"))
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["aiu"] is None
    assert row["provider"] == "opencode"
    assert row["model"] == args.model
    assert row["input_tokens"] == 100
    assert row["provider_token_prices_per_million"] == {"input": 0, "output": 0}
    assert "AIU" not in console.usage()


def test_provider_review_identity_requires_the_copilot_reviewer():
    from runner.copilot.coding_session import ScientificCoding
    from runner.copilot.opencode_provider import DEFAULT_MODEL, resolve_model

    args = adapter.parse_args(
        ["p", "--session-id", "s", "--model", "opencode/free-model"]
    )
    args.provider_model = resolve_model(args.model, provider_catalog())
    coding = ScientificCoding(None, args, adapter.Console())
    coding.child_models = {DEFAULT_MODEL}
    coding.child_reasoning = {"high"}
    coding.verify_reviewer_identity()
    for models in (
        {"opencode/free-model"},
        {"free-model"},
        {DEFAULT_MODEL, "opencode/free-model"},
    ):
        coding.child_models = models
        with pytest.raises(ValueError, match="was not verified"):
            coding.verify_reviewer_identity()


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
        "git show HEAD:robot_learning/training/reward.py",
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
        "uv run python runner/run_experiment.py",
        "uv run python -m runner.run_experiment --check-operation",
        "uv run python runner/run_experiment.py --execute-pending",
        "uv run python runner/run_experiment.py --run-official-assessment",
        "uv run python runner/migrate_policy_runtime.py --help",
        "uv run python -m runner.migrate_policy_runtime --help",
        "uv run python runner/reset_campaign.py --mode fresh",
        "uv run python -m runner.reset_campaign --mode fresh",
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
    assert adapter.command_denial(command, preliminary=True) == adapter.EXECUTION_DENIAL


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


def test_targeted_test_runs_are_refused():
    existing = "tests/autoresearch/test_copilot_researcher.py"
    commands = (
        f"uv run pytest {existing}",
        f"uv run pytest {existing}::test_x",
        f"uv run pytest --maxfail 1 {existing}",
        f"uv run pytest -q {existing}",
        f"uv run pytest --strict {existing}",
        f"uv run pytest --maxfail=1 {existing}",
    )
    for command in commands:
        assert adapter.command_denial(command) == adapter.SUITE_DENIAL


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
        "uv run python analysis.py -w 5",
        "uv --offline run python analysis.py",
        "uv -n run python analysis.py",
        "uv --project . run python analysis.py",
        "uv --project=. run ruff check robot_learning/training/reward.py",
        r"C:\Tools\uv.exe --offline run python analysis.py",
    ):
        assert adapter.command_denial(command) is None


def test_ordinary_research_commands_are_not_obstructed():
    for command in (
        "uv run ruff check robot_learning/training/reward.py",
        "uv run python -c \"import json; print('ok')\"",
        "Get-Content campaigns/brief.md",
    ):
        assert adapter.command_denial(command) is None


@pytest.mark.parametrize(
    ("command", "expected", "preliminary"),
    [
        ("Get-Content runner/run_experiment.py", adapter.FILE_READ_DENIAL, False),
        (
            "rg request_official_assessment runner/protocol.py",
            adapter.FILE_READ_DENIAL,
            False,
        ),
        (
            "Select-String -Path contracts/program.md -Pattern official_assessment",
            None,
            False,
        ),
        ("python -c \"print(operation['campaign_conclusion'])\"", None, False),
        ("cat robot_learning/train.py", None, False),
        (r"Get-Content -LiteralPath robot_learning\evaluate.py", None, False),
        ("rg policy robot_learning/play.py", None, False),
        ("cat robot_learning/lab/run_experiment.py", None, False),
        (
            r"Get-Content benchmark\adapters\final_benchmark.py",
            adapter.FILE_READ_DENIAL,
            False,
        ),
        (
            r"Get-Content benchmark\adapters\final_benchmark.py",
            adapter.FILE_READ_DENIAL,
            True,
        ),
        (r"rg success benchmark\final_benchmark.py", adapter.FILE_READ_DENIAL, True),
        (r"Get-Content runner\run_experiment.py", adapter.FILE_READ_DENIAL, True),
    ],
)
def test_reader_targets_distinguish_reserved_files_from_scientific_sources(
    command, expected, preliminary
):
    assert adapter.command_denial(command, preliminary=preliminary) == expected


def test_the_execution_target_is_resolved_through_the_launcher_prefix():
    resolve = adapter.execution_target

    assert resolve(["uv", "run", "python", "runner/run_experiment.py"]) == (
        "runner/run_experiment.py"
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


@pytest.mark.parametrize(
    ("command", "preliminary", "expected"),
    [
        ("git push", False, adapter.GIT_DENIAL),
        (
            r"Get-Content benchmark\adapters\final_benchmark.py",
            False,
            adapter.FILE_READ_DENIAL,
        ),
        (
            r"Get-Content benchmark\adapters\final_benchmark.py",
            True,
            adapter.FILE_READ_DENIAL,
        ),
        (r"Get-Content runner\protocol.py", True, adapter.FILE_READ_DENIAL),
    ],
)
def test_shell_permissions_respect_the_command_and_session_phase(
    command, preliminary, expected, capsys
):
    pytest.importorskip("copilot")
    from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject
    from copilot.session_events import PermissionRequestShell

    console = adapter.Console()
    _, on_permission = adapter.build_handlers(
        console, asyncio.Event(), preliminary=preliminary
    )
    request = PermissionRequestShell(
        can_offer_session_approval=False,
        commands=[],
        full_command_text=command,
        has_write_file_redirection=False,
        intention="publish",
        possible_paths=[],
        possible_urls=[],
        tool_call_id="call-3",
    )

    decision = on_permission(request, {})

    if expected is None:
        assert isinstance(decision, PermissionDecisionApproveOnce)
        assert "call-3" not in console.denied_calls
    else:
        assert isinstance(decision, PermissionDecisionReject)
        assert decision.feedback == expected
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
        file_name="runner/run_experiment.py",
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
        adapter.file_edit_denial("pi_workspace/scientific_model.md", preliminary=True)
        is None
    )
    assert (
        adapter.file_edit_denial(
            "pi_workspace/operation_request.json", preliminary=True
        )
        == adapter.FILE_EDIT_DENIAL
    )
    assert adapter.file_edit_denial("pi_workspace/operation_request.json") is None
    assert (
        adapter.file_edit_denial(
            "benchmark/adapters/final_benchmark.py", preliminary=True
        )
        == adapter.FILE_EDIT_DENIAL
    )


@pytest.mark.parametrize(
    ("path", "preliminary_readable"),
    [
        ("runner/run_experiment.py", False),
        ("runner/protocol.py", False),
        ("runner/copilot/copilot_adapter.py", False),
        ("benchmark/adapters/final_benchmark.py", False),
        (str(ROOT / "benchmark" / "final_benchmark.py"), False),
        ("docs/harness-experiment-log.md", False),
        ("tests/autoresearch/test_copilot_researcher.py", False),
        (r"DOCS\IMPLEMENTATION_PLAN_CAMPAIGN_CORRECTNESS.md", False),
        (
            str(
                ROOT
                / "docs"
                / "research-overview"
                / "robot-learning-overview-20261002.html"
            ),
            False,
        ),
    ],
)
@pytest.mark.parametrize("preliminary", [False, True])
def test_reserved_read_permissions_respect_session_phase(
    path, preliminary_readable, preliminary, capsys
):
    pytest.importorskip("copilot")
    from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject
    from copilot.session_events import PermissionRequestRead

    console = adapter.Console()
    _, on_permission = adapter.build_handlers(
        console, asyncio.Event(), preliminary=preliminary
    )
    request = PermissionRequestRead(
        intention="inspect a file", path=path, tool_call_id="read-denied"
    )
    decision = on_permission(request, {})
    if preliminary and preliminary_readable:
        assert isinstance(decision, PermissionDecisionApproveOnce)
        assert "read-denied" not in console.denied_calls
    else:
        assert isinstance(decision, PermissionDecisionReject)
        assert decision.feedback == adapter.FILE_READ_DENIAL
        assert "read-denied" in console.denied_calls
    capsys.readouterr()


@pytest.mark.parametrize(
    "path",
    [
        "AGENTS.md",
        "contracts/program.md",
        "contracts/instruments.md",
        "pi_workspace/scientific_model.md",
        "campaigns/brief.md",
        "robot_learning/train.py",
        "robot_learning/evaluate.py",
        "robot_learning/play.py",
        str(ROOT / "robot_learning" / "train.py"),
        "robot_learning/lab/diagnostic.py",
        "robot_learning/lab/run_experiment.py",
        "robot_learning/scenario/environment.py",
        "contracts/robots/two_joint_arm.xml",
    ],
)
def test_scientific_corpus_remains_readable(path):
    pytest.importorskip("copilot")
    from copilot.rpc import PermissionDecisionApproveOnce
    from copilot.session_events import PermissionRequestRead

    _, on_permission = adapter.build_handlers(adapter.Console(), asyncio.Event())
    request = PermissionRequestRead(intention="scientific inspection", path=path)
    assert isinstance(on_permission(request, {}), PermissionDecisionApproveOnce)


@pytest.mark.parametrize(
    "command",
    [
        r"Get-Content docs\harness-experiment-log.md",
        r"Get-Content -LiteralPath='docs\harness-experiment-log.md'",
        r"cat runner\protocol.py",
        r"rg -n route docs\harness-experiment-log.md",
        r"Select-String -Path docs\harness-experiment-log.md -Pattern route",
        r"Get-Content tests\autoresearch\test_copilot_researcher.py",
        r"rg -n adapter tests\autoresearch",
    ],
)
@pytest.mark.parametrize("preliminary", [False, True])
def test_explicit_shell_reads_use_the_reserved_path_policy(command, preliminary):
    assert (
        adapter.command_denial(command, preliminary=preliminary)
        == adapter.FILE_READ_DENIAL
    )


def test_searching_scientific_code_for_a_reserved_name_is_not_a_reserved_read():
    assert adapter.command_denial(r"rg run_research.ps1 robot_learning\lab") is None


# --- the session profile ----------------------------------------------------


@pytest.mark.parametrize("preliminary", [False, True])
def test_the_session_runs_a_trimmed_tool_profile_inside_the_worktree(preliminary):
    pytest.importorskip("copilot")
    arguments = ["p", "--session-id", "s", "--reasoning", "medium"]
    if preliminary:
        arguments.append("--preliminary")
    args = adapter.parse_args(arguments)

    options = adapter.session_options(args, adapter.Console(), asyncio.Event())

    assert options["model"] == "gpt-6-luna"
    assert options["reasoning_effort"] == "medium"
    assert options["working_directory"] == str(ROOT)
    assert options["streaming"] is True
    assert options["enable_file_change_tracking"] is True
    # Everything a robotics experiment cannot use stays out of the context.
    assert options["enable_skills"] is False
    assert options["enable_session_store"] is False
    assert options["enable_mcp_apps"] is False
    assert "system_message" not in options
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

    async def start(self):
        pass

    async def stop(self):
        pass

    async def force_stop(self):
        pass

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


@pytest.mark.parametrize(
    ("completion", "stalled_step", "failure", "expected_code"),
    [
        ("finished", None, None, adapter.EXIT_OK),
        ("finished", "disconnect", "timeout", adapter.EXIT_OK),
        ("finished", "stop", "timeout", adapter.EXIT_OK),
        ("finished", "stop", "error", adapter.EXIT_OK),
        ("finished", "force_stop", "timeout", adapter.EXIT_RUNTIME_FAILURE),
        ("finished", "force_stop", "error", adapter.EXIT_RUNTIME_FAILURE),
        ("timeout", "abort", "timeout", adapter.EXIT_TIMEOUT),
        ("interrupted", "abort", "timeout", adapter.EXIT_INTERRUPTED),
        ("session_error", "stop", "timeout", adapter.EXIT_SESSION_ERROR),
    ],
)
def test_shutdown_is_bounded_without_repeating_or_losing_pi_work(
    monkeypatch, tmp_path, capsys, completion, stalled_step, failure, expected_code
):
    client = FakeClient()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.force_stop = AsyncMock()
    session = SimpleNamespace(
        session_id="phase-1",
        send=AsyncMock(),
        abort=AsyncMock(),
        disconnect=AsyncMock(),
    )
    client.create_session = AsyncMock(return_value=session)

    async def stall():
        await asyncio.Event().wait()

    if stalled_step == "force_stop":
        client.stop.side_effect = stall
    if stalled_step:
        target = session if stalled_step in {"abort", "disconnect"} else client
        getattr(target, stalled_step).side_effect = (
            stall if failure == "timeout" else RuntimeError("cleanup failed")
        )

    def options(args, console, finished):
        if completion == "session_error":
            console.session_error = True
        if completion not in {"timeout", "interrupted"}:
            session.send.side_effect = lambda prompt: finished.set()
        return {}

    async def stop_request():
        if completion != "interrupted":
            await asyncio.Event().wait()

    install_fake_sdk(monkeypatch, client)
    monkeypatch.setattr(adapter, "ROOT", tmp_path)
    monkeypatch.setattr(adapter, "session_options", options)
    monkeypatch.setattr(adapter, "stop_requested", lambda: False)
    monkeypatch.setattr(adapter, "wait_for_stop_request", stop_request)
    monkeypatch.setattr(adapter, "worktree_status", dict)
    monkeypatch.setattr(adapter, "offload_snapshot", set)
    monkeypatch.setattr(adapter, "offloaded_since", lambda before: (0, 0))
    monkeypatch.setattr(adapter, "SHUTDOWN_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(adapter, "FORCE_STOP_TIMEOUT_SECONDS", 0.01)
    run = asyncio.run
    monkeypatch.setattr(
        adapter.asyncio, "run", lambda coro: run(asyncio.wait_for(coro, timeout=1))
    )
    campaign_id = "11111111-1111-1111-1111-111111111111"
    research = tmp_path / "campaigns"
    research.mkdir()
    preserved = {
        research / "operation_request.json": b'{"saved":"request"}\n',
        research / "research_state.json": b'{"saved":"state"}\n',
    }
    for path, content in preserved.items():
        path.write_bytes(content)

    code = adapter.main(
        [
            "p",
            "--session-id",
            session.session_id,
            "--campaign-id",
            campaign_id,
            "--timeout",
            "0.01",
        ]
    )

    assert code == expected_code
    client.start.assert_awaited_once()
    client.create_session.assert_awaited_once_with(session_id=session.session_id)
    session.send.assert_awaited_once_with("p")
    assert client.resumed == []
    assert session.abort.await_count == int(completion in {"timeout", "interrupted"})
    assert client.force_stop.await_count == int(stalled_step is not None)
    if stalled_step is None:
        session.disconnect.assert_awaited_once()
        client.stop.assert_awaited_once()
    for path, content in preserved.items():
        assert path.read_bytes() == content
    rows = (
        (tmp_path / "reports" / "session_usage" / f"{campaign_id}.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(rows) == 1
    usage = json.loads(rows[0])
    assert usage["exit_code"] == expected_code
    assert usage["duration_seconds"] < 0.5
    output = capsys.readouterr()
    if stalled_step:
        assert "forcing the adapter-owned runtime" in output.out
    if stalled_step == "force_stop":
        assert "Copilot runtime failure:" in output.err
        assert "force-stopped" not in output.out


@pytest.mark.parametrize("cancellation_step", ["send", "disconnect"])
def test_task_cancellation_still_cleans_up_owned_runtime(
    monkeypatch, cancellation_step
):
    client = FakeClient()
    client.force_stop = AsyncMock()

    async def stall():
        await asyncio.Event().wait()

    session = SimpleNamespace(
        session_id="phase-1",
        send=AsyncMock(),
        abort=AsyncMock(side_effect=stall),
        disconnect=AsyncMock(),
    )
    getattr(session, cancellation_step).side_effect = asyncio.CancelledError()

    def options(args, console, finished):
        if cancellation_step == "disconnect":
            session.send.side_effect = lambda prompt: finished.set()
        return {}

    install_fake_sdk(monkeypatch, client)
    monkeypatch.setattr(adapter, "open_session", AsyncMock(return_value=session))
    monkeypatch.setattr(adapter, "session_options", options)
    monkeypatch.setattr(adapter, "stop_requested", lambda: False)
    monkeypatch.setattr(adapter, "worktree_status", dict)
    monkeypatch.setattr(adapter, "offload_snapshot", set)
    monkeypatch.setattr(adapter, "SHUTDOWN_TIMEOUT_SECONDS", 0.01)
    args = adapter.parse_args(["p", "--session-id", session.session_id])

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(asyncio.wait_for(adapter.run(args), timeout=1))

    assert session.abort.await_count == int(cancellation_step == "send")
    client.force_stop.assert_awaited_once()


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


@pytest.mark.parametrize(
    "operation",
    [
        {
            "training": {
                "initialization": "fresh",
                "seed": True,
                "steps": 1,
                "description": "Train",
                "rationale": "Measure learning",
            }
        },
        {"measurement": {"description": "Measure"}},
        {
            "measurement": {
                "description": "Measure",
                "rationale": "Inspect a quantity",
                "measurements": [
                    {
                        "instrument": "python_module",
                        "module": "robot_learning.lab.measure",
                        "args": ["--output", "{artifact}"],
                        "artifact": "output.json",
                    }
                ],
            }
        },
    ],
)
def test_sdk_operation_handler_rejects_invalid_bodies_before_controller(operation):
    from runner.copilot.copilot_console import Console
    from runner.copilot.operation_submission import OperationSubmission

    channel = SimpleNamespace(send=AsyncMock(), receive=AsyncMock())
    binding = {
        "session_id": "inert",
        "campaign_id": "campaign",
        "invocation_id": "invocation",
        "state": {"operation_event_count": 0},
    }
    tool = OperationSubmission(channel, binding, Console(), None).tool()
    invocation = SimpleNamespace(
        arguments={"request": operation},
        session_id="inert",
        agent_id=None,
        tool_call_id="call-1",
    )
    result = asyncio.run(tool.handler(invocation))

    assert result.result_type == "failure"
    channel.send.assert_not_awaited()
    channel.receive.assert_not_awaited()


def test_sdk_operation_handler_preserves_literal_arguments_and_failed_operation_metadata():
    from runner.copilot.copilot_console import Console
    from runner.copilot.operation_submission import OperationSubmission

    entry = {
        "instrument": "python_module",
        "module": "robot_learning.lab.measure",
        "args": [
            "--output",
            "campaigns/evaluations/campaign/output.json",
            "--label",
            "literal value with spaces",
        ],
        "artifact": "campaigns/evaluations/campaign/output.json",
    }
    operation = {
        "measurement": {
            "description": "Inspect a quantity",
            "rationale": "Inform a decision",
            "measurements": [entry],
        }
    }
    binding = {
        "session_id": "inert",
        "campaign_id": "campaign",
        "invocation_id": "invocation",
        "state": {"operation_event_count": 0},
    }
    channel = SimpleNamespace(
        send=AsyncMock(),
        receive=AsyncMock(
            return_value={
                "type": "operation_result",
                "invocation_id": "invocation",
                "call_id": "call-1",
                "status": "implementation_error",
                "error": "Execution failed",
                "accepted_measurement": entry,
                "state": binding["state"],
            }
        ),
    )
    operations = OperationSubmission(channel, binding, Console(), None)
    invocation = SimpleNamespace(
        arguments={"request": operation},
        session_id="inert",
        agent_id=None,
        tool_call_id="call-1",
    )
    tool = operations.tool()
    result = asyncio.run(tool.handler(invocation))
    assert result.result_type == "success"
    response = json.loads(result.text_result_for_llm)
    assert response["accepted_measurement"] == entry
    assert response["error"] == "Execution failed"
    assert operations.closed is False
    assert channel.send.call_args.args[0]["request"] == operation
    asyncio.run(tool.handler(invocation))
    assert channel.send.await_count == 1


def test_coding_context_and_source_only_handoff_survive_same_child_correction(
    monkeypatch,
):
    from runner.copilot import coding_session
    from runner.copilot.coding_contracts import (
        CodingReport,
        ReviewReport,
        ScientificCodingParams,
    )
    from runner.copilot.copilot_console import Console

    args = adapter.parse_args(
        [
            "p",
            "--session-id",
            "inert",
            "--campaign-id",
            "11111111-1111-1111-1111-111111111111",
        ]
    )
    coding = coding_session.ScientificCoding(None, args, Console())
    coding.session = SimpleNamespace(
        rpc=SimpleNamespace(
            tools=SimpleNamespace(initialize_and_validate=AsyncMock()),
            tasks=SimpleNamespace(
                list=AsyncMock(
                    return_value=SimpleNamespace(
                        tasks=[
                            SimpleNamespace(
                                id="coder", status=SimpleNamespace(value="idle")
                            ),
                            SimpleNamespace(
                                id="reviewer", status=SimpleNamespace(value="idle")
                            ),
                        ]
                    )
                )
            ),
        )
    )
    monkeypatch.setattr(coding_session, "coding_snapshot", lambda _paths: {})
    monkeypatch.setattr(coding_session, "coding_changes", lambda _before: ([], ""))
    captured = []

    async def child(*, agent, prompt, binding, result, handle):
        payload = json.loads(prompt)
        captured.append((agent, payload, binding, handle))
        if agent == "scientific-coder":
            coding.active_handle = "coder"
            coding.bindings["coder"] = binding
            if handle is None:
                coding.original_requests["coder"] = payload
            report = CodingReport(
                summary="Requested change authored", unchecked_scope=["Not executed"]
            )
        else:
            coding.active_handle = "reviewer"
            coding.review_handles.add("reviewer")
            report = ReviewReport(
                summary="Implementation reviewed",
                decision="ready_for_pi",
                decision_reason="No confirmed defects",
                findings=[],
                requested_changes=[],
                unchecked_scope=["Not executed"],
            )
            result.update(report.model_dump())
        result.update(status="completed", session_handle=coding.active_handle)
        return report

    monkeypatch.setattr(coding, "run_child", child)
    invocation = SimpleNamespace(
        session_id="inert", agent_id=None, tool_call_id="call-1"
    )
    initial = json.loads(
        asyncio.run(
            coding.invoke(
                ScientificCodingParams(
                    intent="Author the requested behavior",
                    allowed_paths=["robot_learning/training/environment.py"],
                    source_context="Preserve the caller interface.",
                ),
                invocation,
            )
        )
    )
    assert initial["status"] == "completed"
    context = captured[0][1]["task_context"]
    assert context["scenario"] == (ROOT / "contracts" / "scenario.md").read_text(
        encoding="utf-8"
    )
    assert captured[1][1]["request"]["task_context"] == context
    assert captured[0][1]["source_context"] == "Preserve the caller interface."
    assert captured[0][2]["read_paths"] == ["robot_learning/training/environment.py"]
    assert captured[1][2]["allowed_paths"] == []
    assert captured[1][2]["read_paths"] == captured[0][2]["read_paths"]
    assert {
        "proposed_check",
        "proposed_compatibility_check",
        "verification_module",
    }.isdisjoint(initial)

    monkeypatch.setattr(
        coding,
        "task_context",
        lambda: pytest.fail("Correction lost its stored context"),
    )
    correction = json.loads(
        asyncio.run(
            coding.invoke(
                ScientificCodingParams(
                    intent="Correct the same change",
                    session_handle="coder",
                ),
                invocation,
            )
        )
    )
    assert correction["status"] == "completed"
    assert captured[2][3] == "coder"
    assert captured[3][3] == "reviewer"
    assert captured[2][1]["task_context"] == context
    assert captured[3][1]["task_context"] == context
    assert captured[3][1]["mode"] == "correction"
    assert "request" not in captured[3][1]
    assert captured[2][2] == captured[0][2]
