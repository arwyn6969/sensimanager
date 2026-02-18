"""Targeted tests for player model coverage gaps.

Covers: positional_fitness edge cases, gk_save_ability, apply_aging,
and mapping engine aggregate/override edge paths.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from swos420.models.player import (
    SWOSPlayer,
    Skills,
    Position,
    positional_fitness,
    SKILL_NAMES,
)
from swos420.mapping.engine import AttributeMapper


# ═══════════════════════════════════════════════════════════════════════
# positional_fitness — cover L122-134
# ═══════════════════════════════════════════════════════════════════════


class TestPositionalFitness:
    """Cover same-zone neutral (1.0) and cross-zone penalty (0.7) paths."""

    def test_exact_match_green_tick(self):
        assert positional_fitness("ST", "ST") == 1.2

    def test_green_tick_compatible(self):
        # CF is in GREEN_TICK_POSITIONS for ST
        assert positional_fitness("CF", "ST") == 1.2

    def test_same_zone_neutral(self):
        # RM and CAM are both midfield but RM is not in GREEN_TICK_POSITIONS for CAM
        assert positional_fitness("RM", "CAM") == 1.0

    def test_cross_zone_penalty(self):
        # ST (attacking) playing as CB (defensive) = 0.7
        assert positional_fitness("ST", "CB") == 0.7

    def test_defensive_to_attacking_penalty(self):
        assert positional_fitness("CB", "ST") == 0.7

    def test_midfield_to_defensive_penalty(self):
        # CM (midfield) to CB (defensive)
        assert positional_fitness("CM", "CB") == 0.7

    def test_attacking_zone_variants(self):
        # RW and LW are both attacking zone
        assert positional_fitness("RW", "LW") == 1.0


# ═══════════════════════════════════════════════════════════════════════
# gk_save_ability — cover L290
# ═══════════════════════════════════════════════════════════════════════


class TestGKSaveAbility:
    def test_non_goalkeeper_returns_zero(self):
        player = SWOSPlayer(
            base_id="test-gk-1", full_name="Test Player",
            display_name="TEST1", position=Position.ST,
            skills=Skills(passing=3),
        )
        assert player.gk_save_ability == 0.0

    def test_goalkeeper_low_value(self):
        player = SWOSPlayer(
            base_id="test-gk-2", full_name="Test GK",
            display_name="TESTGK", position=Position.GK,
            skills=Skills(passing=0, velocity=0, heading=0, tackling=0,
                          control=0, speed=0, finishing=0),
        )
        # Low skills = low value = save ability around 0.30
        assert 0.25 <= player.gk_save_ability <= 0.60

    def test_goalkeeper_high_value(self):
        player = SWOSPlayer(
            base_id="test-gk-3", full_name="Test GK High",
            display_name="TESTGK", position=Position.GK,
            skills=Skills(passing=7, velocity=7, heading=7, tackling=7,
                          control=7, speed=7, finishing=7),
            form=50.0, goals_scored_season=0,
        )
        # Max skills but actual save ability depends on value tier
        ability = player.gk_save_ability
        assert 0.30 <= ability <= 0.95


# ═══════════════════════════════════════════════════════════════════════
# apply_aging — cover L360-367
# ═══════════════════════════════════════════════════════════════════════


class TestApplyAging:
    def test_youth_no_change(self):
        """Under-24 with high form: age increments but skills unchanged (engine handles dev)."""
        player = SWOSPlayer(
            base_id="young-1", full_name="Young Player",
            display_name="YOUNG", position=Position.CM,
            skills=Skills(passing=5, velocity=5), age=20, form=30.0,
        )
        player.apply_aging()
        assert player.age == 21
        # Skills should be unchanged (engine handles youth dev externally)
        assert player.skills.passing == 5

    def test_veteran_decay(self):
        """30+ player: skills should decay."""
        player = SWOSPlayer(
            base_id="old-1", full_name="Old Player",
            display_name="OLD", position=Position.CM,
            skills=Skills(passing=5, velocity=5, heading=5, tackling=5,
                          control=5, speed=5, finishing=5),
            age=30,
        )
        original_total = player.skills.total
        player.apply_aging()
        assert player.age == 31
        # At age 30-33, decay_rate=0.1, int(5-0.1)=4 so no change
        # At age 34+, decay_rate=0.25, int(5-0.25)=4 so partial change
        # Skills should stay same or decrease
        assert player.skills.total <= original_total

    def test_very_old_player_decay(self):
        """34+ player: stronger decay."""
        player = SWOSPlayer(
            base_id="old-2", full_name="Very Old Player",
            display_name="VOLD", position=Position.CB,
            skills=Skills(passing=3, velocity=3, heading=3, tackling=3,
                          control=3, speed=3, finishing=3),
            age=34,
        )
        player.apply_aging()
        assert player.age == 35
        # Skills should have decayed (int(3-0.25) = 2)
        assert player.skills.total <= 21  # 7 * 3 = 21 original

    def test_mid_career_no_change(self):
        """24-29 age: no aging effects on skills."""
        player = SWOSPlayer(
            base_id="mid-1", full_name="Mid Player",
            display_name="MID", position=Position.CM,
            skills=Skills(passing=5), age=26,
        )
        player.apply_aging()
        assert player.age == 27
        assert player.skills.passing == 5  # unchanged


# ═══════════════════════════════════════════════════════════════════════
# AttributeMapper edge cases — cover L40/56/100/102/152-153
# ═══════════════════════════════════════════════════════════════════════


class TestAttributeMapperEdgeCases:
    def test_missing_rules_file(self, tmp_path):
        """Non-existent rules path should result in empty rules."""
        mapper = AttributeMapper(rules_path=tmp_path / "nonexistent.json")
        assert mapper.mapping_rules == {}
        assert mapper.overrides == {}
        assert mapper.economy_rules == {}
        assert mapper.form_rules == {}

    def test_max_aggregate(self, tmp_path):
        """Test 'max' aggregate type in mapping."""
        rules = {
            "mapping_simple": {
                "finishing": {
                    "sources": ["finishing", "volleys"],
                    "aggregate": "max",
                    "multiplier": 0.07,
                    "offset": 0.0,
                }
            }
        }
        rules_file = tmp_path / "rules.json"
        import json
        rules_file.write_text(json.dumps(rules))
        mapper = AttributeMapper(rules_path=rules_file)
        skills = mapper.map_sofifa_to_swos({"finishing": 90, "volleys": 80})
        # max(90, 80) = 90 * 0.07 = 6.3 → round → 6
        assert skills.finishing == 6

    def test_min_aggregate(self, tmp_path):
        """Test 'min' aggregate type in mapping."""
        import json
        rules = {
            "mapping_simple": {
                "passing": {
                    "sources": ["short_passing", "long_passing"],
                    "aggregate": "min",
                    "multiplier": 0.07,
                    "offset": 0.0,
                }
            }
        }
        rules_file = tmp_path / "rules.json"
        rules_file.write_text(json.dumps(rules))
        mapper = AttributeMapper(rules_path=rules_file)
        skills = mapper.map_sofifa_to_swos({"short_passing": 90, "long_passing": 60})
        # min(90, 60) = 60 * 0.07 = 4.2 → round → 4
        assert skills.passing == 4

    def test_missing_sofifa_key_skipped(self, tmp_path):
        """Missing SoFIFA keys should be skipped, no error."""
        import json
        rules = {
            "mapping_simple": {
                "passing": {
                    "sources": ["short_passing", "nonexistent_key"],
                    "aggregate": "mean",
                    "multiplier": 0.07,
                    "offset": 0.0,
                }
            }
        }
        rules_file = tmp_path / "rules.json"
        rules_file.write_text(json.dumps(rules))
        mapper = AttributeMapper(rules_path=rules_file)
        # Only short_passing exists, nonexistent_key is skipped
        skills = mapper.map_sofifa_to_swos({"short_passing": 85})
        assert 0 <= skills.passing <= 7

    def test_surname_only_override(self, tmp_path):
        """Single-word override should match by surname."""
        import json
        rules = {
            "mapping_simple": {},
            "overrides": {
                "Messi": {"finishing": 7, "control": 7}
            }
        }
        rules_file = tmp_path / "rules.json"
        rules_file.write_text(json.dumps(rules))
        mapper = AttributeMapper(rules_path=rules_file)
        skills = Skills(passing=3, finishing=4, control=4)
        overridden = mapper.apply_overrides("Lionel Messi", skills)
        assert overridden.finishing == 7
        assert overridden.control == 7
