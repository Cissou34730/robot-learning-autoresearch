"""Private, recoverable delivery of a recipe and its best-known candidate, without development records or Git."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

from runner import paths, protocol, repository

_TRAINED_ARTIFACT_NAMES = {
    *repository.INFERENCE_ARTIFACT_FILES,
    *repository.OPTIONAL_ARTIFACT_FILES,
    *repository.SAVED_MODEL_MEMBERS.values(),
    repository.SAVED_COMPONENTS_FILE,
}
_TRAINED_ARTIFACT_SUFFIXES = {".pkl", ".pickle", ".pt", ".pth", ".ckpt", ".safetensors"}
LINEAGE_PATH = "campaigns/recipe_lineage.json"
_DEVELOPMENT_DIRECTORY_NAMES = {
    "variants",
    "lab",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "checkpoints",
    "training_logs",
    "evaluations",
    "tensorboard",
}


def is_recipe_source(relative: str) -> bool:
    source = Path(relative)
    return (
        relative.startswith("robot_learning/")
        and protocol.is_researcher_owned(relative)
        and not protocol.is_campaign_lab(relative)
        and not repository.is_runner_owned(relative)
        and not any(
            part.casefold() in _DEVELOPMENT_DIRECTORY_NAMES for part in source.parts
        )
        and source.suffix.lower()
        not in (*protocol.GENERATED_FILE_SUFFIXES, ".log", *_TRAINED_ARTIFACT_SUFFIXES)
        and source.name not in _TRAINED_ARTIFACT_NAMES
        and source.name not in {"training_metrics.json", "candidate_manifest.json"}
        and not source.name.startswith("events.out.tfevents.")
    )


def _variant_paths(
    state: dict, plan: dict, *, full_recipe: bool = False
) -> dict[str, str] | None:
    if (
        state["recipe_phase"] != "included"
        or state["campaign_phase"] != "recipe_development"
    ):
        return None
    candidate = state["candidates"][plan["candidate_id"]]
    event = next(
        (
            event
            for event in state["operation_events"]
            if event["id"] == candidate["origin_operation"]
        ),
        None,
    )
    if event is None or event["kind"] != "training":
        return None
    label = next(
        (
            variant["label"]
            for variant in event["request"].get("variants", [])
            if candidate["name"].startswith(variant["label"] + "-")
        ),
        None,
    )
    if label is None:
        return None
    selected = [*plan["restore"], *plan["remove_created"]]
    recorded = set(
        repository.git(
            "ls-tree", "-r", "--name-only", plan["parent"], "--", "robot_learning"
        ).splitlines()
    )
    prefix = f"robot_learning/variants/{label}/"
    if full_recipe:
        selected = sorted(
            {relative for relative in recorded if is_recipe_source(relative)}
            | {
                "robot_learning/" + relative.removeprefix(prefix)
                for relative in recorded
                if relative.startswith(prefix)
                and is_recipe_source("robot_learning/" + relative.removeprefix(prefix))
            }
        )
    mapping = {}
    for relative in selected:
        if relative in protocol.PARAMETER_ONLY_PATHS:
            continue
        if not is_recipe_source(relative):
            raise ValueError(
                f"restore path is not a learning-recipe source: {relative}"
            )
        overlay = (
            "robot_learning/variants/"
            + label
            + "/"
            + relative.removeprefix("robot_learning/")
        )
        if overlay in recorded:
            mapping[relative] = overlay
        elif relative in recorded:
            mapping[relative] = relative
    return mapping


def _recorded_source(commit: str, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=paths.ROOT,
        capture_output=True,
        check=True,
    )
    return result.stdout


def restore_variant(state: dict, plan: dict) -> bool:
    """Materialize the canonical files in the accepted variant restore plan."""
    mapping = _variant_paths(state, plan)
    if mapping is None:
        return False
    for relative in [*plan["restore"], *plan["remove_created"]]:
        if relative in protocol.PARAMETER_ONLY_PATHS:
            repository.atomic_write_json(paths.locate(relative), plan["parameters"])
        elif relative in mapping:
            repository.atomic_write_bytes(
                paths.locate(relative),
                _recorded_source(plan["parent"], mapping[relative]),
            )
        else:
            repository.remove_created_path(paths.locate(relative))
    return True


def variant_matches(state: dict, plan: dict) -> bool:
    mapping = _variant_paths(state, plan)
    if mapping is None:
        return repository.recipe_paths_match_commit(plan)
    for relative in [*plan["restore"], *plan["remove_created"]]:
        current = paths.locate(relative)
        if relative in protocol.PARAMETER_ONLY_PATHS:
            if json.loads(current.read_text(encoding="utf-8")) != plan["parameters"]:
                return False
        elif relative in mapping:
            if not current.is_file() or current.read_bytes() != _recorded_source(
                plan["parent"], mapping[relative]
            ):
                return False
        elif current.exists():
            return False
    return True


def require_deliverable_candidate(state: dict) -> None:
    """Refuse a development checkpoint whose canonical recipe is not the delivered one."""
    selected = state["model_roles"]["best_known"]
    if selected is None:
        raise ValueError(
            "The recipe-development checkpoint delivers the best-known candidate. "
            "Assign it with model_role set_best_known before the checkpoint."
        )
    plan = protocol.plan_recipe_restore(
        {"candidate": selected, "reason": "recipe delivery"}, state
    )
    if not variant_matches(state, plan):
        raise ValueError(
            "The canonical recipe differs from the recipe of the best-known "
            f"candidate {selected}. Restore that recipe with restore_recipe, or "
            "assign the best-known candidate whose recipe is canonical, before "
            "the checkpoint."
        )


def _candidate_measurements(state: dict, candidate_id: str) -> list[dict]:
    rows = []
    for event in state["operation_events"]:
        if event["kind"] != "measurement" or event["status"] != "completed":
            continue
        for measurement in (event["result"] or {}).get("measurements") or []:
            metrics = measurement.get("metrics") or {}
            if measurement.get("candidate") == candidate_id and "successes" in metrics:
                rows.append(
                    {
                        "operation": event["id"],
                        "instrument": measurement.get("instrument"),
                        "successes": metrics["successes"],
                        "episodes": metrics["episodes"],
                    }
                )
    return rows


def candidate_lineage(state: dict, candidate_id: str) -> dict:
    """The training chapters that produced a candidate, first chapter first."""
    chapters = []
    current = candidate_id
    while current is not None and all(
        chapter["candidate"] != current for chapter in chapters
    ):
        candidate = state["candidates"].get(current)
        event = next(
            (
                event
                for event in state["operation_events"]
                if candidate is not None
                and event["id"] == candidate["origin_operation"]
                and event["kind"] == "training"
                and event["status"] == "completed"
            ),
            None,
        )
        if event is None:
            break
        result = event["result"]
        variant = next(
            (
                entry
                for entry in result.get("variants") or []
                if candidate["name"].startswith(entry["label"] + "-")
            ),
            None,
        )
        parent = variant.get("parent") if variant else result.get("parent")
        changed = [
            entry["path"]
            for entry in (result.get("mechanical_provenance") or {}).get(
                "changed_files"
            )
            or []
        ]
        if variant is not None:
            own = f"robot_learning/variants/{variant['label']}/"
            changed = [
                path
                for path in changed
                if path.startswith(own)
                or not path.startswith("robot_learning/variants/")
            ]
        chapters.append(
            {
                "operation": event["id"],
                "variant": variant["label"] if variant else None,
                "initialization": result.get("initialization"),
                "parent": parent,
                "seed": result.get("seed"),
                "training_steps": candidate["training_steps"],
                "parameter_changes": (variant or {}).get("parameters") or {},
                "changed_files": changed,
                "candidate": current,
                "measurements": _candidate_measurements(state, current),
            }
        )
        current = parent
    chapters.reverse()
    return {"candidate": candidate_id, "chapters": chapters}


def _marker_path(root: Path) -> Path:
    return paths.recipe_handoff_directory(root) / "handoff.json"


def _require_separate_root(root: Path) -> None:
    harness = paths.HARNESS_ROOT.resolve()
    if root == harness or root.is_relative_to(harness) or harness.is_relative_to(root):
        raise RuntimeError(
            "Isolated recipe delivery requires a separate campaign repository."
        )
    private = paths.recipe_handoff_directory(root)
    if private.is_relative_to(harness) or private.is_relative_to(root):
        raise RuntimeError("Recipe delivery archive must be outside both repositories.")


def _build_public_tree(root: Path, staged: Path, state: dict, parameters: dict) -> str:
    from tools.initialize_campaign import CAMPAIGN_GITIGNORE

    staged.mkdir(parents=True)
    package = root / "robot_learning"
    for source in package.rglob("*"):
        relative = source.relative_to(package)
        if any(part in _DEVELOPMENT_DIRECTORY_NAMES for part in relative.parts):
            continue
        if source.is_symlink():
            raise RuntimeError("Delivered recipe source cannot contain symbolic links.")
    commit = state["recipe_development"]["scientific_commit"]
    recorded = repository.git(
        "ls-tree", "-r", "--name-only", "-z", commit, "--", "robot_learning"
    ).split("\0")
    for logical in recorded:
        if not logical or not (
            protocol.is_researcher_owned(logical)
            or logical in protocol.PROTECTED_BENCHMARK_PATHS
        ):
            continue
        relative = Path(logical).relative_to("robot_learning")
        if any(part in _DEVELOPMENT_DIRECTORY_NAMES for part in relative.parts):
            continue
        source = root / logical
        if (
            source.suffix in (*protocol.GENERATED_FILE_SUFFIXES, ".log")
            or source.name in {"training_metrics.json", "candidate_manifest.json"}
            or source.name.startswith("events.out.tfevents.")
        ):
            continue
        if (
            source.name in _TRAINED_ARTIFACT_NAMES
            or source.suffix.lower() in _TRAINED_ARTIFACT_SUFFIXES
        ):
            raise RuntimeError(
                f"Canonical recipe contains an excluded trained artifact: {logical}; "
                "recipe delivery cannot preserve trained-artifact dependencies."
            )
        repository.require_path_at_commit(commit, logical)
        if source.stat().st_nlink != 1:
            raise RuntimeError("Delivered recipe source cannot contain hard links.")
        target = staged / logical
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    repository.atomic_write_json(
        staged / "robot_learning/training/current_params.json", parameters
    )
    model = root / state["scientific_model"]["path"]
    repository.require_path_at_commit(
        state["scientific_model"]["commit"], state["scientific_model"]["path"]
    )
    target_model = staged / state["scientific_model"]["path"]
    target_model.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(model, target_model)
    repository.atomic_write_text(staged / ".gitignore", CAMPAIGN_GITIGNORE)
    for directory in ("reports/session_usage", "reports/tui_observations"):
        source = root / directory
        if source.is_dir():
            shutil.copytree(source, staged / directory)

    def git(*arguments: str) -> str:
        return repository._git_at(
            staged, ("-c", f"safe.directory={staged}", *arguments)
        )

    git("init", "--quiet", "--initial-branch=recipe")
    for field in ("user.name", "user.email"):
        git("config", field, repository.git("config", "--get", field).strip())
    git("config", "commit.gpgsign", "false")
    git("config", "core.hooksPath", ".disabled-hooks")
    git("add", "--", ".gitignore", "robot_learning", "pi_workspace/scientific_model.md")
    git(
        "commit",
        "--quiet",
        "-m",
        repository.campaign_commit_message("delivered recipe"),
    )
    recipe_commit = git("rev-parse", "HEAD").strip()
    fresh = repository.empty_campaign_state(
        campaign={
            **copy.deepcopy(state["campaign"]),
            "base_commit": recipe_commit,
            "recipe_source_commit": recipe_commit,
        },
        human_goal=state["human_goal"],
        last_verdict="Recipe delivered; startup is ready.",
    )
    fresh["campaign_phase"] = "startup"
    fresh["scientific_model"] = {**state["scientific_model"], "commit": recipe_commit}
    fresh["recipe_handover"] = {
        name: state["recipe_development"][name]
        for name in repository.RECIPE_HANDOVER_FIELDS
    }
    delivered: list[str] = []
    selected = state["model_roles"]["best_known"]
    if selected is not None:
        candidate = copy.deepcopy(state["candidates"][selected])
        source_artifact = repository.resolve_repo_path(candidate["artifact"])
        repository.require_complete_inference_artifact(
            source_artifact, f"delivered candidate {selected}"
        )
        if repository.artifact_fingerprint(source_artifact) != candidate["fingerprint"]:
            raise RuntimeError(f"Delivered candidate {selected} fingerprint changed.")
        repository.copy_artifact(source_artifact, staged / candidate["artifact"])
        # The delivered recipe commit is this candidate's recipe; the checkpoint
        # refused any other canonical recipe.
        candidate.update(scientific_commit=recipe_commit, evaluation_artifacts=[])
        fresh["candidates"] = {selected: candidate}
        fresh["model_roles"] = {
            "working": selected,
            "best_known": selected,
            "retained": {},
        }
        fresh["counters"]["training"] = int(candidate["origin_operation"][1:])
        repository.atomic_write_json(
            staged / LINEAGE_PATH, candidate_lineage(state, selected)
        )
        delivered = [candidate["artifact"], LINEAGE_PATH]
    repository.validate_research_state(fresh, allow_missing_artifact=True)
    repository.atomic_write_json(staged / "runner/state/research_state.json", fresh)
    repository.atomic_write_text(staged / "campaigns/results.jsonl", "")
    repository.atomic_write_text(staged / "campaigns/EXPERIMENTS.md", "")
    git(
        "add",
        "--",
        "runner/state/research_state.json",
        "campaigns/results.jsonl",
        "campaigns/EXPERIMENTS.md",
    )
    if delivered:
        git("add", "-f", "--", *delivered)
    git("commit", "--quiet", "-m", repository.campaign_commit_message("fresh startup"))

    # Keep starting references, but never later development history.
    def tags(*selection: str) -> set[str]:
        return set(
            repository.git(
                "for-each-ref", "--format=%(refname)", *selection, "refs/tags"
            ).split()
        )

    base = state["campaign"]["base_commit"]
    development_tags = tags("--contains", base) - tags("--points-at", base)
    references = sorted(tags() - development_tags)
    if references:
        git(
            "-c",
            f"safe.directory={root}",
            "fetch",
            "--quiet",
            "--no-tags",
            str(root),
            *(f"{reference}:{reference}" for reference in references),
        )
    return git("rev-parse", "HEAD").strip()


def _finish_swap(root: Path, marker: dict) -> None:
    archive = paths.recipe_development_archive(root, marker["campaign_id"])
    staged = archive.parent / "public"
    if not archive.exists():
        if (
            repository._git_at(root, ("rev-parse", "HEAD")).strip()
            != marker["development_head"]
        ):
            raise RuntimeError("Development repository changed during recipe delivery.")
        root.replace(archive)
    if not root.exists():
        staged.replace(root)
    if repository._git_at(root, ("rev-parse", "HEAD")).strip() != marker["public_head"]:
        raise RuntimeError("Recipe delivery has an unexpected public repository.")
    marker["stage"] = "published"
    repository.atomic_write_json(_marker_path(root), marker)


def _previous_delivery(root: Path) -> dict | None:
    marker_path = _marker_path(root)
    if not marker_path.is_file():
        return None
    return json.loads(marker_path.read_text(encoding="utf-8"))


def require_no_unfinished_swap(root: Path) -> None:
    """A reset must not start while this folder's delivery swap is unfinished."""
    marker = _previous_delivery(root.resolve())
    if marker is not None and marker.get("stage") in {"preparing", "ready"}:
        raise RuntimeError(
            f"Recipe delivery of campaign {marker.get('campaign_id')} is unfinished "
            f"({marker.get('stage')}). Finish it before resetting: with "
            "ROBOT_LEARNING_CAMPAIGN_ROOT set to this folder, run "
            "`uv run python -m runner.recipe_development` from the harness."
        )


