"""Short local throughput check for synchronized vector environments."""

import json
import time

import numpy as np
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from robot_learning.environments.reach_env import TwoJointArmReachEnv


def measure(n_envs: int, transitions: int = 4000) -> dict:
    vec_type = DummyVecEnv if n_envs == 1 else SubprocVecEnv
    env = make_vec_env(
        TwoJointArmReachEnv,
        n_envs=n_envs,
        seed=0,
        env_kwargs={"stage_index": 0},
        vec_env_cls=vec_type,
    )
    env.reset()
    actions = np.zeros((n_envs, 2), dtype=np.float32)
    started = time.perf_counter()
    completed = 0
    while completed < transitions:
        env.step(actions)
        completed += n_envs
    elapsed = time.perf_counter() - started
    env.close()
    return {
        "n_envs": n_envs,
        "transitions": completed,
        "seconds": elapsed,
        "transitions_per_second": completed / elapsed,
    }


def main() -> None:
    results = []
    for n_envs in (1, 2, 4):
        try:
            results.append(measure(n_envs))
        except Exception as error:  # noqa: BLE001
            results.append({"n_envs": n_envs, "error": str(error)})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
