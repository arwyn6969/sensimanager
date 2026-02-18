"""Action space definitions and masking for AI managers.

Defines the multi-component action space: formation, style, training focus,
transfers, substitutions, and scouting. Provides action masking to prevent
invalid actions (e.g., transfers outside windows, subs with unavailable players).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Available formations (index → formation string)
FORMATIONS = [
    "4-4-2", "4-3-3", "4-2-3-1", "3-5-2", "3-4-3",
    "5-3-2", "5-4-1", "4-1-4-1", "4-3-2-1", "3-4-2-1",
]

# Playing styles
STYLES = ["attacking", "defensive", "balanced", "counter"]

# Training focus options
TRAINING_FOCUS = ["attack", "defence", "stamina", "set_pieces", "rest", "youth"]


@dataclass
class ManagerAction:
    """Decoded action from an AI manager for one matchday.

    This is the human-readable action after decoding from the raw
    action vector the RL agent produces.
    """
    formation: str = "4-4-2"
    style: str = "balanced"
    training_focus: str = "rest"

    # Transfer bids: list of (target_player_id, bid_amount)
    transfer_bids: list[tuple[str, int]] = None  # type: ignore

    # Substitutions: list of (bench_player_id) to swap in for weakest starter
    substitutions: list[str] = None  # type: ignore

    # Scouting spend tier (0-3)
    scouting_level: int = 0

    def __post_init__(self):
        if self.transfer_bids is None:
            self.transfer_bids = []
        if self.substitutions is None:
            self.substitutions = []


def decode_action(
    raw_action: dict[str, int | float | np.ndarray],
    available_targets: list[str] | None = None,
    bench_player_ids: list[str] | None = None,
    transfer_budget: int = 0,
    is_transfer_window: bool = False,
) -> ManagerAction:
    """Decode a raw action dict from the RL agent into a ManagerAction.

    Args:
        raw_action: Dict with keys matching the action space.
        available_targets: List of player IDs available for transfer bids.
        bench_player_ids: List of bench player IDs available for substitution.
        transfer_budget: Current transfer budget for bid amount scaling.
        is_transfer_window: Whether transfers are currently allowed.

    Returns:
        Decoded ManagerAction.
    """
    formation_idx = int(raw_action.get("formation", 0)) % len(FORMATIONS)
    style_idx = int(raw_action.get("style", 2)) % len(STYLES)
    training_idx = int(raw_action.get("training_focus", 4)) % len(TRAINING_FOCUS)
    scouting = int(raw_action.get("scouting_level", 0)) % 4

    action = ManagerAction(
        formation=FORMATIONS[formation_idx],
        style=STYLES[style_idx],
        training_focus=TRAINING_FOCUS[training_idx],
        scouting_level=scouting,
    )

    # Decode transfer bids (only during windows)
    if is_transfer_window and available_targets:
        for i in range(3):
            target_key = f"transfer_bid_{i}"
            amount_key = f"bid_amount_{i}"
            target_idx = int(raw_action.get(target_key, 0))
            bid_frac = float(raw_action.get(amount_key, 0.0))

            # 0 = no bid, 1..N = target player index
            if target_idx > 0 and target_idx <= len(available_targets):
                player_id = available_targets[target_idx - 1]
                bid_amount = max(25_000, int(bid_frac * transfer_budget))
                action.transfer_bids.append((player_id, bid_amount))

    # Decode substitutions
    if bench_player_ids:
        for i in range(3):
            sub_key = f"sub_{i}"
            sub_idx = int(raw_action.get(sub_key, 0))
            if sub_idx > 0 and sub_idx <= len(bench_player_ids):
                action.substitutions.append(bench_player_ids[sub_idx - 1])

    return action


def build_action_mask(
    num_targets: int = 0,
    num_bench: int = 0,
    is_transfer_window: bool = False,
    budget: int = 0,
) -> dict[str, np.ndarray]:
    """Build action masks for invalid actions.

    Returns:
        Dict of boolean masks (True = valid action) for each action component.
    """
    masks = {
        "formation": np.ones(len(FORMATIONS), dtype=np.int8),
        "style": np.ones(len(STYLES), dtype=np.int8),
        "training_focus": np.ones(len(TRAINING_FOCUS), dtype=np.int8),
        "scouting_level": np.ones(4, dtype=np.int8),
    }

    # Transfer masks: only valid during windows with budget
    for i in range(3):
        size = num_targets + 1  # +1 for "no bid" option
        mask = np.zeros(size, dtype=np.int8)
        mask[0] = 1  # "No bid" always valid
        if is_transfer_window and budget > 0:
            mask[1:] = 1  # All targets valid if window is open
        masks[f"transfer_bid_{i}"] = mask

    # Substitution masks
    for i in range(3):
        size = num_bench + 1  # +1 for "no sub" option
        mask = np.ones(size, dtype=np.int8)  # All bench players valid subs
        masks[f"sub_{i}"] = mask

    return masks
