#!/usr/bin/env python3
"""train_managers.py — Train AI football managers with parameter-sharing PPO.

Creates a Gymnasium wrapper around the PettingZoo SWOSManagerEnv that presents
each agent's perspective as a separate Gymnasium step (parameter-sharing MAPPO).
This avoids supersuit compatibility issues with Dict observation spaces.

Usage:
    python scripts/train_managers.py
    python scripts/train_managers.py --timesteps 500000 --num-teams 8 --device mps
    python scripts/train_managers.py --eval-only --model-path models/swos420_ppo
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import gymnasium
import numpy as np
from gymnasium import spaces

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("train_managers")


class SWOSGymWrapper(gymnasium.Env):
    """Wraps SWOSManagerEnv into a single-agent Gymnasium env.

    Implements parameter-sharing MAPPO: each Gymnasium 'step' processes
    one agent's turn. All agents share the same observation/action space
    and policy network.

    Observations are flattened from Dict → Box for SB3 compatibility.
    Actions are mapped from flat MultiDiscrete → the Dict expected by the env.
    """

    metadata = {"render_modes": []}

    def __init__(self, num_teams: int = 4, seed: int = 42, **kwargs):
        super().__init__()
        from swos420.ai.env import SWOSManagerEnv
        from swos420.ai.actions import FORMATIONS, STYLES, TRAINING_FOCUS

        self._pz_env = SWOSManagerEnv(num_teams=num_teams, seed=seed)
        self._num_teams = num_teams
        self._seed = seed

        # Build flat observation space
        # league_table: (num_teams, 6) + own_squad: (22, 12) + finances: (4,) + meta: (4,)
        self._obs_size = num_teams * 6 + 22 * 12 + 4 + 4
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(self._obs_size,), dtype=np.float32
        )

        # Build flat action space as MultiDiscrete
        # [formation, style, training_focus, scouting_level,
        #  transfer_bid_0..2, sub_0..2]
        # bid_amount is discretized to 10 levels
        n_formations = len(FORMATIONS)
        n_styles = len(STYLES)
        n_training = len(TRAINING_FOCUS)
        self._max_targets = 16  # 0 = no bid, 1-15 = target index
        self._max_bench = 6    # 0 = no sub, 1-5 = bench slot

        self.action_space = spaces.MultiDiscrete([
            n_formations,       # formation
            n_styles,           # style
            n_training,         # training_focus
            4,                  # scouting_level
            self._max_targets,  # transfer_bid_0
            10,                 # bid_amount_0 (discretized 0-1)
            self._max_targets,  # transfer_bid_1
            10,                 # bid_amount_1
            self._max_targets,  # transfer_bid_2
            10,                 # bid_amount_2
            self._max_bench,    # sub_0
            self._max_bench,    # sub_1
            self._max_bench,    # sub_2
        ])

        # State tracking
        self._current_obs = {}
        self._agent_queue = []
        self._pending_actions = {}
        self._last_rewards = {}

    def _flatten_obs(self, obs_dict: dict) -> np.ndarray:
        """Flatten Dict observation to a 1D float32 array."""
        parts = [
            obs_dict["league_table"].flatten(),
            obs_dict["own_squad"].flatten(),
            obs_dict["finances"].flatten(),
            obs_dict["meta"].flatten(),
        ]
        return np.concatenate(parts).astype(np.float32)

    def _unflatten_action(self, flat_action: np.ndarray) -> dict:
        """Convert MultiDiscrete action to the Dict format expected by PZ env."""
        return {
            "formation": int(flat_action[0]),
            "style": int(flat_action[1]),
            "training_focus": int(flat_action[2]),
            "scouting_level": int(flat_action[3]),
            "transfer_bid_0": int(flat_action[4]),
            "bid_amount_0": np.float32(flat_action[5] / 9.0),
            "transfer_bid_1": int(flat_action[6]),
            "bid_amount_1": np.float32(flat_action[7] / 9.0),
            "transfer_bid_2": int(flat_action[8]),
            "bid_amount_2": np.float32(flat_action[9] / 9.0),
            "sub_0": int(flat_action[10]),
            "sub_1": int(flat_action[11]),
            "sub_2": int(flat_action[12]),
        }

    def reset(self, *, seed=None, options=None):
        """Reset the environment, return first agent's observation."""
        obs_dict, infos = self._pz_env.reset(seed=seed or self._seed)
        self._current_obs = obs_dict
        self._agent_queue = list(self._pz_env.agents)
        self._pending_actions = {}
        self._last_rewards = {a: 0.0 for a in self._agent_queue}

        if not self._agent_queue:
            return np.zeros(self._obs_size, dtype=np.float32), {}

        current_agent = self._agent_queue[0]
        flat_obs = self._flatten_obs(self._current_obs[current_agent])
        return flat_obs, {"agent": current_agent}

    def step(self, action):
        """Process one agent's action. When all agents have acted, step the PZ env."""
        if not self._agent_queue:
            return (
                np.zeros(self._obs_size, dtype=np.float32),
                0.0, True, False, {},
            )

        current_agent = self._agent_queue.pop(0)
        self._pending_actions[current_agent] = self._unflatten_action(action)

        # If more agents need to act this turn, return next agent's obs
        if self._agent_queue:
            next_agent = self._agent_queue[0]
            flat_obs = self._flatten_obs(self._current_obs[next_agent])
            # Return intermediate step with zero reward (real rewards come after matchday)
            return flat_obs, 0.0, False, False, {"agent": next_agent}

        # All agents have acted — step the PZ environment (simulate matchday)
        obs_dict, rewards, terms, truncs, infos = self._pz_env.step(self._pending_actions)
        self._current_obs = obs_dict
        self._last_rewards = rewards
        self._pending_actions = {}

        # Check if season is over
        if not self._pz_env.agents:
            # Season done — return final agent's reward
            flat_obs = np.zeros(self._obs_size, dtype=np.float32)
            final_reward = sum(rewards.values()) / max(len(rewards), 1)
            return flat_obs, final_reward, True, False, {"season_done": True}

        # Set up the next round of agent turns
        self._agent_queue = list(self._pz_env.agents)
        first_agent = self._agent_queue[0]
        flat_obs = self._flatten_obs(self._current_obs[first_agent])

        # Return first agent's obs with mean reward from the matchday
        mean_reward = sum(rewards.values()) / max(len(rewards), 1)
        return flat_obs, mean_reward, False, False, {"agent": first_agent}


