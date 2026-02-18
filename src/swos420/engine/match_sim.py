"""SWOS420 Fast Match Simulator — The Heart of the Game.

Poisson-based match engine with:
- Position-weighted team ratings from effective skills (form-modified)
- 10×10 tactics interaction matrix
- Weather & referee modifiers
- Per-player match ratings (4.0–10.0)
- Live injury rolls during match
- Goal/assist attribution weighted by finishing/passing
- Post-match form updates via existing SWOSPlayer.apply_form_change()
- Stats accumulation (goals, assists, appearances, clean sheets)

All tuning constants are hot-reloadable from rules.json.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

import numpy as np

from swos420.engine.match_result import (
    EventType,
    MatchEvent,
    MatchResult,
    PlayerMatchStats,
)
from swos420.models.player import SWOSPlayer

logger = logging.getLogger(__name__)


# ── Default Tactics Matrix (10×10) ──────────────────────────────────────
# Positive value = advantage for the ROW formation against COLUMN formation.
# Symmetric: matrix[A][B] = -matrix[B][A]
DEFAULT_TACTICS_MATRIX: dict[str, dict[str, float]] = {
    "4-4-2": {
        "4-4-2": 0.00, "4-3-3": 0.12, "4-2-3-1": -0.08, "3-5-2": 0.05,
        "3-4-3": 0.10, "5-3-2": -0.06, "5-4-1": -0.12, "4-1-4-1": 0.04,
        "4-3-2-1": 0.03, "3-4-2-1": 0.07,
    },
    "4-3-3": {
        "4-4-2": -0.12, "4-3-3": 0.00, "4-2-3-1": 0.15, "3-5-2": -0.10,
        "3-4-3": 0.06, "5-3-2": 0.08, "5-4-1": -0.05, "4-1-4-1": 0.10,
        "4-3-2-1": 0.05, "3-4-2-1": -0.03,
    },
    "4-2-3-1": {
        "4-4-2": 0.08, "4-3-3": -0.15, "4-2-3-1": 0.00, "3-5-2": 0.12,
        "3-4-3": -0.08, "5-3-2": 0.06, "5-4-1": 0.10, "4-1-4-1": -0.06,
        "4-3-2-1": 0.08, "3-4-2-1": 0.04,
    },
    "3-5-2": {
        "4-4-2": -0.05, "4-3-3": 0.10, "4-2-3-1": -0.12, "3-5-2": 0.00,
        "3-4-3": 0.08, "5-3-2": -0.10, "5-4-1": -0.08, "4-1-4-1": 0.12,
        "4-3-2-1": -0.04, "3-4-2-1": 0.06,
    },
    "3-4-3": {
        "4-4-2": -0.10, "4-3-3": -0.06, "4-2-3-1": 0.08, "3-5-2": -0.08,
        "3-4-3": 0.00, "5-3-2": 0.14, "5-4-1": 0.12, "4-1-4-1": -0.04,
        "4-3-2-1": -0.06, "3-4-2-1": 0.10,
    },
    "5-3-2": {
        "4-4-2": 0.06, "4-3-3": -0.08, "4-2-3-1": -0.06, "3-5-2": 0.10,
        "3-4-3": -0.14, "5-3-2": 0.00, "5-4-1": 0.04, "4-1-4-1": 0.08,
        "4-3-2-1": 0.06, "3-4-2-1": -0.10,
    },
    "5-4-1": {
        "4-4-2": 0.12, "4-3-3": 0.05, "4-2-3-1": -0.10, "3-5-2": 0.08,
        "3-4-3": -0.12, "5-3-2": -0.04, "5-4-1": 0.00, "4-1-4-1": 0.06,
        "4-3-2-1": 0.10, "3-4-2-1": -0.08,
    },
    "4-1-4-1": {
        "4-4-2": -0.04, "4-3-3": -0.10, "4-2-3-1": 0.06, "3-5-2": -0.12,
        "3-4-3": 0.04, "5-3-2": -0.08, "5-4-1": -0.06, "4-1-4-1": 0.00,
        "4-3-2-1": -0.08, "3-4-2-1": 0.12,
    },
    "4-3-2-1": {
        "4-4-2": -0.03, "4-3-3": -0.05, "4-2-3-1": -0.08, "3-5-2": 0.04,
        "3-4-3": 0.06, "5-3-2": -0.06, "5-4-1": -0.10, "4-1-4-1": 0.08,
        "4-3-2-1": 0.00, "3-4-2-1": 0.05,
    },
    "3-4-2-1": {
        "4-4-2": -0.07, "4-3-3": 0.03, "4-2-3-1": -0.04, "3-5-2": -0.06,
        "3-4-3": -0.10, "5-3-2": 0.10, "5-4-1": 0.08, "4-1-4-1": -0.12,
        "4-3-2-1": -0.05, "3-4-2-1": 0.00,
    },
}

# Weather multipliers on overall team quality
DEFAULT_WEATHER_MULT: dict[str, float] = {
    "dry": 1.00,
    "wet": 0.92,
    "muddy": 0.85,
    "snow": 0.78,
}

# Position role classification for weighted ratings
ATTACKING_POSITIONS = {"ST", "CF", "SS", "LW", "RW"}
MIDFIELD_POSITIONS = {"CM", "CAM", "AM", "RM", "LM", "CDM"}
DEFENSIVE_POSITIONS = {"CB", "RB", "LB", "RWB", "LWB", "SW"}
GOALKEEPER_POSITIONS = {"GK"}


class MatchSimulator:
    """Fast management match simulator — Poisson goals + rich per-player stats.

    Returns everything needed for DB updates, AI rewards, and NFT metadata.
    """

    def __init__(self, rules_path: str | Path | None = None):
        """Initialize with rules.json for tuning constants.

        Args:
            rules_path: Path to rules.json. If None, uses built-in defaults.
        """
        self.tactics_matrix = dict(DEFAULT_TACTICS_MATRIX)
        self.weather_mult = dict(DEFAULT_WEATHER_MULT)
        self.home_advantage = 0.25  # xG bonus for home team
        self.xg_base = 2.85  # Poisson scaling constant
        self.xg_defense_offset = 8.0  # Denominator offset to prevent extreme λ
        self.injury_match_base_rate = 0.035  # Per-player per-match injury chance
        self.card_base_rate = 0.12  # Yellow card chance per player per match

        if rules_path is not None:
            self._load_rules(rules_path)

    def _load_rules(self, rules_path: str | Path) -> None:
        """Load tuning constants from rules.json."""
        path = Path(rules_path)
        if not path.exists():
            logger.warning(f"Rules file not found: {path}, using defaults")
            return

        with open(path) as f:
            rules = json.load(f)

        match_rules = rules.get("match", {})

        # Load tactics matrix if present
        if "tactics_matrix" in match_rules:
            self.tactics_matrix.update(match_rules["tactics_matrix"])

        # Load weather multipliers
        if "weather_modifiers" in match_rules:
            # Convert weather_modifiers format to simple multipliers
            for weather, mods in match_rules["weather_modifiers"].items():
                if isinstance(mods, dict):
                    # Calculate average debuff from skill-specific modifiers
                    if mods:
                        avg_mod = sum(mods.values()) / len(mods)
                        self.weather_mult[weather] = max(0.5, 1.0 + avg_mod)
                    else:
                        self.weather_mult[weather] = 1.0

        # Load scalar tuning constants
        self.home_advantage = match_rules.get("home_advantage_bonus", self.home_advantage)
        self.xg_base = match_rules.get("base_goal_lambda", self.xg_base)
        self.injury_match_base_rate = match_rules.get(
            "injury_during_match_base_rate", self.injury_match_base_rate
        )

    def reload(self, rules_path: str | Path) -> None:
        """Hot-reload all tuning constants."""
        self._load_rules(rules_path)

    # ── Main Simulation ─────────────────────────────────────────────────

    def simulate_match(
        self,
        home_squad: list[SWOSPlayer],
        away_squad: list[SWOSPlayer],
        home_formation: str = "4-4-2",
        away_formation: str = "4-4-2",
        weather: str = "dry",
        referee_strictness: float = 1.0,
        home_team_name: str = "Home",
        away_team_name: str = "Away",
    ) -> MatchResult:
        """Simulate a full match between two squads.

        Args:
            home_squad: Home team players (first 11 play, rest are bench).
            away_squad: Away team players (first 11 play, rest are bench).
            home_formation: Home tactical formation (e.g. "4-4-2").
            away_formation: Away tactical formation.
            weather: One of "dry", "wet", "muddy", "snow".
            referee_strictness: 0.6 (lenient) to 1.4 (strict).
            home_team_name: Display name for home team.
            away_team_name: Display name for away team.

        Returns:
            MatchResult with complete match data.
        """
        home_xi = home_squad[:11]
        away_xi = away_squad[:11]
        events: list[MatchEvent] = []

        # 1. Calculate team ratings
        home_attack, home_defense = self._calculate_team_ratings(home_xi)
        away_attack, away_defense = self._calculate_team_ratings(away_xi)

        # 2. Apply tactics modifier
        tac_mod = self._get_tactics_modifier(home_formation, away_formation)
        home_attack += tac_mod * 1.8
        away_attack -= tac_mod * 1.2  # Inverse effect on away
        home_defense -= tac_mod * 0.3  # Small counter-effect
        away_defense += tac_mod * 0.3

        # 3. Apply weather
        w_mult = self.weather_mult.get(weather, 1.0)
        home_attack *= w_mult
        away_attack *= w_mult
        # Defence less affected by weather
        home_defense *= (1.0 + w_mult) / 2
        away_defense *= (1.0 + w_mult) / 2

        # 4. Home advantage
        home_attack += self.home_advantage

        # 5. Poisson λ for goals
        home_lambda = max(0.3, home_attack / (away_defense + self.xg_defense_offset) * self.xg_base)
        away_lambda = max(0.3, away_attack / (home_defense + self.xg_defense_offset) * self.xg_base)

        # 6. Generate goals
        home_goals = int(np.random.poisson(home_lambda))
        away_goals = int(np.random.poisson(away_lambda))

        # 7. Per-player ratings + live events
        home_stats = self._generate_player_stats(
            home_xi, home_goals, "home", events, referee_strictness, home_team_name
        )
        away_stats = self._generate_player_stats(
            away_xi, away_goals, "away", events, referee_strictness, away_team_name
        )

        # 8. Attribute goals and assists
        self._attribute_goals(home_xi, home_goals, "home", events, home_team_name, home_stats)
        self._attribute_goals(away_xi, away_goals, "away", events, away_team_name, away_stats)

        # 9. Sort events chronologically
        events.sort(key=lambda e: e.minute)

        # 10. Post-match updates: form, fatigue, appearances, clean sheets
        home_result_bonus = self._result_bonus(home_goals, away_goals)
        away_result_bonus = self._result_bonus(away_goals, home_goals)

        for stat in home_stats:
            player = self._find_player(home_xi, stat.player_id)
            if player:
                player.apply_form_change(home_result_bonus, stat.rating)
                player.appearances_season += 1
                player.fatigue = min(100.0, player.fatigue + random.uniform(5.0, 15.0))
                if away_goals == 0 and player.position.value in DEFENSIVE_POSITIONS | GOALKEEPER_POSITIONS:
                    player.clean_sheets_season += 1

        for stat in away_stats:
            player = self._find_player(away_xi, stat.player_id)
            if player:
                player.apply_form_change(away_result_bonus, stat.rating)
                player.appearances_season += 1
                player.fatigue = min(100.0, player.fatigue + random.uniform(5.0, 15.0))
                if home_goals == 0 and player.position.value in DEFENSIVE_POSITIONS | GOALKEEPER_POSITIONS:
                    player.clean_sheets_season += 1

        result = MatchResult(
            home_team=home_team_name,
            away_team=away_team_name,
            home_goals=home_goals,
            away_goals=away_goals,
            home_xg=round(home_lambda, 2),
            away_xg=round(away_lambda, 2),
            weather=weather,
            referee_strictness=referee_strictness,
            home_player_stats=home_stats,
            away_player_stats=away_stats,
            events=events,
        )

        logger.info(
            f"Match: {result.scoreline()} (xG: {result.home_xg}-{result.away_xg}, "
            f"weather={weather})"
        )
        return result

    # ── Team Rating Calculation ──────────────────────────────────────────

    def _calculate_team_ratings(
        self, squad: list[SWOSPlayer]
    ) -> tuple[float, float]:
        """Calculate weighted attack and defense ratings from player effective skills.

        Attackers weight finishing/speed more, defenders weight tackling/heading more.
        Returns (attack_rating, defense_rating).
        """
        if not squad:
            return 1.0, 1.0

        attack_total = 0.0
        defense_total = 0.0

        for player in squad:
            pos = player.position.value

            if pos in ATTACKING_POSITIONS:
                attack_total += (
                    player.effective_skill("finishing") * 1.4
                    + player.effective_skill("speed") * 0.8
                    + player.effective_skill("control") * 0.6
                    + player.effective_skill("velocity") * 0.4
                )
                defense_total += player.effective_skill("tackling") * 0.2

            elif pos in MIDFIELD_POSITIONS:
                attack_total += (
                    player.effective_skill("passing") * 1.0
                    + player.effective_skill("control") * 0.6
                    + player.effective_skill("finishing") * 0.4
                )
                defense_total += (
                    player.effective_skill("tackling") * 0.8
                    + player.effective_skill("heading") * 0.4
                    + player.effective_skill("passing") * 0.3
                )

            elif pos in DEFENSIVE_POSITIONS:
                attack_total += (
                    player.effective_skill("heading") * 0.3
                    + player.effective_skill("passing") * 0.2
                )
                defense_total += (
                    player.effective_skill("tackling") * 1.3
                    + player.effective_skill("heading") * 0.9
                    + player.effective_skill("speed") * 0.4
                )

            elif pos in GOALKEEPER_POSITIONS:
                # GK contributes mainly to defense via control/heading as proxy
                defense_total += (
                    player.effective_skill("control") * 1.2
                    + player.effective_skill("velocity") * 0.8
                    + player.effective_skill("heading") * 0.5
                )

        # Normalize by squad size
        n = len(squad)
        return attack_total / n, defense_total / n

    # ── Tactics ──────────────────────────────────────────────────────────

    def _get_tactics_modifier(self, home_formation: str, away_formation: str) -> float:
        """Look up tactics advantage from the 10×10 matrix."""
        return self.tactics_matrix.get(home_formation, {}).get(away_formation, 0.0)

    # ── Per-Player Ratings & Events ──────────────────────────────────────

    def _generate_player_stats(
        self,
        squad: list[SWOSPlayer],
        team_goals: int,
        side: str,
        events: list[MatchEvent],
        referee_strictness: float,
        team_name: str,
    ) -> list[PlayerMatchStats]:
        """Generate individual ratings, injuries, and cards for each player."""
        stats = []

        for player in squad:
            # Base rating from skill contribution
            skill_contrib = (
                player.effective_skill("finishing") * 0.20
                + player.effective_skill("passing") * 0.20
                + player.effective_skill("tackling") * 0.15
                + player.effective_skill("control") * 0.15
                + player.effective_skill("speed") * 0.15
                + player.effective_skill("heading") * 0.10
                + player.effective_skill("velocity") * 0.05
            )

            # Rating: 6.0 base + skill contribution + noise
            rating = 6.0 + (skill_contrib * 0.4) + random.gauss(0, 1.0)

            # Bonus for team winning
            if team_goals > 0:
                rating += 0.3

            rating = max(4.0, min(10.0, rating))

            stat = PlayerMatchStats(
                player_id=player.base_id,
                display_name=player.display_name,
                position=player.position.value,
                rating=round(rating, 1),
            )

            # Live injury roll
            injury_prob = self.injury_match_base_rate * (1.0 + max(0.0, (50 - player.form) / 100))
            injury_prob *= (1.0 + player.fatigue / 200)  # fatigue increases risk
            if random.random() < injury_prob:
                injury_days = self._roll_injury_severity()
                stat.injured = True
                stat.injury_days = injury_days
                player.injury_days = injury_days
                events.append(MatchEvent(
                    minute=random.randint(1, 90),
                    event_type=EventType.INJURY,
                    player_id=player.base_id,
                    player_name=player.display_name,
                    team=side,
                    detail=f"Out for {injury_days} days",
                ))
                stat.rating = max(4.0, stat.rating - 1.5)

            # Card roll (referee strictness modifies probability)
            card_prob = self.card_base_rate * referee_strictness
            if player.position.value in DEFENSIVE_POSITIONS | MIDFIELD_POSITIONS:
                card_prob *= 1.3  # defenders/midfielders foul more
            if random.random() < card_prob:
                stat.yellow_card = True
                events.append(MatchEvent(
                    minute=random.randint(1, 90),
                    event_type=EventType.YELLOW_CARD,
                    player_id=player.base_id,
                    player_name=player.display_name,
                    team=side,
                    detail="Foul",
                ))
                # Second yellow → red (5% chance if already booked)
                if random.random() < 0.05:
                    stat.red_card = True
                    stat.yellow_card = False  # upgraded
                    events.append(MatchEvent(
                        minute=random.randint(60, 90),
                        event_type=EventType.RED_CARD,
                        player_id=player.base_id,
                        player_name=player.display_name,
                        team=side,
                        detail="Second yellow",
                    ))

            stats.append(stat)

        return stats

    def _attribute_goals(
        self,
        squad: list[SWOSPlayer],
        num_goals: int,
        side: str,
        events: list[MatchEvent],
        team_name: str,
        stats: list[PlayerMatchStats],
    ) -> None:
        """Attribute goals to specific players, weighted by finishing skill."""
        if num_goals == 0 or not squad:
            return

        # Build weights: attackers/midfielders more likely to score
        weights = []
        for player in squad:
            pos = player.position.value
            finishing = player.effective_skill("finishing")
            speed = player.effective_skill("speed")

            if pos in ATTACKING_POSITIONS:
                w = finishing * 3.0 + speed * 0.5
            elif pos in MIDFIELD_POSITIONS:
                w = finishing * 1.5 + player.effective_skill("velocity") * 0.5
            elif pos in DEFENSIVE_POSITIONS:
                w = finishing * 0.3 + player.effective_skill("heading") * 0.8
            else:
                w = 0.1  # GK

            weights.append(max(0.1, w))

        total_w = sum(weights)
        probs = [w / total_w for w in weights]

        for _ in range(num_goals):
            # Pick scorer
            scorer_idx = np.random.choice(len(squad), p=probs)
            scorer = squad[scorer_idx]
            minute = random.randint(1, 90)

            events.append(MatchEvent(
                minute=minute,
                event_type=EventType.GOAL,
                player_id=scorer.base_id,
                player_name=scorer.display_name,
                team=side,
                detail=f"Goal for {team_name}",
            ))

            # Update player stats
            scorer.goals_scored_season += 1
            for stat in stats:
                if stat.player_id == scorer.base_id:
                    stat.goals += 1
                    stat.rating = min(10.0, stat.rating + 0.8)
                    break

            # Attribute assist (different player, weighted by passing)
            assist_weights = []
            for i, player in enumerate(squad):
                if i == scorer_idx:
                    assist_weights.append(0.0)
                else:
                    assist_weights.append(max(0.1, player.effective_skill("passing") * 1.5
                                              + player.effective_skill("control") * 0.5))

            total_aw = sum(assist_weights)
            if total_aw > 0:
                assist_probs = [w / total_aw for w in assist_weights]
                # 75% chance each goal has a credited assist
                if random.random() < 0.75:
                    assister_idx = np.random.choice(len(squad), p=assist_probs)
                    assister = squad[assister_idx]

                    events.append(MatchEvent(
                        minute=minute,
                        event_type=EventType.ASSIST,
                        player_id=assister.base_id,
                        player_name=assister.display_name,
                        team=side,
                        detail=f"Assist for {scorer.display_name}",
                    ))

                    assister.assists_season += 1
                    for stat in stats:
                        if stat.player_id == assister.base_id:
                            stat.assists += 1
                            stat.rating = min(10.0, stat.rating + 0.4)
                            break

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _roll_injury_severity() -> int:
        """Roll injury duration based on severity distribution.

        50% minor (1-7 days), 30% medium (8-28), 15% serious (29-90), 5% season-ending.
        """
        roll = random.random()
        if roll < 0.50:
            return random.randint(1, 7)
        elif roll < 0.80:
            return random.randint(8, 28)
        elif roll < 0.95:
            return random.randint(29, 90)
        else:
            return random.randint(91, 180)

    @staticmethod
    def _result_bonus(goals_for: int, goals_against: int) -> float:
        """Convert match result to form bonus.

        Win: +3.0, Draw: +0.5, Loss: -2.0 (from rules.json defaults).
        """
        if goals_for > goals_against:
            return 3.0
        elif goals_for == goals_against:
            return 0.5
        return -2.0

    @staticmethod
    def _find_player(squad: list[SWOSPlayer], base_id: str) -> SWOSPlayer | None:
        for p in squad:
            if p.base_id == base_id:
                return p
        return None


class ArcadeMatchSimulator:
    """Placeholder for zlatkok/swos-port pybind11 arcade wrapper.

    When the native SWOS engine is compiled with Python bindings,
    this class will call self.swos_engine.step() for pixel-level
    arcade match simulation. Until then, falls back to MatchSimulator.
    """

    def __init__(self, rules_path: str | Path | None = None):
        self._fallback = MatchSimulator(rules_path=rules_path)
        self._native_available = False

    def simulate(
        self,
        home_squad: list[SWOSPlayer],
        away_squad: list[SWOSPlayer],
        **kwargs,
    ) -> MatchResult:
        """Run arcade simulation (or fallback to fast match)."""
        if self._native_available:
            # TODO: call self.swos_engine.step(...) when pybind11 wrapper ready
            raise NotImplementedError("Native SWOS arcade engine not yet compiled")

        return self._fallback.simulate_match(home_squad, away_squad, **kwargs)
