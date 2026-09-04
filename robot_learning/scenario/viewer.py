"""Scenario-owned rendering: live training view and trained-policy playback.

Generic code asks for a viewer callback or a playback run; everything about the
MuJoCo viewer, the control period and this robot's episode telemetry lives here.
"""

import time
from pathlib import Path

from stable_baselines3.common.callbacks import BaseCallback

from robot_learning.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env


class _LiveViewerCallback(BaseCallback):
    def __init__(self, real_time: bool = True, speed: float = 1.0) -> None:
        super().__init__()
        self.real_time = real_time
        self.speed = speed
        self.viewer = None
        self._control_dt = 0.02

    def _on_training_start(self) -> None:
        # Imported here so headless runs never load the windowing stack.
        import mujoco.viewer

        env = self.training_env.envs[0].unwrapped
        self._control_dt = float(env.model.opt.timestep * env.frame_skip)
        self.viewer = mujoco.viewer.launch_passive(env.model, env.data)
        self.viewer.sync()

    def _on_step(self) -> bool:
        if self.viewer.is_running():
            self.viewer.sync()
            if self.real_time:
                time.sleep(self._control_dt / max(self.speed, 1e-6))
        return True

    def _on_training_end(self) -> None:
        if not self.viewer.is_running():
            return
        print("Training finished. Close the MuJoCo viewer window to exit.")
        while self.viewer.is_running():
            time.sleep(0.1)


def make_training_viewer_callback(speed: float = 1.0) -> BaseCallback:
    """Callback that shows this scenario live while training."""
    return _LiveViewerCallback(speed=speed)


def watch_scenario_policy(
    model_path: Path, *, episodes: int = 10, speed: float = 1.0
) -> None:
    """Replay a trained policy in this scenario's viewer."""
    import mujoco.viewer

    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    control_dt = env.model.opt.timestep * env.frame_skip

    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        for _ in range(episodes):
            obs, _ = env.reset()
            runtime.reset()
            episode_reward = 0.0
            done = False
            while not done and viewer.is_running():
                action = runtime.predict(obs)
                obs, reward, terminated, truncated, info = env.step(action)
                episode_reward += reward
                done = terminated or truncated
                viewer.sync()
                time.sleep(control_dt / max(speed, 1e-6))
            print(
                f"episode finished: reward={episode_reward:.2f} "
                f"success={info['is_success']}"
            )
            if not viewer.is_running():
                break
