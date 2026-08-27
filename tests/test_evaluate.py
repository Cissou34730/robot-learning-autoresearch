from robot_learning.evaluate import achieved_milestones


def test_milestones_measure_progress_without_changing_final_goal():
    # One 20 ms sample at 1.5 cm clears 3 cm and 2 cm touch, but not 1 cm.
    achieved = achieved_milestones([0.05, 0.015, 0.04], control_dt=0.02)
    assert achieved[:2] == [True, True]
    assert achieved[2:] == [False] * 6


def test_hold_milestones_use_consecutive_time_in_band():
    distances = [0.005] * 25  # 0.5 seconds at 20 ms/control step
    achieved = achieved_milestones(distances, control_dt=0.02)
    assert achieved[:5] == [True] * 5
    assert achieved[5:] == [False] * 3
