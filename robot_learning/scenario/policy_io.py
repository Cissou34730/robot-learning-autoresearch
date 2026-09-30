"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import (
    reach_observation,
    select_analytic_ik_reference,
    wrap_to_pi,
)

REFERENCE_POSITION_GAIN = 0.16
REFERENCE_VELOCITY_GAIN = 0.035
RESIDUAL_TORQUE_SCALE = 0.5
ACTUATOR_GEAR = 5.0


class BranchConditionedReference:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._qpos: np.ndarray | None = None
        self._qvel: np.ndarray | None = None
        self._target: np.ndarray | None = None
        self._joint_reference: np.ndarray | None = None
        self._ik_branch: int | None = None

    def observe(self, data) -> np.ndarray:
        self._qpos = np.array(data.qpos[:2], dtype=np.float64, copy=True)
        self._qvel = np.array(data.qvel[:2], dtype=np.float64, copy=True)
        self._target = np.array(data.mocap_pos[0, :2], dtype=np.float64, copy=True)
        if self._joint_reference is None:
            self._joint_reference, self._ik_branch = select_analytic_ik_reference(
                self._target, self._qpos
            )
        return reach_observation(
            data,
            joint_reference=self._joint_reference,
            ik_branch=self._ik_branch,
        )

    def action(self, action) -> np.ndarray:
        requested = np.asarray(action, dtype=np.float64)
        if self._qpos is None or self._qvel is None or self._joint_reference is None:
            return requested

        reference_error = np.array(
            [
                wrap_to_pi(
                    float(self._joint_reference[index]) - float(self._qpos[index])
                )
                for index in range(2)
            ],
            dtype=np.float64,
        )
        scaffold = (
            REFERENCE_POSITION_GAIN * reference_error
            - REFERENCE_VELOCITY_GAIN * self._qvel
        ) / ACTUATOR_GEAR
        return (scaffold + RESIDUAL_TORQUE_SCALE * requested).astype(
            np.float64, copy=False
        )


def physical_action(action):
    return action


def make_policy_io():
    reference = BranchConditionedReference()
    return PolicyIO(
        observe=reference.observe,
        action=reference.action,
        reset=reference.reset,
    )
