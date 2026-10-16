"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


BRANCH_AWARE_RUNTIME_MARKER = "branch-aware-control-v1"


def physical_action(action):
    return action


def make_policy_io():
    # The runtime contract reconstructs PolicyIO from its callables when it
    # loads an artifact.  Keep the marker on the serialized action callable as
    # well as on the container so that reconstruction cannot discard it.
    physical_action.runtime_marker = BRANCH_AWARE_RUNTIME_MARKER
    policy_io = PolicyIO(observe=reach_observation, action=physical_action)
    # PolicyIO is intentionally a small, backwards-compatible dataclass owned
    # by the runtime contract.  This explicit attribute is serialized with
    # newly exported artifacts; old payloads have no marker and remain direct.
    policy_io.runtime_marker = BRANCH_AWARE_RUNTIME_MARKER
    return policy_io


def is_branch_aware_policy_io(policy_io) -> bool:
    """Gate the new controller on the serialized artifact marker."""
    return (
        getattr(policy_io, "runtime_marker", None)
        == BRANCH_AWARE_RUNTIME_MARKER
        or getattr(policy_io.action, "runtime_marker", None)
        == BRANCH_AWARE_RUNTIME_MARKER
    )
