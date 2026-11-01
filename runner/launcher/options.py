"""Launch parameters and their defaults."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROVIDERS = ("github-copilot", "opencode", "opencode-go")
REASONING_LEVELS = ("low", "medium", "high", "xhigh", "max")
# Each phase has its own PI backend; goal review and inquiries share "research".
PHASES = ("analyst", "recipe", "startup", "research")
DEFAULT_REASONING = {
    "analyst": "max",
    "recipe": "high",
    "startup": "high",
    "research": "high",
}
DEFAULT_MAX_INQUIRIES = 15
DEFAULT_TIMESTEPS = 120000
DEFAULT_MAX_TIMESTEPS = 360000
DEFAULT_STOP_TIMEOUT_SECONDS = 180
COPILOT_DEFAULT_MODEL = "gpt-6-luna"
# One OpenCode key covers Zen and Go; the free Zen model is the default for both.
OPENCODE_DEFAULT_MODEL = "opencode/deepseek-v4.1-flash-free"


def default_campaign_root(harness_root: Path) -> Path:
    return harness_root.parent / "robot-learning-campaigns" / "campaign-1"


def resolve_model(model: str | None, provider: str | None) -> str:
    if not model:
        if not provider or provider == "github-copilot":
            return COPILOT_DEFAULT_MODEL
        return OPENCODE_DEFAULT_MODEL
    if provider:
        if "/" in model:
            if model.split("/", 1)[0] != provider:
                raise ValueError("The model prefix and selected provider do not match.")
        elif provider != "github-copilot":
            return f"{provider}/{model}"
    return model


def phase_of(session_kind: str) -> str:
    """The launch phase whose backend serves a scientific session kind."""
    if session_kind == "recipe_development":
        return "recipe"
    if session_kind == "startup":
        return "startup"
    if session_kind in {"goal_review", "inquiry"}:
        return "research"
    raise ValueError(f"No launch phase serves the session kind {session_kind!r}.")


@dataclass(frozen=True)
class PhaseBackend:
    model: str
    reasoning: str


@dataclass(frozen=True)
class LaunchOptions:
    harness_root: Path
    campaign_root: Path
    backends: dict[str, PhaseBackend]
    max_inquiries: int
    max_inquiries_explicit: bool
    timesteps: int
    max_timesteps: int
    stop_timeout_seconds: int
    stop_after_preparation: bool = False

    def analyst(self) -> PhaseBackend:
        return self.backends["analyst"]

    def session(self, session_kind: str) -> PhaseBackend:
        return self.backends[phase_of(session_kind)]
