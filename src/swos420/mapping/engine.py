"""Attribute mapping engine — Sofifa → SWOS 0-7 stored scale.

Loads mapping rules from config/rules.json, applies formulas with
configurable multipliers and offsets, supports star-player overrides,
and clamps all values to the 0-7 SWOS stored skill range.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from swos420.models.player import SKILL_NAMES, Skills


DEFAULT_RULES_PATH = Path(__file__).parent.parent.parent.parent / "config" / "rules.json"


class AttributeMapper:
    """Maps Sofifa CSV attributes to SWOS 7-skill system.

    Usage:
        mapper = AttributeMapper()  # loads default rules.json
        skills = mapper.map_sofifa_to_swos(sofifa_attrs)
        skills = mapper.apply_overrides("Erling Haaland", skills)
    """

    def __init__(self, rules_path: str | Path | None = None):
        self.rules_path = Path(rules_path) if rules_path else DEFAULT_RULES_PATH
        self._rules: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        """(Re)load rules from JSON config. Hot-reloadable."""
        if self.rules_path.exists():
            with open(self.rules_path) as f:
                self._rules = json.load(f)
        else:
            self._rules = {}

    @property
    def mapping_rules(self) -> dict[str, Any]:
        return self._rules.get("mapping_simple", {})

    @property
    def overrides(self) -> dict[str, dict[str, int]]:
        return self._rules.get("overrides", {})

    @property
    def economy_rules(self) -> dict[str, Any]:
        return self._rules.get("economy", {})

    @property
    def form_rules(self) -> dict[str, Any]:
        return self._rules.get("form", {})

    def map_sofifa_to_swos(self, sofifa_attrs: dict[str, float | int]) -> Skills:
        """Apply mapping formulas to convert Sofifa 0-100 attributes to SWOS 0-7.

        Each SWOS skill is derived from one or more Sofifa attributes using:
            aggregate(sources) * multiplier + offset
        Then clamped to [0, 7] (stored range).

        Args:
            sofifa_attrs: Dict of Sofifa attribute names → values (0-100 scale).
                          Keys should be lowercase without 'sofifa_' prefix.

        Returns:
            Skills object with mapped 0-7 stored values.
        """
        mapped = {}

        for swos_skill in SKILL_NAMES:
            rule = self.mapping_rules.get(swos_skill)
            if rule is None:
                mapped[swos_skill] = 3  # default mid-range (0-7)
                continue

            sources = rule.get("sources", [])
            multiplier = rule.get("multiplier", 0.15)
            offset = rule.get("offset", 0)
            aggregate = rule.get("aggregate", "first")

            # Gather source values
            values = []
            for src in sources:
                val = sofifa_attrs.get(src)
                if val is not None:
                    values.append(float(val))

            if not values:
                mapped[swos_skill] = 3  # default mid-range (0-7)
                continue

            # Aggregate
            if aggregate == "mean":
                raw = sum(values) / len(values)
            elif aggregate == "max":
                raw = max(values)
            elif aggregate == "min":
                raw = min(values)
            else:  # "first"
                raw = values[0]

            # Apply formula: raw * multiplier + offset
            result = raw * multiplier + offset

            # Clamp to 0-7 (SWOS stored range)
            mapped[swos_skill] = _clamp(int(round(result)), 0, 7)

        return Skills(**mapped)

    def apply_overrides(self, player_name: str, skills: Skills) -> Skills:
        """Apply star-player overrides from rules.json.

        Matches against full name or partial name (case-insensitive).
        Override values replace the mapped values entirely.
        """
        overrides = self._find_override(player_name)
        if not overrides:
            return skills

        data = skills.as_dict()
        for skill_name, value in overrides.items():
            if skill_name in SKILL_NAMES:
                data[skill_name] = _clamp(value, 0, 7)

        return Skills(**data)

    def _find_override(self, player_name: str) -> dict[str, int] | None:
        """Find matching override entry.

        Matches if all words in the override name appear in the player name
        (case-insensitive). E.g., override 'Erling Haaland' matches
        player 'Erling Braut Haaland'.
        """
        name_lower = player_name.lower()
        name_words = set(name_lower.split())
        best_match = None
        best_word_count = 0

        for override_name, override_vals in self.overrides.items():
            override_words = override_name.lower().split()
            # Check if all override name words appear in the player name
            if all(word in name_words for word in override_words):
                if len(override_words) > best_word_count:
                    best_word_count = len(override_words)
                    best_match = override_vals
            # Also check surname-only match (last word)
            elif override_words[-1] in name_words and len(override_words) == 1:
                if best_match is None:
                    best_match = override_vals

        return best_match

    def map_and_override(
        self, player_name: str, sofifa_attrs: dict[str, float | int]
    ) -> Skills:
        """Convenience: map Sofifa attrs then apply any overrides."""
        skills = self.map_sofifa_to_swos(sofifa_attrs)
        return self.apply_overrides(player_name, skills)

    def calculate_base_value(self, skills: Skills, position: str = "CM") -> int:
        """Calculate base transfer value from skills.

        Formula: sum(skills) * position_weight * 50_000
        """
        total = skills.total
        position_weights = {
            "GK": 0.6, "CB": 0.8, "RB": 0.7, "LB": 0.7,
            "CDM": 0.85, "CM": 0.9, "CAM": 1.0, "AM": 1.0,
            "RM": 0.85, "LM": 0.85, "RW": 0.95, "LW": 0.95,
            "CF": 1.1, "ST": 1.2, "SS": 1.1,
        }
        weight = position_weights.get(position, 0.9)
        return max(50_000, int(total * weight * 50_000))

    def get_league_multiplier(self, league_name: str) -> float:
        """Get wage/value multiplier for a league."""
        multipliers = self.economy_rules.get("league_multipliers", {})
        return multipliers.get(league_name, multipliers.get("default", 1.0))


def _clamp(value: int, low: int, high: int) -> int:
    """Clamp an integer to [low, high]."""
    return max(low, min(high, value))