def abandon_queued_delivery(root: Path) -> None:
    """A reset discards the campaign whose delivery was only queued."""
    root = root.resolve()
    marker = _previous_delivery(root)
    if marker is None or marker.get("stage") != "awaiting_session_end":
        return
    marker_path = _marker_path(root)
    campaign_id = marker.get("campaign_id") or "unknown"
    marker_path.replace(marker_path.with_name(f"handoff.abandoned-{campaign_id}.json"))


def recovery_pending(campaign_root: Path) -> bool:
    root = campaign_root.resolve()
    marker_path = _marker_path(root)
    if not marker_path.is_file():
        return False
    _require_separate_root(root)
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("root") != str(root) or marker.get("version") != 1:
        raise RuntimeError(
            "Recipe delivery recovery record does not match the campaign root."
        )
    stage = marker.get("stage")
    if stage not in {"awaiting_session_end", "preparing", "ready", "published"}:
        raise RuntimeError("Unsupported recipe delivery recovery stage.")
    if not root.exists():
        campaign_id = marker.get("campaign_id")
        if not isinstance(campaign_id, str) or not campaign_id:
            raise RuntimeError("Recipe delivery recovery requires a campaign identity.")
        archive = paths.recipe_development_archive(root, campaign_id)
        if (
            stage != "ready"
            or not marker.get("public_head")
            or not archive.is_dir()
            or not (archive.parent / "public" / ".git").is_dir()
        ):
            raise RuntimeError(
                "Recipe delivery recovery has no staged public repository."
            )
    return stage in {"preparing", "ready"}


