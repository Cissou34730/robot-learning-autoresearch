# Current scenario: two-joint arm reach-and-hold

The scientific problem studied by this repository. `research/program.md` defines
the research protocol; read both.

## Objective

Fixed by the human:

* target sampled 6–20 cm from the robot base;
* end effector within 1 cm of the target;
* held continuously within tolerance for 2 seconds — currently 100 control
  steps, derived from the official control timing;
* at least 98% success over the fixed 200-episode official benchmark.

Only the human-owned official benchmark may declare the objective reached.

## Protected boundary

The official task fixes:

* the robot asset referenced by `TWO_JOINT_ARM_XML_PATH`, its geometry, joints,
  actuators and actuator limits;
* action semantics and control limits;
* the MuJoCo timestep, `frame_skip` and official control timing;
* reset and initial-state semantics;
* the target distribution, success tolerance, hold duration, episode horizon and
  success computation.

These define the physical problem and are not research variables.

A proposal is rejected if it changes any file on the trust path between the
runner and the protected task:

* `research/run_experiment.py`;
* `robot_learning/benchmark/final_contract.py`;
* `robot_learning/benchmark/final_benchmark.py`;
* `robot_learning/scenario/final_benchmark.py`;
* `robot_learning/robots/two_joint_arm.py`;
* `robot_learning/robots/two_joint_arm.xml`;
* the `__init__.py` of `robot_learning`, `robot_learning/benchmark`,
  `robot_learning/robots` and `robot_learning/scenario`, which resolve those
  imports;
* anything under `tests/benchmark/`, which verifies the frozen robot, the task
  contract, the hold metric and the goal verdict;
* anything under `tests/autoresearch/`, which verifies the generic research
  protocol and protected boundary.

## Training and research environment

The official task is what is measured; the environment used to learn it is
yours. Research may change the reward, observations, normalization, exploration,
curriculum, training target distribution and randomization, wrappers, learning
algorithm, optimizer, architecture, and the action representation as long as the
resulting policy still controls the official robot correctly.

A curriculum or an easier training environment is legitimate. Reporting success
on it is not.

Policy-specific preprocessing and normalization belong to the learned artifact
and may run during official evaluation when the policy needs them. They must not
redefine the official physics or objective.

## Scenario code

`robot_learning/scenario/` is researcher-owned except the protected
`final_benchmark.py` and `__init__.py`:

* `environment.py` — training task mechanics and `make_training_env()`;
* `observations.py` — the observation the policy receives;
* `reward.py` — the complete reward, including its coefficients;
* `evaluation.py` — research evaluation and researcher-owned scientific instrumentation;
* `progress.py` — the scenario phrase shown in the live training console;
* `viewer.py` — MuJoCo live training view and trained-policy playback.

Reward coefficients are not in `research/current_params.json`; to change the
reward, change `reward.py`.

`tests/scenario/` covers this surface and belongs to you. A change to the
reward, the observation or the training task should update it in the same
experiment. Do not freeze a numerical snapshot of mutable scenario output as a
test expectation; express expectations through the active implementation.
