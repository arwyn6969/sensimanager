"""Tests for player economy mechanics — wages, values, form swings."""

import pytest

from swos420.models.player import Skills, SWOSPlayer, Position, SWOS_SKILL_BASE


@pytest.fixture
def star_player():
    """A high-tier player at neutral form (0-7 stored skills)."""
    return SWOSPlayer(
        base_id="star123456789abc",
        full_name="Star Player",
        display_name="STAR",
        position=Position.ST,
        skills=Skills(passing=5, velocity=6, heading=5,
                      tackling=3, control=6, speed=6, finishing=7),
        age=27,
        base_value=15_000_000,
        form=0.0,
    )


class TestWageCalculation:
    def test_neutral_form_wage(self, star_player):
        """Neutral form: wage = current_value * 0.0018."""
        wage = star_player.calculate_wage()
        value = star_player.calculate_current_value()
        expected = max(5_000, int(value * 0.0018))
        assert wage == expected

    def test_wage_minimum(self):
        """Even worst players get minimum £5k wage."""
        player = SWOSPlayer(
            base_id="min0123456789abc",
            full_name="Min Wage Player",
            display_name="MINWAGE",
            base_value=100_000,
            form=-50.0,
        )
        assert player.calculate_wage() >= 5_000

    def test_wage_with_league_multiplier(self, star_player):
        """Premier League multiplier (1.8) should increase wages."""
        base_wage = star_player.calculate_wage(league_multiplier=1.0)
        prem_wage = star_player.calculate_wage(league_multiplier=1.8)
        assert prem_wage > base_wage

    def test_wage_from_value_formula(self, star_player):
        """Community-confirmed: wage ≈ value × 0.0012-0.0025."""
        value = star_player.calculate_current_value()
        wage = star_player.calculate_wage()
        ratio = wage / value if value > 0 else 0
        assert 0.001 < ratio < 0.003, f"Wage ratio {ratio} outside expected range"


class TestValueFluctuation:
    def test_positive_form_increases_value(self, star_player):
        """High form should significantly increase value."""
        neutral_val = star_player.calculate_current_value()
        star_player.form = 50.0
        high_form_val = star_player.calculate_current_value()
        assert high_form_val > neutral_val

    def test_negative_form_decreases_value(self, star_player):
        neutral_val = star_player.calculate_current_value()
        star_player.form = -50.0
        low_form_val = star_player.calculate_current_value()
        assert low_form_val < neutral_val

    def test_form_swing_40_percent(self, star_player):
        """PRD: Form system should produce ±40% value swings in a season."""
        star_player.form = -50.0
        low = star_player.calculate_current_value()
        star_player.form = 50.0
        high = star_player.calculate_current_value()
        swing_pct = (high - low) / ((high + low) / 2) * 100
        assert swing_pct > 30, f"Value swing {swing_pct:.1f}% — expected >30%"

    def test_goals_increase_value(self, star_player):
        """Scoring goals should boost market value."""
        base_val = star_player.calculate_current_value()
        star_player.goals_scored_season = 30
        goals_val = star_player.calculate_current_value()
        assert goals_val > base_val

    def test_age_reduces_value(self, star_player):
        """Aging past peak should reduce value."""
        peak_val = star_player.calculate_current_value()
        star_player.age = 34
        aging_val = star_player.calculate_current_value()
        assert aging_val < peak_val

    def test_value_minimum(self):
        """Value should never go below £25k."""
        player = SWOSPlayer(
            base_id="min0123456789abc",
            full_name="Minimum Value Player",
            display_name="MINVAL",
            base_value=50_000,
            form=-50.0,
            age=38,
        )
        assert player.calculate_current_value() >= 25_000


class TestFormMechanics:
    def test_win_increases_form(self, star_player):
        """Win bonus + good individual rating → form up."""
        star_player.form = 0.0
        star_player.apply_form_change(team_result_bonus=3.0, individual_rating=8.0)
        assert star_player.form > 0

    def test_loss_decreases_form(self, star_player):
        """Loss + poor rating → form down."""
        star_player.form = 0.0
        star_player.apply_form_change(team_result_bonus=-2.0, individual_rating=4.0)
        assert star_player.form < 0

    def test_form_capped_at_50(self, star_player):
        star_player.form = 48.0
        star_player.apply_form_change(team_result_bonus=5.0, individual_rating=10.0)
        assert star_player.form <= 50.0

    def test_form_floored_at_minus_50(self, star_player):
        star_player.form = -48.0
        star_player.apply_form_change(team_result_bonus=-5.0, individual_rating=1.0)
        assert star_player.form >= -50.0

    def test_bench_form_decay(self, star_player):
        star_player.form = 20.0
        star_player.apply_bench_decay(weeks=3)
        assert star_player.form < 20.0

    def test_effective_skill_range(self, star_player):
        """Effective skill with max positive form should be (stored+8) * 1.25."""
        star_player.form = 50.0
        eff = star_player.effective_skill("finishing")
        base_effective = star_player.skills.finishing + SWOS_SKILL_BASE
        assert eff == base_effective * 1.25

    def test_effective_skill_negative(self, star_player):
        """Effective skill with max negative form should be (stored+8) * 0.75."""
        star_player.form = -50.0
        eff = star_player.effective_skill("finishing")
        base_effective = star_player.skills.finishing + SWOS_SKILL_BASE
        assert eff == base_effective * 0.75


class TestInjuryRisk:
    def test_base_lambda(self, star_player):
        star_player.form = 0.0
        star_player.fatigue = 0.0
        assert star_player.injury_risk_lambda == pytest.approx(0.08)

    def test_negative_form_increases_risk(self, star_player):
        star_player.form = -30.0
        assert star_player.injury_risk_lambda > 0.08

    def test_fatigue_increases_risk(self, star_player):
        star_player.fatigue = 80.0
        assert star_player.injury_risk_lambda > 0.08

    def test_combined_risk(self, star_player):
        """Negative form + high fatigue = significantly higher injury risk."""
        star_player.form = -40.0
        star_player.fatigue = 90.0
        lambda_val = star_player.injury_risk_lambda
        assert lambda_val > 0.15, f"Combined risk {lambda_val} — expected >0.15"
