"""Human-only migration of a trusted legacy policy into a NEW artifact directory.

The caller chooses the exact historical scientific revision. No current-code
fallback, Git checkout, campaign mutation, training or evaluation is performed.
"""

import argparse
import io
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def migrate(source: Path, destination: Path, revision: str, *, identity_actions=False):
    source = source.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("Migration destination must not exist")
    if not (source / "model.zip").is_file() or not (source / "artifact.json").is_file():
        raise ValueError("Legacy artifact must contain model.zip and artifact.json")
    if not (source / "vecnormalize.pkl").is_file():
        raise ValueError(
            "Legacy migration requires saved normalization; absence cannot imply unnormalized inputs"
        )
    commit = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    archive = subprocess.run(
        ["git", "archive", "--format=zip", commit, "robot_learning"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="policy-migration-") as directory:
        checkout = Path(directory).resolve()
        with zipfile.ZipFile(io.BytesIO(archive)) as contents:
            for name in contents.namelist():
                if not (checkout / name).resolve().is_relative_to(checkout):
                    raise ValueError("Unsafe archive member")
            contents.extractall(checkout)
        shutil.copyfile(
            ROOT / "robot_learning/policy_runtime.py",
            checkout / "robot_learning/policy_runtime.py",
        )
        interface = checkout / "robot_learning/scenario/policy_io.py"
        if not interface.exists():
            if not identity_actions:
                raise ValueError(
                    "Historical code has no explicit policy_io. Inspect its action path; "
                    "--identity-actions is required only if it applied network outputs directly."
                )
            interface.write_text(
                "from robot_learning.policy_runtime import PolicyIO\n"
                "from robot_learning.scenario.observations import reach_observation\n"
                "def identity(action): return action\n"
                "def make_policy_io(): return PolicyIO(reach_observation, identity)\n",
                encoding="utf-8",
            )
        # This subprocess imports the historical science, not the caller's active
        # modules. Export into a staging directory; publish only after success.
        staging = checkout / "artifact"
        shutil.copytree(source, staging)
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    "from robot_learning.policy_runtime import save_runtime, load_runtime; "
                    "from robot_learning.scenario.policy_io import make_policy_io; "
                    "from robot_learning.training.algorithms import load_policy; "
                    "from robot_learning.training.normalization import load_observation_normalizer; "
                    "p=Path('artifact/model.zip'); s=p.parent/'vecnormalize.pkl'; "
                    "save_runtime(p, policy_io=make_policy_io(), loader=load_policy, "
                    "normalizer=load_observation_normalizer(p), stats_path=s if s.exists() else None); "
                    "r=load_runtime(p); "
                    "from robot_learning.benchmark.final_benchmark import official_environment; "
                    "e=official_environment(); e.reset(seed=0); "
                    "o=r.io.observe(e.data); "
                    "assert o.shape == r.observation_space.shape, 'Historical observation contract mismatches policy'; "
                    "r.predict(o); e.close()"
                ),
            ],
            cwd=checkout,
            check=True,
        )
        shutil.copytree(staging, destination)
    print(
        f"Migrated copy: {destination}\nScientific source: {commit}\nOriginal artifact unchanged."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--identity-actions", action="store_true")
    args = parser.parse_args()
    migrate(
        args.artifact,
        args.output,
        args.source_ref,
        identity_actions=args.identity_actions,
    )
