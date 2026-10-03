"""Check whether the frozen M7 artifact can enter the candidate-role contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from research import runner_protocol, runner_repository


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(frozen_artifact: Path, output: Path) -> None:
    state = runner_repository.load_state()
    artifact = runner_repository.resolve_repo_path(str(frozen_artifact))
    required_files = (
        "model.zip",
        "artifact.json",
        "vecnormalize.pkl",
        "policy_runtime.pkl",
    )
    metadata = json.loads((artifact / "artifact.json").read_text(encoding="utf-8"))
    candidate_id = "M7:frozen-reflection-wrapped-t1"
    role_request = {
        "action": "set_best_known",
        "candidate": candidate_id,
        "reason": "probe exact M7 artifact binding",
        "evidence": ["M7"],
    }
    try:
        runner_protocol.plan_model_role(role_request, state)
    except (KeyError, TypeError, ValueError) as error:
        role_error = str(error)
    else:
        role_error = None

    output_data = {
        "schema_version": 1,
        "measurement": "candidate_binding_probe",
        "frozen_artifact": runner_repository.repo_relative_path(artifact),
        "artifact_exists": artifact.is_dir(),
        "required_files": {
            filename: (artifact / filename).is_file() for filename in required_files
        },
        "artifact_fingerprint": runner_repository.artifact_fingerprint(artifact),
        "model_sha256": _sha256(artifact / "model.zip"),
        "runtime_sha256": _sha256(artifact / "policy_runtime.pkl"),
        "frozen_wrapper": metadata.get("frozen_wrapper"),
        "source_model_sha256": metadata.get("source_model_sha256"),
        "registry": {
            "candidate_id_probed": candidate_id,
            "candidate_registered": candidate_id in state["candidates"],
            "registered_candidate_count": len(state["candidates"]),
            "role_resolution_error": role_error,
            "model_role_actions": [
                "set_working",
                "set_best_known",
                "retain",
            ],
            "operation_kinds": sorted(runner_protocol.OPERATION_KEYS),
            "candidate_registration_operation_supported": (
                "candidate_registration" in runner_protocol.OPERATION_KEYS
            ),
        },
        "conclusion": (
            "artifact_is_complete_but_exact_frozen_runtime_is_not_registered"
            if role_error is not None
            else "exact_frozen_runtime_resolves_as_registered_candidate"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-artifact", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    run(args.frozen_artifact, args.artifact)


if __name__ == "__main__":
    main()
