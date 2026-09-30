"""Policy representations used by the current learning method."""

import gymnasium as gym
import torch
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from torch import nn


class BranchFactorizedExtractor(BaseFeaturesExtractor):
    """Keep separate learned pathways for the two observed IK branches."""

    def __init__(
        self,
        observation_space: gym.spaces.Box,
        *,
        hidden_size: int = 32,
    ) -> None:
        if observation_space.shape != (11,):
            raise ValueError(
                "branch-factorized policy requires the 11-element observation"
            )
        if hidden_size < 1:
            raise ValueError("hidden_size must be positive")
        super().__init__(observation_space, features_dim=2 * hidden_size)
        self.shared = nn.Sequential(
            nn.Linear(7, hidden_size),
            nn.Tanh(),
            nn.Linear(hidden_size, hidden_size),
            nn.Tanh(),
        )
        self.experts = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(hidden_size + 2, hidden_size),
                    nn.Tanh(),
                    nn.Linear(hidden_size, hidden_size),
                    nn.Tanh(),
                )
                for _ in range(2)
            ]
        )
        self.gate = nn.Sequential(
            nn.Linear(hidden_size + 4, hidden_size),
            nn.Tanh(),
            nn.Linear(hidden_size, 2),
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        shared = self.shared(observations[:, :7])
        branch_errors = observations[:, 7:11]
        gate = torch.softmax(self.gate(torch.cat((shared, branch_errors), dim=1)), dim=1)
        expert_inputs = (
            torch.cat((shared, branch_errors[:, 0:2]), dim=1),
            torch.cat((shared, branch_errors[:, 2:4]), dim=1),
        )
        expert_outputs = torch.stack(
            [expert(inputs) for expert, inputs in zip(self.experts, expert_inputs)],
            dim=1,
        )
        return (gate.unsqueeze(-1) * expert_outputs).flatten(start_dim=1)
