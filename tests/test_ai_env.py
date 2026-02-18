"""Tests for the PettingZoo SWOSManagerEnv."""

from __future__ import annotations

import numpy as np

from swos420.ai.env import SWOSManagerEnv
from swos420.ai.baseline_agents import RandomAgent, HeuristicAgent


# ═══════════════════════════════════════════════════════════════════════
# Environment API Tests
# ═══════════════════════════════════════════════════════════════════════

class TestEnvInit:
    def test_creates_correct_agents(self):
        env = SWOSManagerEnv(num_teams=4, seed=42)
        obs, infos = env.reset()
        assert len(env.agents) == 4
        assert env.agents == ["club_0", "club_1", "club_2", "club_3"]

    def test_observation_shapes(self):
        env = SWOSManagerEnv(num_teams=4, seed=42)
        obs, infos = env.reset()

        for agent in env.agents:
            assert obs[agent]["league_table"].shape == (4, 6)
            assert obs[agent]["own_squad"].shape == (22, 12)
            assert obs[agent]["finances"].shape == (4,)
            assert obs[agent]["meta"].shape == (4,)

    def test_observation_ranges(self):
        env = SWOSManagerEnv(num_teams=4, seed=42)
        obs, infos = env.reset()

        for agent in env.agents:
            for key in obs[agent]:
                arr = obs[agent][key]
                assert np.all(arr >= 0.0), f"{key} has negative values"
                assert np.all(arr <= 1.0), f"{key} has values > 1"


class TestEnvStep:
    def test_single_step(self):
        env = SWOSManagerEnv(num_teams=4, seed=42)
        obs, infos = env.reset()

        # Generate random actions for all agents
        actions = {
            agent: env.action_space(agent).sample() for agent in env.agents
        }
        obs, rewards, terms, truncs, infos = env.step(actions)

        # All agents should get observations
        assert len(obs) == 4

        # All agents should get rewards
        for agent in ["club_0", "club_1", "club_2", "club_3"]:
            assert isinstance(rewards[agent], (int, float))

    def test_full_season_completes(self):
        """Run a full season with random agents — smoke test."""
        env = SWOSManagerEnv(num_teams=4, seed=42)
        obs, infos = env.reset()

        step_count = 0
        while env.agents:
            actions = {
                agent: env.action_space(agent).sample() for agent in env.agents
            }
            obs, rewards, terms, truncs, infos = env.step(actions)
            step_count += 1

            if step_count > 100:  # Safety valve
                break

        # A 4-team league should have 6 matchdays (round-robin)
        assert step_count == 6

    def test_season_end_has_rewards(self):
        """Final step should include season-end bonus/penalty."""
        env = SWOSManagerEnv(num_teams=4, seed=42)
        obs, _ = env.reset()

        last_rewards = {}
        while env.agents:
            actions = {
                agent: env.action_space(agent).sample()
                for agent in env.agents
            }
            obs, rewards, terms, truncs, infos = env.step(actions)
            last_rewards = rewards

        # At least one agent should have a significant reward (title bonus)
        max_reward = max(last_rewards.values())
        assert max_reward > 0


class TestBaselineAgents:
    def test_random_agent_runs(self):
        env = SWOSManagerEnv(num_teams=4, seed=42)
        obs, _ = env.reset()

        agents = {
            agent: RandomAgent(env.action_space(agent), seed=42)
            for agent in env.agents
        }

        step_count = 0
        while env.agents:
            actions = {
                agent: agents[agent].act(obs.get(agent))
                for agent in env.agents
            }
            obs, rewards, terms, truncs, infos = env.step(actions)
            step_count += 1

        assert step_count > 0

    def test_heuristic_agent_runs(self):
        env = SWOSManagerEnv(num_teams=4, seed=42)
        obs, _ = env.reset()

        agents = {
            agent: HeuristicAgent(seed=42) for agent in env.agents
        }

        step_count = 0
        while env.agents:
            actions = {
                agent: agents[agent].act(obs.get(agent))
                for agent in env.agents
            }
            obs, rewards, terms, truncs, infos = env.step(actions)
            step_count += 1

        assert step_count > 0


class TestEnvDeterminism:
    def test_same_seed_same_results(self):
        """Identical seeds should produce identical seasons."""
        def run_season(seed: int) -> dict:
            env = SWOSManagerEnv(num_teams=4, seed=seed)
            obs, _ = env.reset()
            total_rewards = {a: 0.0 for a in env.possible_agents}

            while env.agents:
                # Use deterministic actions (all zeros)
                actions = {
                    agent: {
                        "formation": 0, "style": 0, "training_focus": 0,
                        "scouting_level": 0,
                        "transfer_bid_0": 0, "bid_amount_0": np.float32(0.0),
                        "transfer_bid_1": 0, "bid_amount_1": np.float32(0.0),
                        "transfer_bid_2": 0, "bid_amount_2": np.float32(0.0),
                        "sub_0": 0, "sub_1": 0, "sub_2": 0,
                    }
                    for agent in env.agents
                }
                _, rewards, _, _, _ = env.step(actions)
                for a, r in rewards.items():
                    total_rewards[a] += r

            return total_rewards

        r1 = run_season(42)
        r2 = run_season(42)

        for agent in r1:
            assert abs(r1[agent] - r2[agent]) < 1e-6, \
                f"Determinism failed for {agent}: {r1[agent]} vs {r2[agent]}"
