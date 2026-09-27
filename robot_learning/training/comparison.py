"""Researcher-owned inferential statistics over protected paired counts.

Episode identity, conflict rejection, shared-panel reconciliation and the paired
contingency counts are protected in `robot_learning.paired_evidence`. This module
is the researcher-owned choice of what to do with those counts, so a Researcher
may replace the statistic without weakening measurement integrity.

The Runner stores the protected counts only; any statistic computed here is a
research-side presentation of them, not part of the durable measurement contract.
"""

import math

from robot_learning.paired_evidence import paired_comparison as paired_counts

# The Researcher's default comparison assessment. The method name and version are
# recorded so the assessment stays self-describing if the statistic is replaced.
COMPARISON_ASSESSMENT_METHOD = "exact_mcnemar"
COMPARISON_ASSESSMENT_VERSION = "1"


def exact_mcnemar_pvalue(candidate_wins: int, reference_wins: int) -> float:
    """Return the two-sided exact sign test over discordant episodes."""
    discordant = candidate_wins + reference_wins
    if discordant == 0:
        return 1.0
    smaller = min(candidate_wins, reference_wins)
    tail = sum(math.comb(discordant, value) for value in range(smaller + 1))
    return min(1.0, 2 * tail / (2**discordant))


def paired_comparison(candidate: list[dict], reference: list[dict]) -> dict:
    """Protected paired counts with the researcher's exact statistic added."""
    result = paired_counts(candidate, reference)
    return {
        **result,
        "exact_p_value": exact_mcnemar_pvalue(
            int(result["candidate_wins"]), int(result["reference_wins"])
        ),
    }


def comparison_assessment(
    candidate_name: str,
    reference_name: str,
    candidate: list[dict],
    reference: list[dict],
    *,
    interpretation: str,
    limitations: str,
    artifacts: list[str] | None = None,
) -> dict:
    """Default researcher-authored assessment over the protected paired record.

    The protected counts identify the comparison; the method and version name the
    statistic this Researcher chose, and the uncertainty measure is its exact
    p-value. Interpretation and limitations remain the Researcher's text. A
    Researcher may replace the method and uncertainty with another justified
    statistic without weakening the protected counts, because the Runner validates
    only that the referenced record matches the measured ledger.
    """
    result = paired_counts(candidate, reference)
    return {
        "record": {
            "candidate": str(candidate_name),
            "reference": str(reference_name),
            "artifacts": list(artifacts or []),
            "episodes": int(result["episodes"]),
            "candidate_wins": int(result["candidate_wins"]),
            "reference_wins": int(result["reference_wins"]),
        },
        "method": COMPARISON_ASSESSMENT_METHOD,
        "method_version": COMPARISON_ASSESSMENT_VERSION,
        "uncertainty": {
            "measure": "exact_p_value",
            "value": exact_mcnemar_pvalue(
                int(result["candidate_wins"]), int(result["reference_wins"])
            ),
        },
        "interpretation": str(interpretation),
        "limitations": str(limitations),
    }
