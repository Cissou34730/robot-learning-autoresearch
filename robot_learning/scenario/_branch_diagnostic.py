"""Temporary researcher diagnostic: observe the working policy's joint trajectory.

Not part of the scientific recipe; removed before the proposal is written.
"""

import json
import sys

import numpy as np

from robot_learning.policy_runtime import load_runtime
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH as L2
from robot_learning.robots.two_joint_arm import UPPER_ARM_LENGTH as L1
from robot_learning.scenario.environment import make_evaluation_env

MODEL = (
    "research/checkpoints/retained/59709a6b-6a0b-4fa1-95e7-9b9cba8cdeed/"
    "e2-cada55eb5-45653a1b42227142f0a58cfb97bf6cf8672ad93f3d5688e6094760fd2246f771/model.zip"
)


def wrap_to_pi(angle):
    return (angle + np.pi) % (2.0 * np.pi) - np.pi


def branches(tx, ty):
    r2 = tx * tx + ty * ty
    c = (r2 - L1 * L1 - L2 * L2) / (2.0 * L1 * L2)
    elbow_open = float(np.arccos(np.clip(c, -1.0, 1.0)))
    phi = np.arctan2(ty, tx)
    shoulder_open = phi - np.arctan2(
        L2 * np.sin(elbow_open), L1 + L2 * np.cos(elbow_open)
    )
    shoulder_folded = phi - np.arctan2(
        -L2 * np.sin(elbow_open), L1 + L2 * np.cos(elbow_open)
    )
    return shoulder_open, elbow_open, shoulder_folded, -elbow_open


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    seed0 = int(sys.argv[2]) if len(sys.argv) > 2 else 26000
    runtime = load_runtime(MODEL)
    env = make_evaluation_env(policy_runtime=runtime)
    rows = []
    for ep in range(n):
        seed = seed0 + ep
        obs, _ = env.reset(seed=seed)
        runtime.reset()
        tx = float(env.data.mocap_pos[0][0])
        ty = float(env.data.mocap_pos[0][1])
        so, _eo, sf, ef = branches(tx, ty)
        wrapped = float(np.degrees(wrap_to_pi(so)))
        folded = abs(wrapped) > 170.0
        sh_min = sh_max = el_min = el_max = None
        shoulder_at_min = elbow_at_min = None
        min_d = float("inf")
        success = False
        steps = 0
        while True:
            action = runtime.predict(obs)
            obs, _reward, term, trunc, info = env.step(action)
            steps += 1
            q0 = float(env.data.qpos[0])
            q1 = float(env.data.qpos[1])
            d = float(info["distance"])
            if d < min_d:
                min_d = d
                shoulder_at_min = q0
                elbow_at_min = q1
            sh_min = q0 if sh_min is None else min(sh_min, q0)
            sh_max = q0 if sh_max is None else max(sh_max, q0)
            el_min = q1 if el_min is None else min(el_min, q1)
            el_max = q1 if el_max is None else max(el_max, q1)
            if info.get("is_success"):
                success = True
            if term or trunc:
                break
        rows.append(
            {
                "seed": seed,
                "folded": folded,
                "success": success,
                "wrapped_open_shoulder_deg": wrapped,
                "open_shoulder_deg": float(np.degrees(so)),
                "folded_shoulder_deg": float(np.degrees(sf)),
                "folded_elbow_deg": float(np.degrees(ef)),
                "min_d_cm": 100.0 * min_d,
                "shoulder_at_min_deg": float(np.degrees(shoulder_at_min)),
                "elbow_at_min_deg": float(np.degrees(elbow_at_min)),
                "shoulder_min_deg": float(np.degrees(sh_min)),
                "shoulder_max_deg": float(np.degrees(sh_max)),
                "elbow_min_deg": float(np.degrees(el_min)),
                "elbow_max_deg": float(np.degrees(el_max)),
                "final_shoulder_deg": float(np.degrees(float(env.data.qpos[0]))),
                "final_elbow_deg": float(np.degrees(float(env.data.qpos[1]))),
                "steps": steps,
            }
        )
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
