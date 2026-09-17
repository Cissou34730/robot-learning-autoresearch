"""Guard the development panel against coincidence with the official panel.

Issue #42: the research-evaluation default seed and episode count once matched
the official benchmark exactly, so ``research_evaluation`` reproduced the
terminal verdict panel during development and the official result was not held
out. The defaults remain decoupled, and requests that would overlap the
protected episodes are rejected.
"""

import pytest

from robot_learning.benchmark import final_contract
from robot_learning.benchmark.final_benchmark import official_environment
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.training import research_config


def _sample_targets(env, seed: int, episodes: int) -> list[tuple[float, float, float]]:
    targets = []
    for episode in range(episodes):
        env.reset(seed=seed + episode)
        targets.append(tuple(float(value) for value in env.data.mocap_pos[0]))
    return targets


def test_development_defaults_do_not_coincide_with_the_official_panel():
    development = (
        research_config.RESEARCH_EVALUATION_SEED,
        research_config.RESEARCH_EVALUATION_EPISODES,
    )
    official = (
        final_contract.EVALUATION_SEED,
        final_contract.EVALUATION_EPISODES,
    )
    assert development != official


def test_development_defaults_differ_on_seed_and_episode_count():
    assert research_config.RESEARCH_EVALUATION_SEED != final_contract.EVALUATION_SEED
    assert (
        research_config.RESEARCH_EVALUATION_EPISODES
        != final_contract.EVALUATION_EPISODES
    )


def test_default_development_target_sequence_differs_from_the_official_one():
    episodes = min(
        research_config.RESEARCH_EVALUATION_EPISODES,
        final_contract.EVALUATION_EPISODES,
    )
    development = _sample_targets(
        make_evaluation_env(), research_config.RESEARCH_EVALUATION_SEED, episodes
    )
    official = _sample_targets(
        official_environment(), final_contract.EVALUATION_SEED, episodes
    )
    assert development != official


def test_explicit_official_panel_is_rejected():
    from research import runner_protocol as protocol

    request = {
        "experiment": 1,
        "question": "question",
        "reason": "reason",
        "measurements": [
            {
                "instrument": "research_evaluation",
                "candidate": "candidate",
                "episodes": final_contract.EVALUATION_EPISODES,
                "seed": final_contract.EVALUATION_SEED,
                "selection": "explicitly choose the official episodes",
                "omitted_alternative": None,
            }
        ],
    }
    protocol.validate_evaluation_request(request)
    with pytest.raises(ValueError, match="protected benchmark evidence"):
        protocol.validate_panel_independence(request, [])
