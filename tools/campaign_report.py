"""Human-only, read-only campaign report. No training, SDK, Git or scenario imports."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
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
    """Normalize existing record shapes and count an artifact only once."""
    found = {}
    for source in (
        *row.get("requested_evaluations", []),
        *row.get("task_reference_evaluations", []),
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


def comparison_metrics(campaign: dict) -> dict:
    rows, usage = campaign["rows"], campaign["usage"]
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
    final = [
        str(r["index"])
        for r in rows
        if (r.get("closure_decision") or {}).get("request_final_benchmark")
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
        "Final benchmark requested after experiments": ", ".join(final)
        or "none recorded",
        "Recorded Researcher invocations": str(len(usage)),
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
        "AIU": usage_total(usage, "aiu"),
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
    for name in ("working_lineage", "best_known_lineage"):
        lineage = state.get(name) or (rows[-1].get(name) if rows else None) or {}
        lines.append(
            f"- {name}: experiment {lineage.get('origin_experiment', NA)}, "
            f"{lineage.get('candidate', NA)}, {lineage.get('training_steps', NA)} accumulated steps."
        )
    lines += ["", "### Experiment progression", ""]
    progression = []
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
        progression.append(
            [
                row["index"],
                row.get("family", NA),
                f"{row.get('kind', NA)} / {row.get('initialization', NA)}",
                row.get("training_parent", NA),
                row.get("status", NA),
                outcome,
                decision.get("continue_from", NA),
                (decision.get("code") or {}).get("action", NA),
                f"exp {best_known.get('origin_experiment', NA)} / {best_known.get('candidate', NA)}",
            ]
        )
    lines += table(
        [
            "Exp",
            "Family",
            "Operation / init",
            "Parent",
            "Status",
            "Best measured by instrument",
            "Working choice",
            "Recipe action",
            "Best-known snapshot",
        ],
        progression,
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
            higher = [
                p["name"]
                for p in proxies
                if proxy is not None
                and p["training_success"] > proxy
                and p["name"] not in selected
            ]
            selections.append(
                [
                    m.get("candidate", NA),
                    m["instrument"],
                    c.get("timesteps", "saved lineage"),
                    number(proxy),
                    number(c.get("ep_rew_mean")),
                    ", ".join(higher) or "none / unavailable",
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
                "Unmeasured higher proxy",
                "Recorded selection rationale",
            ],
            selections,
        )
    lines += [
        "### Initialization, hypothesis memory and lineage decisions",
        "",
        "Citations and rationales are Researcher-authored records; they do not prove that an artifact was inspected or that a causal claim is correct.",
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
            f"Objective link: {cell(reasoning.get('objective_link'))}",
            "",
            f"Expected / sought observation: {cell(reasoning.get('expected_observation') or reasoning.get('observations_sought'))}",
            "",
            f"Contradicting observation / exploratory uncertainty: {cell(reasoning.get('contradicting_observation') or reasoning.get('uncertainty'))}",
            "",
            f"Assessment: {cell(row.get('hypothesis_assessment'))}",
            "",
            f"Lineage rationale: {cell(decision.get('reason'))}",
            "",
            f"Recipe rationale: {cell((decision.get('code') or {}).get('reason'))}",
            "",
        ]
        for e in reasoning.get("evidence", []):
            source = e.get("source", "")
            # Explicit reference extraction only: never infer use of prior history from a broad file citation.
            refs = sorted(
                {
                    int(n)
                    for n in re.findall(
                        r"experiment[-_ ](\d+)",
                        source + " " + e.get("observation", ""),
                        re.IGNORECASE,
                    )
                }
            )
            prior = [n for n in refs if n < row["index"]]
            lines.append(
                f"- Evidence: {link(repo, source) if source else NA}; {cell(e.get('observation'))}"
                + (
                    f" [explicit prior experiment references: {', '.join(map(str, prior))}]"
                    if prior
                    else ""
                )
            )
        lines += [
            "",
            f"Postmortem: {link(repo, row.get('postmortem') or 'research/postmortems.md')}",
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
    for row in rows:
        decision = row.get("closure_decision") or {}
        if decision.get("request_final_benchmark"):
            lines += [
                f"- Final requested after experiment {row['index']}: {cell(decision.get('reason'))}"
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
                "Invocations",
                "Input",
                "Cache read",
                "Output",
                "AIU",
                "Tools",
                "Seconds",
                "Nonzero exits",
            ],
            [
                [
                    *key,
                    len(group),
                    *(
                        usage_total(group, f)
                        for f in (
                            "input_tokens",
                            "cache_read_tokens",
                            "output_tokens",
                            "aiu",
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
