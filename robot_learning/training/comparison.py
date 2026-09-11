"""Paired statistics available for researcher-designed comparisons."""

import math


def exact_mcnemar_pvalue(candidate_wins: int, reference_wins: int) -> float:
    """Return the two-sided exact sign test over discordant episodes."""
    discordant = candidate_wins + reference_wins
    if discordant == 0:
        return 1.0
    smaller = min(candidate_wins, reference_wins)
    tail = sum(math.comb(discordant, value) for value in range(smaller + 1))
    return min(1.0, 2 * tail / (2**discordant))


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
    """Compare policies on their shared distinct recorded episode identities."""
    candidate_outcomes = episode_outcomes(candidate)
    reference_outcomes = episode_outcomes(reference)
    shared = candidate_outcomes.keys() & reference_outcomes.keys()
    if not shared:
        raise ValueError("paired evaluations do not share any episodes")
    candidate_wins = sum(
        candidate_outcomes[key] and not reference_outcomes[key]
        for key in shared
    )
    reference_wins = sum(
        reference_outcomes[key] and not candidate_outcomes[key]
        for key in shared
    )
    episode_count = len(shared)
    return {
        "episodes": episode_count,
        "shared_episodes": episode_count,
        "candidate_episode_coverage": len(candidate_outcomes),
        "reference_episode_coverage": len(reference_outcomes),
        "candidate_wins": candidate_wins,
        "reference_wins": reference_wins,
        "discordant_episodes": candidate_wins + reference_wins,
        "net_wins": candidate_wins - reference_wins,
        "success_delta_percent": 100
        * (candidate_wins - reference_wins)
        / episode_count,
        "exact_p_value": exact_mcnemar_pvalue(candidate_wins, reference_wins),
    }
