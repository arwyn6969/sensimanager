"""Tests for the SWOS420 Stadium Ad Hoarding Manager."""

import json
import time

import pytest

from swos420.engine.ad_manager import (
    AdManager,
    ClubHoardings,
    HoardingSlot,
)


@pytest.fixture
def ad_manager(tmp_path):
    """Create an AdManager with a temp streaming directory."""
    return AdManager(streaming_dir=tmp_path, cache_path=tmp_path / "cache.json")


@pytest.fixture
def tranmere_slot():
    """Create a sample Tranmere Rovers hoarding slot."""
    return HoardingSlot(
        slot_id=100,
        club_id=1,
        position=0,
        content_uri="ar://abc123/swa_hoarding.svg",
        brand_name="Super White Army",
        brand_address="0x1234567890abcdef",
        expires_at=int(time.time()) + 30 * 86400,  # 30 days from now
        paid_amount_wei=1_000_000_000_000_000,  # 0.001 ETH
        is_active=True,
    )


class TestHoardingSlot:
    """Tests for the HoardingSlot dataclass."""

    def test_active_slot_not_expired(self, tranmere_slot):
        assert not tranmere_slot.is_expired

    def test_expired_slot(self):
        slot = HoardingSlot(
            slot_id=200,
            club_id=2,
            position=0,
            content_uri="ar://expired",
            expires_at=int(time.time()) - 86400,  # yesterday
        )
        assert slot.is_expired

    def test_days_remaining(self, tranmere_slot):
        assert 28 <= tranmere_slot.days_remaining <= 30

    def test_days_remaining_expired(self):
        slot = HoardingSlot(
            slot_id=200,
            club_id=2,
            position=0,
            content_uri="ar://expired",
            expires_at=int(time.time()) - 86400,
        )
        assert slot.days_remaining == 0


class TestClubHoardings:
    """Tests for the ClubHoardings dataclass."""

    def test_active_slots(self, tranmere_slot):
        club = ClubHoardings(
            club_id=1,
            club_name="Tranmere Rovers",
            club_code="TRN",
            tier=2,
            max_slots=16,
            slots=[tranmere_slot],
        )
        assert len(club.active_slots) == 1

    def test_available_positions(self, tranmere_slot):
        club = ClubHoardings(
            club_id=1,
            club_name="Tranmere Rovers",
            club_code="TRN",
            max_slots=4,
            slots=[tranmere_slot],
        )
        assert 0 not in club.available_positions
        assert 1 in club.available_positions
        assert len(club.available_positions) == 3

    def test_occupancy_rate(self, tranmere_slot):
        club = ClubHoardings(
            club_id=1,
            club_name="Tranmere Rovers",
            club_code="TRN",
            max_slots=10,
            slots=[tranmere_slot],
        )
        assert club.occupancy_rate == pytest.approx(0.1)


