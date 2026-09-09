"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

OBSERVATION_SIZE = 11


def reach_observation(data) -> np.ndarray:
    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    end_effector = data.site("end_effector").xpos.copy()
    return np.concatenate(
        [
            np.sin(data.qpos),
            np.cos(data.qpos),
            data.qvel,
            end_effector - data.mocap_pos[0],
            [target_x, target_y],
        ]
    ).astype(np.float32)
