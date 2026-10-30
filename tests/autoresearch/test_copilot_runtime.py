"""Copilot runtime boundary: permissions, OpenCode routing, native children, usage."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from runner import paths
from runner.copilot import coding_session
from runner.copilot import copilot_adapter as adapter
from runner.copilot import opencode_provider as provider
from runner.copilot import operation_submission as submission_module
from runner.copilot.coding_contracts import (
    CODING_TOOLS,
    REVIEW_TOOLS,
    ScientificCodingParams,
)
from runner.copilot.coding_session import ScientificCoding
from runner.copilot.operation_submission import OperationSubmission
from runner.copilot.pi_tools import scoped_search
from runner.copilot.reporting import SessionReporter as Console
from runner.copilot.reporting import tool_detail
from runner.copilot.system_prompt import (
    ANALYST_EXPLORATION,
    REFERENCE_READ_DENIAL,
    reference_paths,
    system_message,
    system_prompt,
)
from runner.copilot.tool_policy import scoped_tool_hook, tool_denial

SOURCE = "robot_learning/training/environment.py"
LIMITS = {"context": 200000, "output": 32000}


@pytest.mark.parametrize("stop_at", ["before_connect", "during_connect", "never"])
def test_controller_runtime_startup_stop_does_not_report_connection_failure(
    monkeypatch, stop_at
):
    stopped = [stop_at == "before_connect"]
    monkeypatch.setattr(adapter, "stop_requested", lambda: stopped[0])

    async def connect(*args, **kwargs):
        assert stop_at != "before_connect"
        stopped[0] = stop_at == "during_connect"
        raise ConnectionRefusedError("listener closed")

    monkeypatch.setattr(adapter.asyncio, "open_connection", connect)
    if stop_at == "never":
        with pytest.raises(ConnectionRefusedError):
            asyncio.run(adapter.serve(SimpleNamespace(controller_port=12345)))
    else:
        assert (
            asyncio.run(adapter.serve(SimpleNamespace(controller_port=12345)))
            == adapter.EXIT_INTERRUPTED
        )


def catalog():
    openai = "https://opencode.ai/inference/openai/v1"
    return {
        "opencode": {
            "npm": "@ai-sdk/openai-compatible",
            "api": openai,
            "models": {
                "free-model": {
                    "reasoning": True,
                    "cost": {"input": 0, "output": 0},
                    "limit": LIMITS,
                },
                "luna": {
                    "limit": LIMITS,
                    "provider": {"npm": "@ai-sdk/openai", "api": openai},
                },
                "claude": {
                    "limit": LIMITS,
                    "provider": {
                        "npm": "@ai-sdk/anthropic",
                        "api": "https://opencode.ai/inference/anthropic/v1",
                    },
                },
                "gemini": {"limit": LIMITS, "provider": {"npm": "@ai-sdk/google"}},
                "old": {"limit": LIMITS, "status": "deprecated"},
            },
        },
        "opencode-go": {
            "npm": "@ai-sdk/openai-compatible",
            "api": "https://opencode.ai/inference/go/openai/v1",
            "models": {"plain-model": {"limit": LIMITS}},
        },
    }


def opencode_args(model="opencode/free-model", *extra):
    args = adapter.parse_args(["p", "--session-id", "s", "--model", model, *extra])
    args.provider_model = provider.resolve_model(args.model, catalog())
    args.provider_identity = provider.create_session_id()
    args.provider_project = "project"
    return args


# --- model selection and OpenCode routing -----------------------------------


def test_default_models_per_provider():
    assert adapter.parse_args(["p", "--session-id", "s"]).model == "gpt-6-luna"
    for name in ("opencode", "opencode-go"):
        args = adapter.parse_args(["p", "--session-id", "s", "--provider", name])
        assert args.model == "opencode/deepseek-v4.1-flash-free"
    with pytest.raises(SystemExit):
        adapter.parse_args(
            [
                "p",
                "--session-id",
                "s",
                "--provider",
                "opencode",
                "--model",
                "opencode-go/x",
            ]
        )


@pytest.mark.parametrize(
    ("selection", "sdk_type", "wire_api", "base_url"),
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
def test_catalog_selects_protocol_and_endpoint(selection, sdk_type, wire_api, base_url):
    model = provider.resolve_model(selection, catalog())
    assert (model.sdk_type, model.wire_api, model.base_url) == (
        sdk_type,
        wire_api,
        base_url,
    )


@pytest.mark.parametrize(
    "selection", ["opencode/gemini", "opencode/old", "opencode/absent"]
)
def test_unsupported_models_are_refused_not_substituted(selection):
    with pytest.raises((TypeError, ValueError)):
        provider.resolve_model(selection, catalog())


def test_session_identity_persists_and_headers_match_the_opencode_client(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(provider, "STATE_DIRECTORY", tmp_path)
    identity = provider.session_identity("sdk", "opencode/free-model")
    assert (
        provider.session_identity("sdk", "opencode/free-model", resume=True) == identity
    )
    with pytest.raises(ValueError):
        provider.session_identity("unknown", "opencode/free-model", resume=True)
    headers = provider.identity_headers(identity, "project")
    assert headers["User-Agent"].startswith("opencode/latest/")
    assert headers["x-opencode-client"] == "cli"
    assert headers["x-opencode-project"] == "project"
    for name in (
        "x-opencode-session",
        "x-opencode-session-id",
        "x-session-affinity",
        "x-session-id",
    ):
        assert headers[name] == identity


def test_one_opencode_key_serves_zen_and_go(monkeypatch):
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENCODE_API_KEY"):
        provider.api_key()
    monkeypatch.setenv("OPENCODE_API_KEY", "key")
    assert provider.api_key() == "key"


# --- session profile ---------------------------------------------------------


def test_opencode_sessions_always_send_read_and_identity(monkeypatch):
    pytest.importorskip("copilot")
    monkeypatch.setenv("OPENCODE_API_KEY", "key")
    args = opencode_args("opencode/free-model", "--preliminary")
    options = adapter.session_options(args, Console(), asyncio.Event())
    read = next(tool for tool in options["tools"] if tool.name == "read")
    assert read.defer == "never"
    assert "custom:read" in options["available_tools"].to_list()
    route = options["providers"][0]
    assert route["api_key"] == "key"
    assert route["headers"]["x-opencode-session"] == args.provider_identity
    assert options["models"][0]["wire_model"] == "free-model"


def test_copilot_sessions_have_no_read_alias():
    pytest.importorskip("copilot")
    args = adapter.parse_args(["p", "--session-id", "s", "--preliminary"])
    options = adapter.session_options(args, Console(), asyncio.Event())
    assert all(tool.name != "read" for tool in options["tools"])
    assert "providers" not in options


# --- tool permissions ----------------------------------------------------------


def test_main_pi_cannot_write_or_run_shell_or_read_reserved_files():
    for name, arguments in (
        ("apply_patch", {"input": f"*** Update File: {SOURCE}\n"}),
        ("create", {"path": SOURCE}),
        ("powershell", {"command": "dir"}),
        ("view", {"path": "tests/autoresearch"}),
        ("view", {"path": "runner/run_experiment.py"}),
    ):
        assert tool_denial(name, arguments), name
    assert tool_denial("view", {"path": SOURCE}) is None


def test_preliminary_editors_reach_only_the_scientific_model():
    model = {"path": "pi_workspace/scientific_model.md"}
    assert tool_denial("powershell", {"command": "dir"}, preliminary=True)
    assert tool_denial("create", model, preliminary=True, json_editors=True) is None
    assert tool_denial("create", {"path": SOURCE}, preliminary=True, json_editors=True)
    assert tool_denial("create", model, json_editors=True)


def test_reference_files_are_refused_to_the_pi_and_analyst_not_the_coder():
    model = {"path": "pi_workspace/scientific_model.md"}
    program = {"path": "contracts/program.md"}
    assert tool_denial("view", program) == REFERENCE_READ_DENIAL
    assert tool_denial("view", model) is None
    assert tool_denial("view", program, preliminary=True) is None
    assert (
        tool_denial("view", {"path": "contracts/authority.md"}, preliminary=True)
        == REFERENCE_READ_DENIAL
    )
    scope = {
        "coding_paths": frozenset({SOURCE}),
        "read_paths": frozenset({SOURCE, "pi_workspace/scientific_model.md"}),
    }
    assert tool_denial("view", model, **scope) is None


def test_search_refuses_an_explicit_reference_target():
    args = adapter.parse_args(["p", "--session-id", "s"])
    search = scoped_search(args, None, lambda _: None)
    with pytest.raises(ValueError, match="system prompt"):
        search.target("contracts/program.md")
    assert search.target("robot_learning").is_dir()


def test_each_reference_file_is_in_the_system_message_once():
    for preliminary in (False, True):
        text = system_message(preliminary)["content"]
        for path in reference_paths(preliminary):
            assert text.count(f"File {path}:\n") == 1, path


def test_the_system_message_replaces_the_cli_prompt_with_one_fixed_text():
    for preliminary in (False, True):
        message = system_message(preliminary)
        assert message == {"mode": "replace", "content": system_prompt(preliminary)}
        assert str(paths.ROOT) in message["content"]
    assert ANALYST_EXPLORATION in system_prompt(True)
    assert ANALYST_EXPLORATION not in system_prompt(False)


def test_an_assistant_message_is_a_note_when_it_requests_a_tool():
    from copilot.session_events import AssistantMessageData

    from runner.copilot.session_events import event_handler

    calls = []
    console = SimpleNamespace(message=lambda *values: calls.append(values))
    handler = event_handler(console, asyncio.Event())
    for message_id, requests in (("m1", [object()]), ("m2", None)):
        data = AssistantMessageData(
            content="text", message_id=message_id, tool_requests=requests
        )
        handler(SimpleNamespace(agent_id=None, data=data))
    assert calls == [("text", "m1", "note"), ("text", "m2", "end")]


def test_coder_is_confined_to_its_binding():
    scope = {"coding_paths": frozenset({SOURCE}), "read_paths": frozenset({SOURCE})}
    assert (
        tool_denial("apply_patch", {"input": f"*** Update File: {SOURCE}\n"}, **scope)
        is None
    )
    assert tool_denial(
        "apply_patch", {"input": "*** Update File: AGENTS.md\n"}, **scope
    )
    assert tool_denial("apply_patch", {"input": "*** Move to: runner/x.py\n"}, **scope)
    assert tool_denial("view", {"path": "AGENTS.md"}, **scope)
    assert tool_denial("submit_operation", {}, **scope)


def test_a_locked_runner_denies_every_call():
    hook = scoped_tool_hook(operations=SimpleNamespace(locked=True))
    decision = hook({"toolName": "view", "toolArgs": {"path": SOURCE}}, {})
    assert decision["permissionDecision"] == "deny"


def test_a_long_operation_is_awaited_in_slices(monkeypatch, tmp_path, capsys):
    from runner import typed_events

    monkeypatch.setattr(submission_module, "WAIT_SLICE_SECONDS", 0.05)
    feed = tmp_path / "typed.events.jsonl"
    monkeypatch.setenv("TUI_TYPED_EVENTS", str(feed))
    typed_events.set_campaign("c")

    class Channel:
        def __init__(self) -> None:
            self.sent: list[dict] = []
            self.reply: asyncio.Future = asyncio.get_running_loop().create_future()

        async def send(self, message: dict) -> None:
            self.sent.append(message)

        async def receive(self) -> dict:
            return await self.reply

    async def exercise() -> None:
        channel = Channel()
        binding = {
            "session_id": "s",
            "invocation_id": "i",
            "campaign_id": "c",
            "state": {"operation_event_count": 0},
        }
        operations = OperationSubmission(
            channel, binding, Console(session_id="s"), None
        )
        hook = scoped_tool_hook(operations=operations)

        def call(call_id: str, request):
            return operations.invoke(
                SimpleNamespace(request=request),
                SimpleNamespace(session_id="s", tool_call_id=call_id),
            )

        first = json.loads(await call("a", {"kind": "train"}))
        assert first["status"] == "running" and len(channel.sent) == 1
        assert (
            hook({"toolName": "view", "toolArgs": {}}, {})["permissionDecision"]
            == "deny"
        )
        assert hook({"toolName": "submit_operation", "toolArgs": {}}, {}) is None
        other = json.loads(await call("b", {"kind": "train"}))
        assert other["status"] == "running" and len(channel.sent) == 1

        waiting = asyncio.ensure_future(call("c", None))
        await asyncio.sleep(0)
        channel.reply.set_result(
            {
                "type": "operation_result",
                "invocation_id": "i",
                "call_id": "a",
                "status": "completed",
            }
        )
        assert json.loads(await waiting)["status"] == "completed"
        assert not operations.locked and len(channel.sent) == 1

    with typed_events.context(session_id="S1"):
        asyncio.run(exercise())
    events = [
        json.loads(line) for line in feed.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["kind"] for event in events] == [
        "operation_submitted",
        "operation_submitted",
    ]
    assert [event["payload"]["status"] for event in events] == ["running", "completed"]
    assert all(
        event["campaign_id"] == "c" and event["session_id"] == "S1" for event in events
    )
    assert capsys.readouterr().out == ""


# --- native children ----------------------------------------------------------------


def test_external_pi_coder_uses_the_pi_model_and_the_reviewer_stays_on_copilot():
    coding = ScientificCoding(None, opencode_args("opencode/free-model"), Console())
    coder, reviewer = coding.agent(), coding.reviewer_agent()
    assert "model" not in coder and reviewer["model"] == "gpt-6-luna"
    assert coder["tools"] == [*CODING_TOOLS, "create", "edit"]
    assert reviewer["tools"] == REVIEW_TOOLS
    coding.busy, coding.active_handle = True, "child"
    coding.binding = {"allowed_paths": [SOURCE], "read_paths": [SOURCE]}
    for tool in ("read", "powershell", "submit_operation"):
        request = {"sessionId": "child", "toolName": tool, "toolArgs": {"path": SOURCE}}
        assert (
            coding.pre_tool_use(request, {"session_id": "s"})["permissionDecision"]
            == "deny"
        )
    for path, allowed in ((SOURCE, True), ("pi_workspace/scientific_model.md", False)):
        request = {
            "sessionId": "child",
            "toolName": "create",
            "toolArgs": {"path": path},
        }
        decision = coding.pre_tool_use(request, {"session_id": "s"})
        assert (decision is None) is allowed, path
    coding.active_agent = "scientific-reviewer"
    request = {"sessionId": "child", "toolName": "apply_patch", "toolArgs": {}}
    assert (
        coding.pre_tool_use(request, {"session_id": "s"})["permissionDecision"]
        == "deny"
    )
    copilot = ScientificCoding(
        None, adapter.parse_args(["p", "--session-id", "s"]), Console()
    )
    assert copilot.agent()["tools"] == CODING_TOOLS


def test_coding_creates_the_missing_folder_of_an_authorized_file(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "locate", lambda relative: tmp_path / relative)
    monkeypatch.setattr(coding_session, "load_task_context", lambda root: {})
    args = adapter.parse_args(
        [
            "p",
            "--session-id",
            "s",
            "--campaign-id",
            "00000000-0000-0000-0000-000000000001",
        ]
    )
    coding = ScientificCoding(None, args, Console())

    async def validate():
        return None

    coding.session = SimpleNamespace(
        rpc=SimpleNamespace(tools=SimpleNamespace(initialize_and_validate=validate))
    )
    params = ScientificCodingParams(
        intent="x", allowed_paths=["robot_learning/lab/new_tool.py"]
    )
    invocation = SimpleNamespace(session_id="s", agent_id=None, tool_call_id="t")
    asyncio.run(coding._prepare(params, invocation))
    assert (tmp_path / "robot_learning/lab").is_dir()


def test_reviewer_identity_must_match_the_requested_copilot_model():
    coding = ScientificCoding(None, opencode_args("opencode/free-model"), Console())
    coding.child_models, coding.child_reasoning = {"gpt-6-luna"}, {"high"}
    coding.verify_reviewer_identity()
    coding.child_models = {"opencode/free-model"}
    with pytest.raises(ValueError, match="was not verified"):
        coding.verify_reviewer_identity()


# --- usage, console and launcher outcome --------------------------------------


def test_usage_row_never_invents_external_aiu(tmp_path, monkeypatch):
    from runner.copilot import usage as usage_module

    monkeypatch.setattr(usage_module, "ROOT", tmp_path)
    args = opencode_args(
        "opencode/free-model", "--campaign-id", "00000000-0000-0000-0000-000000000001"
    )
    console = Console()
    console.usage.add_assistant_usage(
        SimpleNamespace(
            input_tokens=100,
            output_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            copilot_usage=SimpleNamespace(total_nano_aiu=5),
        )
    )
    usage_module.record_usage(args, console.usage, 1.0, 0)
    row = json.loads(
        next((tmp_path / "reports" / "session_usage").glob("*.jsonl")).read_text()
    )
    assert (row["provider"], row["aiu"], row["input_tokens"], row["output_tokens"]) == (
        "opencode",
        None,
        100,
        None,
    )
    assert row["provider_token_prices_per_million"] == {"input": 0, "output": 0}


def test_console_shows_patch_targets_not_patch_bodies():
    detail = tool_detail(
        "apply_patch", {"input": f"*** Update File: {SOURCE}\n+secret = 1\n"}
    )
    assert "environment.py" in detail and "secret" not in detail


def test_launcher_outcome_reports_timeouts_and_unexplained_failures():
    args = SimpleNamespace(
        timeout=5, usage_console=Console(), operation_submission=None
    )
    assert adapter.session_outcome(5, args, None)[0] == "controller_fatal"
    assert adapter.session_outcome(130, args, None)[0] == "interrupted"
    assert adapter.session_outcome(6, args, None)[0] == "controller_fatal"
    assert adapter.session_outcome(0, args, None) == ("preliminary", None)
