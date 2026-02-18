"""SWOS420 Player Model — v3.0 with authentic SWOS 96/97 mechanics.

Every player has 7 core skills stored as 0-7 (database values) that map
to effective 8-15 at runtime (+8 offset). This creates only 8 discrete
skill levels with a compressed 2× gap between worst and best, matching
the original Sensible World of Soccer engine.

GK performance is driven by value tier (Hex Price Byte), not skills.
Player values use a stepped hex-tier economy, not linear scaling.
Positional fitness ('Green Tick') modifies ICP contributions.
"""

from __future__ import annotations

import bisect
import hashlib
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Position(str, Enum):
    """All 20+ player positions (modern mods)."""
    GK = "GK"
    RB = "RB"
    CB = "CB"
    LB = "LB"
    RWB = "RWB"
    LWB = "LWB"
    CDM = "CDM"
    RM = "RM"
    CM = "CM"
    LM = "LM"
    CAM = "CAM"
    RW = "RW"
    LW = "LW"
    AM = "AM"
    CF = "CF"
    ST = "ST"
    SS = "SS"  # Second striker
    SW = "SW"  # Sweeper


# Canonical SWOS 7-skill names and their abbreviations
SKILL_NAMES = ("passing", "velocity", "heading", "tackling", "control", "speed", "finishing")
SKILL_ABBREVS = {"passing": "PA", "velocity": "VE", "heading": "HE", "tackling": "TA",
                 "control": "CO", "speed": "SP", "finishing": "FI"}

# ── Authentic SWOS Constants ──────────────────────────────────────────
SWOS_SKILL_BASE = 8       # Engine adds +8 to stored value at runtime
SWOS_STORED_MAX = 7       # Max stored value in database (0-7)
SWOS_EFFECTIVE_MAX = 15   # Max effective value (7 + 8)
SWOS_EFFECTIVE_MIN = 8    # Min effective value (0 + 8)
SWOS_SQUAD_SIZE = 16      # Authentic SWOS squad size

# Stepped hex-tier value table — values jump at thresholds, not linear.
# Indexed by effective skill tier (8-15), mapping skill-total ranges to value tiers.
HEX_VALUE_TABLE: list[tuple[int, int]] = [
    # (skill_total_threshold, value_in_pounds)
    (0,   25_000),
    (5,   50_000),
    (10,  75_000),
    (14,  100_000),
    (17,  250_000),
    (20,  500_000),
    (23,  750_000),
    (26,  1_000_000),
    (29,  1_500_000),
    (32,  2_500_000),
    (35,  5_000_000),
    (38,  7_500_000),
    (41,  10_000_000),
    (44,  12_500_000),
    (47,  15_000_000),
]
HEX_THRESHOLDS = [t for t, _ in HEX_VALUE_TABLE]
HEX_VALUES = [v for _, v in HEX_VALUE_TABLE]

# Positional fitness — maps Position → set of natural positions (Green Tick).
# If player.position is in GREEN_TICK_POSITIONS[assigned_role], they
# get the 1.2× ICP multiplier. Otherwise they get 1.0× (neutral) or
# 0.7× (red cross) if completely wrong.
GREEN_TICK_POSITIONS: dict[str, set[str]] = {
    "GK": {"GK"},
    "RB": {"RB", "RWB"},
    "CB": {"CB", "SW"},
    "LB": {"LB", "LWB"},
    "RWB": {"RB", "RWB"},
    "LWB": {"LB", "LWB"},
    "CDM": {"CDM", "CM"},
    "RM": {"RM", "RW"},
    "CM": {"CM", "CDM", "CAM"},
    "LM": {"LM", "LW"},
    "CAM": {"CAM", "AM", "CM"},
    "RW": {"RW", "RM"},
    "LW": {"LW", "LM"},
    "AM": {"AM", "CAM", "SS"},
    "CF": {"CF", "ST", "SS"},
    "ST": {"ST", "CF"},
    "SS": {"SS", "CF", "AM"},
    "SW": {"SW", "CB"},
}

# Cross-category penalties: playing a defender as attacker (or vice versa)
# gets the Red Cross 0.7× penalty.
_DEFENSIVE = {"GK", "RB", "CB", "LB", "RWB", "LWB", "SW"}
_MIDFIELD = {"CDM", "RM", "CM", "LM", "CAM", "AM"}
_ATTACKING = {"RW", "LW", "CF", "ST", "SS"}


