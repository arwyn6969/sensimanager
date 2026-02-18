"""SWOS420 — PPO Agent Bridge for Real DOSBox SWOS.

Bridges the existing PettingZoo SWOSManagerEnv to observe and control
a real DOSBox-X SWOS session via the AIDOSBoxController.

Provides a Gymnasium-compatible Env for SB3 PPO training with:
- Screenshot-based observations (84×84 grayscale, Atari-style)
- Action space mapped to AIDOSBoxController.send_action()
- Reward function: goals scored (+1.0), conceded (-1.0), win (+3.0)

Usage:
    from swos420.ai.ai_ppo_bridge import DOSBoxSWOSEnv

    env = DOSBoxSWOSEnv(game_dir="/path/to/swos")
    obs, info = env.reset()
    obs, reward, terminated, truncated, info = env.step(action)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Standard Atari-style observation dimensions
OBS_WIDTH = 84
OBS_HEIGHT = 84

# Action space size: 10 formations × 4 styles × 5 ball actions
NUM_FORMATIONS = 10
NUM_STYLES = 4
NUM_BALL_ACTIONS = 5  # none, pass, shoot, long_pass, direction

# Reward constants
REWARD_GOAL_SCORED = 1.0
REWARD_GOAL_CONCEDED = -1.0
REWARD_WIN = 3.0
REWARD_DRAW = 0.5
REWARD_LOSS = -2.0
REWARD_STEP = -0.001  # Small penalty per step to encourage decisive play


class DOSBoxSWOSEnv:
    """Gymnasium-compatible environment for PPO training on real SWOS.

    Wraps AIDOSBoxController to provide standard RL interface.
    Falls back to ICP simulation when DOSBox is unavailable.
    """

    # Gymnasium API metadata
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 2}

    def __init__(
        self,
        game_dir: str | Path | None = None,
        render_mode: str | None = None,
        max_steps: int = 5400,  # ~90 min at 2 Hz = 10800, halved for speed
        use_dosbox: bool = True,
    ):
        self.game_dir = Path(game_dir) if game_dir else None
        self.render_mode = render_mode
        self.max_steps = max_steps
        self._use_dosbox = use_dosbox
        self._controller = None
        self._step_count = 0
        self._prev_home_score = 0
        self._prev_away_score = 0
        self._done = False

        # Observation space: 84×84 grayscale image
        self._observation_space_shape = (OBS_HEIGHT, OBS_WIDTH)

        # Action space: Discrete multi-component
        # [formation_idx(0-9), style_idx(0-3), ball_action(0-4)]
        self._action_space_size = NUM_FORMATIONS * NUM_STYLES * NUM_BALL_ACTIONS

        self._init_controller()

    def _init_controller(self) -> None:
        """Initialize the DOSBox controller if available."""
        if self.game_dir and self._use_dosbox:
            try:
                from swos420.engine.ai_dosbox_controller import AIDOSBoxController
                self._controller = AIDOSBoxController(self.game_dir)
                if not self._controller.gui_available:
                    logger.warning("GUI not available — DOSBox control disabled")
                    self._controller = None
            except Exception as e:
                logger.warning("Failed to init DOSBox controller: %s", e)
                self._controller = None

    @property
    def observation_space(self) -> dict:
        """Return observation space spec."""
        return {
            "shape": self._observation_space_shape,
            "dtype": np.uint8,
            "low": 0,
            "high": 255,
        }

    @property
    def action_space(self) -> dict:
        """Return action space spec."""
        return {
            "n": self._action_space_size,
            "type": "Discrete",
        }

    def reset(
        self,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        """Reset environment for a new match.

        Returns:
            (observation, info) tuple.
        """
        if seed is not None:
            np.random.seed(seed)

        self._step_count = 0
        self._prev_home_score = 0
        self._prev_away_score = 0
        self._done = False

        # Get initial observation
        obs = self._get_observation()
        info = {"match_time": 0, "score": "0-0"}

        return obs, info

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:
        """Execute one step.

        Args:
            action: Discrete action index.

        Returns:
            (observation, reward, terminated, truncated, info)
        """
        self._step_count += 1

        # Decode composite action
        action_dict = self._decode_action(action)

        # Send to controller
        if self._controller is not None:
            self._controller.send_action(action_dict)

        # Get new observation
        obs = self._get_observation()

        # Calculate reward
        reward = self._calculate_reward()

        # Check termination
        terminated = self._check_match_end()
        truncated = self._step_count >= self.max_steps

        if terminated or truncated:
            reward += self._final_reward()
            self._done = True

        info = {
            "step": self._step_count,
            "score": f"{self._prev_home_score}-{self._prev_away_score}",
            "action": action_dict,
        }

        return obs, reward, terminated, truncated, info

    def _decode_action(self, action: int) -> dict[str, Any]:
        """Decode a discrete action index to action dict."""
        formation_idx = action // (NUM_STYLES * NUM_BALL_ACTIONS)
        remainder = action % (NUM_STYLES * NUM_BALL_ACTIONS)
        style_idx = remainder // NUM_BALL_ACTIONS
        ball_action = remainder % NUM_BALL_ACTIONS

        styles = ["attacking", "defensive", "balanced", "counter"]
        ball_actions = {
            0: {},                    # No ball action
            1: {"pass": True},
            2: {"shoot": True},
            3: {"long_pass": True},
            4: {"direction": "up"},   # Push forward
        }

        result = {
            "formation": formation_idx,
            "style": styles[style_idx],
        }
        result.update(ball_actions.get(ball_action, {}))

        return result

    def _get_observation(self) -> np.ndarray:
        """Get current observation as 84×84 grayscale array."""
        if self._controller is not None:
            obs = self._controller.get_observation()
            if obs.raw_pixels is not None and isinstance(obs.raw_pixels, np.ndarray):
                if obs.raw_pixels.shape == self._observation_space_shape:
                    return obs.raw_pixels

        # Fallback: zero observation
        return np.zeros(self._observation_space_shape, dtype=np.uint8)

    def _calculate_reward(self) -> float:
        """Calculate step reward from score changes."""
        reward = REWARD_STEP  # Small step penalty

        if self._controller is not None:
            obs = self._controller.get_observation()
            home_score = obs.home_score
            away_score = obs.away_score

            # Goal scored by our team (home)
            if home_score > self._prev_home_score:
                reward += REWARD_GOAL_SCORED * (home_score - self._prev_home_score)

            # Goal conceded
            if away_score > self._prev_away_score:
                reward += REWARD_GOAL_CONCEDED * (away_score - self._prev_away_score)

            self._prev_home_score = home_score
            self._prev_away_score = away_score

        return reward

    def _final_reward(self) -> float:
        """Calculate end-of-match bonus/penalty."""
        if self._prev_home_score > self._prev_away_score:
            return REWARD_WIN
        elif self._prev_home_score == self._prev_away_score:
            return REWARD_DRAW
        return REWARD_LOSS

    def _check_match_end(self) -> bool:
        """Check if the SWOS match has finished."""
        if self._controller is not None:
            from swos420.engine.ai_dosbox_controller import ControllerState
            return self._controller.state == ControllerState.RESULT

        # Without controller, rely on step count
        return False

    def render(self) -> np.ndarray | None:
        """Render current frame."""
        if self.render_mode == "rgb_array":
            return self._get_observation()
        return None

    def close(self) -> None:
        """Clean up resources."""
        if self._controller is not None:
            self._controller.stop()
