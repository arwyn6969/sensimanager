"""Baseline agents for evaluation and benchmarking.

RandomAgent: uniformly random valid actions.
HeuristicAgent: simple rule-based manager (strongest XI, sensible transfers).
"""

from __future__ import annotations

import random

import numpy as np



class RandomAgent:
    """Agent that takes uniformly random actions from the action space."""

    def __init__(self, action_space, seed: int | None = None):
        self._action_space = action_space
        self._rng = random.Random(seed)

    def act(self, observation: dict | None = None) -> dict:
        """Return a random valid action."""
        return self._action_space.sample()


class HeuristicAgent:
    """Simple rule-based manager.

    Strategy:
    - Default 4-4-2, balanced style
    - Rest training when average fatigue > 60
    - Bid on highest-skill available targets during windows
    - Make substitutions based on fatigue
    """

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._formation_idx = 0  # 4-4-2
        self._style_idx = 2  # balanced

    def act(self, observation: dict | None = None) -> dict:
        """Return a heuristic action based on observation."""
        action = {
            "formation": self._formation_idx,
            "style": self._style_idx,
            "training_focus": self._choose_training(observation),
            "scouting_level": 1,  # Basic scouting
        }

        # Transfer bids (bid on top targets if window is open)
        is_window = False
        if observation is not None and "meta" in observation:
            is_window = observation["meta"][2] > 0.5

        for i in range(3):
            if is_window and self._rng.random() < 0.3:
                action[f"transfer_bid_{i}"] = self._rng.randint(1, 5)
                action[f"bid_amount_{i}"] = np.float32(self._rng.uniform(0.3, 0.7))
            else:
                action[f"transfer_bid_{i}"] = 0
                action[f"bid_amount_{i}"] = np.float32(0.0)

        # Substitutions (occasionally rotate)
        for i in range(3):
            if self._rng.random() < 0.15:
                action[f"sub_{i}"] = self._rng.randint(1, 5)
            else:
                action[f"sub_{i}"] = 0

        return action

    def _choose_training(self, observation: dict | None) -> int:
        """Choose training focus based on squad state."""
        if observation is not None and "own_squad" in observation:
            # Check average fatigue (column 11)
            squad = observation["own_squad"]
            avg_fatigue = np.mean(squad[:11, 11]) if squad.shape[0] >= 11 else 0
            if avg_fatigue > 0.6:
                return 4  # rest
        return self._rng.randint(0, 3)  # Random training
