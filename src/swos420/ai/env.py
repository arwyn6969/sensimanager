"""SWOSManagerEnv — PettingZoo ParallelEnv for multi-agent league management.

Each agent controls one club, making weekly decisions (formation, style,
training, transfers, substitutions, scouting). The environment wraps the
existing SeasonRunner + MatchSimulator to simulate matches.

One episode = one full league season.
One step = one matchday.
"""

from __future__ import annotations

import functools
import random
from typing import Any, Optional

import gymnasium
import numpy as np
from gymnasium import spaces
from pettingzoo import ParallelEnv

from swos420.ai.actions import (
    FORMATIONS,
    STYLES,
    TRAINING_FOCUS,
    ManagerAction,
    decode_action,
    build_action_mask,
)
from swos420.ai.obs import (
    build_league_table_obs,
    build_squad_obs,
    build_finances_obs,
    build_meta_obs,
)
from swos420.ai.rewards import (
    compute_matchday_reward,
    compute_season_end_reward,
)
from swos420.engine.match_sim import MatchSimulator
from swos420.engine.season_runner import SeasonRunner, TeamSeasonState
from swos420.engine.transfer_market import TransferMarket, generate_free_agents
from swos420.engine.scouting import ScoutingSystem
from swos420.models.player import Position, Skills, SWOSPlayer, generate_base_id, SKILL_NAMES
from swos420.models.team import Team, TeamFinances


# Transfer windows occur at these matchdays (configurable)
DEFAULT_TRANSFER_MATCHDAYS = {0, 19}  # Summer + winter windows
MAX_MARKET_TARGETS = 15
MAX_SQUAD_DISPLAY = 22
MAX_BENCH = 5


def _make_test_players(
    code: str, n: int = 18, skill_range: tuple[int, int] = (5, 12),
) -> list[SWOSPlayer]:
    """Generate a squad of test players for environment initialization."""
    positions = [
        Position.GK, Position.RB, Position.CB, Position.CB, Position.LB,
        Position.RM, Position.CM, Position.CM, Position.LM,
        Position.ST, Position.ST,
        # Subs
        Position.GK, Position.CB, Position.CM, Position.LW, Position.ST,
        Position.RB, Position.CAM,
    ]
    players = []
    for i in range(min(n, len(positions))):
        skill_lvl = random.randint(*skill_range)
        skills = {s: skill_lvl for s in SKILL_NAMES}
        age = random.randint(19, 33)
        players.append(SWOSPlayer(
            base_id=generate_base_id(f"{code}_{i}_{random.randint(1, 99999)}", "25/26"),
            full_name=f"{code} Player {i+1}",
            display_name=f"{code} P{i+1:02d}",
            position=positions[i],
            skills=Skills(**skills),
            age=age,
            club_name=f"Club {code}",
            club_code=code,
            base_value=skill_lvl * 500_000,
        ))
    return players