def recover(campaign_root: Path | None = None) -> bool:
    """Finish a staged directory swap before any public state or Git is read."""
    root = (campaign_root or paths.ROOT).resolve()
    marker_path = _marker_path(root)
    if not marker_path.is_file():
        return False
    _require_separate_root(root)
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("root") != str(root) or marker.get("version") != 1:
        raise RuntimeError(
            "Recipe delivery recovery record does not match the campaign root."
        )
    if marker["stage"] == "published":
        return False
    if marker["stage"] == "awaiting_session_end":
        return False
    if marker["stage"] == "preparing":
        if root != paths.ROOT.resolve():
            raise RuntimeError(
                "Preparing recipe recovery requires the selected campaign root."
            )
        publish(repository.read_state(), marker["parameters"])
    elif marker["stage"] == "ready":
        _finish_swap(root, marker)
    else:
        raise RuntimeError("Unsupported recipe delivery recovery stage.")
    return True


def _delivery_inputs(state: dict, *, finalized: bool = False) -> dict:
    committed = repository.read_committed_state("HEAD")
    checkpoint = state["recipe_development"]
    if (
        repository.current_campaign_id(committed)
        != repository.current_campaign_id(state)
        or committed["recipe_development"] != checkpoint
        or committed["scientific_model"] != state["scientific_model"]
    ):
        raise RuntimeError("Recipe delivery checkpoint does not match versioned state.")
    event = next(
        (
            event
            for event in committed["operation_events"]
            if event["kind"] == "checkpoint"
            and event["session_id"] == checkpoint["session_id"]
            and event["status"] == "completed"
        ),
        None,
    )
    if event is None:
        raise RuntimeError("Recipe delivery has no versioned checkpoint operation.")
    pending = committed["pending_operation"]
    if finalized and pending is not None:
        raise RuntimeError("Recipe delivery checkpoint is not finalized in Git.")
    if pending is None and repository.git("log", "-1", "--format=%s").strip() == (
        repository.campaign_commit_message(f"finalize {event['id']}")
    ):
        previous = repository.read_committed_state("HEAD^")
        if previous["recipe_development"] != checkpoint:
            raise RuntimeError("Recipe delivery finalized a different checkpoint.")
        pending = previous["pending_operation"]
    if pending is not None:
        if (
            pending["id"] != event["id"]
            or pending["kind"] != "checkpoint"
            or pending["progress"] != "completed"
            or pending["session_id"] != checkpoint["session_id"]
            or pending["data"]["scientific_commit"] != checkpoint["scientific_commit"]
        ):
            raise RuntimeError("Recipe delivery has no matching frozen checkpoint.")
        parameters = pending["data"]["effective_parameters"]
    else:
        parameters = json.loads(
            _recorded_source(
                checkpoint["scientific_commit"],
                "robot_learning/training/current_params.json",
            )
        )
    return {
        "campaign_id": repository.current_campaign_id(committed),
        "checkpoint_operation": event["id"],
        "checkpoint_session": checkpoint["session_id"],
        "scientific_commit": checkpoint["scientific_commit"],
        "scientific_model_commit": state["scientific_model"]["commit"],
        "parameters": copy.deepcopy(parameters),
    }


