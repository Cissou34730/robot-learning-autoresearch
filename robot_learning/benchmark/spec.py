"""Immutable benchmark constants.

Research code may change how the robot learns, but never these values.
"""

TARGET_RADIUS_RANGE = (0.06, 0.20)
MAX_EPISODE_STEPS = 500
FRAME_SKIP = 10

CURRICULUM_STAGES: tuple[tuple[float, float], ...] = (
    (0.03, 0.02),
    (0.02, 0.02),
    (0.01, 0.02),
    (0.01, 0.10),
    (0.01, 0.50),
    (0.01, 1.00),
    (0.01, 1.50),
    (0.01, 2.00),
)

FINAL_STAGE_INDEX = len(CURRICULUM_STAGES) - 1
FINAL_SUCCESS_PERCENT = 98.0
STAGE_PROMOTION_PERCENT = 60.0
EVALUATION_EPISODES = 200
EVALUATION_SEED = 1000


def stage_spec(stage_index: int) -> tuple[float, float]:
    if not 0 <= stage_index < len(CURRICULUM_STAGES):
        raise ValueError(f"invalid curriculum stage: {stage_index}")
    return CURRICULUM_STAGES[stage_index]

