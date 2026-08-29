"""Scenario-owned rendering of measured evidence for the research brief.

The generic brief builder inserts the returned Markdown block without knowing
what any of it means.
"""


def render_scenario_evidence(metrics: dict | None) -> list[str]:
    if not metrics:
        return ["Not available yet."]
    failures = metrics.get("failure_diagnostics", [])
    episodes = int(metrics.get("episodes", 0))
    if not episodes:
        return ["Not available yet."]

    def percent(count: int) -> str:
        return f"{100 * count / episodes:.1f}%"

    successes = episodes - len(failures)
    required = int(metrics["failed_episode_progress"]["required_steps"])
    longest_holds = sorted(int(item["longest_consecutive_steps"]) for item in failures)
    best_windows = sorted(int(item["best_window_inside_steps"]) for item in failures)

    def quantile(values: list[int], fraction: float) -> int:
        return values[round((len(values) - 1) * fraction)]

    lines = [
        f"- Entered the target tolerance: {percent(sum(item['best_window_inside_steps'] > 0 for item in failures) + successes)}.",
        f"- Completed the required hold: {metrics.get('success_percent', 0):.1f}%",
    ]
    if longest_holds:
        lines.extend(
            [
                f"- Failed hold progress: median {quantile(longest_holds, 0.5)}/{required}; upper quantile {quantile(longest_holds, 0.9)}/{required}.",
                f"- Failed best-window progress: median {quantile(best_windows, 0.5)}/{required}; upper quantile {quantile(best_windows, 0.9)}/{required}.",
            ]
        )
    for label, low, high in (
        ("6-10 cm", 6, 10),
        ("10-15 cm", 10, 15),
        ("15-20 cm", 15, 20),
    ):
        bucket = [item for item in failures if low <= item["target_radius_cm"] < high]
        if bucket:
            lines.append(
                f"- Failures at {label}: {len(bucket)}; mean longest hold "
                f"{sum(item['longest_consecutive_steps'] for item in bucket) / len(bucket):.1f}."
            )
    directional: dict[str, list[dict]] = {"left": [], "right": []}
    for item in failures:
        if "target_angle_degrees" in item:
            directional[
                "left" if float(item["target_angle_degrees"]) < 0 else "right"
            ].append(item)
    if len(failures) >= 4 and all(directional.values()):
        lines.append(
            "- Directional failures: "
            + "; ".join(
                f"{side} {len(items)} failures, median hold "
                f"{quantile(sorted(int(item['longest_consecutive_steps']) for item in items), 0.5)}/{required}"
                for side, items in directional.items()
            )
            + "."
        )
    lines.append("")
    lines.extend(
        [
            f"- seed {item['episode_seed']}: radius "
            f"{item['target_radius_cm']:.2f} cm, angle "
            f"{item['target_angle_degrees']:.1f}°, longest hold "
            f"{item['longest_consecutive_steps']}/100, best window "
            f"{item['best_window_inside_steps']}/100."
            for item in failures[:5]
        ]
        or ["Not available yet."]
    )
    return lines