class SWOSManagerEnv(ParallelEnv):
    """Multi-agent environment for SWOS420 league management.

    Args:
        num_teams: Number of teams/agents (4, 8, 16, or 20).
        skill_range: (min, max) skill range for generated players.
        transfer_matchdays: Set of matchday numbers where transfers are allowed.
        reward_weights: Override default reward weights.
        seed: Random seed for reproducibility.
    """

    metadata = {"name": "swos_manager_v0", "is_parallelizable": True}

    def __init__(
        self,
        num_teams: int = 4,
        skill_range: tuple[int, int] = (5, 12),
        transfer_matchdays: set[int] | None = None,
        reward_weights: dict[str, float] | None = None,
        seed: int | None = None,
    ):
        super().__init__()
        assert num_teams >= 2, "Need at least 2 teams"
        assert num_teams % 2 == 0 or num_teams >= 3, "Odd teams need >=3"

        self.num_teams = num_teams
        self._skill_range = skill_range
        self._transfer_matchdays = transfer_matchdays or DEFAULT_TRANSFER_MATCHDAYS
        self._reward_weights = reward_weights
        self._seed = seed

        # Agent IDs
        self.possible_agents = [f"club_{i}" for i in range(num_teams)]
        self.agents = list(self.possible_agents)

        # State (populated on reset)
        self._runner: Optional[SeasonRunner] = None
        self._team_states: list[TeamSeasonState] = []
        self._agent_to_team: dict[str, TeamSeasonState] = {}
        self._market: TransferMarket = TransferMarket()
        self._scout: ScoutingSystem = ScoutingSystem(seed=seed)
        self._market_players: list[SWOSPlayer] = []
        self._consecutive_losses: dict[str, int] = {}
        self._total_matchdays: int = 0

        # Spaces (lazy-initialized)
        self._obs_space: Optional[spaces.Dict] = None
        self._act_space: Optional[spaces.Dict] = None

    @functools.lru_cache(maxsize=None)
    def observation_space(self, agent: str) -> spaces.Dict:
        """Observation space for each agent."""
        return spaces.Dict({
            "league_table": spaces.Box(0, 1, shape=(self.num_teams, 6), dtype=np.float32),
            "own_squad": spaces.Box(0, 1, shape=(MAX_SQUAD_DISPLAY, 12), dtype=np.float32),
            "finances": spaces.Box(0, 1, shape=(4,), dtype=np.float32),
            "meta": spaces.Box(0, 1, shape=(4,), dtype=np.float32),
        })

    @functools.lru_cache(maxsize=None)
    def action_space(self, agent: str) -> spaces.Dict:
        """Action space for each agent."""
        act = {
            "formation": spaces.Discrete(len(FORMATIONS)),
            "style": spaces.Discrete(len(STYLES)),
            "training_focus": spaces.Discrete(len(TRAINING_FOCUS)),
            "scouting_level": spaces.Discrete(4),
        }
        # Transfer slots
        for i in range(3):
            act[f"transfer_bid_{i}"] = spaces.Discrete(MAX_MARKET_TARGETS + 1)
            act[f"bid_amount_{i}"] = spaces.Box(0, 1, shape=(), dtype=np.float32)
        # Substitution slots
        for i in range(3):
            act[f"sub_{i}"] = spaces.Discrete(MAX_BENCH + 1)

        return spaces.Dict(act)

    def reset(
        self,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[dict[str, dict], dict[str, dict]]:
        """Reset environment for a new season.

        Returns:
            (observations, infos) for all agents.
        """
        if seed is not None:
            self._seed = seed
        if self._seed is not None:
            random.seed(self._seed)
            np.random.seed(self._seed)

        self.agents = list(self.possible_agents)
        self._consecutive_losses = {a: 0 for a in self.agents}

        # Generate teams with random squads
        self._team_states = []
        codes = [f"T{i:02d}" for i in range(self.num_teams)]
        for code in codes:
            players = _make_test_players(code, n=18, skill_range=self._skill_range)
            team = Team(
                name=f"Club {code}",
                code=code,
                formation="4-4-2",
                player_ids=[p.base_id for p in players],
                finances=TeamFinances(
                    balance=random.randint(5_000_000, 50_000_000),
                    transfer_budget=random.randint(2_000_000, 20_000_000),
                ),
            )
            self._team_states.append(TeamSeasonState(team=team, players=players))

        # Map agents to teams
        self._agent_to_team = {
            f"club_{i}": self._team_states[i] for i in range(self.num_teams)
        }

        # Create season runner
        self._runner = SeasonRunner(
            teams=self._team_states,
            season_id="25/26",
        )
        self._total_matchdays = self._runner.total_matchdays

        # Generate market players for transfer windows
        self._market_players = generate_free_agents(n=MAX_MARKET_TARGETS)
        self._scout.reset()

        # Build initial observations
        obs = {agent: self._get_obs(agent) for agent in self.agents}
        infos = {agent: {} for agent in self.agents}

        return obs, infos

    def step(
        self, actions: dict[str, dict],
    ) -> tuple[
        dict[str, dict],        # observations
        dict[str, float],       # rewards
        dict[str, bool],        # terminations
        dict[str, bool],        # truncations
        dict[str, dict],        # infos
    ]:
        """Execute one matchday with all agent actions.

        Args:
            actions: Dict of agent_id → raw action dict.

        Returns:
            (observations, rewards, terminations, truncations, infos)
        """
        assert self._runner is not None, "Call reset() before step()"

        current_matchday = self._runner.current_matchday
        is_window = current_matchday in self._transfer_matchdays

        # Apply each agent's tactical actions
        for agent_id, raw_action in actions.items():
            if agent_id not in self._agent_to_team:
                continue
            state = self._agent_to_team[agent_id]

            decoded = decode_action(
                raw_action,
                available_targets=[p.base_id for p in self._market_players],
                bench_player_ids=[p.base_id for p in state.players[11:]],
                transfer_budget=state.team.finances.transfer_budget,
                is_transfer_window=is_window,
            )

            # Apply formation
            state.team.formation = decoded.formation

            # Apply training focus (simplified: rest reduces fatigue)
            if decoded.training_focus == "rest":
                for p in state.players:
                    p.fatigue = max(0, p.fatigue - 15)
            elif decoded.training_focus != "youth":
                for p in state.players:
                    p.fatigue = min(100, p.fatigue + 3)

        # Play the matchday
        results = self._runner.play_matchday()

        # Check if season is complete
        season_done = self._runner.current_matchday >= self._total_matchdays

        # Compute rewards and build observations
        observations = {}
        rewards = {}
        terminations = {}
        truncations = {}
        infos = {}

        for agent_id in self.agents:
            state = self._agent_to_team[agent_id]
            team_code = state.team.code

            # Find this team's match result (if they played this matchday)
            agent_reward = 0.0
            for result in results:
                is_home = result.home_team == state.team.name
                is_away = result.away_team == state.team.name
                if is_home or is_away:
                    # Compute form average
                    avg_form = np.mean([p.form for p in state.players])

                    components = compute_matchday_reward(
                        team=state.team,
                        match_result=result,
                        is_home=is_home,
                        avg_squad_form=float(avg_form),
                        consecutive_losses=self._consecutive_losses[agent_id],
                        weights=self._reward_weights,
                    )
                    agent_reward = components.total

                    # Update consecutive losses tracker
                    if is_home:
                        lost = result.home_goals < result.away_goals
                    else:
                        lost = result.away_goals < result.home_goals
                    if lost:
                        self._consecutive_losses[agent_id] += 1
                    else:
                        self._consecutive_losses[agent_id] = 0
                    break

            # Add season-end bonus
            if season_done:
                table = self._runner.get_league_table()
                for pos, team in enumerate(table, 1):
                    if team.code == team_code:
                        agent_reward += compute_season_end_reward(
                            pos, self.num_teams, self._reward_weights,
                        )
                        break

            observations[agent_id] = self._get_obs(agent_id)
            rewards[agent_id] = agent_reward
            terminations[agent_id] = season_done
            truncations[agent_id] = False
            infos[agent_id] = {
                "matchday": self._runner.current_matchday,
                "season_done": season_done,
            }

        if season_done:
            self.agents = []  # Signal that episode is done

        return observations, rewards, terminations, truncations, infos

    def _get_obs(self, agent_id: str) -> dict[str, np.ndarray]:
        """Build observation dict for a single agent."""
        state = self._agent_to_team[agent_id]
        teams = [s.team for s in self._team_states]
        matchday = self._runner.current_matchday if self._runner else 0
        is_window = matchday in self._transfer_matchdays

        return {
            "league_table": build_league_table_obs(teams, self.num_teams),
            "own_squad": build_squad_obs(state.players, MAX_SQUAD_DISPLAY),
            "finances": build_finances_obs(state.team),
            "meta": build_meta_obs(matchday, self._total_matchdays, 1, is_window),
        }

    def render(self) -> None:
        """Render is a no-op for headless training."""
        pass

    def close(self) -> None:
        """Clean up resources."""
        pass