def _validate_marker(marker: dict, inputs: dict, head: str) -> None:
    if (
        marker.get("version") != 1
        or marker.get("root") != str(paths.ROOT.resolve())
        or marker.get("stage")
        not in {"awaiting_session_end", "preparing", "ready", "published"}
        or any(marker.get(key) != value for key, value in inputs.items())
    ):
        raise RuntimeError("Recipe delivery inputs changed during preparation.")
    if marker["development_head"] != head and (
        marker["stage"] != "awaiting_session_end"
        or repository.git("rev-parse", "HEAD^").strip() != marker["development_head"]
        or repository.git("log", "-1", "--format=%s").strip()
        != repository.campaign_commit_message(
            f"finalize {inputs['checkpoint_operation']}"
        )
    ):
        raise RuntimeError("Recipe delivery inputs changed during preparation.")


def queue(state: dict, parameters: dict) -> None:
    """Keep delivery inputs durable while the development invocation finishes."""
    if state["recipe_development"] is None:
        return
    root = paths.ROOT.resolve()
    _require_separate_root(root)
    inputs = _delivery_inputs(state)
    if inputs["parameters"] != parameters:
        raise RuntimeError("Recipe delivery parameters do not match the checkpoint.")
    head = repository.git("rev-parse", "HEAD").strip()
    marker_path = _marker_path(root)
    if marker_path.exists():
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker.get("campaign_id") == inputs["campaign_id"]:
            _validate_marker(marker, inputs, head)
            if marker["stage"] != "awaiting_session_end":
                raise RuntimeError("Recipe delivery is already being published.")
        elif marker.get("stage") != "published":
            raise RuntimeError("Another recipe delivery remains unfinished.")
    repository.atomic_write_json(
        marker_path,
        {
            "version": 1,
            "root": str(root),
            **inputs,
            "development_head": head,
            "stage": "awaiting_session_end",
        },
    )


