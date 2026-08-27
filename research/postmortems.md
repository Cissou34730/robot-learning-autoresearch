# Research postmortems

## Geometry reset

All experiments before this reset are scientifically invalid for stages at or
below 2 cm. The end effector moved at z=2 cm while targets were sampled at z=0,
creating a 2 cm lower bound in the 3-D distance. Do not use those experiments as
negative evidence about PPO, SAC, rewards, observations, network size, or
curricula. The corrected program restarts with a fresh PPO baseline at stage 0.
