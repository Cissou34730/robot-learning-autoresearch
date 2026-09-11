"""A bounded Researcher session is observed, not guessed.

Three independent facts describe every session -- the process outcome, the
presence of the expected deliverable and its validity -- and none of them is
read from whatever the Researcher printed.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOOP = (ROOT / "run_research.ps1").read_text(encoding="utf-8")
SESSION_LIBRARY_PATH = ROOT / "researcher_session.ps1"
SESSION_LIBRARY = SESSION_LIBRARY_PATH.read_text(encoding="utf-8")
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
EVALUATION_EXECUTION_FAILURE = (
    "Runner execution of the validated evaluation request failed."
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
    assert LOOP.count("Invoke-ResearcherSession -Prompt") == 4
    assert LOOP.count("-Continue") == 2
    assert "$script:ResearcherExitCode = if ($null -eq $LASTEXITCODE)" in LOOP


def test_the_exit_code_never_decides_whether_a_bounded_phase_is_complete():
    for phase in ("proposalStatus", "analysisStatus"):
        assert LOOP.count(f"if (-not ${phase}.Complete)") == 2

    assert "ResearcherExitCode -ne" not in LOOP
    assert "ResearcherExitCode -eq" not in LOOP
    # Completion is a property of the deliverable alone.
    assert "Complete    = ($Present -and $Valid)" in SESSION_LIBRARY


def test_each_phase_reports_its_session_before_deciding_to_retry():
    assert LOOP.count("Write-ResearcherSessionStatus") == 4
    for status, retry in (
        ("$proposalStatus", "=== Research proposal missing or invalid"),
        ("$analysisStatus", "=== Analysis deliverable missing or invalid"),
    ):
        assert LOOP.index(f"Write-ResearcherSessionStatus {status}") < LOOP.index(retry)


def test_every_phase_validates_its_deliverable_with_the_protected_validator():
    for validator in (
        "--check-proposal",
        "--check-analysis-deliverable",
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


def test_launcher_stops_for_either_terminal_official_assessment():
    terminal_guard = LOOP.split("terminal_campaign_status", 1)[1].split(
        'if (Test-Path "research\\RECOVERY_PENDING")', 1
    )[0]

    assert "Official assessment complete" in terminal_guard
    assert "break" in terminal_guard
