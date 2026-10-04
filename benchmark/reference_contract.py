"""Human-owned task-reference panel.

The same protected human task as the final benchmark, measured on a different
fixed panel. It exists so models can be compared against the original task
during research, independently of whatever training environment, reward or
research evaluation the researcher currently uses.

It is development evidence only. A task-reference score never means the
objective has been reached; only the final benchmark produces that verdict.
"""

PANEL_VERSION = 1
PANEL_ID = "task-reference-v1"
EVALUATION_EPISODES = 200
# Distinct from the final benchmark seed so the two panels never coincide.
EVALUATION_SEED = 7300