def train(args: argparse.Namespace) -> Path:
    """Train PPO agents on the SWOS420 league environment."""
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CheckpointCallback
    from stable_baselines3.common.vec_env import DummyVecEnv

    logger.info("🏟  SWOS420 AI Manager Training")
    logger.info(f"   Teams: {args.num_teams}")
    logger.info(f"   Timesteps: {args.timesteps:,}")
    logger.info(f"   Device: {args.device}")
    logger.info(f"   Seed: {args.seed}")
    logger.info("=" * 60)

    # Create vectorized env
    vec_env = DummyVecEnv([
        lambda: SWOSGymWrapper(num_teams=args.num_teams, seed=args.seed)
    ])

    model_dir = Path(args.model_path)
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = model_dir.parent / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # Configure PPO
    model = PPO(
        "MlpPolicy",
        vec_env,
        verbose=1,
        learning_rate=3e-4,
        n_steps=256,
        batch_size=64,
        n_epochs=4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        device=args.device,
        seed=args.seed,
    )

    # Checkpoint periodically
    checkpoint_callback = CheckpointCallback(
        save_freq=max(10_000, args.timesteps // 10),
        save_path=str(checkpoint_dir),
        name_prefix="swos420_ppo",
    )

    start = time.time()
    logger.info("🚀 Training started...")

    model.learn(
        total_timesteps=args.timesteps,
        callback=checkpoint_callback,
    )

    elapsed = time.time() - start
    logger.info(f"⏱  Training completed in {elapsed:.1f}s")

    # Save final model
    model.save(str(model_dir))
    logger.info(f"💾 Model saved to {model_dir}")

    vec_env.close()
    return model_dir


def evaluate(args: argparse.Namespace) -> None:
    """Evaluate a trained model vs heuristic baseline over multiple seasons."""
    from stable_baselines3 import PPO

    model_path = Path(args.model_path)
    if not model_path.exists() and not Path(f"{model_path}.zip").exists():
        logger.error(f"Model not found: {model_path}")
        sys.exit(1)

    logger.info(f"📊 Evaluating model: {model_path}")
    model = PPO.load(str(model_path))

    env = SWOSGymWrapper(num_teams=args.num_teams, seed=args.seed)

    total_reward = 0.0
    for episode in range(3):
        obs, info = env.reset()
        ep_reward = 0.0
        done = False

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            ep_reward += reward
            done = terminated or truncated

        total_reward += ep_reward
        logger.info(f"  Episode {episode + 1}: reward = {ep_reward:+.2f}")

    print()
    print("=" * 60)
    print(f"  📊 Mean reward over 3 seasons: {total_reward / 3:+.2f}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SWOS420 — Train AI Football Managers with MAPPO"
    )
    parser.add_argument(
        "--timesteps", type=int, default=100_000,
        help="Total training timesteps (default: 100,000)",
    )
    parser.add_argument(
        "--num-teams", type=int, default=4,
        help="Number of teams in the league (default: 4)",
    )
    parser.add_argument(
        "--device", default="auto",
        help="PyTorch device: 'auto', 'cpu', 'cuda', 'mps' (default: auto)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--model-path", default="models/swos420_ppo",
        help="Path to save/load model (default: models/swos420_ppo)",
    )
    parser.add_argument(
        "--eval-only", action="store_true",
        help="Skip training, evaluate existing model",
    )
    args = parser.parse_args()

    if args.eval_only:
        evaluate(args)
    else:
        train(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
