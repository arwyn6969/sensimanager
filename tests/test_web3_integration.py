"""Tests for web3 NFT integration — mint, wages, metadata, base_id conversion.

These tests validate the Python-side logic WITHOUT requiring a live blockchain.
All web3 calls are tested via the script's utility functions.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swos420.models.player import Skills, SWOSPlayer, Position


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_players():
    """Create a set of test players with varying attributes."""
    return [
        SWOSPlayer(
            base_id="abcdef1234567890",
            full_name="Erling Haaland",
            display_name="HAALAND",
            position=Position.ST,
            club_name="Manchester City",
            skills=Skills(passing=4, velocity=6, heading=6, tackling=2,
                          control=5, speed=6, finishing=7),
            age=25,
            base_value=15_000_000,
            form=20.0,
            goals_scored_season=25,
        ),
        SWOSPlayer(
            base_id="1234567890abcdef",
            full_name="Virgil van Dijk",
            display_name="VAN DIJK",
            position=Position.CB,
            club_name="Liverpool",
            skills=Skills(passing=5, velocity=3, heading=7, tackling=7,
                          control=4, speed=4, finishing=1),
            age=32,
            base_value=10_000_000,
            form=-5.0,
        ),
        SWOSPlayer(
            base_id="fedcba0987654321",
            full_name="Lamine Yamal",
            display_name="YAMAL",
            position=Position.RW,
            club_name="Barcelona",
            skills=Skills(passing=6, velocity=5, heading=2, tackling=2,
                          control=6, speed=7, finishing=5),
            age=18,
            base_value=8_000_000,
            form=30.0,
        ),
    ]


# ── base_id → uint256 conversion ────────────────────────────────────────


class TestBaseIdConversion:
    """Test the base_id hex string → uint256 token ID conversion."""

    def test_known_conversion(self):
        """abcdef1234567890 should convert to a known integer."""
        from scripts.mint_from_db import base_id_to_uint256

        result = base_id_to_uint256("abcdef1234567890")
        expected = int("abcdef1234567890", 16)
        assert result == expected
        assert result == 0xABCDEF1234567890

    def test_zero_id(self):
        from scripts.mint_from_db import base_id_to_uint256
        assert base_id_to_uint256("0000000000000000") == 0

    def test_max_16_hex(self):
        from scripts.mint_from_db import base_id_to_uint256
        result = base_id_to_uint256("ffffffffffffffff")
        assert result == 0xFFFFFFFFFFFFFFFF

    def test_consistency(self, sample_players):
        """All player base_ids should produce unique uint256 token IDs."""
        from scripts.mint_from_db import base_id_to_uint256

        ids = [base_id_to_uint256(p.base_id) for p in sample_players]
        assert len(set(ids)) == len(ids), "Token IDs must be unique"

    def test_deterministic(self):
        """Same base_id should always produce same token ID."""
        from scripts.mint_from_db import base_id_to_uint256

        id1 = base_id_to_uint256("abcdef1234567890")
        id2 = base_id_to_uint256("abcdef1234567890")
        assert id1 == id2


# ── NFT Metadata ─────────────────────────────────────────────────────────


class TestNFTMetadata:
    """Test that to_nft_metadata() produces ERC-721 compatible output."""

    def test_metadata_has_required_fields(self, sample_players):
        """ERC-721 metadata must have name, description, image, attributes."""
        for player in sample_players:
            meta = player.to_nft_metadata()
            assert "name" in meta
            assert "description" in meta
            assert "image" in meta
            assert "attributes" in meta

    def test_metadata_name_matches(self, sample_players):
        meta = sample_players[0].to_nft_metadata()
        assert meta["name"] == "Erling Haaland"

    def test_metadata_has_skill_attributes(self, sample_players):
        meta = sample_players[0].to_nft_metadata()
        attr_types = {a["trait_type"] for a in meta["attributes"]}
        # Should have all 7 skill abbreviations
        for abbrev in ["PA", "VE", "HE", "TA", "CO", "SP", "FI"]:
            assert abbrev in attr_types, f"Missing skill attribute: {abbrev}"

    def test_metadata_has_economy_attributes(self, sample_players):
        meta = sample_players[0].to_nft_metadata()
        attr_types = {a["trait_type"] for a in meta["attributes"]}
        assert "Market Value" in attr_types
        assert "Weekly Wage" in attr_types
        assert "Form" in attr_types

    def test_metadata_json_serializable(self, sample_players):
        """Metadata must be JSON-serializable for IPFS upload."""
        for player in sample_players:
            meta = player.to_nft_metadata()
            json_str = json.dumps(meta)
            assert len(json_str) > 0
            # Round-trip should preserve structure
            parsed = json.loads(json_str)
            assert parsed["name"] == player.full_name


# ── Metadata Export ──────────────────────────────────────────────────────


class TestMetadataExport:
    """Test the metadata file export function."""

    def test_export_creates_files(self, sample_players):
        from scripts.mint_from_db import export_metadata

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "metadata"
            records = export_metadata(sample_players, output_dir)

            assert len(records) == 3
            for r in records:
                meta_path = Path(r["metadata_path"])
                assert meta_path.exists()
                with open(meta_path) as f:
                    data = json.load(f)
                assert "name" in data
                assert "token_id" in data

    def test_export_records_have_token_ids(self, sample_players):
        from scripts.mint_from_db import export_metadata

        with tempfile.TemporaryDirectory() as tmpdir:
            records = export_metadata(sample_players, Path(tmpdir))
            for r in records:
                assert r["token_id"] > 0
                assert len(r["base_id"]) == 16


# ── Wage Calculation ─────────────────────────────────────────────────────


class TestWageCalculation:
    """Test the wage calculation and split logic."""

    def test_wage_splits_sum_to_total(self, sample_players):
        from scripts.distribute_wages import calculate_wages

        economy = {
            "nft_owner_share": 0.90,
            "burn_share": 0.05,
            "treasury_share": 0.05,
            "league_multipliers": {"default": 1.0},
        }

        records = calculate_wages(sample_players, economy)
        for r in records:
            # Owner + burn + treasury should approximately equal total
            parts = r["wage_owner"] + r["wage_burn"] + r["wage_treasury"]
            assert parts == r["wage_total"], (
                f"Splits don't sum to total for {r['name']}: "
                f"{parts} != {r['wage_total']}"
            )

    def test_injured_players_excluded(self, sample_players):
        from scripts.distribute_wages import calculate_wages

        # Injure the first player
        sample_players[0].injury_days = 14

        economy = {
            "nft_owner_share": 0.90,
            "burn_share": 0.05,
            "treasury_share": 0.05,
            "league_multipliers": {"default": 1.0},
        }

        records = calculate_wages(sample_players, economy)
        names = [r["name"] for r in records]
        assert "Erling Haaland" not in names

    def test_wage_owner_share_is_90_percent(self, sample_players):
        from scripts.distribute_wages import calculate_wages

        economy = {
            "nft_owner_share": 0.90,
            "burn_share": 0.05,
            "treasury_share": 0.05,
            "league_multipliers": {"default": 1.0},
        }

        records = calculate_wages(sample_players, economy)
        for r in records:
            expected_owner = int(r["wage_total"] * 0.90)
            assert r["wage_owner"] == expected_owner

    def test_wages_are_in_wei(self, sample_players):
        """Wages should be scaled to 18 decimals (wei)."""
        from scripts.distribute_wages import calculate_wages

        economy = {
            "nft_owner_share": 0.90,
            "burn_share": 0.05,
            "treasury_share": 0.05,
            "league_multipliers": {"default": 1.0},
        }

        records = calculate_wages(sample_players, economy)
        for r in records:
            # Minimum wage is £5,000 → 5000 * 10^18 wei
            assert r["wage_total"] >= 5_000 * 10**18
