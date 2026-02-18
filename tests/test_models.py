"""Tests for SWOSPlayer model — v3.0 authentic SWOS mechanics."""

import pytest

from swos420.models.player import (
    SKILL_NAMES,
    SWOS_SKILL_BASE,
    Position,
    Skills,
    SWOSPlayer,
    generate_base_id,
    hex_tier_value,
)


# ── Skills Tests ──────────────────────────────────────────────────────


class TestSkills:
    def test_default_skills(self):
        skills = Skills()
        assert all(getattr(skills, s) == 3 for s in SKILL_NAMES)

    def test_skill_clamping_lower(self):
        with pytest.raises(ValueError):
            Skills(passing=-1)

    def test_skill_clamping_upper(self):
        with pytest.raises(ValueError):
            Skills(finishing=8)  # Max is 7

    def test_total(self):
        skills = Skills(passing=5, velocity=6, heading=4,
                        tackling=3, control=7, speed=7, finishing=7)
        assert skills.total == 39  # Stored total

    def test_effective_total(self):
        skills = Skills(passing=5, velocity=6, heading=4,
                        tackling=3, control=7, speed=7, finishing=7)
        assert skills.effective_total == 39 + 7 * SWOS_SKILL_BASE  # 39 + 56 = 95

    def test_effective(self):
        skills = Skills(passing=5)
        assert skills.effective("passing") == 5 + SWOS_SKILL_BASE  # 13

    def test_top3(self):
        skills = Skills(passing=2, velocity=2, heading=2,
                        tackling=2, control=5, speed=7, finishing=6)
        top = skills.top3
        assert top[0] == "SP"
        assert top[1] == "FI"
        assert top[2] == "CO"

    def test_as_dict(self):
        skills = Skills(passing=5)
        d = skills.as_dict()
        assert d["passing"] == 5  # Stored value
        assert len(d) == 7

    def test_effective_dict(self):
        skills = Skills(passing=5)
        d = skills.effective_dict()
        assert d["passing"] == 13  # 5 + 8


# ── Base ID Generation ────────────────────────────────────────────────


class TestBaseID:
    def test_deterministic(self):
        id1 = generate_base_id(239085, "25/26")
        id2 = generate_base_id(239085, "25/26")
        assert id1 == id2

    def test_different_seasons(self):
        id1 = generate_base_id(239085, "25/26")
        id2 = generate_base_id(239085, "26/27")
        assert id1 != id2

    def test_length(self):
        base_id = generate_base_id(239085, "25/26")
        assert len(base_id) == 16


# ── Player Model Tests ───────────────────────────────────────────────


