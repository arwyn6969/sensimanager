"""Shared policy I/O contract for watch-first manager tooling.

The manager training lane is currently kept deliberately narrow: formation,
style, and training are the live decision surfaces, while transfer/scouting/
substitution intelligence remains parked. This module centralizes the
observation/action wire contract used by training, evaluation, and benchmarking
so those tools cannot silently drift apart.
"""

from __future__ import annotations

from typing import Any

from gymnasium import spaces
import numpy as np

LEAGUE_TABLE_FEATURES = 6
PLAYER_FEATURES = 12
FINANCE_FEATURES = 4
META_FEATURES = 4
MAX_SQUAD_OBS_PLAYERS = 16
FLAT_ACTION_COMPONENTS = 13


class PolicyContractError(RuntimeError):
    """Raised when a policy checkpoint does not match the expected env contract."""


def expected_observation_size(
    num_teams: int,
    *,
    max_players: int = MAX_SQUAD_OBS_PLAYERS,
) -> int:
    """Return the flattened observation length for the shared manager contract."""
    return (
        num_teams * LEAGUE_TABLE_FEATURES
        + max_players * PLAYER_FEATURES
        + FINANCE_FEATURES
        + META_FEATURES
    )


def flatten_observation(observation: dict[str, np.ndarray]) -> np.ndarray:
    """Flatten a manager Dict observation into a 1D float32 vector."""
    parts = [
        observation["league_table"].flatten(),
        observation["own_squad"].flatten(),
        observation["finances"].flatten(),
        observation["meta"].flatten(),
    ]
    return np.concatenate(parts).astype(np.float32)


def decode_flat_action(
    flat_action: np.ndarray | list[int] | tuple[int, ...],
) -> dict[str, Any]:
    """Convert a flattened MultiDiscrete action into the manager env payload."""
    action_array = np.asarray(flat_action, dtype=np.int64).reshape(-1)
    if action_array.size != FLAT_ACTION_COMPONENTS:
        raise PolicyContractError(
            f"Expected {FLAT_ACTION_COMPONENTS} action components, got {action_array.size}"
        )

    return {
        "formation": int(action_array[0]),
        "style": int(action_array[1]),
        "training_focus": int(action_array[2]),
        "scouting_level": int(action_array[3]),
        "transfer_bid_0": int(action_array[4]),
        "bid_amount_0": np.float32(action_array[5] / 9.0),
        "transfer_bid_1": int(action_array[6]),
        "bid_amount_1": np.float32(action_array[7] / 9.0),
        "transfer_bid_2": int(action_array[8]),
        "bid_amount_2": np.float32(action_array[9] / 9.0),
        "sub_0": int(action_array[10]),
        "sub_1": int(action_array[11]),
        "sub_2": int(action_array[12]),
    }


def validate_policy_contract(
    observation_space: Any,
    action_space: Any,
    *,
    num_teams: int,
) -> None:
    """Ensure a loaded policy matches the repo's shared env contract."""
    expected_obs_shape = (expected_observation_size(num_teams),)
    actual_obs_shape = getattr(observation_space, "shape", None)
    if actual_obs_shape != expected_obs_shape:
        raise PolicyContractError(
            "Policy observation contract mismatch: "
            f"expected {expected_obs_shape}, got {actual_obs_shape}. "
            "This usually means the checkpoint was trained before the shared "
            "16-player watch-first observation contract."
        )

    if not isinstance(action_space, spaces.MultiDiscrete):
        raise PolicyContractError(
            "Policy action contract mismatch: expected a MultiDiscrete action space."
        )

    action_components = int(np.asarray(action_space.nvec).size)
    if action_components != FLAT_ACTION_COMPONENTS:
        raise PolicyContractError(
            "Policy action contract mismatch: "
            f"expected {FLAT_ACTION_COMPONENTS} components, got {action_components}."
        )
