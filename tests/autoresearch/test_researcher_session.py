"""A bounded Researcher session is observed, not guessed.

Three independent facts describe every session -- the process outcome, the
presence of the expected deliverable and its validity -- and none of them is
read from whatever the Researcher printed.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from research.run_experiment import (
    check_evaluation_request,
    execute_pending_evaluations,
    main,
)

ROOT = Path(__file__).resolve().parents[2]
LOOP = (ROOT / "run_research.ps1").read_text(encoding="utf-8")
SESSION_LIBRARY_PATH = ROOT / "researcher_session.ps1"
SESSION_LIBRARY = SESSION_LIBRARY_PATH.read_text(encoding="utf-8")
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
EVALUATION_EXECUTION_FAILURE = (
    "Runner execution of the validated evaluation request failed."
)
LINEAGE_EXECUTION_FAILURE = (
    "Runner application of the validated lineage decision failed."
)

powershell_only = pytest.mark.skipif(
    POWERSHELL is None, reason="no PowerShell host to run the launcher library"
)


def run_session_script(body: str, tmp_path: Path) -> str:
    script = tmp_path / "session_case.ps1"
    script.write_text(f". '{SESSION_LIBRARY_PATH}'\n{body}\n", encoding="utf-8")
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def observe(
    *,
    exit_code: str,
    present: bool,
    valid: bool,
    reason: str = "",
    attempt: int = 1,
    variable: str = "status",
) -> str:
    return (
        f"${variable} = New-ResearcherSessionStatus -Phase 'new hypothesis' "
        f"-Attempt {attempt} -ExitCode {exit_code} "
        f"-Deliverable 'research/proposal.json' "
        f"-Present ${str(present).lower()} -Valid ${str(valid).lower()} "
        f"-Reason '{reason}'\n"
        f"Write-ResearcherSessionStatus ${variable}\n"
        f'Write-Host "complete=$(${variable}.Complete)"\n'
    )


# --- the three observed facts ----------------------------------------------


@powershell_only
def test_successful_process_with_a_valid_deliverable_completes_the_phase(tmp_path):
    console = run_session_script(
        observe(exit_code="0", present=True, valid=True), tmp_path
    )

    assert "complete=True" in console
    assert "process=0" in console
    assert "research/proposal.json=valid" in console
    # A normal session stays a single quiet line.
    assert "=== Researcher session" not in console


@powershell_only
def test_successful_process_without_a_deliverable_leaves_the_phase_open(tmp_path):
    console = run_session_script(
        observe(
            exit_code="0",
            present=False,
            valid=False,
            reason="research/proposal.json was not created",
        ),
        tmp_path,
    )

    assert "complete=False" in console
    assert "Process exit : 0" in console
    assert "Deliverable  : research/proposal.json (missing)" in console
    assert "Validation   : not run" in console


@powershell_only
def test_failed_process_without_a_deliverable_reports_both_facts(tmp_path):
    console = run_session_script(
        observe(
            exit_code="1",
            present=False,
            valid=False,
            reason="research/proposal.json was not created",
        ),
        tmp_path,
    )

    assert "complete=False" in console
    assert "Process exit : 1" in console
    assert "Deliverable  : research/proposal.json (missing)" in console
    assert "Validation   : not run" in console


@powershell_only
def test_invalid_deliverable_keeps_the_validator_reason(tmp_path):
    reason = "PROPOSAL_INVALID: proposal initialization must be transfer or fresh"
    console = run_session_script(
        observe(exit_code="0", present=True, valid=False, reason=reason), tmp_path
    )

    assert "complete=False" in console
    assert "Process exit : 0" in console
    assert "Deliverable  : research/proposal.json (present)" in console
    assert "Validation   : invalid" in console
    assert f"Reason       : {reason}" in console


@powershell_only
def test_failed_process_with_a_valid_deliverable_is_not_discarded(tmp_path):
    console = run_session_script(
        observe(exit_code="1", present=True, valid=True), tmp_path
    )

    # The process anomaly is reported, the scientific deliverable is kept.
    assert "complete=True" in console
    assert "Process exit : 1" in console
    assert "Validation   : valid" in console


@powershell_only
def test_a_missing_exit_code_is_reported_as_such(tmp_path):
    console = run_session_script(
        observe(exit_code="$null", present=False, valid=False), tmp_path
    )

    assert "Process exit : unavailable" in console


@powershell_only
def test_the_first_attempt_stays_visible_after_the_retry(tmp_path):
    body = observe(
        exit_code="1",
        present=False,
        valid=False,
        reason="research/proposal.json was not created",
        attempt=1,
        variable="first",
    ) + observe(
        exit_code="0",
        present=True,
        valid=False,
        reason="PROPOSAL_INVALID: proposal initialization must be fresh",
        attempt=2,
        variable="second",
    )
    console = run_session_script(body, tmp_path)

    first = console.index("attempt 1")
    second = console.index("attempt 2")
    assert first < second
    assert console.index("Process exit : 1") < second
    assert console.index("Validation   : invalid") > first


# --- how the launcher uses those facts -------------------------------------


def test_every_researcher_invocation_goes_through_the_one_process_boundary():
    invocations = [
        line.strip() for line in LOOP.splitlines() if "researcher_copilot.py" in line
    ]

    # One command builds every session; continuation is an argument, not a branch.
    assert invocations == [
        "uv run --group researcher python researcher_copilot.py @sessionArgs $Prompt",
    ]
    assert LOOP.count("Invoke-ResearcherSession -Prompt") == 6
    assert LOOP.count("-Continue") == 3
    assert "$script:ResearcherExitCode = if ($null -eq $LASTEXITCODE)" in LOOP


def test_the_exit_code_never_decides_whether_a_bounded_phase_is_complete():
    for phase in ("proposalStatus", "evaluationStatus", "lineageStatus"):
        assert LOOP.count(f"if (-not ${phase}.Complete)") == 2

    assert "ResearcherExitCode -ne" not in LOOP
    assert "ResearcherExitCode -eq" not in LOOP
    # Completion is a property of the deliverable alone.
    assert "Complete    = ($Present -and $Valid)" in SESSION_LIBRARY


def test_each_phase_reports_its_session_before_deciding_to_retry():
    assert LOOP.count("Write-ResearcherSessionStatus") == 6
    for status, retry in (
        ("$proposalStatus", "=== Research proposal missing or invalid"),
        ("$evaluationStatus", "=== Evaluation request missing or invalid"),
        ("$lineageStatus", "=== Lineage deliverable invalid"),
    ):
        assert LOOP.index(f"Write-ResearcherSessionStatus {status}") < LOOP.index(retry)


def test_every_phase_validates_its_deliverable_with_the_protected_validator():
    for validator in (
        "--check-proposal",
        "--check-evaluation-request",
        "--check-lineage-evidence",
    ):
        assert validator in LOOP


def test_session_observation_reads_no_researcher_output():
    for text in (LOOP, SESSION_LIBRARY):
        for forbidden in (
            "Tee-Object",
            "Select-String",
            "Out-String",
            "--format json",
        ):
            assert forbidden not in text
    # The provider command is invoked, never captured or interpreted.
    assert "= uv run" not in LOOP
    assert "researcher_copilot" not in SESSION_LIBRARY
    assert "copilot" not in SESSION_LIBRARY


def test_session_observation_is_console_only():
    for text in (LOOP, SESSION_LIBRARY):
        for durable in ("session_history", "process_events", "researcher_runs"):
            assert durable not in text
    # The observation has one destination, and it is the console.
    for persisting in ("Out-File", "Add-Content", "Set-Content", "ConvertTo-Json"):
        assert persisting not in SESSION_LIBRARY


def test_runner_execution_failure_never_reopens_the_researcher_phase():
    for marker in (EVALUATION_EXECUTION_FAILURE, LINEAGE_EXECUTION_FAILURE):
        assert marker in LOOP
        remainder = LOOP.split(marker, 1)[1].split("continue", 1)[0]
        assert "Invoke-ResearcherSession" not in remainder
        assert "retry" not in remainder.lower()


# --- the evaluation-request preflight --------------------------------------


def _valid_request() -> dict:
    return {
        "experiment": 3,
        "question": "does the intervention change the outcome",
        "reason": "the champion and the candidate must be compared",
        "evaluations": [{"candidate": "experiment-3", "episodes": 200, "seed": 1000}],
    }


def _pending_state() -> dict:
    return {
        "accepted_artifact": "research/checkpoints/accepted",
        "pending_evaluation_request": {
            "experiment": 3,
            "champion_available": True,
            "candidates": [
                {
                    "name": "experiment-3",
                    "artifact": "models/candidates/experiment-3",
                }
            ],
        },
    }


def _preflight_files(monkeypatch, tmp_path, request: dict | str) -> Path:
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state_path.write_text(json.dumps(_pending_state()), encoding="utf-8")
    if isinstance(request, str):
        request_path.write_text(request, encoding="utf-8")
    else:
        request_path.write_text(json.dumps(request), encoding="utf-8")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)

    def fail_if_measured(*args, **kwargs):
        del args, kwargs
        pytest.fail("the preflight executed a measurement")

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", fail_if_measured)
    return state_path


def test_evaluation_preflight_accepts_a_valid_request_without_measuring(
    monkeypatch, tmp_path, capsys
):
    state_path = _preflight_files(monkeypatch, tmp_path, _valid_request())
    original_state = state_path.read_bytes()

    assert check_evaluation_request() == 0
    assert "EVALUATION_REQUEST_VALID" in capsys.readouterr().out
    assert state_path.read_bytes() == original_state


@pytest.mark.parametrize(
    ("requested", "message"),
    [
        (
            dict(_valid_request(), question=""),
            "requires a non-empty question",
        ),
        (
            {
                "experiment": 3,
                "question": "q",
                "reason": "r",
                "evaluations": [],
            },
            "at least one research or task-reference evaluation",
        ),
        (
            dict(_valid_request(), experiment=2),
            "wrong experiment",
        ),
        (
            dict(
                _valid_request(),
                task_reference_evaluations=[{"candidate": "champion", "seed": 7}],
            ),
            "task-reference panel is human-owned",
        ),
        # Entry-level rules, all resolved before the first measurement.
        (
            dict(
                _valid_request(),
                evaluations=[{"candidate": "experiment-9", "episodes": 200, "seed": 1}],
            ),
            "unknown evaluation candidate 'experiment-9'",
        ),
        (
            dict(
                _valid_request(),
                evaluations=[{"candidate": "experiment-3", "episodes": 0, "seed": 1}],
            ),
            "evaluation episodes must be positive",
        ),
        (
            dict(
                _valid_request(),
                evaluations=[
                    {"candidate": "experiment-3", "episodes": "many", "seed": 1}
                ],
            ),
            "episodes and seed must be whole numbers",
        ),
        (
            dict(
                _valid_request(),
                evaluations=[{"candidate": "experiment-3", "episodes": 200}],
            ),
            "missing required fields: ['seed']",
        ),
        (
            dict(_valid_request(), evaluations=["experiment-3"]),
            "each requested evaluation must be an object",
        ),
        (
            dict(
                _valid_request(),
                evaluations=[
                    {
                        "candidate": "experiment-3",
                        "episodes": 200,
                        "seed": 1,
                        "official_benchmark": True,
                    }
                ],
            ),
            "official_benchmark is not valid in a research evaluation request",
        ),
        (
            dict(
                _valid_request(),
                task_reference_evaluations=[{"candidate": "experiment-9"}],
            ),
            "unknown task-reference candidate 'experiment-9'",
        ),
        # A single unusable entry keeps the whole request out of execution.
        (
            dict(
                _valid_request(),
                evaluations=[
                    {"candidate": "experiment-3", "episodes": 200, "seed": 1},
                    {"candidate": "experiment-3", "episodes": -5, "seed": 2},
                ],
            ),
            "evaluation episodes must be positive",
        ),
        ("{not json", "Expecting"),
    ],
)
def test_evaluation_preflight_rejects_with_a_usable_reason(
    monkeypatch, tmp_path, capsys, requested, message
):
    state_path = _preflight_files(monkeypatch, tmp_path, requested)
    original_state = state_path.read_bytes()

    assert check_evaluation_request() == 1
    console = capsys.readouterr().out
    assert "EVALUATION_REQUEST_INVALID" in console
    assert message in console
    assert state_path.read_bytes() == original_state


def test_evaluation_preflight_accepts_the_champion_the_brief_exposes(
    monkeypatch, tmp_path, capsys
):
    _preflight_files(
        monkeypatch,
        tmp_path,
        dict(
            _valid_request(),
            evaluations=[{"candidate": "champion", "episodes": 200, "seed": 1000}],
            task_reference_evaluations=[{"candidate": "champion"}],
        ),
    )

    assert check_evaluation_request() == 0
    assert "EVALUATION_REQUEST_VALID" in capsys.readouterr().out


@pytest.mark.parametrize(
    "evaluations",
    [
        [{"candidate": "experiment-9", "episodes": 200, "seed": 1}],
        [{"candidate": "experiment-3", "episodes": 0, "seed": 1}],
        [{"candidate": "experiment-3", "episodes": 200}],
    ],
)
def test_execution_rejects_exactly_what_the_preflight_rejects(
    monkeypatch, tmp_path, capsys, evaluations
):
    """One contract: validation-only and execution resolve the same plan."""
    _preflight_files(
        monkeypatch, tmp_path, dict(_valid_request(), evaluations=evaluations)
    )

    assert check_evaluation_request() == 1
    preflight_reason = capsys.readouterr().out.split("EVALUATION_REQUEST_INVALID: ")[1]

    with pytest.raises((TypeError, ValueError)) as execution_error:
        execute_pending_evaluations()

    assert str(execution_error.value) in preflight_reason


def test_evaluation_preflight_reports_a_missing_deliverable(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(
        "research.runner_paths.STATE_PATH", tmp_path / "research_state.json"
    )
    monkeypatch.setattr(
        "research.runner_paths.EVALUATION_REQUEST_PATH",
        tmp_path / "evaluation_request.json",
    )

    assert check_evaluation_request() == 1
    assert "research/evaluation_request.json was not created" in capsys.readouterr().out


def test_evaluation_preflight_rejects_a_request_outside_its_phase(
    monkeypatch, tmp_path, capsys
):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state_path.write_text(
        json.dumps({"pending_evaluation_request": None}), encoding="utf-8"
    )
    request_path.write_text(json.dumps(_valid_request()), encoding="utf-8")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)

    assert check_evaluation_request() == 1
    assert "awaiting a research evaluation" in capsys.readouterr().out


def test_the_preflight_is_reachable_as_a_validation_only_command(
    monkeypatch, tmp_path, capsys
):
    _preflight_files(monkeypatch, tmp_path, dict(_valid_request(), experiment=9))
    monkeypatch.setattr("sys.argv", ["run_experiment.py", "--check-evaluation-request"])

    assert main() == 1
    assert "EVALUATION_REQUEST_INVALID" in capsys.readouterr().out
