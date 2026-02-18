"""Tests for the transfer market system."""

from __future__ import annotations

import random

import pytest

from swos420.engine.transfer_market import (
    TransferMarket,
    generate_free_agents,
    MIN_SQUAD_SIZE,
    MAX_SQUAD_SIZE,
)
from swos420.models.player import Position, Skills, SWOSPlayer, generate_base_id


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_player(
    name: str = "TEST PLAYER",
    club_code: str = "TST",
    skill_level: int = 8,
    age: int = 25,
    value: int = 5_000_000,
) -> SWOSPlayer:
    skills = {s: skill_level for s in
              ["passing", "velocity", "heading", "tackling", "control", "speed", "finishing"]}
    return SWOSPlayer(
        base_id=generate_base_id(f"{name}_{random.randint(1, 999999)}", "25/26"),
        full_name=name.title(),
        display_name=name.upper()[:15],
        position=Position.CM,
        skills=Skills(**skills),
        age=age,
        base_value=value,
        club_name=f"Club {club_code}",
        club_code=club_code,
    )


def _default_market() -> TransferMarket:
    """Market with 2 teams, reasonable budgets."""
    market = TransferMarket()
    market.open_window(
        team_budgets={"ARS": 50_000_000, "MCI": 80_000_000, "CHE": 30_000_000},
        team_squad_sizes={"ARS": 22, "MCI": 20, "CHE": 25},
    )
    return market


# ═══════════════════════════════════════════════════════════════════════
# TransferMarket Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTransferListing:
    def test_list_player(self):
        market = _default_market()
        player = _make_player("TARGET", club_code="ARS")
        assert market.list_player("ARS", player, reserve_price=3_000_000)
        assert len(market.available_players) == 1

    def test_list_sets_default_reserve(self):
        market = _default_market()
        player = _make_player("TARGET", club_code="ARS", value=10_000_000)
        market.list_player("ARS", player)
        listing = market.get_listing(player.base_id)
        assert listing is not None
        # Default reserve = 80% of current value
        assert listing.reserve_price > 0

    def test_cannot_list_when_closed(self):
        market = TransferMarket()
        player = _make_player()
        assert not market.list_player("ARS", player)

    def test_cannot_list_duplicate(self):
        market = _default_market()
        player = _make_player("TARGET", club_code="ARS")
        assert market.list_player("ARS", player)
        assert not market.list_player("ARS", player)

    def test_cannot_list_at_min_squad(self):
        market = TransferMarket()
        market.open_window(
            team_budgets={"ARS": 50_000_000},
            team_squad_sizes={"ARS": MIN_SQUAD_SIZE},  # Already at minimum
        )
        player = _make_player("TARGET", club_code="ARS")
        assert not market.list_player("ARS", player)


class TestBidding:
    def test_place_valid_bid(self):
        market = _default_market()
        player = _make_player("TARGET", club_code="ARS")
        market.list_player("ARS", player, reserve_price=3_000_000)
        assert market.place_bid("MCI", player.base_id, 4_000_000)

    def test_cannot_bid_when_closed(self):
        market = TransferMarket()
        assert not market.place_bid("MCI", "fake_id", 1_000_000)

    def test_cannot_bid_on_unlisted(self):
        market = _default_market()
        assert not market.place_bid("MCI", "nonexistent_id", 1_000_000)

    def test_cannot_bid_on_own_player(self):
        market = _default_market()
        player = _make_player("TARGET", club_code="ARS")
        market.list_player("ARS", player, reserve_price=3_000_000)
        assert not market.place_bid("ARS", player.base_id, 4_000_000)

    def test_cannot_bid_over_budget(self):
        market = _default_market()
        player = _make_player("TARGET", club_code="ARS")
        market.list_player("ARS", player, reserve_price=3_000_000)
        # CHE has 30M budget
        assert not market.place_bid("CHE", player.base_id, 100_000_000)

    def test_cannot_bid_when_squad_full(self):
        market = TransferMarket()
        market.open_window(
            team_budgets={"ARS": 50_000_000, "MCI": 50_000_000},
            team_squad_sizes={"ARS": 22, "MCI": MAX_SQUAD_SIZE},
        )
        player = _make_player("TARGET", club_code="ARS")
        market.list_player("ARS", player, reserve_price=1_000_000)
        assert not market.place_bid("MCI", player.base_id, 2_000_000)


