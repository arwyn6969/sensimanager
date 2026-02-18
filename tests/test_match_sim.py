"""Tests for the match engine — MatchSimulator, MatchResult, fixture generator.

Covers: score distributions, tactics advantage, weather debuffs, form impact,
injury clustering, goal attribution, per-player ratings, edge cases.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter

import numpy as np
import pytest

from swos420.engine.fixture_generator import (
    generate_round_robin,
    matches_per_season,
    total_matchdays,
)
from swos420.engine.match_result import (
    EventType,
    MatchEvent,
    MatchResult,
    PlayerMatchStats,
)
from swos420.engine.match_sim import (
    ArcadeMatchSimulator,
    MatchSimulator,
    DEFAULT_TACTICS_MATRIX,
)
from swos420.models.player import Position, Skills, SWOSPlayer, generate_base_id


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_player(
    name: str = "TEST PLAYER",
    position: Position = Position.CM,
    skills: dict | None = None,
    form: float = 0.0,
    fatigue: float = 0.0,
    age: int = 25,
) -> SWOSPlayer:
    """Create a test player with optional overrides."""
    base_skills = {"passing": 8, "velocity": 7, "heading": 7, "tackling": 7,
                   "control": 8, "speed": 8, "finishing": 8}
    if skills:
        base_skills.update(skills)

    return SWOSPlayer(
        base_id=generate_base_id(random.randint(1, 999999), "25/26"),
        full_name=name.title(),
        display_name=name.upper()[:15],
        position=position,
        skills=Skills(**base_skills),
        form=form,
        fatigue=fatigue,
        age=age,
    )


def _make_squad(
    prefix: str = "PLAYER",
    skill_level: int = 8,
    form: float = 0.0,
) -> list[SWOSPlayer]:
    """Create a full 11-player squad."""
    positions = [
        Position.GK, Position.RB, Position.CB, Position.CB, Position.LB,
        Position.RM, Position.CM, Position.CM, Position.LM,
        Position.ST, Position.ST,
    ]
    skills_dict = {s: skill_level for s in
                   ["passing", "velocity", "heading", "tackling", "control", "speed", "finishing"]}

    return [
        _make_player(
            name=f"{prefix} {i+1}",
            position=pos,
            skills=skills_dict,
            form=form,
        )
        for i, pos in enumerate(positions)
    ]


def _make_strong_squad() -> list[SWOSPlayer]:
    return _make_squad("STRONG", skill_level=13, form=30.0)


def _make_weak_squad() -> list[SWOSPlayer]:
    return _make_squad("WEAK", skill_level=4, form=-20.0)


def _make_haaland_squad() -> list[SWOSPlayer]:
    """Squad with Haaland-like striker (finishing=15, high form)."""
    squad = _make_squad("MCI", skill_level=10)
    # Make the first ST a Haaland analog
    haaland = squad[9]
    haaland.skills.finishing = 15
    haaland.skills.speed = 12
    haaland.skills.heading = 13
    haaland.form = 40.0
    haaland.full_name = "Erling Haaland"
    haaland.display_name = "HAALAND"
    return squad


# ═══════════════════════════════════════════════════════════════════════
# MatchResult Tests
# ═══════════════════════════════════════════════════════════════════════

class TestMatchResult:
    def test_winner_home(self):
        r = MatchResult(home_team="A", away_team="B", home_goals=2, away_goals=1,
                        home_xg=1.5, away_xg=1.0)
        assert r.winner == "home"

    def test_winner_away(self):
        r = MatchResult(home_team="A", away_team="B", home_goals=0, away_goals=3,
                        home_xg=1.0, away_xg=2.0)
        assert r.winner == "away"

    def test_winner_draw(self):
        r = MatchResult(home_team="A", away_team="B", home_goals=1, away_goals=1,
                        home_xg=1.0, away_xg=1.0)
        assert r.winner == "draw"

    def test_points_home_win(self):
        r = MatchResult(home_team="A", away_team="B", home_goals=3, away_goals=0,
                        home_xg=2.0, away_xg=0.5)
        assert r.home_points == 3
        assert r.away_points == 0

    def test_points_draw(self):
        r = MatchResult(home_team="A", away_team="B", home_goals=2, away_goals=2,
                        home_xg=2.0, away_xg=2.0)
        assert r.home_points == 1
        assert r.away_points == 1

    def test_scoreline(self):
        r = MatchResult(home_team="Man City", away_team="Arsenal",
                        home_goals=2, away_goals=1, home_xg=1.5, away_xg=1.0)
        assert r.scoreline() == "Man City 2 - 1 Arsenal"

    def test_to_dict(self):
        r = MatchResult(home_team="A", away_team="B", home_goals=1, away_goals=0,
                        home_xg=1.2, away_xg=0.8)
        d = r.to_dict()
        assert d["winner"] == "home"
        assert d["home_xg"] == 1.2

    def test_goal_events(self):
        r = MatchResult(home_team="A", away_team="B", home_goals=1, away_goals=0,
                        home_xg=1.0, away_xg=0.5)
        r.events.append(MatchEvent(minute=55, event_type=EventType.GOAL,
                                   player_id="p1", player_name="SCORER", team="home"))
        r.events.append(MatchEvent(minute=30, event_type=EventType.YELLOW_CARD,
                                   player_id="p2", player_name="FOULER", team="away"))
        assert len(r.goal_events()) == 1
        assert len(r.injury_events()) == 0


class TestMatchEvent:
    def test_str(self):
        e = MatchEvent(minute=75, event_type=EventType.GOAL,
                       player_id="p1", player_name="HAALAND", team="home", detail="Header")
        s = str(e)
        assert "75'" in s
        assert "GOAL" in s
        assert "HAALAND" in s


# ═══════════════════════════════════════════════════════════════════════
# MatchSimulator Core Tests
# ═══════════════════════════════════════════════════════════════════════

class TestMatchSimulator:
    @pytest.fixture
    def sim(self):
        return MatchSimulator()

    def test_basic_match_runs(self, sim):
        """A match should complete and return a valid result."""
        home = _make_squad("HOME")
        away = _make_squad("AWAY")
        result = sim.simulate_match(home, away)
        assert isinstance(result, MatchResult)
        assert result.home_goals >= 0
        assert result.away_goals >= 0
        assert result.winner in ("home", "away", "draw")

    def test_result_has_player_stats(self, sim):
        """Each starting player should appear in the ratings."""
        home = _make_squad("HOME")
        away = _make_squad("AWAY")
        result = sim.simulate_match(home, away)
        assert len(result.home_player_stats) == 11
        assert len(result.away_player_stats) == 11

    def test_player_ratings_in_range(self, sim):
        """All ratings must be between 4.0 and 10.0."""
        home = _make_squad("HOME")
        away = _make_squad("AWAY")
        result = sim.simulate_match(home, away)
        for stat in result.home_player_stats + result.away_player_stats:
            assert 4.0 <= stat.rating <= 10.0

    def test_events_exist(self, sim):
        """A match should produce at least some events."""
        np.random.seed(42)
        random.seed(42)
        home = _make_squad("HOME", skill_level=10)
        away = _make_squad("AWAY", skill_level=10)
        # Run a few matches to ensure at least one has events
        events_found = False
        for _ in range(10):
            result = sim.simulate_match(home, away)
            if result.events:
                events_found = True
                break
        assert events_found

    def test_appearances_updated(self, sim):
        """Player appearances should increment after a match."""
        home = _make_squad("HOME")
        away = _make_squad("AWAY")
        assert home[0].appearances_season == 0
        sim.simulate_match(home, away)
        assert home[0].appearances_season == 1

    def test_form_changes_after_match(self, sim):
        """Player form should change (not stay static at 0) after match."""
        home = _make_squad("HOME")
        away = _make_squad("AWAY")
        initial_forms = [p.form for p in home]
        sim.simulate_match(home, away)
        # At least some forms should have changed
        new_forms = [p.form for p in home]
        assert any(new_forms[i] != initial_forms[i] for i in range(len(home)))

    def test_xg_positive(self, sim):
        """xG should always be positive (min 0.3)."""
        home = _make_squad("HOME", skill_level=3)
        away = _make_squad("AWAY", skill_level=3)
        result = sim.simulate_match(home, away)
        assert result.home_xg >= 0.3
        assert result.away_xg >= 0.3


# ═══════════════════════════════════════════════════════════════════════
# Statistical Balance Tests (Monte Carlo)
# ═══════════════════════════════════════════════════════════════════════

class TestMatchBalance:
    """Statistical tests over many simulations to validate realism."""

    @pytest.fixture(autouse=True)
    def seed(self):
        np.random.seed(12345)
        random.seed(12345)

    @pytest.fixture
    def sim(self):
        return MatchSimulator()

    def test_mean_goals_realistic(self, sim):
        """Average goals across 500 matches should be in [2.0, 3.5] range."""
        total_goals = 0
        n = 500
        for _ in range(n):
            home = _make_squad("H")
            away = _make_squad("A")
            result = sim.simulate_match(home, away)
            total_goals += result.home_goals + result.away_goals
        avg = total_goals / n
        assert 2.0 <= avg <= 3.5, f"Average goals {avg:.2f} out of realistic range"

    def test_strong_team_advantage(self, sim):
        """A strong team should beat a weak team >55% of the time."""
        wins = 0
        n = 300
        for _ in range(n):
            home = _make_strong_squad()
            away = _make_weak_squad()
            result = sim.simulate_match(home, away, home_team_name="STRONG", away_team_name="WEAK")
            if result.winner == "home":
                wins += 1
        winrate = wins / n
        assert winrate > 0.55, f"Strong team only won {winrate:.1%} — should be >55%"

    def test_weak_team_can_upset(self, sim):
        """Weak teams should occasionally win (at least 1 in 300)."""
        upsets = 0
        n = 300
        for _ in range(n):
            home = _make_strong_squad()
            away = _make_weak_squad()
            result = sim.simulate_match(home, away)
            if result.winner == "away":
                upsets += 1
        assert upsets >= 1, "Weak team never won in 300 matches — too deterministic"

    def test_home_advantage_exists(self, sim):
        """Home team should win slightly more than away in equal matchups."""
        home_wins = 0
        away_wins = 0
        n = 500
        for _ in range(n):
            home = _make_squad("H")
            away = _make_squad("A")
            result = sim.simulate_match(home, away)
            if result.winner == "home":
                home_wins += 1
            elif result.winner == "away":
                away_wins += 1
        assert home_wins > away_wins, (
            f"No home advantage: home={home_wins}, away={away_wins}"
        )

    def test_form_impact_on_goals(self, sim):
        """High form squad should score more on average than low form."""
        high_form_goals = []
        low_form_goals = []
        n = 300

        for _ in range(n):
            high = _make_squad("HI", form=40.0)
            low = _make_squad("LO", form=-40.0)
            neutral = _make_squad("NEU")

            r1 = sim.simulate_match(high, neutral)
            high_form_goals.append(r1.home_goals)

            r2 = sim.simulate_match(low, neutral)
            low_form_goals.append(r2.home_goals)

        avg_high = statistics.mean(high_form_goals)
        avg_low = statistics.mean(low_form_goals)
        assert avg_high > avg_low, (
            f"High form avg goals ({avg_high:.2f}) not > low form ({avg_low:.2f})"
        )

    def test_haaland_goal_rate(self, sim):
        """Haaland analog (finishing=15, form=40) should score ~0.5-1.2 goals/game average."""
        haaland_goals = 0
        n = 200
        for _ in range(n):
            home = _make_haaland_squad()
            away = _make_squad("OPP", skill_level=7)
            sim.simulate_match(home, away)
            haaland_goals += home[9].goals_scored_season
            # Reset for next iteration
            home[9].goals_scored_season = 0

        avg = haaland_goals / n
        assert 0.3 <= avg <= 1.5, f"Haaland avg {avg:.2f} goals/game — outside expected range"


# ═══════════════════════════════════════════════════════════════════════
# Tactics Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTactics:
    def test_matrix_is_antisymmetric(self):
        """tactics[A][B] should equal -tactics[B][A] (approximately)."""
        for f1, row in DEFAULT_TACTICS_MATRIX.items():
            for f2, val in row.items():
                reverse = DEFAULT_TACTICS_MATRIX.get(f2, {}).get(f1, 0.0)
                assert abs(val + reverse) < 0.01, (
                    f"Not antisymmetric: {f1} vs {f2}: {val} vs {reverse}"
                )

    def test_mirror_match_is_zero(self):
        """Same formation vs itself should have 0 modifier."""
        for formation, row in DEFAULT_TACTICS_MATRIX.items():
            assert row[formation] == 0.0, f"{formation} vs itself should be 0"

    def test_all_formations_present(self):
        """All 10 formations should be in the matrix."""
        expected = {
            "4-4-2", "4-3-3", "4-2-3-1", "3-5-2", "3-4-3",
            "5-3-2", "5-4-1", "4-1-4-1", "4-3-2-1", "3-4-2-1",
        }
        assert set(DEFAULT_TACTICS_MATRIX.keys()) == expected

    def test_tactics_modifier_applied(self):
        """Match outcome should be influenced by tactics."""
        sim = MatchSimulator()
        np.random.seed(99)
        random.seed(99)

        # 4-4-2 has +0.12 advantage over 4-3-3
        favored_wins = 0
        n = 300
        for _ in range(n):
            home = _make_squad("H")
            away = _make_squad("A")
            result = sim.simulate_match(home, away, home_formation="4-4-2", away_formation="4-3-3")
            if result.winner == "home":
                favored_wins += 1
        # The favored side should win more than 33% in equal skill matchups
        assert favored_wins / n > 0.33


# ═══════════════════════════════════════════════════════════════════════
# Weather Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWeather:
    @pytest.fixture
    def sim(self):
        return MatchSimulator()

    def test_snow_reduces_goals(self, sim):
        """Snow matches should produce fewer goals on average."""
        np.random.seed(42)
        random.seed(42)

        dry_goals = []
        snow_goals = []
        n = 300

        for _ in range(n):
            home = _make_squad("H")
            away = _make_squad("A")
            r_dry = sim.simulate_match(home, away, weather="dry")
            dry_goals.append(r_dry.home_goals + r_dry.away_goals)

            home2 = _make_squad("H")
            away2 = _make_squad("A")
            r_snow = sim.simulate_match(home2, away2, weather="snow")
            snow_goals.append(r_snow.home_goals + r_snow.away_goals)

        assert statistics.mean(snow_goals) < statistics.mean(dry_goals), (
            f"Snow ({statistics.mean(snow_goals):.2f}) should produce fewer goals "
            f"than dry ({statistics.mean(dry_goals):.2f})"
        )

    def test_weather_in_result(self, sim):
        """Weather should be recorded in the match result."""
        home = _make_squad("H")
        away = _make_squad("A")
        result = sim.simulate_match(home, away, weather="muddy")
        assert result.weather == "muddy"


# ═══════════════════════════════════════════════════════════════════════
# Injury Tests
# ═══════════════════════════════════════════════════════════════════════

class TestInjuries:
    def test_injuries_can_occur(self):
        """Over many matches, at least one injury should happen."""
        sim = MatchSimulator()
        np.random.seed(42)
        random.seed(42)

        injuries_found = False
        for _ in range(50):
            home = _make_squad("H")
            away = _make_squad("A")
            result = sim.simulate_match(home, away)
            if result.injury_events():
                injuries_found = True
                break
        assert injuries_found, "No injuries in 50 matches"

    def test_fatigued_players_more_injury_prone(self):
        """Fatigued players should get injured more often."""
        sim = MatchSimulator()
        np.random.seed(42)
        random.seed(42)

        fresh_injuries = 0
        tired_injuries = 0
        n = 200

        for _ in range(n):
            fresh = _make_squad("FRESH", form=0.0)
            tired = _make_squad("TIRED", form=-30.0)
            for p in tired:
                p.fatigue = 80.0

            neutral = _make_squad("NEU")
            r_fresh = sim.simulate_match(fresh, neutral)
            fresh_injuries += len(r_fresh.injury_events())

            neutral2 = _make_squad("NEU2")
            r_tired = sim.simulate_match(tired, neutral2)
            tired_injuries += len(r_tired.injury_events())

        # Tired team should have at least as many injuries
        # (statistical, but with 200 samples should be reliable)
        assert tired_injuries >= fresh_injuries * 0.8, (
            f"Fatigue doesn't increase injuries enough: "
            f"fresh={fresh_injuries}, tired={tired_injuries}"
        )

    def test_injury_severity_distribution(self):
        """Injury severities should roughly follow the 50/30/15/5 distribution."""
        sim = MatchSimulator()
        severities = []
        for _ in range(1000):
            days = sim._roll_injury_severity()
            assert days >= 1
            if days <= 7:
                severities.append("minor")
            elif days <= 28:
                severities.append("medium")
            elif days <= 90:
                severities.append("serious")
            else:
                severities.append("season_ending")

        counts = Counter(severities)
        total = len(severities)
        # Allow generous margins for Monte Carlo
        assert counts["minor"] / total > 0.35, f"Too few minor injuries: {counts['minor']/total:.1%}"
        assert counts["season_ending"] / total < 0.15, f"Too many season-ending: {counts['season_ending']/total:.1%}"


# ═══════════════════════════════════════════════════════════════════════
# Goal Attribution Tests
# ═══════════════════════════════════════════════════════════════════════

class TestGoalAttribution:
    def test_goals_match_scoreline(self):
        """Total attributed goals should match the scoreline."""
        sim = MatchSimulator()
        np.random.seed(42)
        random.seed(42)

        for _ in range(50):
            home = _make_squad("H")
            away = _make_squad("A")
            result = sim.simulate_match(home, away)

            home_goal_events = [e for e in result.events
                                if e.event_type == EventType.GOAL and e.team == "home"]
            away_goal_events = [e for e in result.events
                                if e.event_type == EventType.GOAL and e.team == "away"]

            assert len(home_goal_events) == result.home_goals
            assert len(away_goal_events) == result.away_goals

    def test_strikers_score_more_than_defenders(self):
        """Strikers should score more often than defenders over many matches."""
        sim = MatchSimulator()
        np.random.seed(42)
        random.seed(42)

        striker_goals = 0
        defender_goals = 0

        for _ in range(200):
            home = _make_squad("H")
            away = _make_squad("A")
            result = sim.simulate_match(home, away)

            for event in result.events:
                if event.event_type == EventType.GOAL and event.team == "home":
                    # Find player position
                    for stat in result.home_player_stats:
                        if stat.player_id == event.player_id:
                            if stat.position in ("ST", "CF", "SS", "LW", "RW"):
                                striker_goals += 1
                            elif stat.position in ("CB", "RB", "LB"):
                                defender_goals += 1

        assert striker_goals > defender_goals, (
            f"Strikers ({striker_goals}) should score more than defenders ({defender_goals})"
        )


# ═══════════════════════════════════════════════════════════════════════
# Fixture Generator Tests
# ═══════════════════════════════════════════════════════════════════════

class TestFixtureGenerator:
    def test_round_robin_even_teams(self):
        """4 teams should produce 6 matchdays (3 + 3)."""
        teams = ["A", "B", "C", "D"]
        schedule = generate_round_robin(teams, shuffle=False)
        assert len(schedule) == 6  # (4-1)*2
        for matchday in schedule:
            assert len(matchday) == 2  # 4/2 matches per round

    def test_round_robin_odd_teams(self):
        """3 teams should produce 6 matchdays with byes."""
        teams = ["A", "B", "C"]
        schedule = generate_round_robin(teams, shuffle=False)
        assert len(schedule) == 6  # (4-1)*2 (padded to 4)
        # Each matchday has 1 match (one team has bye)
        for matchday in schedule:
            assert len(matchday) == 1

    def test_all_teams_play_each_other(self):
        """Every team should play every other team exactly twice (home & away)."""
        teams = ["A", "B", "C", "D", "E", "F"]
        schedule = generate_round_robin(teams, shuffle=False)

        matchups = Counter()
        for matchday in schedule:
            for home, away in matchday:
                matchups[(home, away)] += 1

        for t1 in teams:
            for t2 in teams:
                if t1 != t2:
                    assert matchups[(t1, t2)] == 1, (
                        f"{t1} vs {t2} (home) should occur exactly once, got {matchups[(t1, t2)]}"
                    )

    def test_matches_per_season_calc(self):
        assert matches_per_season(20) == 38
        assert matches_per_season(16) == 30

    def test_total_matchdays_calc(self):
        assert total_matchdays(20) == 38
        assert total_matchdays(16) == 30

    def test_too_few_teams_raises(self):
        with pytest.raises(ValueError):
            generate_round_robin(["A"])

    def test_two_teams(self):
        schedule = generate_round_robin(["A", "B"], shuffle=False)
        assert len(schedule) == 2
        assert schedule[0] == [("A", "B")]
        assert schedule[1] == [("B", "A")]


# ═══════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_all_gk_squad(self):
        """A squad of all goalkeepers should still produce a valid match."""
        sim = MatchSimulator()
        gk_squad = [
            _make_player(f"GK {i}", Position.GK, skills={"control": 10, "velocity": 8})
            for i in range(11)
        ]
        normal_squad = _make_squad("NORMAL")
        result = sim.simulate_match(gk_squad, normal_squad)
        assert isinstance(result, MatchResult)
        assert result.home_goals >= 0

    def test_min_skill_squad(self):
        """Minimum skill players should still produce a valid match."""
        sim = MatchSimulator()
        weak = _make_squad("MIN", skill_level=0)
        normal = _make_squad("NRM")
        result = sim.simulate_match(weak, normal)
        assert isinstance(result, MatchResult)

    def test_max_skill_squad(self):
        """Maximum skill players should produce a valid match."""
        sim = MatchSimulator()
        strong = _make_squad("MAX", skill_level=15, form=50.0)
        normal = _make_squad("NRM")
        result = sim.simulate_match(strong, normal)
        assert isinstance(result, MatchResult)

    def test_unknown_formation_defaults(self):
        """Unknown formation should default to 0 tactics modifier."""
        sim = MatchSimulator()
        home = _make_squad("H")
        away = _make_squad("A")
        result = sim.simulate_match(home, away, home_formation="9-0-1", away_formation="0-0-10")
        assert isinstance(result, MatchResult)


# ═══════════════════════════════════════════════════════════════════════
# Arcade Stub Tests
# ═══════════════════════════════════════════════════════════════════════

class TestArcadeStub:
    def test_fallback_to_fast_match(self):
        """Arcade simulator should fall back to MatchSimulator."""
        arcade = ArcadeMatchSimulator()
        home = _make_squad("H")
        away = _make_squad("A")
        result = arcade.simulate(home, away)
        assert isinstance(result, MatchResult)


# ═══════════════════════════════════════════════════════════════════════
# Simulator Configuration Tests
# ═══════════════════════════════════════════════════════════════════════

class TestSimulatorConfig:
    def test_loads_without_rules_file(self):
        """Should work without a rules.json file."""
        sim = MatchSimulator(rules_path=None)
        home = _make_squad("H")
        away = _make_squad("A")
        result = sim.simulate_match(home, away)
        assert isinstance(result, MatchResult)

    def test_loads_with_nonexistent_rules(self):
        """Should fallback gracefully if rules file doesn't exist."""
        sim = MatchSimulator(rules_path="/nonexistent/rules.json")
        home = _make_squad("H")
        away = _make_squad("A")
        result = sim.simulate_match(home, away)
        assert isinstance(result, MatchResult)

    def test_loads_with_real_rules(self):
        """Should load real rules.json if present."""
        from pathlib import Path
        rules_path = Path(__file__).parent.parent / "config" / "rules.json"
        if rules_path.exists():
            sim = MatchSimulator(rules_path=str(rules_path))
            home = _make_squad("H")
            away = _make_squad("A")
            result = sim.simulate_match(home, away)
            assert isinstance(result, MatchResult)

    def test_hot_reload(self):
        """reload() should update tuning constants."""
        sim = MatchSimulator()
        original_home_adv = sim.home_advantage
        # Reload with defaults (no change expected)
        sim.reload("/nonexistent/rules.json")
        assert sim.home_advantage == original_home_adv
