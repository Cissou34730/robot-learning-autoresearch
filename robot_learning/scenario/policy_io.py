"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


DIRECT_CONTROL_PROFILE = "direct"
RESIDUAL_TORQUE_PROFILE = "residual_torque"
CONTROL_PROFILE_MARKER = "control_profile"
KNOWN_CONTROL_PROFILES = {
    DIRECT_CONTROL_PROFILE,
    RESIDUAL_TORQUE_PROFILE,
}


def physical_action(action):
    return action


def make_policy_io(control_profile: str = DIRECT_CONTROL_PROFILE):
    if (
        not isinstance(control_profile, str)
        or control_profile not in KNOWN_CONTROL_PROFILES
    ):
        raise ValueError(f"unknown control profile: {control_profile}")
    policy_io = PolicyIO(observe=reach_observation, action=physical_action)
    object.__setattr__(policy_io, CONTROL_PROFILE_MARKER, control_profile)
    return policy_io