class TestResolution:
    def test_highest_bid_wins(self):
        market = _default_market()
        player = _make_player("STAR", club_code="ARS")
        market.list_player("ARS", player, reserve_price=3_000_000)
        market.place_bid("MCI", player.base_id, 5_000_000)
        market.place_bid("CHE", player.base_id, 4_000_000)

        results = market.resolve_window()
        assert len(results) == 1
        result = results[0]
        assert result.success
        assert result.to_club == "MCI"
        assert result.fee == 5_000_000

    def test_below_reserve_fails(self):
        market = _default_market()
        player = _make_player("STAR", club_code="ARS")
        market.list_player("ARS", player, reserve_price=10_000_000)
        market.place_bid("MCI", player.base_id, 2_000_000)  # Way below reserve

        results = market.resolve_window()
        assert len(results) == 1
        assert not results[0].success

    def test_no_bids_fails(self):
        market = _default_market()
        player = _make_player("UNWANTED", club_code="ARS")
        market.list_player("ARS", player, reserve_price=1_000_000)

        results = market.resolve_window()
        assert len(results) == 1
        assert not results[0].success
        assert "No bids" in results[0].reason

    def test_budget_updated_after_transfer(self):
        market = _default_market()
        player = _make_player("STAR", club_code="ARS")
        market.list_player("ARS", player, reserve_price=3_000_000)
        market.place_bid("MCI", player.base_id, 5_000_000)

        market.resolve_window()
        # MCI spent 5M from 80M budget
        assert market._team_budgets["MCI"] == 75_000_000
        # ARS received 5M on top of 50M
        assert market._team_budgets["ARS"] == 55_000_000

    def test_squad_sizes_updated(self):
        market = _default_market()
        player = _make_player("STAR", club_code="ARS")
        market.list_player("ARS", player, reserve_price=3_000_000)
        market.place_bid("MCI", player.base_id, 5_000_000)

        market.resolve_window()
        assert market._team_squad_sizes["MCI"] == 21  # was 20
        assert market._team_squad_sizes["ARS"] == 21  # was 22

    def test_window_closes_after_resolve(self):
        market = _default_market()
        market.resolve_window()
        assert not market.is_open

    def test_multiple_transfers_in_one_window(self):
        market = _default_market()
        p1 = _make_player("PLAYER1", club_code="ARS")
        p2 = _make_player("PLAYER2", club_code="CHE")
        market.list_player("ARS", p1, reserve_price=2_000_000)
        market.list_player("CHE", p2, reserve_price=1_000_000)

        market.place_bid("MCI", p1.base_id, 3_000_000)
        market.place_bid("MCI", p2.base_id, 2_000_000)

        results = market.resolve_window()
        successful = [r for r in results if r.success]
        assert len(successful) == 2


class TestFreeAgents:
    def test_generates_correct_count(self):
        agents = generate_free_agents(n=5)
        assert len(agents) == 5

    def test_free_agents_have_no_club(self):
        agents = generate_free_agents(n=3)
        for agent in agents:
            assert agent.club_name == "Free Agent"
            assert agent.club_code == "FA"

    def test_skills_in_range(self):
        agents = generate_free_agents(n=10, skill_range=(3, 10))
        for agent in agents:
            for s in ["passing", "velocity", "heading", "tackling",
                      "control", "speed", "finishing"]:
                # Youth might get +1-3 bonus, so upper bound is 13
                assert 0 <= getattr(agent.skills, s) <= 15

    def test_ages_in_range(self):
        agents = generate_free_agents(n=20, age_range=(20, 30))
        for agent in agents:
            assert 20 <= agent.age <= 30
