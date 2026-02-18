"""Tests for attribute mapping engine — Sofifa → SWOS 0-15 scale."""

import pytest
from pathlib import Path

from swos420.mapping.engine import AttributeMapper, _clamp
from swos420.models.player import Skills


RULES_PATH = Path(__file__).parent.parent / "config" / "rules.json"


@pytest.fixture
def mapper():
    return AttributeMapper(rules_path=RULES_PATH)


class TestClamp:
    def test_in_range(self):
        assert _clamp(10, 0, 15) == 10

    def test_below(self):
        assert _clamp(-5, 0, 15) == 0

    def test_above(self):
        assert _clamp(20, 0, 15) == 15


class TestAttributeMapper:
    def test_loads_rules(self, mapper):
        assert mapper.mapping_rules is not None
        assert len(mapper.mapping_rules) == 7

    def test_map_sofifa_all_skills(self, mapper):
        """Map a complete set of Sofifa attributes to SWOS skills."""
        sofifa = {
            "passing": 85,
            "shot_power": 90,
            "heading_accuracy": 80,
            "standing_tackle": 70,
            "sliding_tackle": 65,
            "ball_control": 88,
            "dribbling": 92,
            "sprint_speed": 95,
            "acceleration": 90,
            "finishing": 97,
        }
        skills = mapper.map_sofifa_to_swos(sofifa)
        assert isinstance(skills, Skills)
        for s in ("passing", "velocity", "heading", "tackling",
                  "control", "speed", "finishing"):
            val = getattr(skills, s)
            assert 0 <= val <= 15, f"{s} = {val} out of range"

    def test_map_missing_attrs_uses_default(self, mapper):
        """Missing attributes should produce mid-range defaults."""
        skills = mapper.map_sofifa_to_swos({})
        assert skills.passing == 5

    def test_map_values_clamped(self, mapper):
        """Even extreme inputs should be clamped to 0-15."""
        sofifa = {"finishing": 200}  # impossible but shouldn't crash
        skills = mapper.map_sofifa_to_swos(sofifa)
        assert skills.finishing <= 15

    # ── Star Player Override Tests (PRD requirements) ──────────────────

    def test_override_haaland(self, mapper):
        """PRD: Haaland finishing must be 15."""
        skills = Skills(finishing=10)
        result = mapper.apply_overrides("Erling Braut Haaland", skills)
        assert result.finishing == 15

    def test_override_haaland_heading(self, mapper):
        """PRD: Haaland heading override = 13."""
        skills = Skills()
        result = mapper.apply_overrides("Erling Braut Haaland", skills)
        assert result.heading == 13

    def test_override_yamal_pace(self, mapper):
        """PRD: Yamal speed must be 14."""
        skills = Skills()
        result = mapper.apply_overrides("Lamine Yamal Nasraoui Ebana", skills)
        assert result.speed == 14

    def test_override_mbappe(self, mapper):
        """PRD: Mbappé speed=15, finishing=14."""
        skills = Skills()
        result = mapper.apply_overrides("Kylian Mbappé Lottin", skills)
        assert result.speed == 15
        assert result.finishing == 14

    def test_override_kane(self, mapper):
        """PRD: Kane finishing=15."""
        skills = Skills()
        result = mapper.apply_overrides("Harry Edward Kane", skills)
        assert result.finishing == 15

    def test_override_rodri(self, mapper):
        """PRD: Rodri passing=14, tackling=14."""
        skills = Skills()
        result = mapper.apply_overrides("Rodrigo Hernández Cascante", skills)
        assert result.passing == 14
        assert result.tackling == 14

    def test_no_override_random_player(self, mapper):
        """Unknown player should not be modified."""
        skills = Skills(passing=8, finishing=7)
        result = mapper.apply_overrides("Random Unknown Player", skills)
        assert result.passing == 8
        assert result.finishing == 7

    def test_map_and_override(self, mapper):
        """Full pipeline: map then override."""
        sofifa = {
            "passing": 65, "shot_power": 94, "heading_accuracy": 85,
            "standing_tackle": 35, "sliding_tackle": 30,
            "ball_control": 84, "dribbling": 82,
            "sprint_speed": 86, "acceleration": 80,
            "finishing": 97,
        }
        skills = mapper.map_and_override("Erling Braut Haaland", sofifa)
        assert skills.finishing == 15  # override wins
        assert skills.heading == 13   # override wins

    def test_calculate_base_value(self, mapper):
        skills = Skills(passing=10, velocity=12, heading=8,
                        tackling=6, control=14, speed=15, finishing=15)
        value = mapper.calculate_base_value(skills, "ST")
        assert value > 0
        # ST weight = 1.2, total = 80
        expected = int(80 * 1.2 * 50_000)
        assert value == expected

    def test_league_multiplier(self, mapper):
        assert mapper.get_league_multiplier("Premier League") == 1.8
        assert mapper.get_league_multiplier("Unknown League") == 1.0

    def test_hot_reload(self, mapper):
        """Reload should not crash."""
        mapper.reload()
        assert mapper.mapping_rules is not None
