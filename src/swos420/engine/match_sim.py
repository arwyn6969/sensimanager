"""SWOS420 Match Simulator — Authentic ICP-Based Engine v3.0.

Based on reverse-engineered Sensible World of Soccer 96/97 mechanics:
- Invisible Computer Points (ICP) system for match outcome prediction
- Positional fitness ('Green Tick') multipliers (1.2×/1.0×/0.7×)
- GK save ability from value tier (Hex Price Byte), not skills
- Random form factor for realistic upsets
- Velocity (long-range) vs Finishing (close-range) split
- 10×10 tactics interaction matrix
- Weather & referee modifiers
- Per-player match ratings (4.0–10.0)
- Live injury rolls during match
- Post-match form updates + stats accumulation

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
from swos420.models.player import (
    SWOSPlayer,
    positional_fitness,
)

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
    """SWOS-authentic ICP-based match simulator.

    Uses Invisible Computer Points with positional fitness, random form
    factor, and GK value-tier save ability for authentic SWOS outcomes.
    """

    def __init__(self, rules_path: str | Path | None = None):
        """Initialize with rules.json for tuning constants.

        Args:
            rules_path: Path to rules.json. If None, uses built-in defaults.
        """
        self.tactics_matrix = dict(DEFAULT_TACTICS_MATRIX)
        self.weather_mult = dict(DEFAULT_WEATHER_MULT)
        self.home_advantage = 0.5  # ICP bonus for home team
        self.xg_base = 2.65  # Poisson scaling constant
        self.xg_defense_offset = 16.5  # Calibrated for SWOS effective skill range (8-15)
        self.injury_match_base_rate = 0.015  # Per-player per-match injury chance
        self.card_base_rate = 0.12  # Yellow card chance per player per match
        self.random_form_range = 0.35  # Max ± random form noise per team per match
        self.gk_defense_weight = 12.0  # How much GK value-tier contributes to defense
        self.key_chance_scale = 2.15  # Converts xG into visible non-goal chance events

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

        # 1. Calculate ICP-based team ratings (with positional fitness)
        home_attack, home_defense = self._calculate_icp_ratings(home_xi)
        away_attack, away_defense = self._calculate_icp_ratings(away_xi)

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

        # 4. Home advantage (ICP flat bonus)
        home_attack += self.home_advantage

        # 5. Random form factor — the SWOS "upset" mechanism
        # Each team gets a per-match noise modifier to create variability
        home_form_noise = random.uniform(-self.random_form_range, self.random_form_range)
        away_form_noise = random.uniform(-self.random_form_range, self.random_form_range)
        home_attack *= (1.0 + home_form_noise)
        away_attack *= (1.0 + away_form_noise)

        # 6. Poisson λ for goals (from ICP differential)
        home_lambda = max(0.3, home_attack / (away_defense + self.xg_defense_offset) * self.xg_base)
        away_lambda = max(0.3, away_attack / (home_defense + self.xg_defense_offset) * self.xg_base)

        # 7. Generate goals
        home_goals = int(np.random.poisson(home_lambda))
        away_goals = int(np.random.poisson(away_lambda))

        # 8. Per-player ratings + live events
        home_stats = self._generate_player_stats(
            home_xi, home_goals, "home", events, referee_strictness, home_team_name
        )
        away_stats = self._generate_player_stats(
            away_xi, away_goals, "away", events, referee_strictness, away_team_name
        )

        # 9. Attribute goals and assists (VE/FI split)
        self._attribute_goals(home_xi, home_goals, "home", events, home_team_name, home_stats)
        self._attribute_goals(away_xi, away_goals, "away", events, away_team_name, away_stats)

        # 10. Surface key non-goal chances so matches feel alive between goals.
        self._generate_key_chances(
            squad=home_xi,
            opponents=away_xi,
            num_goals=home_goals,
            team_xg=home_lambda,
            side="home",
            events=events,
            team_name=home_team_name,
            attacking_stats=home_stats,
            defending_stats=away_stats,
        )
        self._generate_key_chances(
            squad=away_xi,
            opponents=home_xi,
            num_goals=away_goals,
            team_xg=away_lambda,
            side="away",
            events=events,
            team_name=away_team_name,
            attacking_stats=away_stats,
            defending_stats=home_stats,
        )

        # 11. Sort events chronologically
        events.sort(key=lambda e: e.minute)

        # 12. Post-match updates: form, fatigue, appearances, clean sheets
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
                    stat.rating = round(min(10.0, stat.rating + 0.35), 1)

        for stat in away_stats:
            player = self._find_player(away_xi, stat.player_id)
            if player:
                player.apply_form_change(away_result_bonus, stat.rating)
                player.appearances_season += 1
                player.fatigue = min(100.0, player.fatigue + random.uniform(5.0, 15.0))
                if home_goals == 0 and player.position.value in DEFENSIVE_POSITIONS | GOALKEEPER_POSITIONS:
                    player.clean_sheets_season += 1
                    stat.rating = round(min(10.0, stat.rating + 0.35), 1)

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

    # ── ICP Team Rating Calculation ──────────────────────────────────────

    def _calculate_icp_ratings(
        self, squad: list[SWOSPlayer]
    ) -> tuple[float, float]:
        """Calculate ICP-based attack and defense ratings.

        Authentic SWOS mechanics:
        - Each player's skill contribution is multiplied by their
          positional fitness (Green Tick 1.2×, Neutral 1.0×, Red Cross 0.7×)
        - GK defense uses value-tier save ability, not skills
        - Velocity (long-range) and Finishing (close-range) are split

        Returns (attack_icp, defense_icp).
        """
        if not squad:
            return 1.0, 1.0

        attack_total = 0.0
        defense_total = 0.0

        for player in squad:
            pos = player.position.value
            # Positional fitness multiplier (Green Tick system)
            fit = positional_fitness(player.position.value, pos)

            if pos in ATTACKING_POSITIONS:
                # FI = close-range, VE = long-range (authentic split)
                attack_total += fit * (
                    player.effective_skill("finishing") * 1.4
                    + player.effective_skill("speed") * 0.8
                    + player.effective_skill("control") * 0.6
                    + player.effective_skill("velocity") * 0.3
                )
                defense_total += fit * player.effective_skill("tackling") * 0.2

            elif pos in MIDFIELD_POSITIONS:
                # Midfielders use VE for long-range threat
                attack_total += fit * (
                    player.effective_skill("passing") * 1.0
                    + player.effective_skill("control") * 0.6
                    + player.effective_skill("velocity") * 0.5  # long-range shots
                    + player.effective_skill("finishing") * 0.3
                )
                defense_total += fit * (
                    player.effective_skill("tackling") * 0.8
                    + player.effective_skill("heading") * 0.4
                    + player.effective_skill("passing") * 0.3
                )

            elif pos in DEFENSIVE_POSITIONS:
                attack_total += fit * (
                    player.effective_skill("heading") * 0.3
                    + player.effective_skill("passing") * 0.2
                )
                defense_total += fit * (
                    player.effective_skill("tackling") * 1.3
                    + player.effective_skill("heading") * 0.9
                    + player.effective_skill("speed") * 0.4
                )

            elif pos in GOALKEEPER_POSITIONS:
                # GK defense from value-tier, not skills (authentic SWOS)
                defense_total += player.gk_save_ability * self.gk_defense_weight

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
            if player.position.value in GOALKEEPER_POSITIONS:
                skill_contrib = 10.5 + player.gk_save_ability * 3.0
                rating = 5.8 + ((skill_contrib - 11.0) * 0.3) + random.gauss(0, 0.45)
            else:
                skill_contrib = (
                    player.effective_skill("finishing") * 0.20
                    + player.effective_skill("passing") * 0.20
                    + player.effective_skill("tackling") * 0.15
                    + player.effective_skill("control") * 0.15
                    + player.effective_skill("speed") * 0.15
                    + player.effective_skill("heading") * 0.10
                    + player.effective_skill("velocity") * 0.05
                )
                rating = 5.8 + ((skill_contrib - 11.0) * 0.26) + random.gauss(0, 0.6)

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
                injury_label = "day" if injury_days == 1 else "days"
                events.append(MatchEvent(
                    minute=random.randint(1, 90),
                    event_type=EventType.INJURY,
                    player_id=player.base_id,
                    player_name=player.display_name,
                    team=side,
                    detail=f"Out for {injury_days} {injury_label}",
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

    def _attacking_weights(self, squad: list[SWOSPlayer]) -> list[float]:
        """Goal/chance involvement weights by role and attacking skill mix."""
        weights = []
        for player in squad:
            pos = player.position.value
            finishing = player.effective_skill("finishing")
            velocity = player.effective_skill("velocity")
            speed = player.effective_skill("speed")

            if pos in ATTACKING_POSITIONS:
                weight = finishing * 3.0 + speed * 0.5 + velocity * 0.2
            elif pos in MIDFIELD_POSITIONS:
                weight = velocity * 1.8 + finishing * 1.0 + speed * 0.3
            elif pos in DEFENSIVE_POSITIONS:
                weight = player.effective_skill("heading") * 0.8 + velocity * 0.4
            else:
                weight = 0.1

            weights.append(max(0.1, weight))

        return weights

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

        weights = self._attacking_weights(squad)
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
                    stat.rating = round(min(10.0, stat.rating + 1.1), 1)
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
                            stat.rating = round(min(10.0, stat.rating + 0.6), 1)
                            break

    @staticmethod
    def _roll_event_minute() -> int:
        """Bias notable events slightly toward the later stages of each half."""
        minute = int(round(np.random.triangular(1, 56, 90)))
        return max(1, min(90, minute))

    def _roll_chance_quality(self, player: SWOSPlayer, team_xg: float) -> float:
        """Approximate the quality of a visible chance on an xG-like scale."""
        pos = player.position.value
        if pos in ATTACKING_POSITIONS:
            base = 0.18
        elif pos in MIDFIELD_POSITIONS:
            base = 0.12
        elif pos in DEFENSIVE_POSITIONS:
            base = 0.08
        else:
            base = 0.03

        skill_factor = (
            0.8
            + player.effective_skill("finishing") / 20
            + player.effective_skill("control") / 40
        )
        form_factor = 1.0 + max(-0.08, min(0.16, player.form / 200))
        team_factor = 0.9 + min(team_xg, 2.6) / 5
        quality = random.gauss(base, 0.04) * skill_factor * form_factor * team_factor
        return max(0.05, min(0.42, quality))

    def _save_probability(self, goalkeeper: SWOSPlayer | None, chance_quality: float) -> float:
        """Estimate whether a non-goal chance is saved instead of missed."""
        keeper_factor = 0.15
        if goalkeeper:
            keeper_factor += goalkeeper.gk_save_ability / 35
        probability = 0.72 - chance_quality + keeper_factor
        return max(0.28, min(0.82, probability))

    def _generate_key_chances(
        self,
        squad: list[SWOSPlayer],
        opponents: list[SWOSPlayer],
        num_goals: int,
        team_xg: float,
        side: str,
        events: list[MatchEvent],
        team_name: str,
        attacking_stats: list[PlayerMatchStats],
        defending_stats: list[PlayerMatchStats],
    ) -> None:
        """Generate visible non-goal chances so the timeline has real texture."""
        if not squad:
            return

        weights = self._attacking_weights(squad)
        total_weight = sum(weights)
        probs = [weight / total_weight for weight in weights]
        raw_chances = int(np.random.poisson(max(0.45, team_xg * self.key_chance_scale)))
        non_goal_chances = max(0, min(6, raw_chances - num_goals + np.random.binomial(1, 0.55)))
        if non_goal_chances == 0:
            return

        goalkeeper = next(
            (player for player in opponents if player.position.value in GOALKEEPER_POSITIONS),
            opponents[0] if opponents else None,
        )
        keeper_stat = next(
            (stat for stat in defending_stats if stat.position in GOALKEEPER_POSITIONS),
            None,
        )

        save_details = [
            "big save by the keeper",
            "turned behind by the goalkeeper",
            "brilliant stop at full stretch",
            "denied from close range",
        ]
        miss_details = [
            "drags wide from a promising opening",
            "clips the outside of the post",
            "can't keep the effort down",
            "wastes a decent opening",
        ]
        big_miss_details = [
            "huge chance missed",
            "lets a glorious opening go begging",
            "should have done better with that one",
            "rattles the bar and stays out",
        ]

        for _ in range(non_goal_chances):
            shooter_idx = int(np.random.choice(len(squad), p=probs))
            shooter = squad[shooter_idx]
            minute = self._roll_event_minute()
            chance_quality = self._roll_chance_quality(shooter, team_xg)
            is_saved = random.random() < self._save_probability(goalkeeper, chance_quality)
            detail_pool = save_details if is_saved else (big_miss_details if chance_quality >= 0.22 else miss_details)
            event_type = EventType.SAVE if is_saved else EventType.MISS

            events.append(
                MatchEvent(
                    minute=minute,
                    event_type=event_type,
                    player_id=shooter.base_id,
                    player_name=shooter.display_name,
                    team=side,
                    detail=random.choice(detail_pool),
                )
            )

            shooter.goals_scored_season += 0
            for stat in attacking_stats:
                if stat.player_id == shooter.base_id:
                    rating_delta = 0.15 if is_saved else (-0.15 if chance_quality >= 0.22 else -0.05)
                    stat.rating = round(max(4.0, min(10.0, stat.rating + rating_delta)), 1)
                    break

            if is_saved and keeper_stat is not None:
                keeper_stat.rating = round(min(10.0, keeper_stat.rating + 0.1), 1)

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
    """SWOS arcade match simulator via DOSBox-X.

    Runs real SWOS 96/97 matches in a headless DOSBox-X instance by
    injecting EDT team data and parsing post-match results.

    Falls back to the fast MatchSimulator when:
    - DOSBox-X is not installed
    - No SWOS game directory is configured
    - force_fallback is True
    """

    def __init__(
        self,
        game_dir: str | Path | None = None,
        rules_path: str | Path | None = None,
        force_fallback: bool = False,
    ):
        self._fallback = MatchSimulator(rules_path=rules_path)
        self._game_dir = Path(game_dir) if game_dir else None
        self._force_fallback = force_fallback

        # Lazy-import to avoid circular dependency
        from swos420.engine.dosbox_runner import DOSBoxRunner

        self._runner: DOSBoxRunner | None = None
        if (
            not force_fallback
            and game_dir
            and DOSBoxRunner.available()
            and DOSBoxRunner.game_dir_valid(game_dir)
        ):
            self._runner = DOSBoxRunner(game_dir)

    @property
    def arcade_available(self) -> bool:
        """Whether real SWOS arcade matches are available."""
        return self._runner is not None

    def simulate(
        self,
        home_squad: list[SWOSPlayer],
        away_squad: list[SWOSPlayer],
        **kwargs,
    ) -> MatchResult:
        """Run arcade simulation (or fallback to fast match).

        If DOSBox-X and game files are available, runs a real SWOS match.
        Otherwise, uses the fast ICP-based MatchSimulator.
        """
        if self._runner:
            return self._simulate_arcade(home_squad, away_squad, **kwargs)
        return self._fallback.simulate_match(home_squad, away_squad, **kwargs)

    def _simulate_arcade(
        self,
        home_squad: list[SWOSPlayer],
        away_squad: list[SWOSPlayer],
        **kwargs,
    ) -> MatchResult:
        """Convert squads to EDT, run in DOSBox, parse results."""
        from swos420.importers.swos_edt_binary import (
            SKILL_ORDER as EDT_SKILLS,
            EdtPlayer,
            EdtTeam,
        )

        def _squad_to_edt(squad: list[SWOSPlayer], team_name: str) -> EdtTeam:
            edt_players = []
            for p in squad[:16]:
                skills_display = {}
                for s in EDT_SKILLS:
                    stored = getattr(p.skills, s, 3)
                    skills_display[s] = min(15, stored * 2)
                edt_players.append(EdtPlayer(
                    name=p.short_name[:22],
                    shirt_number=p.shirt_number,
                    position=p.position.value if hasattr(p.position, "value") else str(p.position),
                    skills=skills_display,
                ))
            # Pad to 16
            while len(edt_players) < 16:
                edt_players.append(EdtPlayer(
                    name=f"Sub {len(edt_players)+1}",
                    skills={s: 4 for s in EDT_SKILLS},
                ))
            return EdtTeam(name=team_name, players=edt_players,
                          player_order=list(range(16)))

        home_name = kwargs.get("home_team_name", "Home")
        away_name = kwargs.get("away_team_name", "Away")
        home_edt = _squad_to_edt(home_squad, home_name)
        away_edt = _squad_to_edt(away_squad, away_name)

        result_dict = self._runner.run_match(home_edt, away_edt)

        # Convert DOSBox result dict back to MatchResult
        return MatchResult(
            home_goals=result_dict.get("home_goals", 0),
            away_goals=result_dict.get("away_goals", 0),
            home_team=home_name,
            away_team=away_name,
            home_stats=[],
            away_stats=[],
            events=[],
            home_xg=0.0,
            away_xg=0.0,
        )
