"""Protected benchmark panel bounds for research panel-independence checks.

Kept outside the runner modules so the generic Runner never imports the
human-owned benchmark package directly. The official seed and episode count are
read from the protected contract, never duplicated here.
"""

from __future__ import annotations


def protected_episode_panel() -> tuple[int, int]:
    """The official benchmark episode interval ``(seed, episodes)``."""
    from robot_learning.benchmark import final_contract

    return final_contract.EVALUATION_SEED, final_contract.EVALUATION_EPISODES
