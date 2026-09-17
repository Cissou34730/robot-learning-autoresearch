"""Protected accounting for paired research measurements.

Deterministic episode identity, distinct-coverage counting, conflict rejection
and the paired contingency counts are correctness properties of measurement
rather than scientific choices. They therefore live on the protected side of the
ownership boundary so that restoring a research recipe can never silently revert
them (issue #35).

The choice of inferential test is deliberately *not* here: the protected
accounting stops at trustworthy counts, and a researcher-owned wrapper
(`robot_learning.training.comparison`) may apply any statistic it prefers.
"""


def episode_outcomes(evaluations: list[dict]) -> dict[tuple[str, int], bool]:
    """Count each deterministic episode once within its evaluation semantics."""
    outcomes: dict[tuple[str, int], bool] = {}
    for evaluation in evaluations:
        episodes = evaluation.get("episode_results")
        if not episodes or len(episodes) != int(evaluation["episodes"]):
            raise ValueError("evaluation requires complete detailed episode outcomes")
        semantics = str(evaluation.get("evaluation_semantics", ""))
        for episode in episodes:
            identity = semantics, int(episode["episode_seed"])
            success = bool(episode["success"])
            if identity in outcomes and outcomes[identity] != success:
                raise ValueError(
                    "conflicting deterministic measurements for episode "
                    f"{identity[1]}"
                )
            outcomes[identity] = success
    return outcomes


def paired_comparison(candidate: list[dict], reference: list[dict]) -> dict:
    """Trustworthy paired contingency counts on shared episode identities."""
    candidate_outcomes = episode_outcomes(candidate)
    reference_outcomes = episode_outcomes(reference)
    if not candidate_outcomes or candidate_outcomes.keys() != reference_outcomes.keys():
        raise ValueError("paired evaluations do not cover identical episodes")
    candidate_wins = sum(
        candidate_outcomes[key] and not reference_outcomes[key]
        for key in candidate_outcomes
    )
    reference_wins = sum(
        reference_outcomes[key] and not candidate_outcomes[key]
        for key in candidate_outcomes
    )
    episode_count = len(candidate_outcomes)
    return {
        "episodes": episode_count,
        "candidate_wins": candidate_wins,
        "reference_wins": reference_wins,
        "discordant_episodes": candidate_wins + reference_wins,
        "net_wins": candidate_wins - reference_wins,
        "success_delta_percent": 100
        * (candidate_wins - reference_wins)
        / episode_count,
    }