class TestAdManager:
    """Tests for the AdManager class."""

    def test_register_club(self, ad_manager):
        club = ad_manager.register_club(1, "Tranmere Rovers", "TRN", tier=2, max_slots=16)
        assert club.club_id == 1
        assert club.club_name == "Tranmere Rovers"
        assert club.tier == 2
        assert club.max_slots == 16
        assert 1 in ad_manager.clubs

    def test_add_slot(self, ad_manager, tranmere_slot):
        ad_manager.register_club(1, "Tranmere Rovers", "TRN")
        ad_manager.add_slot(tranmere_slot)
        active = ad_manager.get_active_slots(1)
        assert len(active) == 1
        assert active[0].brand_name == "Super White Army"

    def test_add_slot_unregistered_club(self, ad_manager, tranmere_slot):
        ad_manager.add_slot(tranmere_slot)  # no club registered
        assert len(ad_manager.clubs) == 0

    def test_remove_expired(self, ad_manager):
        ad_manager.register_club(1, "Tranmere Rovers", "TRN")
        expired = HoardingSlot(
            slot_id=100, club_id=1, position=0,
            content_uri="ar://old",
            expires_at=int(time.time()) - 86400,
        )
        ad_manager.clubs[1].slots.append(expired)
        removed = ad_manager.remove_expired()
        assert removed == 1
        assert len(ad_manager.get_active_slots(1)) == 0

    def test_render_hoardings(self, ad_manager, tranmere_slot, tmp_path):
        ad_manager.register_club(1, "Tranmere Rovers", "TRN", tier=2)
        ad_manager.add_slot(tranmere_slot)
        result = ad_manager.render_hoardings(1)
        assert result["club_name"] == "Tranmere Rovers"
        assert result["active_count"] == 1
        assert len(result["hoardings"]) == 1
        assert result["hoardings"][0]["brand_name"] == "Super White Army"

        # Check file was written
        json_path = tmp_path / "hoardings.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["club_code"] == "TRN"

    def test_update_demand(self, ad_manager):
        factor = ad_manager.update_demand(viewer_count=5000)
        assert factor == pytest.approx(1.8)

    def test_update_demand_zero_viewers(self, ad_manager):
        factor = ad_manager.update_demand(viewer_count=0)
        assert factor == pytest.approx(1.0)

    def test_calculate_price_league_two(self, ad_manager):
        ad_manager.register_club(1, "Tranmere Rovers", "TRN", tier=1)
        ad_manager.update_demand(0)
        price_7d = ad_manager.calculate_price(1, 7)
        price_30d = ad_manager.calculate_price(1, 30)
        assert price_7d > 0
        assert price_30d > price_7d

    def test_calculate_price_tier_scaling(self, ad_manager):
        ad_manager.register_club(1, "Lower Club", "LOW", tier=1)
        ad_manager.register_club(2, "Top Club", "TOP", tier=4)
        ad_manager.update_demand(0)
        price_low = ad_manager.calculate_price(1, 30)
        price_top = ad_manager.calculate_price(2, 30)
        assert price_top > price_low * 3  # Tier 4 should be ~4x tier 1

    def test_get_sponsor_mention(self, ad_manager, tranmere_slot):
        ad_manager.register_club(1, "Tranmere Rovers", "TRN")
        ad_manager.add_slot(tranmere_slot)
        mention = ad_manager.get_sponsor_mention(1, "goal")
        assert mention is not None
        assert "Super White Army" in mention

    def test_get_sponsor_mention_no_sponsors(self, ad_manager):
        ad_manager.register_club(1, "Tranmere Rovers", "TRN")
        mention = ad_manager.get_sponsor_mention(1, "goal")
        assert mention is None

    def test_revenue_report(self, ad_manager, tranmere_slot):
        ad_manager.register_club(1, "Tranmere Rovers", "TRN", tier=2, max_slots=16)
        ad_manager.add_slot(tranmere_slot)
        report = ad_manager.get_revenue_report()
        assert report["total_clubs"] == 1
        assert report["total_active_slots"] == 1
        assert "Tranmere Rovers" in report["clubs"][0]["club_name"]

    def test_cache_persistence(self, ad_manager, tranmere_slot, tmp_path):
        ad_manager.register_club(1, "Tranmere Rovers", "TRN", tier=2)
        ad_manager.add_slot(tranmere_slot)
        ad_manager.update_demand(2500)
        ad_manager.save_cache()

        # Load into a new manager
        new_mgr = AdManager(streaming_dir=tmp_path, cache_path=tmp_path / "cache.json")
        assert 1 in new_mgr.clubs
        assert new_mgr.clubs[1].club_name == "Tranmere Rovers"
        assert len(new_mgr.get_active_slots(1)) == 1
        assert new_mgr.viewer_count == 2500

    def test_get_all_sponsor_names(self, ad_manager, tranmere_slot):
        ad_manager.register_club(1, "Tranmere Rovers", "TRN")
        ad_manager.add_slot(tranmere_slot)
        slot2 = HoardingSlot(
            slot_id=101, club_id=1, position=1,
            content_uri="ar://xyz", brand_name="Prenton Park FC",
            expires_at=int(time.time()) + 7 * 86400,
        )
        ad_manager.add_slot(slot2)
        names = ad_manager.get_all_sponsor_names(1)
        assert "Super White Army" in names
        assert "Prenton Park FC" in names