def positional_fitness(player_pos: str, assigned_role: str) -> float:
    """Return ICP multiplier for positional fitness.

    Returns:
        1.2 — Green Tick (natural position)
        1.0 — Neutral (same zone, different role)
        0.7 — Red Cross (wrong zone entirely)
    """
    if player_pos == assigned_role:
        return 1.2
    green_set = GREEN_TICK_POSITIONS.get(assigned_role, set())
    if player_pos in green_set:
        return 1.2
    # Same zone = neutral
    player_zone = _DEFENSIVE if player_pos in _DEFENSIVE else (
        _MIDFIELD if player_pos in _MIDFIELD else _ATTACKING
    )
    assigned_zone = _DEFENSIVE if assigned_role in _DEFENSIVE else (
        _MIDFIELD if assigned_role in _MIDFIELD else _ATTACKING
    )
    if player_zone == assigned_zone:
        return 1.0
    return 0.7


def hex_tier_value(skill_total: int) -> int:
    """Look up stepped hex-tier value from skill total.

    Values jump at thresholds (e.g., £5M → £10M) rather than scaling
    linearly. This matches the original SWOS hex-code economy.
    """
    idx = bisect.bisect_right(HEX_THRESHOLDS, skill_total) - 1
    return HEX_VALUES[max(0, idx)]


class Skills(BaseModel):
    """The 7 canonical SWOS skills, stored as 0-7 (database values).

    At runtime, the engine adds +8 to get effective values (8-15).
    This creates only 8 discrete skill levels with a compressed 2×
    gap between the worst and best players.
    """
    passing: int = Field(default=3, ge=0, le=7, description="Pass speed/snap, receiver lock accuracy")
    velocity: int = Field(default=3, ge=0, le=7, description="Shot power OUTSIDE penalty area")
    heading: int = Field(default=3, ge=0, le=7, description="Aerial leap height, header accuracy")
    tackling: int = Field(default=3, ge=0, le=7, description="Tackle hitbox radius, clean dispossession prob")
    control: int = Field(default=3, ge=0, le=7, description="Ball friction coefficient, turn retention")
    speed: int = Field(default=3, ge=0, le=7, description="Pixels-per-frame displacement rate")
    finishing: int = Field(default=3, ge=0, le=7, description="Shot power/accuracy INSIDE penalty area")

    @property
    def total(self) -> int:
        """Sum of all 7 stored skills (0-49 range)."""
        return sum(getattr(self, s) for s in SKILL_NAMES)

    @property
    def effective_total(self) -> int:
        """Sum of all 7 effective skills (56-105 range)."""
        return sum(self.effective(s) for s in SKILL_NAMES)

    def effective(self, skill_name: str) -> int:
        """Return the effective skill value (stored + 8).

        Stored 0 → effective 8 (53% of max).
        Stored 7 → effective 15 (100% of max).
        """
        return getattr(self, skill_name) + SWOS_SKILL_BASE

    @property
    def top3(self) -> list[str]:
        """Return the 3 highest skills (by abbreviation), for squad display."""
        ranked = sorted(SKILL_NAMES, key=lambda s: getattr(self, s), reverse=True)
        return [SKILL_ABBREVS[s] for s in ranked[:3]]

    def as_dict(self) -> dict[str, int]:
        """Return stored skill values."""
        return {s: getattr(self, s) for s in SKILL_NAMES}

    def effective_dict(self) -> dict[str, int]:
        """Return effective skill values (stored + 8)."""
        return {s: self.effective(s) for s in SKILL_NAMES}


