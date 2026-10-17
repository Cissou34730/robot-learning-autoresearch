"""OpenCode inference configuration for the existing Copilot agent runtime."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from copilot.session import (
    ModelCapabilitiesOverride,
    ModelSupportsOverride,
)

ROOT = Path(__file__).resolve().parents[2]
STATE_DIRECTORY = ROOT / ".copilot" / "opencode"
CATALOG_URL = "https://models.opencode.ai/api.json"
CATALOG_REFRESH_SECONDS = 24 * 60 * 60
PROVIDERS = ("github-copilot", "opencode", "opencode-go")
DEFAULT_MODEL = "gpt-6-luna"
OPENCODE_DEFAULT_MODEL = "opencode/deepseek-v4.1-flash-free"
# Offline fallback, as in pi-harness, when no catalog has ever been saved.
SEED_CATALOG = {
    "opencode": {
        "npm": "@ai-sdk/openai-compatible",
        "api": "https://opencode.ai/inference/openai/v1",
        "models": {
            "deepseek-v4.1-flash-free": {
                "id": "deepseek-v4.1-flash-free",
                "reasoning": True,
                "tool_call": True,
                "cost": {"input": 0, "output": 0},
                "modalities": {"input": ["text", "image"]},
                "limit": {"context": 200000, "output": 32000},
            }
        },
    },
    "opencode-go": {"models": {}},
}
_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_SESSION_PATTERN = re.compile(r"ses_[0-9a-f]{12}[0-9A-Za-z]{14}\Z")
_last_timestamp = -1
_counter = 0


def provider_of(model: str) -> str:
    return model.split("/", 1)[0] if "/" in model else "github-copilot"


def select_model(model: str | None, provider: str | None = None) -> str:
    if model is None:
        return (
            DEFAULT_MODEL
            if provider in (None, "github-copilot")
            else OPENCODE_DEFAULT_MODEL
        )
    if "/" in model:
        selected, local = model.split("/", 1)
        if not local or selected not in PROVIDERS:
            raise ValueError(f"Unknown provider or empty model in {model!r}.")
        if provider is not None and provider != selected:
            raise ValueError("The model prefix and selected provider do not match.")
        provider = selected
        model = local
    provider = provider or "github-copilot"
    if provider not in PROVIDERS or not model.strip():
        raise ValueError("Select a known provider and a nonempty model.")
    return model if provider == "github-copilot" else f"{provider}/{model}"


def create_session_id() -> str:
    global _last_timestamp, _counter
    timestamp = time.time_ns() // 1_000_000
    _counter = _counter + 1 if timestamp == _last_timestamp else 1
    _last_timestamp = timestamp
    descending = (~(timestamp * 0x1000 + _counter)) & 0xFFFFFFFFFFFF
    random = "".join(
        _ALPHABET[byte % len(_ALPHABET)] for byte in secrets.token_bytes(14)
    )
    return f"ses_{descending:012x}{random}"


def _git(root: Path, *arguments: str) -> str | None:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def project_id(root: Path = ROOT) -> str:
    if not _git(root, "rev-parse", "--show-toplevel"):
        return "global"
    remote = _git(root, "remote", "get-url", "origin")
    if remote:
        parsed = urlsplit(remote)
        if parsed.hostname and parsed.scheme != "file":
            normalized = f"{parsed.hostname.lower()}/{parsed.path.lstrip('/')}"
        else:
            match = re.fullmatch(r"(?:[^@/:]+@)?([^/:]+):(.+)", remote)
            normalized = f"{match[1].lower()}/{match[2]}" if match else None
        if normalized:
            normalized = re.sub(r"\.git/?$", "", normalized).rstrip("/")
            return hashlib.sha1(f"git-remote:{normalized}".encode()).hexdigest()
    roots = _git(root, "rev-list", "--max-parents=0", "HEAD")
    return roots.splitlines()[0] if roots else "global"


def identity_headers(session_id: str, project: str) -> dict[str, str]:
    if not _SESSION_PATTERN.fullmatch(session_id):
        raise ValueError("Invalid persisted OpenCode session identity.")
    version = os.environ.get("OPENCODE_CLI_VERSION", "2.0.27")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("OPENCODE_CLI_VERSION must be a numeric three-part version.")
    return {
        "User-Agent": f"opencode/latest/{version}/cli",
        "x-opencode-client": "cli",
        "x-opencode-session": session_id,
        "x-opencode-session-id": session_id,
        "x-session-affinity": session_id,
        "x-session-id": session_id,
        "x-opencode-project": project,
    }


def session_identity(sdk_session_id: str, model: str, *, resume: bool = False) -> str:
    directory = STATE_DIRECTORY / "sessions"
    path = directory / f"{hashlib.sha256(sdk_session_id.encode()).hexdigest()}.json"
    if path.is_file():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("model") != model:
            raise ValueError(
                "Persisted OpenCode session belongs to another model route."
            )
        identity = saved.get("session_id")
        if not isinstance(identity, str) or not _SESSION_PATTERN.fullmatch(identity):
            raise ValueError("Invalid persisted OpenCode session identity.")
        return identity
    if resume:
        raise ValueError(
            "Cannot resume OpenCode without its persisted session identity."
        )
    directory.mkdir(parents=True, exist_ok=True)
    identity = create_session_id()
    with path.open("x", encoding="utf-8") as handle:
        json.dump({"session_id": identity, "model": model}, handle)
    return identity


def load_catalog() -> dict:
    path = STATE_DIRECTORY / "catalog.json"
    cached = None
    if path.is_file():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(cached.get("providers"), dict):
                raise TypeError("Missing provider catalog.")
            if time.time() - cached["checked_at"] < CATALOG_REFRESH_SECONDS:
                return cached["providers"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            warnings.warn(f"OpenCode catalog cache is invalid: {error}", stacklevel=2)
            cached = None
    try:
        request = Request(CATALOG_URL, headers={"User-Agent": "robot-learning-harness"})
        with urlopen(request, timeout=10) as response:
            catalog = json.load(response)
        providers = {name: catalog[name] for name in PROVIDERS[1:]}
        if any(
            not isinstance(value.get("models"), dict) for value in providers.values()
        ):
            raise ValueError("OpenCode catalog has no model mapping.")
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as error:
        if cached is None:
            warnings.warn(
                f"Cannot load the OpenCode model catalog; using the seed model: {error}",
                stacklevel=2,
            )
            return SEED_CATALOG
        warnings.warn(
            f"OpenCode catalog refresh failed; using the saved catalog: {error}",
            stacklevel=2,
        )
        return cached["providers"]
    STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            json.dumps({"checked_at": time.time(), "providers": providers}),
            encoding="utf-8",
        )
    except OSError as error:
        warnings.warn(f"Cannot save the OpenCode model catalog: {error}", stacklevel=2)
    return providers


def api_key() -> str:
    """One OpenCode key authorizes both Zen and Go."""
    key = os.environ.get("OPENCODE_API_KEY", "").strip()
    if not key:
        raise ValueError("No local OpenCode credential; set OPENCODE_API_KEY.")
    return key


@dataclass(frozen=True)
class OpenCodeModel:
    selection: str
    provider: str
    wire_model: str
    base_url: str
    sdk_type: str
    wire_api: str
    context: int
    output: int
    reasoning: bool
    vision: bool
    cost: dict

    def session_options(self, identity: str, key: str, project: str) -> dict:
        provider = {
            "name": self.provider,
            "type": self.sdk_type,
            # The SDK Anthropic transport appends /v1/messages itself.
            "base_url": self.base_url.removesuffix("/v1")
            if self.sdk_type == "anthropic"
            else self.base_url,
            "api_key": key,
            "headers": identity_headers(identity, project),
        }
        if self.sdk_type == "openai":
            provider["wire_api"] = self.wire_api
        model = {
            "id": self.wire_model,
            "provider": self.provider,
            "wire_model": self.wire_model,
            "max_context_window_tokens": self.context,
            "max_prompt_tokens": self.context - self.output,
            "max_output_tokens": self.output,
            "capabilities": ModelCapabilitiesOverride(
                supports=ModelSupportsOverride(
                    reasoning_effort=self.reasoning, vision=self.vision
                ),
            ),
        }
        return {"model": self.selection, "providers": [provider], "models": [model]}


def resolve_model(selection: str, catalog: dict) -> OpenCodeModel:
    provider, wire_model = selection.split("/", 1)
    source = catalog.get(provider, {})
    model = source.get("models", {}).get(wire_model)
    if not isinstance(model, dict):
        raise TypeError(
            f"{selection!r} is absent from the OpenCode catalog; list models."
        )
    if model.get("status") == "deprecated":
        raise ValueError(f"{selection!r} is deprecated in the OpenCode catalog.")
    if model.get("tool_call") is False:
        raise ValueError(f"{selection!r} does not support agent tool calls.")
    override = model.get("provider") or {}
    package = override.get("npm", source.get("npm"))
    base_url = override.get("api", source.get("api"))
    cost = model.get("cost") or {}
    if package == "@ai-sdk/anthropic":
        sdk_type, wire_api = "anthropic", "completions"
    elif package in ("@ai-sdk/openai-compatible", "@ai-sdk/mistral"):
        sdk_type, wire_api = "openai", "completions"
    elif package == "@ai-sdk/openai":
        sdk_type, wire_api = "openai", "responses"
    else:
        raise ValueError(
            f"{selection!r} uses {package!r}; the installed Copilot SDK does not "
            "expose that provider protocol. No other model will be substituted."
        )
    if not isinstance(base_url, str) or urlsplit(base_url).scheme != "https":
        raise ValueError(f"{selection!r} has no HTTPS inference endpoint.")
    limits = model.get("limit") or {}
    context, output = limits.get("context"), limits.get("output")
    if (
        not isinstance(context, int)
        or not isinstance(output, int)
        or not 0 < output < context
    ):
        raise ValueError(f"{selection!r} has invalid context/output limits.")
    return OpenCodeModel(
        selection=selection,
        provider=provider,
        wire_model=wire_model,
        base_url=base_url.rstrip("/"),
        sdk_type=sdk_type,
        wire_api=wire_api,
        context=context,
        output=output,
        reasoning=model.get("reasoning") is True,
        vision="image" in model.get("modalities", {}).get("input", []),
        cost=cost,
    )
