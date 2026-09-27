# Research postmortems

## a4e64322-8d31-4479-9b0f-c04211eaf8b4 / Scientific strategy

**Current synthesis:** The strongest measured policy is checkpoint-100352, which completed 196 of 200 episodes on the task-reference-v1 development panel. The task couples reaching a 1 cm endpoint tolerance with a continuous 2 second hold, so complete-task success is the relevant baseline criterion rather than training reward. The four failures were 500-step truncations with final distances of approximately 0.986-1.325 cm and targets concentrated near -116 to -128 degrees at radii of 6.7-9.9 cm. This establishes a strong development baseline, not official objective completion.

**Lessons and limits:** Training reward and the training success proxy did not rank policies reliably: the reward peak achieved 94% on the panel, while checkpoint-100352 achieved 98%. The later checkpoint achieved 97%, so additional training did not preserve the selected checkpoint's measured performance. The panel is development evidence and is distinct from the official benchmark; its results cannot establish generalization or campaign success.

**Competing explanations:** The clustered failures may reflect target-dependent reachability or control authority, an observation/action mapping weakness in a particular arm configuration, or a reach-versus-hold settling failure near the tolerance boundary. The late-checkpoint regression may reflect stochastic evaluation variation, training instability, or policy drift, but the current measurements do not discriminate among these explanations.

**Decision frontier:** After baseline designation, determine whether the clustered failures are caused primarily by approach geometry, endpoint settling, or sustained hold control. Evidence that separates these mechanisms should measure the temporal distance and hold trajectory by target region, while preserving the protected task-reference contract. Redirect if failures are not reproducible or if the same mechanism appears across target regions; otherwise use the identified mechanism to define the next inquiry without treating a local reward or parameter change as an explanation.
