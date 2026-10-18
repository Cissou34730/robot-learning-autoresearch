"""Exit codes, timeouts and output limits shared by the Copilot runtime modules."""

from __future__ import annotations

from runner.copilot.path_policy import ROOT

EXIT_OK = 0
EXIT_SESSION_ERROR = 2
EXIT_NOT_AUTHENTICATED = 3
EXIT_MODEL_UNAVAILABLE = 4
EXIT_TIMEOUT = 5
EXIT_RUNTIME_FAILURE = 6
EXIT_INTERRUPTED = 130

SHUTDOWN_TIMEOUT_SECONDS = 30.0
FORCE_STOP_TIMEOUT_SECONDS = 10.0

MODEL_CALL_RETRY_LIMIT = 5
MODEL_CALL_RETRY_DELAY_SECONDS = 5.0

# Oversized tool results are written here instead of occupying the context. The
# threshold stays above campaign artifacts, so primary evidence is not offloaded.
LARGE_OUTPUT_DIR = ROOT / ".copilot" / "large-output"
LARGE_OUTPUT_MAX_BYTES = 262_144
