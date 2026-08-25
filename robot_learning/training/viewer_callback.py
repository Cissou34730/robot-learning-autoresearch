import time

import mujoco
import mujoco.viewer
from stable_baselines3.common.callbacks import BaseCallback


class LiveViewerCallback(BaseCallback):
    def __init__(self, real_time: bool = True, speed: float = 1.0) -> None:
        super().__init__()
        self.real_time = real_time
        self.speed = speed
        self.viewer = None
        self._control_dt = 0.02

    def _on_training_start(self) -> None:
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