class TestSWOSPlayer:
    @pytest.fixture
    def haaland(self):
        return SWOSPlayer(
            base_id="abc123def456789a",
            full_name="Erling Braut Haaland",
            display_name="HAALAND",
            short_name="E. Haaland",
            position=Position.ST,
            nationality="Norway",
            club_name="Manchester City",
            club_code="MCI",
            skills=Skills(
                passing=2, velocity=6, heading=5,
                tackling=1, control=5, speed=6, finishing=7,
            ),
            age=25,
            base_value=15_000_000,
            form=0.0,
        )

    def test_display_name_uppercase(self):
        p = SWOSPlayer(
            base_id="test123456789abc",
            full_name="Test Player",
            display_name="test",
        )
        assert p.display_name == "TEST"

    def test_display_name_max_length(self):
        with pytest.raises(ValueError):
            SWOSPlayer(
                base_id="test123456789abc",
                full_name="Test",
                display_name="A" * 16,
            )

    def test_effective_skill_neutral_form(self, haaland):
        """Form 0 → effective = stored + 8 (no form modifier)."""
        # finishing stored=7, effective = 7+8 = 15
        assert haaland.effective_skill("finishing") == 15.0

    def test_effective_skill_positive_form(self, haaland):
        """Form +50 = +25% boost on effective value."""
        haaland.form = 50.0
        eff = haaland.effective_skill("finishing")
        # effective = (7+8) * (1 + 50/200) = 15 * 1.25 = 18.75
        assert eff == 15 * 1.25  # 18.75

    def test_effective_skill_negative_form(self, haaland):
        """Form -50 = -25% penalty on effective value."""
        haaland.form = -50.0
        eff = haaland.effective_skill("finishing")
        # effective = (7+8) * (1 - 50/200) = 15 * 0.75 = 11.25
        assert eff == 15 * 0.75  # 11.25

    def test_effective_skills_all(self, haaland):
        effs = haaland.effective_skills()
        assert len(effs) == 7
        assert effs["finishing"] == 15.0  # (7+8) * 1.0

    def test_age_factor_youth(self, haaland):
        haaland.age = 18
        assert 0.7 < haaland.age_factor < 1.0

    def test_age_factor_peak(self, haaland):
        haaland.age = 27
        assert haaland.age_factor == 1.0

    def test_age_factor_decline(self, haaland):
        haaland.age = 35
        assert haaland.age_factor < 0.76

    def test_age_factor_floor(self, haaland):
        haaland.age = 40
        assert haaland.age_factor >= 0.3

    def test_calculate_value_hex_tier(self, haaland):
        """Value comes from hex-tier lookup, not linear base_value."""
        val = haaland.calculate_current_value()
        # skill_total = 2+6+5+1+5+6+7 = 32 → hex_tier=2,500,000
        tier_base = hex_tier_value(haaland.skills.total)
        # form=0 → form_mod=1.0, goals=0 → goal_bonus=1.0, age=25 → age_factor=1.0
        assert val == tier_base

    def test_calculate_value_high_form(self, haaland):
        """High form increases value."""
        haaland.form = 50.0
        val = haaland.calculate_current_value()
        tier_base = hex_tier_value(haaland.skills.total)
        assert val > tier_base

    def test_calculate_wage(self, haaland):
        """Wage = current_value * 0.0018."""
        wage = haaland.calculate_wage()
        val = haaland.calculate_current_value()
        expected = max(5_000, int(val * 0.0018))
        assert wage == expected

    def test_form_change(self, haaland):
        """Win bonus + good rating should increase form."""
        haaland.form = 0.0
        haaland.apply_form_change(team_result_bonus=3.0, individual_rating=8.0)
        assert haaland.form > 0

    def test_form_clamped(self, haaland):
        haaland.form = 48.0
        haaland.apply_form_change(team_result_bonus=5.0, individual_rating=9.0)
        assert haaland.form <= 50.0

    def test_bench_decay(self, haaland):
        haaland.form = 30.0
        haaland.apply_bench_decay(weeks=2)
        assert haaland.form < 30.0

    def test_should_retire_by_age(self, haaland):
        haaland.age = 38
        assert haaland.should_retire

    def test_should_retire_by_skills(self, haaland):
        """Total stored skills < 7 → should retire."""
        haaland.age = 30
        haaland.skills = Skills(passing=0, velocity=0, heading=0,
                                tackling=0, control=0, speed=1, finishing=0)
        # 0+0+0+0+0+1+0 = 1 < 7 threshold
        assert haaland.should_retire

    def test_injury_risk_base(self, haaland):
        haaland.form = 0.0
        haaland.fatigue = 0.0
        assert haaland.injury_risk_lambda == pytest.approx(0.08)

    def test_injury_risk_increased(self, haaland):
        haaland.form = -30.0
        haaland.fatigue = 50.0
        assert haaland.injury_risk_lambda > 0.08

    def test_nft_metadata(self, haaland):
        meta = haaland.to_nft_metadata()
        assert meta["name"] == "Erling Braut Haaland"
        assert any(a["trait_type"] == "FI" and a["value"] == 7 for a in meta["attributes"])  # stored value
        assert any(a["trait_type"] == "Position" and a["value"] == "ST" for a in meta["attributes"])

    def test_morale_range(self):
        with pytest.raises(ValueError):
            SWOSPlayer(
                base_id="test123456789abc",
                full_name="Test",
                display_name="TEST",
                morale=101.0,
            )

    def test_form_range(self):
        with pytest.raises(ValueError):
            SWOSPlayer(
                base_id="test123456789abc",
                full_name="Test",
                display_name="TEST",
                form=51.0,
            )
