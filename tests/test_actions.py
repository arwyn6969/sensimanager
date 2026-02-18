"""Tests for the AI manager action space — decode_action and build_action_mask."""

from __future__ import annotations

import numpy as np

from swos420.ai.actions import (
    FORMATIONS,
    STYLES,
    TRAINING_FOCUS,
    ManagerAction,
    build_action_mask,
    decode_action,
)


class TestManagerAction:
    def test_defaults(self):
        action = ManagerAction()
        assert action.formation == "4-4-2"
        assert action.style == "balanced"
        assert action.training_focus == "rest"
        assert action.transfer_bids == []
        assert action.substitutions == []
        assert action.scouting_level == 0

    def test_post_init_none_lists(self):
        """Ensure None lists are converted to empty lists."""
        action = ManagerAction(transfer_bids=None, substitutions=None)
        assert action.transfer_bids == []
        assert action.substitutions == []


class TestDecodeAction:
    def test_basic_decode(self):
        raw = {"formation": 1, "style": 0, "training_focus": 2, "scouting_level": 1}
        action = decode_action(raw)
        assert action.formation == FORMATIONS[1]
        assert action.style == STYLES[0]
        assert action.training_focus == TRAINING_FOCUS[2]
        assert action.scouting_level == 1

    def test_wrapping_indices(self):
        """Out-of-range indices should wrap via modulo."""
        raw = {"formation": len(FORMATIONS) + 2, "style": len(STYLES) + 1}
        action = decode_action(raw)
        assert action.formation == FORMATIONS[2]
        assert action.style == STYLES[1]

    def test_empty_raw_action_uses_defaults(self):
        action = decode_action({})
        assert action.formation == FORMATIONS[0]
        assert action.style == STYLES[2]  # default index 2 = balanced
        assert action.training_focus == TRAINING_FOCUS[4]  # default 4 = rest

    def test_transfer_bids_outside_window(self):
        """No bids should be decoded outside the transfer window."""
        raw = {
            "transfer_bid_0": 1, "bid_amount_0": 0.5,
            "transfer_bid_1": 2, "bid_amount_1": 0.3,
        }
        action = decode_action(
            raw,
            available_targets=["p1", "p2", "p3"],
            transfer_budget=10_000_000,
            is_transfer_window=False,
        )
        assert action.transfer_bids == []

    def test_transfer_bids_during_window(self):
        """Valid bids should be decoded during transfer window."""
        raw = {
            "transfer_bid_0": 1, "bid_amount_0": 0.5,
            "transfer_bid_1": 2, "bid_amount_1": 0.3,
            "transfer_bid_2": 0, "bid_amount_2": 0.0,  # no bid
        }
        action = decode_action(
            raw,
            available_targets=["p1", "p2", "p3"],
            transfer_budget=10_000_000,
            is_transfer_window=True,
        )
        assert len(action.transfer_bids) == 2
        assert action.transfer_bids[0][0] == "p1"
        assert action.transfer_bids[0][1] == 5_000_000  # 0.5 * 10M
        assert action.transfer_bids[1][0] == "p2"
        assert action.transfer_bids[1][1] == 3_000_000  # 0.3 * 10M

    def test_transfer_bid_minimum_amount(self):
        """Bid amount should be at least 25,000."""
        raw = {"transfer_bid_0": 1, "bid_amount_0": 0.0}
        action = decode_action(
            raw,
            available_targets=["p1"],
            transfer_budget=10_000,  # 0.0 * 10K = 0 → clamped to 25K
            is_transfer_window=True,
        )
        assert len(action.transfer_bids) == 1
        assert action.transfer_bids[0][1] == 25_000

    def test_transfer_bid_out_of_range_target(self):
        """Target index beyond available targets should be skipped."""
        raw = {"transfer_bid_0": 5, "bid_amount_0": 0.5}
        action = decode_action(
            raw,
            available_targets=["p1", "p2"],
            transfer_budget=10_000_000,
            is_transfer_window=True,
        )
        assert action.transfer_bids == []

    def test_substitutions(self):
        raw = {"sub_0": 1, "sub_1": 2, "sub_2": 0}
        action = decode_action(raw, bench_player_ids=["b1", "b2", "b3"])
        assert len(action.substitutions) == 2
        assert action.substitutions[0] == "b1"
        assert action.substitutions[1] == "b2"

    def test_substitutions_out_of_range(self):
        raw = {"sub_0": 5}
        action = decode_action(raw, bench_player_ids=["b1"])
        assert action.substitutions == []

    def test_no_bench_no_subs(self):
        raw = {"sub_0": 1}
        action = decode_action(raw, bench_player_ids=None)
        assert action.substitutions == []


class TestBuildActionMask:
    def test_all_base_masks_all_valid(self):
        masks = build_action_mask()
        assert np.all(masks["formation"] == 1)
        assert masks["formation"].shape == (len(FORMATIONS),)
        assert np.all(masks["style"] == 1)
        assert np.all(masks["training_focus"] == 1)
        assert np.all(masks["scouting_level"] == 1)

    def test_transfer_masks_closed_window(self):
        masks = build_action_mask(num_targets=5, is_transfer_window=False, budget=1_000_000)
        for i in range(3):
            mask = masks[f"transfer_bid_{i}"]
            assert mask.shape == (6,)  # 5 targets + 1 "no bid"
            assert mask[0] == 1  # "No bid" always valid
            assert np.all(mask[1:] == 0)  # All targets invalid

    def test_transfer_masks_open_window(self):
        masks = build_action_mask(num_targets=3, is_transfer_window=True, budget=1_000_000)
        for i in range(3):
            mask = masks[f"transfer_bid_{i}"]
            assert mask.shape == (4,)
            assert np.all(mask == 1)  # All valid

    def test_transfer_masks_no_budget(self):
        masks = build_action_mask(num_targets=3, is_transfer_window=True, budget=0)
        for i in range(3):
            mask = masks[f"transfer_bid_{i}"]
            assert mask[0] == 1  # "No bid" valid
            assert np.all(mask[1:] == 0)  # Can't bid with no budget

    def test_sub_masks(self):
        masks = build_action_mask(num_bench=5)
        for i in range(3):
            mask = masks[f"sub_{i}"]
            assert mask.shape == (6,)  # 5 bench + 1 "no sub"
            assert np.all(mask == 1)  # All bench subs valid
