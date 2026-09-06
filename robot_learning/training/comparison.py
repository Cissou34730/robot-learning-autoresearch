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


def paired_comparison(candidate: list[dict], reference: list[dict]) -> dict:
    """Compare policies evaluated on identical seed/episode pairs."""

    def outcomes(evaluations: list[dict]) -> dict[tuple[int, int], bool]:
        return {
            (int(evaluation["seed"]), int(episode["episode"])): bool(episode["success"])
            for evaluation in evaluations
            for episode in evaluation.get("episode_results", [])
        }

    candidate_outcomes = outcomes(candidate)
    reference_outcomes = outcomes(reference)
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
        "exact_p_value": exact_mcnemar_pvalue(candidate_wins, reference_wins),
    }
