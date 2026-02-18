"""Scouting System — tiered skill reveal for transfer targets.

AI managers invest in scouting to progressively reveal player skills
before making transfer bids. Higher tiers cost more but reveal
more information, enabling smarter recruitment.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from swos420.models.player import SWOSPlayer, SKILL_NAMES

# Scouting costs per tier (in £/$CM)
SCOUTING_COSTS = {
    0: 0,        # No scouting — only public info
    1: 50_000,   # Basic — position, age, 2 highest skills
    2: 150_000,  # Detailed — all skills revealed with ±1 noise
    3: 500_000,  # Full — exact skills + hidden potential rating
}


@dataclass
class ScoutingReport:
    """Information revealed by scouting at a given tier."""
    player_id: str
    player_name: str
    position: str
    age: int
    tier: int

    # Tier 0: only above fields
    # Tier 1: top 2 skills revealed
    revealed_skills: dict[str, int] = field(default_factory=dict)

    # Tier 2: all skills (with possible noise)
    all_skills_noisy: dict[str, int] = field(default_factory=dict)

    # Tier 3: exact skills + potential
    exact_skills: dict[str, int] = field(default_factory=dict)
    potential_rating: Optional[float] = None  # 0-100 scale

    # Derived
    estimated_value: int = 0
    scouting_cost: int = 0


class ScoutingSystem:
    """Manages scouting reports for transfer targets.

    Each team tracks how much they've scouted each player.
    Higher tiers reveal more skills and cost more.

    Usage:
        scout = ScoutingSystem()
        report = scout.scout_player(player, tier=1)  # basic report
        report = scout.scout_player(player, tier=3)  # full reveal
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        # Cache: (team_code, player_id) → highest tier scouted
        self._scouted: dict[tuple[str, str], int] = {}

    def scout_player(
        self,
        player: SWOSPlayer,
        tier: int = 1,
        team_code: str = "",
    ) -> ScoutingReport:
        """Generate a scouting report at the requested tier.

        Args:
            player: The player to scout.
            tier: Scouting depth (0-3).
            team_code: The team requesting the report (for caching).

        Returns:
            ScoutingReport with information appropriate for the tier.
        """
        tier = max(0, min(3, tier))
        cost = SCOUTING_COSTS.get(tier, 0)

        # Track highest tier scouted per team+player
        cache_key = (team_code, player.base_id)
        previous_tier = self._scouted.get(cache_key, -1)
        if tier > previous_tier:
            self._scouted[cache_key] = tier

        report = ScoutingReport(
            player_id=player.base_id,
            player_name=player.display_name,
            position=player.position.value,
            age=player.age,
            tier=tier,
            estimated_value=player.calculate_current_value(),
            scouting_cost=cost,
        )

        if tier >= 1:
            report.revealed_skills = self._reveal_top_skills(player, n=2)

        if tier >= 2:
            report.all_skills_noisy = self._reveal_all_noisy(player)

        if tier >= 3:
            report.exact_skills = player.skills.as_dict()
            report.potential_rating = self._calculate_potential(player)

        return report

    def get_scouted_tier(self, team_code: str, player_id: str) -> int:
        """Return the highest tier a team has scouted a player at."""
        return self._scouted.get((team_code, player_id), -1)

    def get_scouting_cost(self, tier: int) -> int:
        """Return the cost for a given scouting tier."""
        return SCOUTING_COSTS.get(max(0, min(3, tier)), 0)

    def reset(self) -> None:
        """Clear all cached scouting data (e.g., new season)."""
        self._scouted.clear()

    def _reveal_top_skills(self, player: SWOSPlayer, n: int = 2) -> dict[str, int]:
        """Reveal the top N skills by value."""
        skills = player.skills.as_dict()
        sorted_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_skills[:n])

    def _reveal_all_noisy(self, player: SWOSPlayer) -> dict[str, int]:
        """Reveal all skills with ±1 noise (simulating imperfect scouting)."""
        skills = player.skills.as_dict()
        noisy = {}
        for name, value in skills.items():
            noise = self._rng.choice([-1, 0, 0, 0, 1])  # bias toward accurate
            noisy[name] = max(0, min(15, value + noise))
        return noisy

    def _calculate_potential(self, player: SWOSPlayer) -> float:
        """Estimate player potential (0-100).

        Young players with high skills = high potential.
        Older players' potential roughly equals current ability.
        """
        skill_avg = player.skills.total / 7.0
        age = player.age

        if age <= 21:
            # Young: potential scales with current skill + age bonus
            base_potential = (skill_avg / 15.0) * 100
            age_bonus = (22 - age) * 5  # younger = higher ceiling
            return min(99.0, base_potential + age_bonus)
        elif age <= 28:
            # Peak: potential ≈ current ability
            return (skill_avg / 15.0) * 90
        else:
            # Declining: potential below current ability
            decline = (age - 28) * 3
            return max(10.0, (skill_avg / 15.0) * 80 - decline)
