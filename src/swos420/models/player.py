"""SWOS420 Player Model — Deep v2.2 with all canonical SWOS mechanics.

Every player has 7 core skills (0-15), dynamic form/morale/fatigue,
and economy fields (wage, value) that drive the NFT ownership layer.
"""

from __future__ import annotations

import hashlib
import math
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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


class Skills(BaseModel):
    """The 7 canonical SWOS skills, each 0-15."""
    passing: int = Field(default=5, ge=0, le=15, description="Pass accuracy, range, through-balls")
    velocity: int = Field(default=5, ge=0, le=15, description="Long-range shot power & swerve")
    heading: int = Field(default=5, ge=0, le=15, description="Aerial duels, corners, crosses")
    tackling: int = Field(default=5, ge=0, le=15, description="Slide tackles, challenges, foul risk")
    control: int = Field(default=5, ge=0, le=15, description="First touch, dribbling, turning")
    speed: int = Field(default=5, ge=0, le=15, description="Top speed, acceleration")
    finishing: int = Field(default=5, ge=0, le=15, description="Close-range shot accuracy & power")

    @property
    def total(self) -> int:
        """Sum of all 7 skills."""
        return sum(getattr(self, s) for s in SKILL_NAMES)

    @property
    def top3(self) -> list[str]:
        """Return the 3 highest skills (by abbreviation), for squad display."""
        ranked = sorted(SKILL_NAMES, key=lambda s: getattr(self, s), reverse=True)
        return [SKILL_ABBREVS[s] for s in ranked[:3]]

    def as_dict(self) -> dict[str, int]:
        return {s: getattr(self, s) for s in SKILL_NAMES}


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
    base_value: int = Field(default=1_000_000, ge=0, description="Base transfer value in £")
    wage_weekly: int = Field(default=10_000, ge=0, description="Weekly wage in £/$CM")

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
        """Apply form modifier to a base skill.

        effective_skill = base_skill * (1.0 + form / 200.0)
        Form +50 = +25% boost, Form -50 = -25% penalty.
        """
        base = getattr(self.skills, skill_name)
        return base * (1.0 + self.form / 200.0)

    def effective_skills(self) -> dict[str, float]:
        """All 7 effective skills (form-modified)."""
        return {s: self.effective_skill(s) for s in SKILL_NAMES}

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
        """Dynamic market value based on base_value, form, goals, and age.

        current_value = base_value * (0.6 + form/100 + goals*0.01) * age_factor
        """
        form_factor = 0.6 + self.form / 100.0 + self.goals_scored_season * 0.01
        return max(25_000, int(self.base_value * form_factor * self.age_factor))

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
            decay_rate = 0.1 if self.age < 34 else 0.25
            for skill_name in SKILL_NAMES:
                current = getattr(self.skills, skill_name)
                new_val = max(0, int(current - decay_rate))
                setattr(self.skills, skill_name, new_val)

    @property
    def should_retire(self) -> bool:
        """Retirement check: age > 36 or total skills < 45."""
        return self.age > 36 or self.skills.total < 45

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
