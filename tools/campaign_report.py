"""Human-only, read-only campaign report. No training, SDK, Git or scenario imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NA = "unavailable"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{number}: invalid JSON: {error.msg}") from error
    return rows


def cell(value: object) -> str:
    return " ".join(str(value if value is not None else NA).split()).replace("|", "\\|")


def table(headers: list[str], rows: list[list]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(cell(v) for v in row) + " |" for row in rows),
        "",
    ]


def number(value: object, suffix: str = "") -> str:
    return f"{value:,.2f}{suffix}" if isinstance(value, (int, float)) else NA


def link(repo: Path, relative: str) -> str:
    return f"[{cell(relative)}](<{(repo / relative).resolve().as_posix()}>)"


def measurements(row: dict) -> list[dict]:
    """Normalize existing record shapes and count an artifact only once.

    Every ledger a record can carry is read, not only the requested ones. A
    preparation or partial round executes the same episodes on the same
    instrument, so reading the requested ledgers alone understated the work a
    campaign performed and the panels it consumed.
    """
    found = {}
    for source in (
        *row.get("requested_evaluations", []),
        *row.get("partial_evaluations", []),
        *row.get("preparation_evaluations", []),
        *row.get("task_reference_evaluations", []),
        *row.get("partial_task_reference_evaluations", []),
        *row.get("preparation_task_reference_evaluations", []),
    ):
        metrics = source.get("metrics") or source
        item = {**source, **metrics}
        item.setdefault("instrument", "research_evaluation")
        path = item.get("evaluation_artifact")
        key = path or (
            item.get("candidate"),
            item["instrument"],
            item.get("seed"),
            item.get("episodes"),
            item.get("evaluation_semantics"),
        )
        found[key] = item
    return list(found.values())


def _candidate_identity(candidate: dict) -> str:
    for key in ("fingerprint", "model_fingerprint", "artifact", "name"):
        value = candidate.get(key)
        if value:
            return str(value)
    return json.dumps(candidate, sort_keys=True, separators=(",", ":"))


def display_order(
    candidates: list[dict],
    campaign_id: str | None = None,
    experiment: object = None,
) -> list[dict]:
    """Mirror build_research_brief.candidate_display_order.

    The order is a metric-independent stable permutation of artifact identity
    salted by campaign/experiment scope, so it never ranks candidates by
    training proxy, timestep or input position, and does not collapse to one
    fixed permutation across experiments.
    """
    scope = f"{campaign_id or ''}|{experiment if experiment is not None else ''}"
    return sorted(
        candidates,
        key=lambda candidate: (
            hashlib.sha256(
                f"{scope}|{_candidate_identity(candidate)}".encode("utf-8")
            ).hexdigest(),
            _candidate_identity(candidate),
        ),
    )


def selection_diagnostics(rows: list[dict]) -> list[list]:
    """Factual selection ranks for each measured checkpoint candidate.

    Exposes how measured candidates sit in the rendered (metric-independent)
    order and in the previous proxy-ranked order, whether they were the endpoint,
    and their timestep rank. It is an audit of presentation and selection, not a
    recommendation.
    """
    diagnostics = []
    for row in rows:
        candidates = [
            candidate
            for candidate in (row.get("candidates") or [])
            if isinstance(candidate, dict)
        ]
        if not candidates:
            continue
        names = {candidate.get("name") for candidate in candidates}
        displayed = {
            candidate.get("name"): position + 1
            for position, candidate in enumerate(
                display_order(candidates, row.get("campaign_id"), row.get("index"))
            )
        }
        proxy_sorted = sorted(
            candidates,
            key=lambda candidate: (
                candidate.get("training_success") is None,
                -float(candidate.get("training_success") or 0.0),
                int(candidate.get("timesteps") or 0),
            ),
        )
        proxy_rank = {
            candidate.get("name"): position + 1
            for position, candidate in enumerate(proxy_sorted)
        }
        timestep_sorted = sorted(
            candidates, key=lambda candidate: int(candidate.get("timesteps") or 0)
        )
        timestep_rank = {
            candidate.get("name"): position + 1
            for position, candidate in enumerate(timestep_sorted)
        }
        latest = max(int(candidate.get("timesteps") or 0) for candidate in candidates)
        endpoints = {
            candidate.get("name")
            for candidate in candidates
            if int(candidate.get("timesteps") or 0) == latest
        }
        selected = sorted(
            {
                measurement.get("candidate")
                for measurement in measurements(row)
                if measurement.get("candidate") in names
            }
        )
        for candidate in selected:
            diagnostics.append(
                [
                    row.get("index"),
                    candidate,
                    displayed.get(candidate),
                    proxy_rank.get(candidate),
                    f"{timestep_rank.get(candidate)}/{len(candidates)}",
                    "yes" if candidate in endpoints else "no",
                ]
            )
    return diagnostics


def load_campaign(repo: Path, campaign_id: str | None = None) -> dict:
    state = read_json(repo / "research/research_state.json")
    history = read_rows(repo / "research/results.jsonl")
    campaign_id = campaign_id or state.get("campaign", {}).get("id")
    if not campaign_id and history:
        campaign_id = history[-1].get("campaign_id")
    latest = {}
    for row in history:
        if row.get("campaign_id") == campaign_id:
            latest[row["index"]] = row
    rows = [latest[n] for n in sorted(latest)]
    current_state = state if state.get("campaign", {}).get("id") == campaign_id else {}
    usage = read_rows(repo / "reports/session_usage" / f"{campaign_id}.jsonl")
    usage = [row for row in usage if row.get("campaign_id") == campaign_id]
    return {
        "repo": repo,
        "id": campaign_id or "legacy",
        "state": current_state,
        "rows": rows,
        "usage": usage,
    }


def usage_total(rows: list[dict], field: str) -> str:
    available = [row[field] for row in rows if isinstance(row.get(field), (int, float))]
    if not available:
        return NA
    total = number(sum(available))
    return (
        total
        if len(available) == len(rows)
        else f"{total} (partial: {len(available)}/{len(rows)} invocations)"
    )


def runtime_label(row: dict) -> str:
    """Rows written before the OpenCode runtime existed carry no runtime field."""
    runtime = row.get("runtime")
    return str(runtime) if runtime else "copilot (legacy)"


def proposal_reasoning(row: dict) -> dict:
    proposal = row.get("proposal_snapshot") or {}
    return proposal.get("reasoning") or row.get("reasoning") or {}


def prior_experiment_references(row: dict) -> list[int]:
    """Return only explicit references recorded in the proposal evidence."""
    references = set()
    for evidence in proposal_reasoning(row).get("evidence", []):
        text = f"{evidence.get('source', '')} {evidence.get('observation', '')}"
        references.update(
            int(number)
            for number in re.findall(r"experiment[-_ ](\d+)", text, re.IGNORECASE)
            if int(number) < row["index"]
        )
    return sorted(references)


def family_area(value: object) -> str:
    family = str(value or NA)
    return re.split(r"[.]", family, maxsplit=1)[0]


def lineage_identity(lineage: dict | None) -> tuple:
    lineage = lineage or {}
    return (
        lineage.get("origin_experiment"),
        lineage.get("candidate"),
        lineage.get("fingerprint"),
    )


def changed_from(previous: dict | None, current: dict | None) -> str:
    if not current:
        return NA
    if not previous:
        return "initial"
    return "yes" if lineage_identity(previous) != lineage_identity(current) else "no"


def changed_paths(row: dict) -> str:
    paths = row.get("code_changes") or []
    if isinstance(paths, str):
        paths = [paths]
    return ", ".join(paths) or "none"


def parameter_change_summary(row: dict) -> str:
    changes = row.get("parameter_changes") or []
    if isinstance(changes, dict):
        changes = [changes]
    rendered = []
    for change in changes:
        if not isinstance(change, dict):
            rendered.append(str(change))
            continue
        path = change.get("path", NA)
        before = change.get("before", NA)
        after = change.get("after", NA)
        rendered.append(f"{path}: {before} -> {after}")
    return "; ".join(rendered) or "none"


def proxy_rank(candidate: dict, proxies: list[dict]) -> str:
    value = candidate.get("training_success")
    if not isinstance(value, (int, float)):
        return NA
    values = sorted({item["training_success"] for item in proxies}, reverse=True)
    return f"{values.index(value) + 1}/{len(values)} distinct values"


def higher_proxy_summary(
    candidate: dict, proxies: list[dict], selected: set[str]
) -> str:
    value = candidate.get("training_success")
    if not isinstance(value, (int, float)):
        return "none / unavailable"
    higher = [
        item
        for item in proxies
        if item["training_success"] > value and item.get("name") not in selected
    ]
    if not higher:
        return "none"
    best = max(higher, key=lambda item: item["training_success"])
    return (
        f"{len(higher)}; best {best.get('name', NA)} "
        f"({number(best.get('training_success'))})"
    )


def preparation_row(state: dict, rows: list[dict]) -> dict | None:
    """The live preparation ledger as a row, when no record carries it yet.

    A preparation round measures saved lineages before its experiment exists.
    When the campaign concludes from preparation, that experiment never runs and
    the ledger is never persisted into a record, so reading only the recorded
    rows hid the very measurements the conclusion was taken on.
    """
    ledger = state.get("preparation_measurement")
    if not isinstance(ledger, dict):
        return None
    index = ledger.get("experiment")
    if index in {row.get("index") for row in rows}:
        return None
    row = {
        "index": index,
        "partial_evaluations": ledger.get("partial_evaluations") or [],
        "partial_task_reference_evaluations": (
            ledger.get("partial_task_reference_evaluations") or []
        ),
    }
    return row if measurements(row) else None


def comparison_metrics(campaign: dict) -> dict:
    rows, usage = campaign["rows"], campaign["usage"]
    state = campaign.get("state") or {}
    initializations = Counter(
        f"{r.get('kind', NA)}/{r.get('initialization', NA)}" for r in rows
    )
    selections = Counter(
        candidate
        for r in rows
        for candidate in {m.get("candidate", "") for m in measurements(r)}
        if candidate.startswith(("checkpoint-", "candidate-"))
    )
    evidence = [m for r in rows for m in measurements(r)]
    preparation = preparation_row(state, rows)
    if preparation is not None:
        evidence += measurements(preparation)
    final = [
        f"closure of experiment {r['index']}"
        for r in rows
        if (r.get("closure_decision") or {}).get("request_final_benchmark")
    ]
    conclusion = state.get("campaign_conclusion")
    if isinstance(conclusion, dict) and (
        conclusion.get("action") == "request_final_benchmark"
    ):
        final.append(
            f"preparation after experiment {rows[-1]['index'] if rows else NA} "
            "(no experiment recorded for the request)"
        )
    fresh_restarts = [
        r["index"]
        for r in rows
        if r.get("initialization") == "fresh" and int(r.get("index", 0)) > 1
    ]
    derived_usage = []
    for u in usage:
        values = dict(u)
        input_tokens, output_tokens, cached = (
            u.get(k) for k in ("input_tokens", "output_tokens", "cache_read_tokens")
        )
        values["total_tokens"] = (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        )
        values["new_input_tokens"] = (
            input_tokens - cached
            if input_tokens is not None and cached is not None
            else None
        )
        derived_usage.append(values)
    return {
        "Recorded experiments": str(len(rows)),
        # The baseline is automatic and always fresh, so it is excluded. This
        # counts the discretionary restarts from zero, which is the quantity
        # that separated the converging campaigns from the stalled ones.
        "Fresh restarts after the baseline": (
            "; ".join(f"experiment {index}" for index in fresh_restarts) or "none"
        )
        + f" ({len(fresh_restarts)} of {len(rows)})",
        "Operations / initialization": "; ".join(
            f"{k}: {v}" for k, v in sorted(initializations.items())
        )
        or NA,
        "Experiments selecting each checkpoint position": "; ".join(
            f"{k}: {v}" for k, v in selections.most_common()
        )
        or NA,
        "Measurement executions": str(len(evidence)),
        "Experiments with / without recorded measurements": f"{sum(bool(measurements(r)) for r in rows)} / {sum(not measurements(r) for r in rows)}",
        "Episode executions (not unique coverage)": number(
            sum(m.get("episodes", 0) for m in evidence)
        ),
        "Instruments": "; ".join(
            f"{k}: {v}" for k, v in Counter(m["instrument"] for m in evidence).items()
        )
        or NA,
        "Final benchmark requested from": "; ".join(final) or "none recorded",
        "Recorded Researcher invocations": str(len(usage)),
        "Researcher runtime": "; ".join(
            f"{k}: {v}" for k, v in Counter(runtime_label(u) for u in usage).items()
        )
        or NA,
        "Models / reasoning": "; ".join(
            f"{k[0]} / {k[1]}: {v}"
            for k, v in Counter(
                (u.get("model"), u.get("reasoning")) for u in usage
            ).items()
        )
        or NA,
        "Total tokens (input + output)": usage_total(derived_usage, "total_tokens"),
        "Input tokens (includes cache reads)": usage_total(usage, "input_tokens"),
        "Cache-read tokens (subset of input)": usage_total(usage, "cache_read_tokens"),
        "New input tokens (input minus cache reads)": usage_total(
            derived_usage, "new_input_tokens"
        ),
        "Output tokens": usage_total(usage, "output_tokens"),
        # Copilot bills in AIU. Only Copilot rows carry it, so an OpenCode row's
        # null leaves this visibly partial rather than counting as zero.
        "AIU": usage_total(usage, "aiu"),
        "Cache-write tokens (OpenCode runtime only)": usage_total(
            usage, "cache_write_tokens"
        ),
        "Reasoning tokens (OpenCode runtime only)": usage_total(
            usage, "reasoning_tokens"
        ),
        "Estimated cost, USD (OpenCode runtime only)": usage_total(
            usage, "reported_cost_usd"
        ),
        "Tool calls": usage_total(usage, "tool_calls"),
        "Researcher duration, seconds": usage_total(usage, "duration_seconds"),
    }


def campaign_sections(campaign: dict) -> list[str]:
    repo, rows, state = campaign["repo"], campaign["rows"], campaign["state"]
    lines = [f"## Campaign `{campaign['id']}`", "", f"Repository: `{repo}`", ""]
    status = state.get("terminal_campaign_status") or "no terminal status recorded"
    pending = next(
        (
            f"{key}, experiment {state[key].get('experiment', NA)}"
            for key in (
                "pending_training_operation",
                "pending_analysis",
                "pending_researcher_decision",
                "pending_evaluation_request",
                "pending_final_benchmark",
            )
            if isinstance(state.get(key), dict)
        ),
        "none recorded",
    )
    lines += [
        f"State: {status}. Pending operation: {pending}.",
        "This is persisted state, not a check of live processes.",
        "",
    ]
    if status == "no terminal status recorded" and pending == "none recorded":
        lines += [
            "Campaign stop or interruption reason: unavailable in persisted data.",
            "",
        ]
    for name in ("working_lineage", "best_known_lineage"):
        lineage = state.get(name) or (rows[-1].get(name) if rows else None) or {}
        lines.append(
            f"- {name}: experiment {lineage.get('origin_experiment', NA)}, "
            f"{lineage.get('candidate', NA)}, {lineage.get('training_steps', NA)} accumulated steps."
        )
    lines += ["", "### Experiment progression", ""]
    progression = []
    previous_best_known = None
    for row in rows:
        evidence = measurements(row)
        best = {}
        for m in evidence:
            score = m.get("success_percent")
            if isinstance(score, (int, float)) and score > best.get(
                m["instrument"], {}
            ).get("success_percent", -1):
                best[m["instrument"]] = m
        outcome = (
            "; ".join(
                f"{instrument}: {m.get('candidate', NA)} {number(m['success_percent'], '%')}"
                for instrument, m in best.items()
            )
            or "no recorded measurements"
        )
        decision = row.get("closure_decision") or {}
        best_known = row.get("best_known_lineage") or {}
        references = prior_experiment_references(row)
        progression.append(
            [
                row["index"],
                row.get("family", NA),
                f"{row.get('kind', NA)} / {row.get('initialization', NA)}",
                row.get("training_parent", NA),
                row.get("status", NA),
                outcome,
                ", ".join(map(str, references)) or "none recorded",
                decision.get("continue_from", NA),
                (decision.get("code") or {}).get("action", NA),
                changed_from(previous_best_known, best_known),
                f"exp {best_known.get('origin_experiment', NA)} / {best_known.get('candidate', NA)}",
            ]
        )
        previous_best_known = best_known or previous_best_known
    lines += table(
        [
            "Exp",
            "Family",
            "Operation / init",
            "Parent",
            "Status",
            "Best measured by instrument",
            "Prior experiments cited",
            "Working choice",
            "Recipe action",
            "Best-known changed",
            "Best-known snapshot",
        ],
        progression,
    )
    lines += ["", "### Selection diagnostics", ""]
    lines += [
        (
            "Ranks audit how measured checkpoints sit in the rendered brief. "
            "Displayed position uses the current metric-independent order; proxy "
            "rank is the order a training-proxy-ranked inventory would have shown. "
            "These ranks are factual and do not rank models for the Researcher."
        ),
        "",
    ]
    lines += table(
        [
            "Exp",
            "Selected candidate",
            "Displayed position",
            "Proxy rank",
            "Timestep rank",
            "Endpoint",
        ],
        selection_diagnostics(rows),
    )
    postmortem = repo / "research/postmortems.md"
    if postmortem.exists():
        strategy = re.search(
            rf"^## {re.escape(campaign['id'])} / Scientific strategy\s*\n(.*?)(?=^## |\Z)",
            postmortem.read_text(encoding="utf-8-sig"),
            re.MULTILINE | re.DOTALL,
        )
        if strategy:
            lines += [
                "### Current recorded scientific strategy",
                "",
                "Researcher-authored synthesis, not an assessment by this report.",
                "",
                strategy.group(1).strip(),
                "",
            ]
    areas = defaultdict(list)
    for row in rows:
        areas[family_area(row.get("family"))].append(row)
    lines += [
        "### Scientific search coverage",
        "",
        (
            "This groups recorded experiment families by their top-level scientific surface. "
            "It describes coverage; it does not rank surfaces or judge whether repetition was justified."
        ),
        "",
    ]
    lines += table(
        [
            "Surface",
            "Experiments",
            "Families",
            "Operations / initialization",
            "Experiments closed with code action=keep",
        ],
        [
            [
                area,
                ", ".join(str(row["index"]) for row in area_rows),
                "; ".join(sorted({str(row.get("family", NA)) for row in area_rows})),
                "; ".join(
                    f"{row['index']}: {row.get('kind', NA)}/{row.get('initialization', NA)}"
                    for row in area_rows
                ),
                ", ".join(
                    str(row["index"])
                    for row in area_rows
                    if ((row.get("closure_decision") or {}).get("code") or {}).get(
                        "action"
                    )
                    == "keep"
                )
                or "none",
            ]
            for area, area_rows in sorted(areas.items())
        ],
    )
    if len(rows) > 1:
        lines += [
            "### Cross-experiment decision chain",
            "",
            (
                "Explicit citations come only from the next proposal's recorded evidence. "
                "No continuity is inferred from similar wording or family names."
            ),
            "",
        ]
        lines += table(
            [
                "Closed experiment",
                "Next experiment",
                "Next family",
                "Next operation / initialization",
                "Earlier experiments explicitly cited by next proposal",
            ],
            [
                [
                    current["index"],
                    following["index"],
                    following.get("family", NA),
                    f"{following.get('kind', NA)} / {following.get('initialization', NA)}",
                    ", ".join(map(str, prior_experiment_references(following)))
                    or "none recorded",
                ]
                for current, following in pairwise(rows)
            ],
        )
    lines += [
        "### Checkpoint selection and trajectory coverage",
        "",
        (
            "Training proxies can justify measurement selection, but do not establish policy quality. "
            "A higher unmeasured proxy is a coverage question, not proof of a better model. "
            "Steps below are checkpoint positions within each run; they are not automatically comparable across fresh and transfer runs."
        ),
        "",
    ]
    for row in rows:
        candidates = row.get("candidates") or []
        selected = {m.get("candidate") for m in measurements(row)}
        proxies = [
            c for c in candidates if isinstance(c.get("training_success"), (int, float))
        ]
        peak = max((c["training_success"] for c in proxies), default=None)
        peak_steps = sorted(
            c.get("timesteps", 0) for c in proxies if c["training_success"] == peak
        )
        near = sorted(
            c.get("timesteps", 0)
            for c in proxies
            if peak is not None and c["training_success"] >= peak - 0.01
        )
        lines += [
            f"#### Experiment {row['index']}",
            "",
            f"Saved checkpoints: {len(candidates)}; measured current checkpoints: {len(selected & {c.get('name') for c in candidates})}.",
            f"Peak training-success proxy: {number(peak)}; exact peak positions: {', '.join(map(str, peak_steps)) or NA}.",
            (
                f"Within 1 percentage point of peak: {', '.join(map(str, near)) or NA}. "
                "Listed positions may be disjoint; this does not assert a continuous plateau."
            ),
            "",
        ]
        selections = []
        by_name = {c.get("name"): c for c in candidates}
        for m in measurements(row):
            c = by_name.get(m.get("candidate"), {})
            proxy = c.get("training_success")
            selections.append(
                [
                    m.get("candidate", NA),
                    m["instrument"],
                    c.get("timesteps", "saved lineage"),
                    number(proxy),
                    number(c.get("ep_rew_mean")),
                    proxy_rank(c, proxies),
                    higher_proxy_summary(c, proxies, selected),
                    m.get("selection", NA),
                ]
            )
        lines += table(
            [
                "Model",
                "Instrument",
                "Steps",
                "Training success",
                "Training reward",
                "Proxy rank",
                "Unmeasured higher proxies",
                "Recorded selection rationale",
            ],
            selections,
        )
    lines += [
        "### Initialization, hypothesis memory and lineage decisions",
        "",
        (
            "Questions, assessments and rationales are Researcher-authored records; "
            "they do not prove that a causal claim is correct. Detailed observations remain in the linked sources."
        ),
        f"Campaign postmortems: {link(repo, 'research/postmortems.md')}",
        "",
    ]
    families = defaultdict(list)
    for row in rows:
        families[row.get("family", NA)].append(str(row["index"]))
        proposal = row.get("proposal_snapshot") or {}
        reasoning = proposal.get("reasoning") or {}
        decision = row.get("closure_decision") or {}
        lines += [
            f"#### Experiment {row['index']}",
            "",
            f"Question: {cell(proposal.get('scientific_question') or proposal.get('hypothesis') or row.get('hypothesis'))}",
            "",
            f"Intervention: {cell(proposal.get('change') or row.get('change'))}",
            "",
            f"Initialization basis: {cell(reasoning.get('initialization_reason'))}",
            "",
            f"Expected / sought observation: {cell(reasoning.get('expected_observation') or reasoning.get('observations_sought'))}",
            "",
            f"Contradicting observation / exploratory uncertainty: {cell(reasoning.get('contradicting_observation') or reasoning.get('uncertainty'))}",
            "",
            f"Assessment: {cell(row.get('hypothesis_assessment'))}",
            "",
            f"Lineage rationale: {cell(decision.get('reason'))}",
            "",
        ]
        sources = list(
            dict.fromkeys(
                evidence.get("source")
                for evidence in reasoning.get("evidence", [])
                if evidence.get("source")
            )
        )
        references = prior_experiment_references(row)
        lines += [
            "Evidence sources: "
            + (", ".join(f"`{cell(source)}`" for source in sources) or NA),
            "",
            "Explicit prior experiment references: "
            + (", ".join(map(str, references)) or "none recorded"),
            "",
        ]
    lines += ["Repeated families (not automatically unjustified repetition):", ""]
    lines += [
        f"- `{family}`: experiments {', '.join(ids)}"
        for family, ids in families.items()
        if len(ids) > 1
    ] or ["- None recorded."]
    lines += [
        "",
        "### Recipe and lineage state",
        "",
        (
            "This table exposes the tested surface and the persisted state after closure. "
            "A commit is a recorded scientific provenance identifier, not a harness version."
        ),
        "",
    ]
    recipe_rows = []
    previous_working = None
    previous_best_known = None
    for row in rows:
        decision = row.get("closure_decision") or {}
        working = row.get("working_lineage") or {}
        best_known = row.get("best_known_lineage") or {}
        scientific_commit = working.get("scientific_commit") or row.get(
            "scientific_commit"
        )
        recipe_rows.append(
            [
                row["index"],
                changed_paths(row),
                parameter_change_summary(row),
                (decision.get("code") or {}).get("action", NA),
                changed_from(previous_working, working),
                f"exp {working.get('origin_experiment', NA)} / {working.get('candidate', NA)}",
                changed_from(previous_best_known, best_known),
                f"exp {best_known.get('origin_experiment', NA)} / {best_known.get('candidate', NA)}",
                str(scientific_commit)[:12] if scientific_commit else NA,
            ]
        )
        previous_working = working or previous_working
        previous_best_known = best_known or previous_best_known
    lines += table(
        [
            "Exp",
            "Tested code paths",
            "Tested parameter changes",
            "Recipe action",
            "Working changed",
            "Working after closure",
            "Best-known changed",
            "Best-known after closure",
            "Scientific commit",
        ],
        recipe_rows,
    )
    lines += [
        "### Evaluation exposure and terminal requests",
        "",
        (
            "Equal panel settings describe reused development coverage, not independent confirmation. "
            "Different settings alone do not prove statistical independence. Round counts are not reconstructed from measurement counts."
        ),
        "",
    ]
    panels = defaultdict(list)
    for row in rows:
        for m in measurements(row):
            key = (
                m["instrument"],
                m.get("panel", m.get("seed", NA)),
                m.get("episodes", NA),
                m.get("evaluation_semantics", "fixed panel"),
            )
            panels[key].append(row["index"])
    lines += table(
        [
            "Instrument",
            "Panel / seed",
            "Episodes",
            "Evaluation identity",
            "Executions",
            "Experiments",
        ],
        [
            [*key, len(ids), ", ".join(map(str, sorted(set(ids))))]
            for key, ids in panels.items()
        ],
    )
    usage_by_experiment = defaultdict(list)
    for invocation in campaign["usage"]:
        usage_by_experiment[invocation.get("experiment")].append(invocation)
    lines += [
        "#### Analysis and measurement flow",
        "",
        (
            "Researcher invocations are recorded runtime sessions, not reconstructed evaluation rounds. "
            "The persisted data does not identify rejected deliverables whose process exited successfully."
        ),
        "",
    ]
    flow_rows = []
    for row in rows:
        evidence = measurements(row)
        invocations = usage_by_experiment.get(row["index"], [])
        post_training = [
            invocation
            for invocation in invocations
            if invocation.get("phase") == "post-training analysis"
        ]
        attempts = [
            invocation.get("attempt")
            for invocation in invocations
            if isinstance(invocation.get("attempt"), int)
        ]
        flow_rows.append(
            [
                row["index"],
                sum(m["instrument"] == "research_evaluation" for m in evidence),
                sum(m["instrument"] == "task_reference" for m in evidence),
                len(row.get("paired_comparisons") or []),
                len(post_training) if invocations else NA,
                max(attempts) if attempts else NA,
                sum(invocation.get("exit_code", 0) != 0 for invocation in invocations)
                if invocations
                else NA,
            ]
        )
    lines += table(
        [
            "Exp",
            "Research evaluations",
            "Task-reference evaluations",
            "Paired comparisons",
            "Post-training invocations",
            "Highest recorded attempt",
            "Nonzero process exits",
        ],
        flow_rows,
    )
    for row in rows:
        decision = row.get("closure_decision") or {}
        if decision.get("request_final_benchmark"):
            lines += [
                f"- Final requested after experiment {row['index']}: {cell(decision.get('reason'))}"
            ]
    conclusion = state.get("campaign_conclusion")
    if isinstance(conclusion, dict) and (
        conclusion.get("action") == "request_final_benchmark"
    ):
        lines += [
            (
                "- Final requested from preparation after experiment "
                f"{rows[-1]['index'] if rows else NA}, with no experiment "
                f"recorded for the request: {cell(conclusion.get('reason'))}"
            ),
        ]
    lines += [
        f"- Official verdict: {cell(state.get('official_benchmark_verdict'))}",
        "",
        "### Researcher usage and tool activity",
        "",
    ]
    usage = campaign["usage"]
    if not usage:
        lines += [
            "No session accounting is recorded. Historical consumption is unavailable, not zero.",
            "",
        ]
    else:
        lines += [
            (
                "Accounting covers only recorded invocations. Resumed attempts are separate invocation deltas, not cumulative session totals. "
                "Input tokens include cache reads; do not add cache reads to input tokens. Missing SDK usage remains unavailable. "
                "SDK output tokens are reported as supplied, with no inferred reasoning-token split."
            ),
            "",
        ]
        covered = {u.get("experiment") for u in usage}
        missing = [str(r["index"]) for r in rows if r["index"] not in covered]
        if missing:
            lines += [
                f"No accounting for recorded experiments: {', '.join(missing)}. Campaign totals are incomplete.",
                "",
            ]
        groups = defaultdict(list)
        for u in usage:
            groups[(u.get("experiment", NA), u.get("phase", NA))].append(u)
        lines += table(
            [
                "Exp",
                "Phase",
                "Runtime",
                "Invocations",
                "Input",
                "Cache read",
                "Output",
                "AIU",
                "Cost USD",
                "Tools",
                "Seconds",
                "Nonzero exits",
            ],
            [
                [
                    *key,
                    ", ".join(sorted({runtime_label(u) for u in group})),
                    len(group),
                    *(
                        usage_total(group, f)
                        for f in (
                            "input_tokens",
                            "cache_read_tokens",
                            "output_tokens",
                            "aiu",
                            "reported_cost_usd",
                            "tool_calls",
                            "duration_seconds",
                        )
                    ),
                    sum(u.get("exit_code", 0) != 0 for u in group),
                ]
                for key, group in sorted(groups.items(), key=lambda item: str(item[0]))
            ],
        )
        tools = Counter()
        for u in usage:
            tools.update(u.get("tools_by_name") or {})
        lines += table(
            ["Tool name", "Calls"],
            [[name, count] for name, count in tools.most_common()],
        )
    return lines


def render_report(campaigns: list[dict]) -> str:
    lines = [
        "# Campaign decision and bias review",
        "",
        (
            "Read-only factual report. It exposes recurring decisions, their recorded bases and evidence coverage; "
            "it does not score scientific quality or declare a bias corrected. "
            "Compare campaigns at similar progress: more transfer, fewer evaluations or lower cost is not inherently better."
        ),
        "",
        "## Overview / comparison",
        "",
    ]
    metrics = [comparison_metrics(c) for c in campaigns]
    lines += table(
        ["Recorded indicator", *(c["id"] for c in campaigns)],
        [[key, *(m[key] for m in metrics)] for key in metrics[0]],
    )
    for c in campaigns:
        lines += campaign_sections(c)
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--campaign-id", help="Default: current persisted campaign")
    parser.add_argument(
        "--compare", type=Path, help="Another worktree or copied campaign repository"
    )
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
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Report could not be generated: {error}\n")
    print(f"Wrote {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
