"""Benchmark utilities for comparing manager policies in SWOSManagerEnv.

Produces reproducible multi-season reports for random, heuristic, and PPO
manager policies. Reports can be exported as JSON and CSV for tracking.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any

import numpy as np

from swos420.ai.baseline_agents import HeuristicAgent, RandomAgent
from swos420.ai.env import SWOSManagerEnv

VALID_POLICIES = {"random", "heuristic", "ppo"}


class BenchmarkError(RuntimeError):
    """Raised when benchmark inputs are invalid or incomplete."""


@dataclass
class PPOManagerAgent:
    """Adapter that lets SB3 PPO behave like a manager policy."""

    model_path: Path
    deterministic: bool = True

    def __post_init__(self) -> None:
        try:
            from stable_baselines3 import PPO
        except Exception as exc:  # pragma: no cover - exercised only if dependency missing
            raise BenchmarkError(
                "stable-baselines3 is required for policy='ppo'. Install with 'pip install -e \".[ai]\"'."
            ) from exc

        self._model = PPO.load(str(self.model_path))

    def act(self, observation: dict[str, np.ndarray] | None = None) -> dict[str, Any]:
        if observation is None:
            raise BenchmarkError("PPO policy requires a valid observation")

        flat_obs = flatten_observation(observation)
        action, _ = self._model.predict(flat_obs, deterministic=self.deterministic)
        return decode_flat_action(action)


def flatten_observation(observation: dict[str, np.ndarray]) -> np.ndarray:
    """Flatten SWOS manager dict observation into a 1D float32 array."""
    parts = [
        observation["league_table"].flatten(),
        observation["own_squad"].flatten(),
        observation["finances"].flatten(),
        observation["meta"].flatten(),
    ]
    return np.concatenate(parts).astype(np.float32)


def decode_flat_action(flat_action: np.ndarray | list[int] | tuple[int, ...]) -> dict[str, Any]:
    """Convert PPO MultiDiscrete output into SWOSManagerEnv action dict."""
    action_array = np.asarray(flat_action, dtype=np.int64).reshape(-1)
    if action_array.size != 13:
        raise BenchmarkError(f"Expected 13 action components, got {action_array.size}")

    return {
        "formation": int(action_array[0]),
        "style": int(action_array[1]),
        "training_focus": int(action_array[2]),
        "scouting_level": int(action_array[3]),
        "transfer_bid_0": int(action_array[4]),
        "bid_amount_0": np.float32(action_array[5] / 9.0),
        "transfer_bid_1": int(action_array[6]),
        "bid_amount_1": np.float32(action_array[7] / 9.0),
        "transfer_bid_2": int(action_array[8]),
        "bid_amount_2": np.float32(action_array[9] / 9.0),
        "sub_0": int(action_array[10]),
        "sub_1": int(action_array[11]),
        "sub_2": int(action_array[12]),
    }


def _build_policy_agent(
    policy: str,
    action_space: Any,
    seed: int,
    model_path: Path | None,
    deterministic_model: bool,
):
    if policy == "random":
        return RandomAgent(action_space, seed=seed)
    if policy == "heuristic":
        return HeuristicAgent(seed=seed)
    if policy == "ppo":
        if model_path is None:
            raise BenchmarkError("policy='ppo' requires --model-path")
        return PPOManagerAgent(model_path=model_path, deterministic=deterministic_model)

    raise BenchmarkError(f"Unsupported policy: {policy}")


def _season_table(env: SWOSManagerEnv) -> list[dict[str, Any]]:
    teams = [state.team for state in getattr(env, "_team_states", [])]
    teams.sort(key=lambda team: (team.points, team.goal_difference, team.goals_for), reverse=True)
    return [
        {
            "code": team.code,
            "name": team.name,
            "points": team.points,
            "goal_difference": team.goal_difference,
            "goals_for": team.goals_for,
            "goals_against": team.goals_against,
            "wins": team.wins,
            "draws": team.draws,
            "losses": team.losses,
        }
        for team in teams
    ]


def run_policy_season(
    *,
    policy: str,
    num_teams: int,
    seed: int,
    model_path: Path | None = None,
    deterministic_model: bool = True,
) -> dict[str, Any]:
    """Run one full season for a single policy and return detailed metrics."""
    env = SWOSManagerEnv(num_teams=num_teams, seed=seed)
    observations, _ = env.reset(seed=seed)

    policy_agents: dict[str, Any] = {}
    for i, agent_id in enumerate(env.agents):
        policy_agents[agent_id] = _build_policy_agent(
            policy=policy,
            action_space=env.action_space(agent_id),
            seed=seed + i,
            model_path=model_path,
            deterministic_model=deterministic_model,
        )

    cumulative_rewards = {agent_id: 0.0 for agent_id in env.possible_agents}
    matchdays_played = 0

    while env.agents:
        actions = {
            agent_id: policy_agents[agent_id].act(observations.get(agent_id))
            for agent_id in env.agents
        }
        observations, rewards, _, _, _ = env.step(actions)
        matchdays_played += 1

        for agent_id, reward in rewards.items():
            cumulative_rewards[agent_id] += float(reward)

    table = _season_table(env)
    champion = table[0] if table else None

    return {
        "seed": seed,
        "matchdays": matchdays_played,
        "mean_reward": float(fmean(cumulative_rewards.values())),
        "min_reward": float(min(cumulative_rewards.values())),
        "max_reward": float(max(cumulative_rewards.values())),
        "cumulative_rewards": cumulative_rewards,
        "champion": champion,
        "table": table,
    }


def run_benchmark(
    *,
    policies: list[str],
    seasons: int,
    num_teams: int,
    seed: int,
    model_path: Path | None = None,
    deterministic_model: bool = True,
) -> dict[str, Any]:
    """Run benchmark suite over multiple policies and seasons."""
    if seasons < 1:
        raise BenchmarkError("seasons must be >= 1")
    if num_teams < 2:
        raise BenchmarkError("num_teams must be >= 2")

    normalized = [policy.lower() for policy in policies]
    unknown = sorted(set(normalized) - VALID_POLICIES)
    if unknown:
        raise BenchmarkError(f"Unknown policy values: {', '.join(unknown)}")

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "policies": normalized,
            "seasons": seasons,
            "num_teams": num_teams,
            "seed": seed,
            "model_path": str(model_path) if model_path else None,
            "deterministic_model": deterministic_model,
        },
        "results": {},
    }

    for policy in normalized:
        season_results = []
        for season_index in range(seasons):
            season_seed = seed + season_index
            season_results.append(
                run_policy_season(
                    policy=policy,
                    num_teams=num_teams,
                    seed=season_seed,
                    model_path=model_path,
                    deterministic_model=deterministic_model,
                )
            )

        mean_rewards = [s["mean_reward"] for s in season_results]
        champion_codes = [
            s["champion"]["code"] for s in season_results if s.get("champion")
        ]
        champion_counts = Counter(champion_codes)
        champion_points = [
            s["champion"]["points"] for s in season_results if s.get("champion")
        ]

        report["results"][policy] = {
            "summary": {
                "mean_reward": float(fmean(mean_rewards)),
                "reward_std": float(pstdev(mean_rewards)) if len(mean_rewards) > 1 else 0.0,
                "best_mean_reward": float(max(mean_rewards)),
                "worst_mean_reward": float(min(mean_rewards)),
                "mean_champion_points": float(fmean(champion_points)) if champion_points else 0.0,
                "champion_distribution": dict(champion_counts),
            },
            "seasons": season_results,
        }

    return report


def write_benchmark_report(
    report: dict[str, Any],
    *,
    output_dir: Path,
    prefix: str = "manager_benchmark",
) -> tuple[Path, Path]:
    """Persist benchmark report to JSON + CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    json_path = output_dir / f"{prefix}_{timestamp}.json"
    csv_path = output_dir / f"{prefix}_{timestamp}.csv"

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "policy",
                "season_index",
                "seed",
                "matchdays",
                "mean_reward",
                "min_reward",
                "max_reward",
                "champion_code",
                "champion_name",
                "champion_points",
            ],
        )
        writer.writeheader()

        for policy, payload in report.get("results", {}).items():
            for season_index, season in enumerate(payload.get("seasons", []), start=1):
                champion = season.get("champion") or {}
                writer.writerow(
                    {
                        "policy": policy,
                        "season_index": season_index,
                        "seed": season.get("seed"),
                        "matchdays": season.get("matchdays"),
                        "mean_reward": season.get("mean_reward"),
                        "min_reward": season.get("min_reward"),
                        "max_reward": season.get("max_reward"),
                        "champion_code": champion.get("code"),
                        "champion_name": champion.get("name"),
                        "champion_points": champion.get("points"),
                    }
                )

    return json_path, csv_path
