"""Human-only factual report for strict schema-6 campaigns."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from runner import repository as runner_repository

ROOT = Path(__file__).resolve().parents[1]
NA = "unavailable"


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"{path}: required schema-6 state is missing")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError(f"{path}: expected a JSON object")
    return value


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{number}: invalid JSON: {error.msg}") from error
        if not isinstance(value, dict):
            raise TypeError(f"{path}:{number}: expected a JSON object")
        rows.append(value)
    return rows


def require_fields(value: object, fields: set[str], description: str) -> dict:
    if not isinstance(value, dict):
        raise TypeError(f"{description} must be an object")
    missing = fields - set(value)
    extra = set(value) - fields
    if missing or extra:
        raise ValueError(
            f"{description} fields are invalid: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    return value


def cell(value: object) -> str:
    if value is None or value == "":
        value = NA
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return " ".join(str(value).split()).replace("|", "\\|")


def table(headers: list[str], rows: list[list[object]]) -> list[str]:
    rendered = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    rendered.extend(
        "| " + " | ".join(cell(value) for value in row) + " |" for row in rows
    )
    if not rows:
        rendered.append("| " + " | ".join("none" for _ in headers) + " |")
    return [*rendered, ""]


def number(value: object, suffix: str = "") -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return NA
    return f"{value:,.2f}{suffix}"


def short_commit(value: object) -> str:
    return str(value)[:12] if value else NA


def usage_total(rows: list[dict], field: str) -> str:
    values = [
        row[field]
        for row in rows
        if isinstance(row.get(field), (int, float))
        and not isinstance(row.get(field), bool)
    ]
    if not values:
        return NA
    rendered = number(sum(values))
    if len(values) != len(rows):
        return f"{rendered} (partial: {len(values)}/{len(rows)} invocations)"
    return rendered


def load_campaign(repo: Path, campaign_id: str | None = None) -> dict:
    state = read_json(repo / "runner" / "state" / "research_state.json")
    runner_repository.validate_research_state(state, allow_missing_artifact=True)
    current_id = str(state["campaign"]["id"])
    if campaign_id is not None and campaign_id != current_id:
        raise ValueError(
            f"requested campaign {campaign_id!r} is not the current schema-6 "
            f"campaign {current_id!r} in {repo}"
        )

    history = read_rows(repo / "campaigns" / "results.jsonl")
    history_events: list[dict] = []
    history_ids: set[str] = set()
    for index, row in enumerate(history, 1):
        fields = set(runner_repository.EVENT_FIELDS) | {"campaign_id"}
        row = require_fields(row, fields, f"results row {index}")
        if row["campaign_id"] != current_id:
            raise ValueError(
                f"results row {index} belongs to foreign campaign "
                f"{row['campaign_id']!r}"
            )
        if row["id"] in history_ids:
            raise ValueError(f"duplicate results operation event id: {row['id']}")
        history_ids.add(row["id"])
        history_events.append(
            {field: row[field] for field in runner_repository.EVENT_FIELDS}
        )
    if history_events != state["operation_events"]:
        raise ValueError(
            "results.jsonl does not exactly match operation_events in order and content"
        )

    usage = [
        row
        for row in read_rows(repo / "reports" / "session_usage" / f"{current_id}.jsonl")
        if row.get("campaign_id") == current_id
    ]
    return {
        "repo": repo,
        "id": current_id,
        "state": state,
        "events": list(state["operation_events"]),
        "usage": usage,
    }


def completed_events(campaign: dict, kind: str | None = None) -> list[dict]:
    return [
        event
        for event in campaign["events"]
        if event["status"] == "completed" and (kind is None or event["kind"] == kind)
    ]


def failed_events(campaign: dict) -> list[dict]:
    return [event for event in campaign["events"] if event["status"] == "failed"]


def inquiry_records(campaign: dict) -> list[dict]:
    inquiries: dict[str, dict] = {}
    for event in completed_events(campaign, "inquiry"):
        request = event["request"]
        result = event["result"]
        inquiry_id = result["inquiry_id"]
        action = result["action"]
        if action == "open":
            inquiries[inquiry_id] = {
                "id": inquiry_id,
                "status": "open",
                "question": request["question"],
                "goal_connection": request["goal_connection"],
                "closure_condition": request["closure_condition"],
                "opened_session": event["session_id"],
                "reframes": 0,
                "outcome": None,
                "reason": None,
            }
        elif action == "reframe":
            record = inquiries.setdefault(inquiry_id, {"id": inquiry_id})
            record.update(
                question=request["question"],
                goal_connection=request["goal_connection"],
                closure_condition=request["closure_condition"],
            )
            record["reframes"] = int(record.get("reframes", 0)) + 1
        else:
            record = inquiries.setdefault(inquiry_id, {"id": inquiry_id})
            record.update(
                status="closed",
                outcome=result["outcome"],
                reason=result["reason"],
            )
    active = campaign["state"]["active_inquiry"]
    if isinstance(active, dict):
        record = inquiries.setdefault(active["id"], {"id": active["id"]})
        record.update(
            status="active",
            question=active["question"],
            goal_connection=active["goal_connection"],
            closure_condition=active["closure_condition"],
            opened_session=active["opened_in_session"],
            reframes=len(active["reframes"]),
        )
    return sorted(inquiries.values(), key=lambda item: item["id"])


def session_records(campaign: dict) -> list[dict]:
    sessions: dict[str, dict] = {}
    for event in campaign["events"]:
        record = sessions.setdefault(
            event["session_id"],
            {
                "id": event["session_id"],
                "inquiry_id": event["inquiry_id"],
                "operations": [],
                "completed": 0,
                "failed": 0,
                "checkpoint": None,
                "active": False,
                "kind": None,
                "objective": None,
                "backend": None,
            },
        )
        record["operations"].append(event["id"])
        record[event["status"]] += 1
        if event["kind"] == "checkpoint" and event["status"] == "completed":
            record["checkpoint"] = event["id"]
    active = campaign["state"]["scientific_session"]
    if isinstance(active, dict):
        record = sessions.setdefault(
            active["id"],
            {
                "id": active["id"],
                "inquiry_id": active["inquiry_id"],
                "operations": list(active["operation_ids"]),
                "completed": 0,
                "failed": 0,
                "checkpoint": None,
                "active": True,
                "kind": active["kind"],
                "objective": active["objective"],
                "backend": active["backend_descriptor"],
            },
        )
        record.update(
            active=True,
            kind=active["kind"],
            objective=active["objective"],
            backend=active["backend_descriptor"],
        )
    return sorted(sessions.values(), key=lambda item: item["id"])


def operation_summary(event: dict) -> str:
    request = event["request"]
    result = event["result"]
    kind = event["kind"]
    if event["status"] == "failed":
        return str(event["error"])
    if kind == "measurement":
        return (
            f"{len(result['measurements'])} measurements; "
            f"{len(result['paired_comparisons'])} paired comparisons"
        )
    if kind == "training":
        return (
            f"{result['initialization']}; {result['completed_steps']}/"
            f"{result['requested_steps']} steps; {len(result['candidates'])} candidates"
        )
    if kind == "inquiry":
        return f"{result['action']} {result['inquiry_id']}"
    if kind == "checkpoint":
        return f"checkpointed {result['session_id']}"
    if kind == "model_role":
        return f"{result['action']} {result['candidate']}"
    if kind == "restore_recipe":
        return f"restored {result['candidate']} from {short_commit(result['scientific_commit'])}"
    return f"{result['status']}; model {result['model'] or 'none'}; {request['reason']}"


def operation_decision_rows(campaign: dict) -> list[list[object]]:
    return [
        [
            event["id"],
            event["kind"],
            event["status"],
            event["request"].get("description"),
            event["request"].get("rationale"),
            event["request"].get("reason"),
        ]
        for event in campaign["events"]
    ]


def checkpoint_history_rows(campaign: dict) -> list[list[object]]:
    rows: list[list[object]] = []
    for event in completed_events(campaign, "checkpoint"):
        checkpoint = event["request"]
        rows.append(
            [
                event["id"],
                event["session_id"],
                event["inquiry_id"],
                event["completed_at"],
                checkpoint["human_goal_connection"],
                checkpoint["current_goal_gap"],
                checkpoint["current_synthesis"],
                ", ".join(checkpoint["evidence_references"]),
                ", ".join(checkpoint["completed_operations"]),
                checkpoint["candidates_and_roles"],
                checkpoint["decision_frontier"],
                checkpoint["next_direction_or_closure"],
                checkpoint["cumulative_resource_use"],
            ]
        )
    return rows


def measurement_rows(campaign: dict) -> list[list[object]]:
    rows: list[list[object]] = []
    for event in completed_events(campaign, "measurement"):
        for measurement in event["result"]["measurements"]:
            metrics = measurement["metrics"]
            subject = measurement.get("candidate") or measurement.get("module")
            panel = (
                f"{metrics.get('panel', 'seed')}={metrics.get('seed', NA)}; "
                f"episodes={metrics.get('episodes', NA)}; "
                f"version={metrics.get('panel_version', NA)}; "
                f"semantics={metrics.get('evaluation_semantics', NA)}"
            )
            rows.append(
                [
                    event["id"],
                    event["session_id"],
                    event["inquiry_id"],
                    measurement["instrument"],
                    subject,
                    measurement["label"],
                    panel,
                    number(metrics.get("success_percent"), "%"),
                    metrics.get("evaluation_artifact"),
                ]
            )
    return rows


def panel_reuse_rows(campaign: dict) -> list[list[object]]:
    groups: dict[tuple[object, ...], list[tuple[str, str, str]]] = defaultdict(list)
    for event in completed_events(campaign, "measurement"):
        for measurement in event["result"]["measurements"]:
            if measurement["instrument"] not in {
                "research_evaluation",
                "task_reference",
            }:
                continue
            metrics = measurement["metrics"]
            key = (
                measurement["instrument"],
                metrics.get("panel"),
                metrics.get("panel_version"),
                metrics.get("seed"),
                metrics.get("episodes"),
                metrics.get("evaluation_semantics"),
            )
            groups[key].append(
                (
                    event["id"],
                    measurement["candidate"],
                    metrics["evaluation_artifact"],
                )
            )
    return [
        [
            *key,
            len(executions),
            len({candidate for _, candidate, _ in executions}),
            ", ".join(operation for operation, _, _ in executions),
            "yes" if len(executions) > 1 else "no",
        ]
        for key, executions in groups.items()
    ]


def training_rows(campaign: dict) -> list[list[object]]:
    rows = []
    for event in completed_events(campaign, "training"):
        result = event["result"]
        dynamics = "; ".join(
            (
                f"{item['candidate']}: steps={item['training_steps']}, "
                f"success={number(item['training_success'])}, "
                f"reward={number(item['ep_rew_mean'])}"
            )
            for item in result["learning_dynamics"]
        )
        rows.append(
            [
                event["id"],
                event["session_id"],
                event["inquiry_id"],
                result["initialization"],
                result["parent"],
                result["seed"],
                result["requested_steps"],
                result["completed_steps"],
                short_commit(result["scientific_commit"]),
                dynamics,
            ]
        )
    return rows


def candidate_rows(campaign: dict) -> list[list[object]]:
    state = campaign["state"]
    roles = state["model_roles"]
    labels: dict[str, list[str]] = defaultdict(list)
    for role in ("working", "best_known"):
        if roles[role]:
            labels[roles[role]].append(role)
    for label, candidate_id in roles["retained"].items():
        labels[candidate_id].append(f"retained:{label}")
    return [
        [
            candidate_id,
            candidate["origin_operation"],
            candidate["name"],
            candidate["training_steps"],
            ", ".join(labels[candidate_id]) or "available",
            candidate["artifact"],
            candidate["fingerprint"],
            short_commit(candidate["scientific_commit"]),
            len(candidate["evaluation_artifacts"]),
        ]
        for candidate_id, candidate in sorted(state["candidates"].items())
    ]


def resource_metrics(campaign: dict) -> dict[str, str]:
    usage = campaign["usage"]
    derived = []
    for row in usage:
        item = dict(row)
        inputs = row.get("input_tokens")
        outputs = row.get("output_tokens")
        cached = row.get("cache_read_tokens")
        item["total_tokens"] = (
            inputs + outputs
            if isinstance(inputs, (int, float)) and isinstance(outputs, (int, float))
            else None
        )
        item["new_input_tokens"] = (
            inputs - cached
            if isinstance(inputs, (int, float)) and isinstance(cached, (int, float))
            else None
        )
        derived.append(item)
    return {
        "Recorded PI invocations": str(len(usage)),
        "Backend sessions": str(len({row.get("session_id") for row in usage})),
        "Models / reasoning": "; ".join(
            f"{model} / {reasoning}: {count}"
            for (model, reasoning), count in Counter(
                (row.get("model", NA), row.get("reasoning", NA)) for row in usage
            ).items()
        )
        or NA,
        "Total tokens (input + output)": usage_total(derived, "total_tokens"),
        "Input tokens (includes cache reads)": usage_total(usage, "input_tokens"),
        "Cache-read tokens (subset of input)": usage_total(usage, "cache_read_tokens"),
        "New input tokens (input minus cache reads)": usage_total(
            derived, "new_input_tokens"
        ),
        "Output tokens": usage_total(usage, "output_tokens"),
        "AIU": usage_total(usage, "aiu"),
        "Tool calls": usage_total(usage, "tool_calls"),
        "PI duration, seconds": usage_total(usage, "duration_seconds"),
        "Nonzero exits": str(sum(row.get("exit_code", 0) != 0 for row in usage)),
    }


def comparison_metrics(campaign: dict) -> dict[str, str]:
    completed = completed_events(campaign)
    failed = failed_events(campaign)
    state = campaign["state"]
    return {
        "Campaign started": cell(state["campaign"]["started_at"]),
        "Completed evidence events": str(len(completed)),
        "Failed execution attempts": str(len(failed)),
        "Superseded failed attempts": str(
            sum(event["superseded_by"] is not None for event in failed)
        ),
        "Completed measurements": str(
            sum(
                len(event["result"]["measurements"])
                for event in completed_events(campaign, "measurement")
            )
        ),
        "Completed training operations": str(
            len(completed_events(campaign, "training"))
        ),
        "Candidates": str(len(state["candidates"])),
        "Inquiries opened": str(
            sum(
                event["result"].get("action") == "open"
                for event in completed_events(campaign, "inquiry")
            )
        ),
        "Scientific sessions observed": str(len(session_records(campaign))),
        "Terminal state": cell(
            state["terminal_state"]["status"] if state["terminal_state"] else None
        ),
        "PI invocations": str(len(campaign["usage"])),
        "PI duration, seconds": usage_total(campaign["usage"], "duration_seconds"),
    }


def campaign_sections(campaign: dict) -> list[str]:
    state = campaign["state"]
    campaign_state = state["campaign"]
    terminal = state["terminal_state"]
    assessment = state["official_assessment"]
    lines = [
        f"## Campaign `{campaign['id']}`",
        "",
        f"Repository: `{campaign['repo']}`",
        "",
        "### Campaign state",
        "",
    ]
    lines += table(
        ["Fact", "Persisted value"],
        [
            ["Started", campaign_state["started_at"]],
            ["Base commit", campaign_state["base_commit"]],
            ["Recipe source commit", campaign_state["recipe_source_commit"]],
            ["Max inquiries", campaign_state["max_inquiries"]],
            ["Human goal source", state["human_goal"]["source"]],
            ["Scientific model status", state["scientific_model"]["status"]],
            ["Scientific model commit", state["scientific_model"]["commit"]],
            ["Last verdict", state["last_verdict"]],
            [
                "Counters",
                "; ".join(f"{key}={value}" for key, value in state["counters"].items()),
            ],
        ],
    )
    lines += ["### Current inquiry, session, and operation", ""]
    active_inquiry = state["active_inquiry"]
    active_session = state["scientific_session"]
    pending = state["pending_operation"]
    lines += table(
        ["Object", "Identity", "State", "Details"],
        [
            [
                "Inquiry",
                active_inquiry.get("id") if active_inquiry else None,
                "active" if active_inquiry else "none",
                active_inquiry.get("question") if active_inquiry else None,
            ],
            [
                "Scientific session",
                active_session.get("id") if active_session else None,
                active_session.get("kind") if active_session else "none",
                active_session.get("objective") if active_session else None,
            ],
            [
                "Runner operation",
                pending.get("id") if pending else None,
                pending.get("progress") if pending else "none",
                (
                    f"{pending['kind']}; failure={pending['failure'] or 'none'}"
                    if pending
                    else None
                ),
            ],
        ],
    )

    lines += ["### Inquiries", ""]
    lines += table(
        [
            "Inquiry",
            "Status",
            "Question",
            "Goal connection",
            "Closure condition",
            "Opened session",
            "Reframes",
            "Outcome",
            "Closure reason",
        ],
        [
            [
                item.get("id"),
                item.get("status"),
                item.get("question"),
                item.get("goal_connection"),
                item.get("closure_condition"),
                item.get("opened_session"),
                item.get("reframes", 0),
                item.get("outcome"),
                item.get("reason"),
            ]
            for item in inquiry_records(campaign)
        ],
    )

    lines += ["### Scientific sessions", ""]
    lines += table(
        [
            "Session",
            "Active",
            "Kind",
            "Inquiry",
            "Completed",
            "Failed",
            "Operations",
            "Checkpoint",
            "Objective",
            "Backend descriptor",
        ],
        [
            [
                item["id"],
                "yes" if item["active"] else "no",
                item["kind"],
                item["inquiry_id"],
                item["completed"],
                item["failed"],
                ", ".join(item["operations"]),
                item["checkpoint"],
                item["objective"],
                item["backend"],
            ]
            for item in session_records(campaign)
        ],
    )

    lines += [
        "### Operation decisions",
        "",
        (
            "Persisted operation descriptions, rationales, and reasons are shown "
            "verbatim; unavailable fields were not part of that operation request."
        ),
        "",
    ]
    lines += table(
        ["Operation", "Kind", "Status", "Description", "Rationale", "Reason"],
        operation_decision_rows(campaign),
    )

    lines += ["### Checkpoint history", ""]
    lines += table(
        [
            "Operation",
            "Session",
            "Inquiry",
            "Completed at",
            "Human-goal connection",
            "Current goal gap",
            "Current synthesis",
            "Evidence references",
            "Completed operations",
            "Candidates and roles",
            "Decision frontier",
            "Next direction or closure",
            "Cumulative resource use",
        ],
        checkpoint_history_rows(campaign),
    )

    lines += [
        "### Completed operation evidence",
        "",
        "Only events persisted with `status=completed` are listed in this evidence table.",
        "",
    ]
    lines += table(
        [
            "Operation",
            "Kind",
            "Session",
            "Inquiry",
            "Supersedes",
            "Completed at",
            "Factual result",
        ],
        [
            [
                event["id"],
                event["kind"],
                event["session_id"],
                event["inquiry_id"],
                event["supersedes"],
                event["completed_at"],
                operation_summary(event),
            ]
            for event in completed_events(campaign)
        ],
    )
    lines += [
        "### Failed and superseded execution history",
        "",
        "These attempts are execution history and are not counted as completed evidence.",
        "",
    ]
    lines += table(
        [
            "Operation",
            "Kind",
            "Session",
            "Inquiry",
            "Error",
            "Superseded by",
            "Completed at",
        ],
        [
            [
                event["id"],
                event["kind"],
                event["session_id"],
                event["inquiry_id"],
                event["error"],
                event["superseded_by"],
                event["completed_at"],
            ]
            for event in failed_events(campaign)
        ],
    )

    lines += ["### Completed measurements", ""]
    lines += table(
        [
            "Operation",
            "Session",
            "Inquiry",
            "Instrument",
            "Candidate / module",
            "Label",
            "Panel identity",
            "Success",
            "Artifact",
        ],
        measurement_rows(campaign),
    )
    lines += [
        "#### Development-panel reuse accounting",
        "",
        (
            "Rows group identical recorded panel identities. Reuse is a factual "
            "execution count; this report makes no independence or quality judgment."
        ),
        "",
    ]
    lines += table(
        [
            "Instrument",
            "Panel",
            "Panel version",
            "Seed",
            "Episodes",
            "Evaluation semantics",
            "Executions",
            "Candidates",
            "Operations",
            "Repeated",
        ],
        panel_reuse_rows(campaign),
    )
    comparisons = [
        [
            event["id"],
            comparison["candidate"],
            comparison["reference"],
            comparison["episodes"],
            comparison["candidate_wins"],
            comparison["reference_wins"],
            comparison["discordant_episodes"],
            comparison["net_wins"],
            comparison["success_delta_percent"],
            comparison["candidate_model_fingerprint"],
            comparison["reference_model_fingerprint"],
            comparison["shared_episode_seeds"],
            comparison["source_artifacts"],
        ]
        for event in completed_events(campaign, "measurement")
        for comparison in event["result"]["paired_comparisons"]
    ]
    lines += ["#### Paired comparisons", ""]
    lines += table(
        [
            "Operation",
            "Candidate",
            "Reference",
            "Episodes",
            "Candidate wins",
            "Reference wins",
            "Discordant",
            "Net wins",
            "Success delta %",
            "Candidate fingerprint",
            "Reference fingerprint",
            "Shared seeds",
            "Source artifacts",
        ],
        comparisons,
    )

    lines += ["### Completed training operations", ""]
    lines += table(
        [
            "Operation",
            "Session",
            "Inquiry",
            "Initialization",
            "Parent",
            "Seed",
            "Requested steps",
            "Completed steps",
            "Scientific commit",
            "Learning dynamics",
        ],
        training_rows(campaign),
    )

    lines += ["### Candidates and current model roles", ""]
    lines += table(
        [
            "Candidate",
            "Origin",
            "Name",
            "Training steps",
            "Current roles",
            "Artifact",
            "Fingerprint",
            "Scientific commit",
            "Evaluation artifacts",
        ],
        candidate_rows(campaign),
    )
    lines += ["#### Model-role assignment history", ""]
    lines += table(
        ["Operation", "Action", "Candidate", "Evidence", "Reason"],
        [
            [
                event["id"],
                event["result"]["action"],
                event["result"]["candidate"],
                ", ".join(event["result"]["evidence"]),
                event["request"]["reason"],
            ]
            for event in completed_events(campaign, "model_role")
        ],
    )

    lines += ["### Assessment and terminal state", ""]
    lines += table(
        ["Fact", "Value"],
        [
            ["Terminal status", terminal.get("status") if terminal else None],
            ["Terminal reason", terminal.get("reason") if terminal else None],
            ["Terminal model", terminal.get("model") if terminal else None],
            ["Assessment status", assessment.get("status") if assessment else None],
            ["Assessment model", assessment.get("model") if assessment else None],
            ["Assessment artifact", assessment.get("artifact") if assessment else None],
            [
                "Assessment fingerprint",
                assessment.get("fingerprint") if assessment else None,
            ],
            ["Assessment summary", assessment.get("summary") if assessment else None],
            [
                "Assessment completed",
                assessment.get("completed_at") if assessment else None,
            ],
        ],
    )

    lines += ["### PI resource accounting", ""]
    metrics = resource_metrics(campaign)
    lines += table(["Resource fact", "Recorded value"], list(metrics.items()))
    lines += table(
        [
            "Phase",
            "Session",
            "Attempt",
            "Model",
            "Reasoning",
            "Input",
            "Cache read",
            "Output",
            "AIU",
            "Tools",
            "Seconds",
            "Exit",
        ],
        [
            [
                row.get("phase"),
                row.get("session_id"),
                row.get("attempt"),
                row.get("model"),
                row.get("reasoning"),
                row.get("input_tokens"),
                row.get("cache_read_tokens"),
                row.get("output_tokens"),
                row.get("aiu"),
                row.get("tool_calls"),
                row.get("duration_seconds"),
                row.get("exit_code"),
            ]
            for row in campaign["usage"]
        ],
    )
    tools = Counter()
    for row in campaign["usage"]:
        tools.update(row.get("tools_by_name") or {})
    lines += table(
        ["Tool name", "Calls"],
        [[name, count] for name, count in tools.most_common()],
    )
    return lines


def render_report(campaigns: list[dict]) -> str:
    if not campaigns:
        raise ValueError("at least one schema-6 campaign is required")
    lines = [
        "# Schema-6 campaign factual report",
        "",
        (
            "Read-only accounting of persisted campaign state, completed evidence, "
            "failed execution history, model roles, assessment, and resource use. "
            "It does not make scientific judgments."
        ),
        "",
        "## Overview / comparison",
        "",
    ]
    metrics = [comparison_metrics(campaign) for campaign in campaigns]
    lines += table(
        ["Recorded fact", *(campaign["id"] for campaign in campaigns)],
        [[key, *(metric[key] for metric in metrics)] for key in metrics[0]],
    )
    for campaign in campaigns:
        lines += campaign_sections(campaign)
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument(
        "--campaign-id", help="Must match the current schema-6 campaign"
    )
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--compare-campaign-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        campaigns = [load_campaign(args.repo.resolve(), args.campaign_id)]
        if args.compare:
            campaigns.append(
                load_campaign(args.compare.resolve(), args.compare_campaign_id)
            )
        output = (
            args.output or args.repo / "reports" / f"campaign-{campaigns[0]['id']}.md"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_report(campaigns), encoding="utf-8")
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as error:
        parser.exit(1, f"Report could not be generated: {error}\n")
    print(f"Wrote {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