def deliver() -> bool:
    """Publish the queued recipe after its backend invocation has closed."""
    state = repository.load_state(allow_missing_artifact=True)
    if state["recipe_development"] is None:
        return False
    pending = state["pending_operation"]
    if pending is not None:
        from runner import run_experiment

        if run_experiment._recipe_checkpoint_finalized_in_git(state, pending):
            run_experiment._finalize_operation(state, pending)
    return publish(state, _delivery_inputs(state, finalized=True)["parameters"])


def publish(state: dict, parameters: dict) -> bool:
    """Mechanically deliver the active recipe after its checkpoint is finalized."""
    if state["recipe_development"] is None:
        return False
    if (
        state["pending_operation"] is not None
        or state["scientific_session"] is not None
    ):
        raise RuntimeError(
            "Recipe delivery requires a fully finalized development checkpoint."
        )
    if (
        state["campaign_phase"] != "startup"
        or state["scientific_model"]["status"] != "ready"
    ):
        raise RuntimeError(
            "Recipe delivery requires the accepted development boundary."
        )
    repository.validate_research_state(state, allow_missing_artifact=True)
    root = paths.ROOT.resolve()
    _require_separate_root(root)
    if not (root / ".git").is_dir():
        raise RuntimeError(
            "Isolated recipe delivery requires self-contained campaign Git."
        )
    if (root / ".git/objects/info/alternates").exists():
        raise RuntimeError(
            "Isolated recipe delivery cannot archive borrowed Git objects."
        )
    campaign_id = repository.current_campaign_id(state)
    inputs = _delivery_inputs(state, finalized=True)
    if inputs["parameters"] != parameters:
        raise RuntimeError("Recipe delivery parameters do not match the checkpoint.")
    head = repository.git("rev-parse", "HEAD").strip()
    archive = paths.recipe_development_archive(root, campaign_id)
    marker_path = _marker_path(root)
    if marker_path.exists():
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker.get("campaign_id") == campaign_id:
            _validate_marker(marker, inputs, head)
            if marker["stage"] == "published":
                return False
            if marker["stage"] == "ready":
                _finish_swap(root, marker)
                return True
        elif marker.get("stage") != "published":
            raise RuntimeError("Another recipe delivery remains unfinished.")
    if archive.exists():
        raise RuntimeError(
            "Recipe development archive already exists without a completed handoff."
        )
    staged = archive.parent / "public"
    marker = {
        "version": 1,
        "root": str(root),
        **inputs,
        "development_head": head,
        "stage": "preparing",
    }
    repository.atomic_write_json(marker_path, marker)
    if staged.exists():
        for file in staged.rglob("*"):
            if file.is_file():
                file.chmod(0o600)
        shutil.rmtree(staged)
    marker["public_head"] = _build_public_tree(root, staged, state, parameters)
    marker["stage"] = "ready"
    repository.atomic_write_json(marker_path, marker)
    _finish_swap(root, marker)
    return True


if __name__ == "__main__":
    recover()
