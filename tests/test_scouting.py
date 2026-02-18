"""Tests for the scouting system."""

from __future__ import annotations


from swos420.engine.scouting import ScoutingSystem, SCOUTING_COSTS
from swos420.models.player import Position, Skills, SWOSPlayer


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_player(
    name: str = "SCOUT TARGET",
    skill_level: int = 10,
    age: int = 22,
) -> SWOSPlayer:
    skills = {s: skill_level for s in
              ["passing", "velocity", "heading", "tackling", "control", "speed", "finishing"]}
    # Give one standout skill for testing top-skill reveal
    skills["speed"] = min(15, skill_level + 3)
    skills["finishing"] = min(15, skill_level + 2)
    return SWOSPlayer(
        base_id=f"scout_test_{name.lower().replace(' ', '_')}",
        full_name=name.title(),
        display_name=name.upper()[:15],
        position=Position.ST,
        skills=Skills(**skills),
        age=age,
        base_value=5_000_000,
    )


# ═══════════════════════════════════════════════════════════════════════
# ScoutingSystem Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTier0:
    """Tier 0: Only public info (position, age, estimated value)."""

    def test_tier0_reveals_basic_info(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player()
        report = scout.scout_player(player, tier=0)

        assert report.player_name == player.display_name
        assert report.position == player.position.value
        assert report.age == player.age
        assert report.estimated_value > 0

    def test_tier0_hides_skills(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player()
        report = scout.scout_player(player, tier=0)

        assert len(report.revealed_skills) == 0
        assert len(report.all_skills_noisy) == 0
        assert len(report.exact_skills) == 0
        assert report.potential_rating is None


class TestTier1:
    """Tier 1: Basic — reveals top 2 skills."""

    def test_tier1_reveals_top_2(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player(skill_level=10)
        report = scout.scout_player(player, tier=1)

        assert len(report.revealed_skills) == 2
        # Speed (13) and finishing (12) should be the top 2
        assert "speed" in report.revealed_skills
        assert "finishing" in report.revealed_skills

    def test_tier1_has_correct_values(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player(skill_level=8)
        report = scout.scout_player(player, tier=1)

        for skill_name, value in report.revealed_skills.items():
            assert value == getattr(player.skills, skill_name)

    def test_tier1_cost(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player()
        report = scout.scout_player(player, tier=1)
        assert report.scouting_cost == SCOUTING_COSTS[1]


class TestTier2:
    """Tier 2: Detailed — all skills with ±1 noise."""

    def test_tier2_reveals_all_skills(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player()
        report = scout.scout_player(player, tier=2)

        assert len(report.all_skills_noisy) == 7

    def test_tier2_noise_within_bounds(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player(skill_level=10)
        report = scout.scout_player(player, tier=2)

        for skill_name, noisy_val in report.all_skills_noisy.items():
            true_val = getattr(player.skills, skill_name)
            # Noise is ±1
            assert abs(noisy_val - true_val) <= 1
            # Clamped to 0-15
            assert 0 <= noisy_val <= 15

    def test_tier2_also_has_top_skills(self):
        """Tier 2 should include tier 1 info as well."""
        scout = ScoutingSystem(seed=42)
        player = _make_player()
        report = scout.scout_player(player, tier=2)
        assert len(report.revealed_skills) == 2  # From tier 1


class TestTier3:
    """Tier 3: Full — exact skills + potential rating."""

    def test_tier3_reveals_exact_skills(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player(skill_level=10)
        report = scout.scout_player(player, tier=3)

        assert len(report.exact_skills) == 7
        for skill_name, value in report.exact_skills.items():
            assert value == getattr(player.skills, skill_name)

    def test_tier3_has_potential(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player(age=19)
        report = scout.scout_player(player, tier=3)

        assert report.potential_rating is not None
        assert 0.0 <= report.potential_rating <= 99.0

    def test_tier3_young_player_high_potential(self):
        scout = ScoutingSystem(seed=42)
        young = _make_player(skill_level=12, age=18)
        old = _make_player(skill_level=12, age=33)

        young_report = scout.scout_player(young, tier=3)
        old_report = scout.scout_player(old, tier=3)

        assert young_report.potential_rating > old_report.potential_rating


class TestScoutingCache:
    def test_tracks_highest_tier(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player()

        scout.scout_player(player, tier=1, team_code="ARS")
        assert scout.get_scouted_tier("ARS", player.base_id) == 1

        scout.scout_player(player, tier=3, team_code="ARS")
        assert scout.get_scouted_tier("ARS", player.base_id) == 3

    def test_different_teams_independent(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player()

        scout.scout_player(player, tier=2, team_code="ARS")
        scout.scout_player(player, tier=1, team_code="MCI")

        assert scout.get_scouted_tier("ARS", player.base_id) == 2
        assert scout.get_scouted_tier("MCI", player.base_id) == 1

    def test_unscouted_returns_minus_one(self):
        scout = ScoutingSystem(seed=42)
        assert scout.get_scouted_tier("ARS", "unknown_player") == -1

    def test_reset_clears_cache(self):
        scout = ScoutingSystem(seed=42)
        player = _make_player()
        scout.scout_player(player, tier=3, team_code="ARS")
        scout.reset()
        assert scout.get_scouted_tier("ARS", player.base_id) == -1


class TestCostLookup:
    def test_all_tiers_have_costs(self):
        scout = ScoutingSystem()
        assert scout.get_scouting_cost(0) == 0
        assert scout.get_scouting_cost(1) == 50_000
        assert scout.get_scouting_cost(2) == 150_000
        assert scout.get_scouting_cost(3) == 500_000

    def test_out_of_range_clamped(self):
        scout = ScoutingSystem()
        assert scout.get_scouting_cost(-1) == 0
        assert scout.get_scouting_cost(99) == 500_000
