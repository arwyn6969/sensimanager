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

from dataclasses import dataclass
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
WIDE_POSITIONS = {"RM", "LM", "RW", "LW", "RB", "LB", "RWB", "LWB"}


@dataclass(frozen=True)
class TeamStyleProfile:
    """Lightweight team identity profile used to shape match feel."""

    key: str
    label: str
    attack_mult: float = 1.0
    defense_mult: float = 1.0
    chance_volume_mult: float = 1.0
    chance_quality_mult: float = 1.0
    card_mult: float = 1.0
    event_peak_minute: float = 56.0


STYLE_PROFILES: dict[str, TeamStyleProfile] = {
    "balanced": TeamStyleProfile(
        key="balanced",
        label="balanced shape",
    ),
    "possession": TeamStyleProfile(
        key="possession",
        label="patient possession",
        attack_mult=1.03,
        defense_mult=1.02,
        chance_volume_mult=0.95,
        chance_quality_mult=1.08,
        card_mult=0.92,
        event_peak_minute=60.0,
    ),
    "direct": TeamStyleProfile(
        key="direct",
        label="direct transition",
        attack_mult=1.05,
        defense_mult=0.98,
        chance_volume_mult=1.15,
        chance_quality_mult=0.97,
        card_mult=1.04,
        event_peak_minute=48.0,
    ),
    "wide": TeamStyleProfile(
        key="wide",
        label="wing-heavy attacks",
        attack_mult=1.02,
        defense_mult=0.99,
        chance_volume_mult=1.10,
        chance_quality_mult=0.99,
        card_mult=1.00,
        event_peak_minute=54.0,
    ),
    "compact": TeamStyleProfile(
        key="compact",
        label="compact defending",
        attack_mult=0.95,
        defense_mult=1.08,
        chance_volume_mult=0.84,
        chance_quality_mult=0.95,
        card_mult=1.12,
        event_peak_minute=63.0,
    ),
}


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

    @staticmethod
    def _mean_combo(players: list[SWOSPlayer], skills: tuple[str, ...]) -> float:
        """Average a small skill bundle across a player group."""
        if not players:
            return 0.0
        return sum(
            sum(player.effective_skill(skill) for skill in skills) / len(skills)
            for player in players
        ) / len(players)

    def _derive_team_style(
        self,
        squad: list[SWOSPlayer],
        formation: str,
    ) -> TeamStyleProfile:
        """Infer a simple team identity from formation and squad strengths."""
        if not squad:
            return STYLE_PROFILES["balanced"]

        attackers = [player for player in squad if player.position.value in ATTACKING_POSITIONS]
        midfielders = [player for player in squad if player.position.value in MIDFIELD_POSITIONS]
        defenders = [player for player in squad if player.position.value in DEFENSIVE_POSITIONS]
        wide_players = [player for player in squad if player.position.value in WIDE_POSITIONS]

        control_score = self._mean_combo(midfielders or squad, ("passing", "control"))
        direct_score = self._mean_combo(attackers or squad, ("speed", "finishing", "velocity"))
        wide_score = self._mean_combo(wide_players or squad, ("speed", "control", "passing"))
        compact_score = self._mean_combo(defenders or squad, ("tackling", "heading", "passing"))

        formation_bonus = {
            "possession": 0.85 if formation in {"4-3-3", "4-2-3-1", "4-3-2-1"} else 0.0,
            "direct": 0.80 if formation in {"4-4-2", "3-4-3", "3-4-2-1"} else 0.0,
            "wide": 0.90 if formation in {"4-3-3", "3-4-3"} else 0.0,
            "compact": 1.05 if formation in {"5-4-1", "5-3-2", "4-1-4-1"} else 0.0,
        }

        style_scores = {
            "possession": control_score + formation_bonus["possession"] + (0.18 if len(midfielders) >= 3 else 0.0),
            "direct": direct_score + formation_bonus["direct"] + (0.18 if len(attackers) >= 2 else 0.0),
            "wide": wide_score + formation_bonus["wide"] + (0.20 if len(wide_players) >= 4 else 0.0),
            "compact": compact_score + formation_bonus["compact"] + (0.18 if len(defenders) >= 4 else 0.0),
        }

        ordered = sorted(style_scores.items(), key=lambda item: item[1], reverse=True)
        top_key, top_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else top_score

        if top_score - second_score < 0.30:
            return STYLE_PROFILES["balanced"]
        return STYLE_PROFILES[top_key]

    @staticmethod
    def _style_matchup_delta(
        attacking_style: TeamStyleProfile,
        defending_style: TeamStyleProfile,
    ) -> float:
        """Small tactical feel adjustments between team identities."""
        matchup = {
            ("possession", "compact"): -0.30,
            ("possession", "direct"): 0.10,
            ("direct", "possession"): 0.18,
            ("direct", "compact"): 0.14,
            ("wide", "compact"): 0.22,
            ("wide", "possession"): 0.08,
            ("compact", "wide"): -0.12,
            ("compact", "direct"): -0.08,
        }
        return matchup.get((attacking_style.key, defending_style.key), 0.0)

    @staticmethod
    def _build_match_narrative(
        home_team_name: str,
        away_team_name: str,
        home_style: TeamStyleProfile,
        away_style: TeamStyleProfile,
    ) -> str:
        """Describe the style clash for commentary and overlays."""
        if home_style.key == away_style.key:
            return (
                f"Both sides lean on {home_style.label}, so control of rhythm should decide it."
            )
        return f"{home_team_name} bring {home_style.label}; {away_team_name} answer with {away_style.label}."

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
        home_style = self._derive_team_style(home_xi, home_formation)
        away_style = self._derive_team_style(away_xi, away_formation)
        match_narrative = self._build_match_narrative(
            home_team_name,
            away_team_name,
            home_style,
            away_style,
        )

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

        # 5.5. Team identity nudges how the same raw quality manifests.
        home_attack *= home_style.attack_mult
        home_defense *= home_style.defense_mult
        away_attack *= away_style.attack_mult
        away_defense *= away_style.defense_mult
        home_attack += self._style_matchup_delta(home_style, away_style)
        away_attack += self._style_matchup_delta(away_style, home_style)

        # 6. Poisson λ for goals (from ICP differential)
        home_lambda = max(0.3, home_attack / (away_defense + self.xg_defense_offset) * self.xg_base)
        away_lambda = max(0.3, away_attack / (home_defense + self.xg_defense_offset) * self.xg_base)

        # 7. Generate goals
        home_goals = int(np.random.poisson(home_lambda))
        away_goals = int(np.random.poisson(away_lambda))

        # 8. Per-player ratings + live events
        home_stats = self._generate_player_stats(
            home_xi, home_goals, "home", events, referee_strictness, home_team_name, home_style
        )
        away_stats = self._generate_player_stats(
            away_xi, away_goals, "away", events, referee_strictness, away_team_name, away_style
        )

        # 9. Attribute goals and assists (VE/FI split)
        self._attribute_goals(home_xi, home_goals, "home", events, home_team_name, home_stats, home_style)
        self._attribute_goals(away_xi, away_goals, "away", events, away_team_name, away_stats, away_style)

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
            style_profile=home_style,
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
            style_profile=away_style,
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
            home_style=home_style.label,
            away_style=away_style.label,
            match_narrative=match_narrative,
            home_player_stats=home_stats,
            away_player_stats=away_stats,
            events=events,
        )

        logger.info(
            f"Match: {result.scoreline()} (xG: {result.home_xg}-{result.away_xg}, "
            f"styles={home_style.key}/{away_style.key}, weather={weather})"
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
        style_profile: TeamStyleProfile,
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
            card_prob = self.card_base_rate * referee_strictness * style_profile.card_mult
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

    @staticmethod
    def _goal_detail_for_style(style_profile: TeamStyleProfile, team_name: str) -> str:
        details = {
            "possession": [
                f"{team_name} finish a patient move",
                f"{team_name} pass their way through",
            ],
            "direct": [
                f"{team_name} break with real speed",
                f"{team_name} strike from transition",
            ],
            "wide": [
                f"{team_name} cash in from a wide delivery",
                f"{team_name} turn width into a goal",
            ],
            "compact": [
                f"{team_name} punish them on the counter",
                f"{team_name} make a rare break count",
            ],
        }
        return random.choice(details.get(style_profile.key, [f"Goal for {team_name}"]))

    @staticmethod
    def _assist_probability(style_profile: TeamStyleProfile) -> float:
        return {
            "possession": 0.84,
            "wide": 0.82,
            "balanced": 0.75,
            "direct": 0.68,
            "compact": 0.62,
        }.get(style_profile.key, 0.75)

    def _attribute_goals(
        self,
        squad: list[SWOSPlayer],
        num_goals: int,
        side: str,
        events: list[MatchEvent],
        team_name: str,
        stats: list[PlayerMatchStats],
        style_profile: TeamStyleProfile,
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
            minute = self._roll_event_minute(style_profile.event_peak_minute)

            events.append(MatchEvent(
                minute=minute,
                event_type=EventType.GOAL,
                player_id=scorer.base_id,
                player_name=scorer.display_name,
                team=side,
                detail=self._goal_detail_for_style(style_profile, team_name),
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
                    weight = (
                        player.effective_skill("passing") * 1.5
                        + player.effective_skill("control") * 0.5
                    )
                    if style_profile.key == "wide" and player.position.value in WIDE_POSITIONS:
                        weight *= 1.25
                    elif style_profile.key == "possession" and player.position.value in MIDFIELD_POSITIONS:
                        weight *= 1.15
                    assist_weights.append(max(0.1, weight))

            total_aw = sum(assist_weights)
            if total_aw > 0:
                assist_probs = [w / total_aw for w in assist_weights]
                if random.random() < self._assist_probability(style_profile):
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
    def _roll_event_minute(peak_minute: float = 56.0) -> int:
        """Bias notable events around a style-dependent peak minute."""
        minute = int(round(np.random.triangular(1, peak_minute, 90)))
        return max(1, min(90, minute))

    def _roll_chance_quality(
        self,
        player: SWOSPlayer,
        team_xg: float,
        style_profile: TeamStyleProfile,
    ) -> float:
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
        quality = (
            random.gauss(base, 0.04)
            * skill_factor
            * form_factor
            * team_factor
            * style_profile.chance_quality_mult
        )
        return max(0.05, min(0.42, quality))

    def _save_probability(self, goalkeeper: SWOSPlayer | None, chance_quality: float) -> float:
        """Estimate whether a non-goal chance is saved instead of missed."""
        keeper_factor = 0.15
        if goalkeeper:
            keeper_factor += goalkeeper.gk_save_ability / 35
        probability = 0.72 - chance_quality + keeper_factor
        return max(0.28, min(0.82, probability))

    @staticmethod
    def _chance_detail_pools(style_profile: TeamStyleProfile) -> tuple[list[str], list[str], list[str]]:
        """Narrative detail pools keyed to a team's attacking identity."""
        save_details = {
            "balanced": [
                "big save by the keeper",
                "turned behind by the goalkeeper",
                "brilliant stop at full stretch",
                "denied from close range",
            ],
            "possession": [
                "the patient move ends with a strong save",
                "a carved opening is turned away",
                "the goalkeeper reads the slick combination",
            ],
            "direct": [
                "the keeper stops the fast break",
                "denied after getting in behind",
                "the breakaway ends with a sharp save",
            ],
            "wide": [
                "met the delivery, but the keeper reacts",
                "the cross finds him, but the finish is saved",
                "the wide move creates danger, yet the keeper holds firm",
            ],
            "compact": [
                "the counter is smothered by the goalkeeper",
                "a rare break is denied by the keeper",
                "the goalkeeper snuffs out the counterattack",
            ],
        }
        miss_details = {
            "balanced": [
                "drags wide from a promising opening",
                "clips the outside of the post",
                "can't keep the effort down",
                "wastes a decent opening",
            ],
            "possession": [
                "the move deserved better than that finish",
                "he drags the tidy move wide",
                "the intricate build-up ends with a loose effort",
            ],
            "direct": [
                "he races through but cannot hit the target",
                "the break is on, but the finish skews wide",
                "he gets in behind and snatches at it",
            ],
            "wide": [
                "he meets the cross and guides it wide",
                "the delivery is excellent, but the finish is not",
                "the wide overload creates it, yet the shot drifts off target",
            ],
            "compact": [
                "the rare chance is hurried wide",
                "the counter opens up, but the finish lacks composure",
                "he cannot turn the break into a clean effort",
            ],
        }
        big_miss_details = {
            "balanced": [
                "huge chance missed",
                "lets a glorious opening go begging",
                "should have done better with that one",
                "rattles the bar and stays out",
            ],
            "possession": [
                "all that passing, and somehow it stays out",
                "the carved opening really should end in a goal",
                "a sweeping move goes unfinished",
            ],
            "direct": [
                "he is clean through and wastes it",
                "the transition is devastating until the finish",
                "it is a clear breakaway, but he cannot convert",
            ],
            "wide": [
                "the cross is perfect, but the finish is not",
                "he meets the delivery and leaves everyone stunned by missing",
                "the winger does everything right except score",
            ],
            "compact": [
                "the breakaway is there for them, and they waste it",
                "a rare gilt-edged counter goes begging",
                "they may not get a better opening than that",
            ],
        }
        key = style_profile.key if style_profile.key in save_details else "balanced"
        return save_details[key], miss_details[key], big_miss_details[key]

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
        style_profile: TeamStyleProfile,
    ) -> None:
        """Generate visible non-goal chances so the timeline has real texture."""
        if not squad:
            return

        weights = self._attacking_weights(squad)
        total_weight = sum(weights)
        probs = [weight / total_weight for weight in weights]
        raw_chances = int(
            np.random.poisson(
                max(0.35, team_xg * self.key_chance_scale * style_profile.chance_volume_mult)
            )
        )
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

        save_details, miss_details, big_miss_details = self._chance_detail_pools(style_profile)

        for _ in range(non_goal_chances):
            shooter_idx = int(np.random.choice(len(squad), p=probs))
            shooter = squad[shooter_idx]
            minute = self._roll_event_minute(style_profile.event_peak_minute)
            chance_quality = self._roll_chance_quality(shooter, team_xg, style_profile)
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
