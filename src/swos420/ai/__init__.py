"""SWOS420 AI manager tooling for the watch-first spectator product.

Formation, style, and training are the live manager controls today. The
transfer/scouting/substitution lane remains parked until the spectator MVP
gates are met.
"""

from swos420.ai.policy_io import (
    MAX_SQUAD_OBS_PLAYERS,
    PolicyContractError,
    decode_flat_action,
    expected_observation_size,
    flatten_observation,
    validate_policy_contract,
)

__all__ = [
    "MAX_SQUAD_OBS_PLAYERS",
    "PolicyContractError",
    "decode_flat_action",
    "expected_observation_size",
    "flatten_observation",
    "validate_policy_contract",
]
