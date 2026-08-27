"""Immutable benchmark constants.

Research code may change how the robot learns, but never these values.
"""

TARGET_RADIUS_RANGE = (0.06, 0.20)
MAX_EPISODE_STEPS = 500
FRAME_SKIP = 10

SUCCESS_THRESHOLD = 0.01
HOLD_SECONDS = 2.0
FINAL_SUCCESS_PERCENT = 98.0
EVALUATION_EPISODES = 200
EVALUATION_SEED = 1000