def generate_base_id(sofifa_id: int | str, season: str) -> str:
    """Generate an immutable Base_ID from Sofifa ID + season hash.

    This UUID-like string serves as the NFT tokenID and never changes,
    ensuring ownership persistence across seasonal updates.
    """
    raw = f"{sofifa_id}:{season}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class SWOSPlayer(BaseModel):
    """Complete SWOS420 player model — v2.2 deep model with all mechanics.

    Static fields are set at import time and only change on youth generation.
    Dynamic fields (form, morale, fatigue, injury, wages, value) change every
    match/week during simulation.
    """

    # ── Identity (Static) ──────────────────────────────────────────────
    base_id: str = Field(description="Immutable UUID (Sofifa ID + season hash), NFT tokenID")
    full_name: str = Field(description="Real name with accents (UTF-8), e.g. 'Lamine Yamal Nasraoui Ebana'")
    display_name: str = Field(
        max_length=15,
        description="Engine-safe: ALL-CAPS, max 15 chars, transliterated fallback",
    )
    short_name: str = Field(default="", description="Common known name, e.g. 'L. Yamal'")
    shirt_number: int = Field(default=1, ge=1, le=99)
    position: Position = Field(default=Position.CM)
    nationality: str = Field(default="Unknown")
    height_cm: int = Field(default=180, ge=150, le=210)
    weight_kg: int = Field(default=75, ge=50, le=120)
    skin_id: int = Field(default=0, ge=0, le=31)
    hair_id: int = Field(default=0, ge=0, le=31)

    # ── Club ───────────────────────────────────────────────────────────
    club_name: str = Field(default="Free Agent")
    club_code: str = Field(default="FA", max_length=5)

    # ── Skills (Static base, modified by effective_skill at runtime) ──
    skills: Skills = Field(default_factory=Skills)

    # ── Dynamic / Runtime ──────────────────────────────────────────────
    age: int = Field(default=25, ge=16, le=40)
    contract_years: int = Field(default=3, ge=0, le=5)
    base_value: int = Field(default=500_000, ge=0, description="Base transfer value in £ (hex-tier)")
    wage_weekly: int = Field(default=10_000, ge=0, description="Weekly wage in £/$SENSI")

    morale: float = Field(default=100.0, ge=0.0, le=100.0)
    form: float = Field(default=0.0, ge=-50.0, le=50.0, description="The secret sauce: -50 to +50")
    injury_days: int = Field(default=0, ge=0, le=365)
    fatigue: float = Field(default=0.0, ge=0.0, le=100.0)

    # ── Season Stats (reset each season) ──────────────────────────────
    goals_scored_season: int = Field(default=0, ge=0)
    assists_season: int = Field(default=0, ge=0)
    appearances_season: int = Field(default=0, ge=0)
    clean_sheets_season: int = Field(default=0, ge=0)

    # ── Ownership (NFT) ───────────────────────────────────────────────
    owner_address: Optional[str] = Field(default=None, description="ERC-721 owner wallet address")

    # ── Validators ─────────────────────────────────────────────────────
    @field_validator("display_name")
    @classmethod
    def display_name_must_be_upper(cls, v: str) -> str:
        return v.upper()

    # ── Economy Methods ────────────────────────────────────────────────
    def effective_skill(self, skill_name: str) -> float:
        """Return effective skill with form modifier applied.

        Base effective = stored_skill + 8 (SWOS offset).
        Form modifies effective: effective * (1.0 + form / 200.0).
        """
        base_effective = self.skills.effective(skill_name)
        return base_effective * (1.0 + self.form / 200.0)

    def effective_skills(self) -> dict[str, float]:
        """All 7 effective skills (offset + form-modified)."""
        return {s: self.effective_skill(s) for s in SKILL_NAMES}

    @property
    def is_goalkeeper(self) -> bool:
        """True if player is a goalkeeper."""
        return self.position == Position.GK

    @property
    def gk_save_ability(self) -> float:
        """GK performance rating derived from value tier, not skills.

        In authentic SWOS, GK skills are all 0 — their save probability
        is driven entirely by their Hex Price Byte (market value = stat).
        Returns a 0.0-1.0 rating based on value tier.
        """
        if not self.is_goalkeeper:
            return 0.0
        value = self.calculate_current_value()
        # Map value to 0.0-1.0 save ability (£25K=0.3, £15M=0.95)
        if value <= 25_000:
            return 0.30
        elif value >= 15_000_000:
            return 0.95
        else:
            # Log scale — big GK value gains diminish returns
            import math
            return 0.30 + 0.65 * (math.log(value / 25_000) / math.log(15_000_000 / 25_000))

    @property
    def age_factor(self) -> float:
        """Age-based value multiplier. Peak at 25-29, drops sharply after 32."""
        if self.age <= 21:
            return 0.7 + (self.age - 16) * 0.06  # 0.7 → 1.0
        elif self.age <= 29:
            return 1.0
        elif self.age <= 32:
            return 1.0 - (self.age - 29) * 0.08  # 1.0 → 0.76
        else:
            return max(0.3, 0.76 - (self.age - 32) * 0.1)  # drops to 0.3 floor

    def calculate_current_value(self) -> int:
        """Dynamic market value using stepped hex-tier economy.

        Base value comes from hex_tier_value(skill_total), then
        modified by form, goals, and age factor.
        """
        # Hex-tier base from skill total
        tier_base = hex_tier_value(self.skills.total)
        # Dynamic modifiers (form + goals + age)
        form_mod = 1.0 + self.form / 100.0
        goal_bonus = 1.0 + self.goals_scored_season * 0.02
        raw = tier_base * form_mod * goal_bonus * self.age_factor
        return max(25_000, int(raw))

    def calculate_wage(self, league_multiplier: float = 1.0) -> int:
        """Weekly wage derived from current market value.

        wage = current_value * 0.0018 * league_multiplier
        """
        current_val = self.calculate_current_value()
        return max(5_000, int(current_val * 0.0018 * league_multiplier))

    def apply_form_change(self, team_result_bonus: float, individual_rating: float) -> None:
        """Update form after a match.

        form_change = (team_result_bonus + individual_rating - 10) * 3
        Clamped to [-50, +50].
        """
        delta = (team_result_bonus + individual_rating - 10.0) * 3.0
        self.form = max(-50.0, min(50.0, self.form + delta))

    def apply_bench_decay(self, weeks: int = 1) -> None:
        """Form decays -5 to -15 per week on bench/injured."""
        decay = min(15.0, 5.0 + weeks * 2.0)
        self.form = max(-50.0, self.form - decay)

    def apply_aging(self) -> None:
        """Age +1 year. Apply skill development or decay.

        Under 24: +0.05-0.25 per skill if high form.
        30+: -0.05-0.20 per skill (faster after 34).
        """
        self.age += 1
        if self.age < 24 and self.form > 10:
            # Youth development: small random boost to 1-3 skills
            # Actual randomness handled by engine — this applies deterministic minimum
            pass  # Engine will call develop_youth() with RNG
        elif self.age >= 30:
            # Decay: older players lose skill points (clamped to 0-7 range)
            decay_rate = 0.1 if self.age < 34 else 0.25
            for skill_name in SKILL_NAMES:
                current = getattr(self.skills, skill_name)
                new_val = max(0, int(current - decay_rate))  # Stays in 0-7
                setattr(self.skills, skill_name, new_val)

    def reset_season_stats(self) -> None:
        """Reset season counters while preserving long-term player state."""
        self.goals_scored_season = 0
        self.assists_season = 0
        self.appearances_season = 0
        self.clean_sheets_season = 0

    @property
    def should_retire(self) -> bool:
        """Retirement check: age > 36 or total stored skills < 7 (all at 1)."""
        return self.age > 36 or self.skills.total < 7

    @property
    def injury_risk_lambda(self) -> float:
        """Poisson λ for injury probability per match.

        Base 0.08, modified by negative form and fatigue.
        """
        base_lambda = 0.08
        form_mod = max(0.0, -self.form * 0.01)  # negative form increases risk
        fatigue_mod = self.fatigue * 0.001
        return base_lambda + form_mod + fatigue_mod

    def to_nft_metadata(self) -> dict:
        """Generate NFT-compatible metadata (ERC-721 tokenURI response)."""
        return {
            "name": self.full_name,
            "description": f"{self.full_name} — {self.position.value} for {self.club_name}",
            "image": f"https://swos420-metadata.base/api/image/{self.base_id}",
            "attributes": [
                {"trait_type": "Position", "value": self.position.value},
                {"trait_type": "Club", "value": self.club_name},
                {"trait_type": "Nationality", "value": self.nationality},
                {"trait_type": "Age", "value": self.age},
                {"trait_type": "Overall", "value": self.skills.total},
                *[{"trait_type": SKILL_ABBREVS[s], "value": getattr(self.skills, s)}
                  for s in SKILL_NAMES],
                {"trait_type": "Form", "value": int(self.form)},
                {"trait_type": "Market Value", "value": self.calculate_current_value()},
                {"trait_type": "Weekly Wage", "value": self.calculate_wage()},
                {"trait_type": "Season Goals", "value": self.goals_scored_season},
            ],
        }
