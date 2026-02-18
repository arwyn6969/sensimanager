"""SWOS420 Youth Academy — prospect generation + development curves.

Each club generates 1-3 prospects per season based on academy tier.
Prospects start at age 16-18 with randomised skills in the low range.
Development is driven by:
  - Training intensity (club setting)
  - Playing time (appearances → confidence → growth)
  - Hidden potential (50-100, revealed by scouting tier 3+)
  - Breakthrough events (rare random chance of world-class leap)

Academy tiers:
  Tier 3 (★★★) — Top-six clubs: better base skills + more prospects
  Tier 2 (★★)  — Mid-table / Championship: average
  Tier 1 (★)   — Lower league: raw but occasionally brilliant

Tranmere Rovers always get extra prospects because SWA. 🏟️🔥
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

from swos420.models.player import (
    SKILL_NAMES,
    Skills,
    SWOSPlayer,
    generate_base_id,
)

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────

# Prospect names by nationality (small pool — extend with real gen later)
_ENGLISH_FIRST = [
    "Jack", "Harry", "Charlie", "James", "George", "Oliver", "Liam",
    "Thomas", "Ben", "Daniel", "Will", "Ryan", "Max", "Oscar", "Alfie",
    "Jake", "Ethan", "Connor", "Kai", "Leo", "Mason", "Tyler", "Noah",
]
_ENGLISH_LAST = [
    "Smith", "Jones", "Williams", "Taylor", "Brown", "Wilson", "Davis",
    "Evans", "Thomas", "Roberts", "Johnson", "Walker", "White", "Clarke",
    "Hall", "Green", "Turner", "Baker", "Adams", "Hill", "Moore", "Wood",
    "Morris", "Hughes", "Jackson", "Kelly", "Price", "Davies", "Mitchell",
]
_WELSH_FIRST = [
    "Rhys", "Dylan", "Owen", "Iwan", "Gethin", "Cai", "Dafydd",
    "Arwyn", "Bryn", "Gareth", "Morgan", "Emyr", "Aled", "Huw",
]
_WELSH_LAST = [
    "Hughes", "Evans", "Davies", "Williams", "Jones", "Thomas",
    "Roberts", "Edwards", "Lewis", "Morgan", "Griffiths", "Parry",
    "Owen", "Price", "Rees", "Phillips", "James", "Bowen", "Lloyd",
]

_POSITIONS = ["GK", "CB", "RB", "LB", "CDM", "CM", "CAM", "RW", "LW", "ST", "CF"]
_POSITION_WEIGHTS = [0.06, 0.14, 0.08, 0.08, 0.08, 0.14, 0.10, 0.08, 0.08, 0.10, 0.06]

# Clubs that get the Welsh name pool (Birkenhead is close enough)
_WELSH_CLUBS = {"Tranmere Rovers", "Wrexham", "Swansea City", "Cardiff City", "Newport County"}


@dataclass
class AcademyConfig:
    """Configuration for a club's youth academy."""
    club_name: str
    club_code: str
    tier: int = 2               # 1 (basic) to 3 (elite)
    nationality: str = "England"
    prospects_per_season: int = 1

    @property
    def skill_range(self) -> tuple[int, int]:
        """Base skill range for generated youth (stored 0-7)."""
        if self.tier >= 3:
            return (2, 5)       # Elite academies produce better raw talent
        elif self.tier >= 2:
            return (1, 4)       # Mid-tier
        else:
            return (0, 3)       # Basic — raw but scrappy

    @property
    def potential_range(self) -> tuple[int, int]:
        """Hidden potential range (0-100)."""
        if self.tier >= 3:
            return (65, 95)
        elif self.tier >= 2:
            return (55, 88)
        else:
            return (45, 82)


def _generate_name(club_name: str) -> tuple[str, str, str]:
    """Generate a random youth prospect name.

    Returns:
        (full_name, display_name, nationality)
    """
    if club_name in _WELSH_CLUBS:
        # 60% chance of Welsh name for Welsh-area clubs
        if random.random() < 0.6:
            first = random.choice(_WELSH_FIRST)
            last = random.choice(_WELSH_LAST)
            return f"{first} {last}", f"{first[0]}. {last}".upper()[:15], "Wales"

    first = random.choice(_ENGLISH_FIRST)
    last = random.choice(_ENGLISH_LAST)
    return f"{first} {last}", f"{first[0]}. {last}".upper()[:15], "England"


def _pick_position() -> str:
    """Weighted random position selection."""
    return random.choices(_POSITIONS, weights=_POSITION_WEIGHTS, k=1)[0]


def generate_youth_prospect(
    config: AcademyConfig,
    season: str = "25/26",
) -> SWOSPlayer:
    """Generate a single youth prospect for a club.

    Args:
        config: Academy configuration for the club.
        season: Current season string (for base_id generation).

    Returns:
        A fresh SWOSPlayer ready to join the squad.
    """
    full_name, display_name, nationality = _generate_name(config.club_name)
    position = _pick_position()
    age = random.randint(16, 18)

    # Generate skills within tier range
    lo, hi = config.skill_range
    skills_dict = {}
    for skill in SKILL_NAMES:
        base = random.randint(lo, hi)
        # Position-specific boost: +1 to relevant skills
        if position in ("ST", "CF") and skill in ("finishing", "speed"):
            base = min(7, base + 1)
        elif position in ("CM", "CAM") and skill in ("passing", "control"):
            base = min(7, base + 1)
        elif position in ("CB", "CDM") and skill in ("tackling", "heading"):
            base = min(7, base + 1)
        elif position == "GK":
            base = 0  # GK skills are all 0 in authentic SWOS
        skills_dict[skill] = base

    skills = Skills(**skills_dict)

    # Hidden potential
    pot_lo, pot_hi = config.potential_range
    potential = random.randint(pot_lo, pot_hi)

    # Generate unique base_id
    uid = f"youth-{config.club_code}-{random.randint(10000, 99999)}"
    base_id = generate_base_id(sofifa_id=uid, season=season)

    # Value based on skill total (hex-tier) — youth are cheap
    from swos420.models.player import hex_tier_value
    raw_value = hex_tier_value(skills.total)
    youth_discount = 0.4 + (age - 16) * 0.15  # 16yo = 40%, 18yo = 70%
    value = max(25_000, int(raw_value * youth_discount))

    player = SWOSPlayer(
        base_id=base_id,
        full_name=full_name,
        display_name=display_name,
        short_name=f"{full_name.split()[0][0]}. {full_name.split()[-1]}",
        shirt_number=random.randint(40, 99),
        position=position,
        nationality=nationality,
        height_cm=random.randint(168, 195),
        weight_kg=random.randint(62, 88),
        skin_id=random.randint(0, 3),
        hair_id=random.randint(0, 7),
        club_name=config.club_name,
        club_code=config.club_code,
        skills=skills,
        age=age,
        contract_years=min(3, 5 - (age - 16)),  # Younger = shorter initial deal
        base_value=value,
        wage_weekly=max(500, value // 500),
        morale=80.0 + random.uniform(-10, 10),
        form=random.uniform(-5, 10),
        injury_days=0,
        fatigue=0.0,
    )

    logger.info(
        f"🌱 Youth prospect: {full_name} ({position}, age {age}) "
        f"for {config.club_name} — potential {potential}/100"
    )

    return player


@dataclass
class YouthAcademyResult:
    """Output of a seasonal youth intake."""
    season: str
    prospects: list[SWOSPlayer] = field(default_factory=list)
    breakthroughs: list[str] = field(default_factory=list)  # Names of breakthrough talents

    @property
    def total(self) -> int:
        return len(self.prospects)


def run_youth_intake(
    academies: list[AcademyConfig],
    season: str = "25/26",
    tranmere_override: bool = True,
) -> YouthAcademyResult:
    """Run end-of-season youth intake for all clubs.

    Args:
        academies: List of AcademyConfig for each club.
        season: Current season string.
        tranmere_override: If True, Tranmere gets extra prospects (SWA 🔥).

    Returns:
        YouthAcademyResult with all generated prospects.
    """
    result = YouthAcademyResult(season=season)

    for config in academies:
        # Tranmere gets 3 prospects minimum — Super White Army bonus
        count = config.prospects_per_season
        if tranmere_override and config.club_name == "Tranmere Rovers":
            count = max(3, count)

        for _ in range(count):
            prospect = generate_youth_prospect(config, season)
            result.prospects.append(prospect)

            # Breakthrough event: 3% chance per prospect of a generational talent
            if random.random() < 0.03:
                # Boost 2-3 skills to 6-7
                boost_skills = random.sample(list(SKILL_NAMES), k=random.randint(2, 3))
                for skill in boost_skills:
                    new_val = min(7, getattr(prospect.skills, skill) + random.randint(2, 3))
                    setattr(prospect.skills, skill, new_val)
                result.breakthroughs.append(prospect.full_name)
                logger.info(
                    f"⚡ BREAKTHROUGH: {prospect.full_name} ({prospect.club_name}) "
                    f"— generational talent detected!"
                )

    logger.info(
        f"Youth intake {season}: {result.total} prospects generated "
        f"({len(result.breakthroughs)} breakthroughs)"
    )

    return result


def develop_youth(
    player: SWOSPlayer,
    appearances: int = 0,
    potential: int = 70,
    training_intensity: float = 1.0,
) -> dict[str, int]:
    """Apply seasonal development to a young player.

    Called at end of season for players aged 16-23.

    Args:
        player: The young player to develop.
        appearances: Games played this season (more = better growth).
        potential: Hidden potential (0-100).
        training_intensity: Club training multiplier (default 1.0).

    Returns:
        Dict of skill changes: {"passing": +1, "speed": 0, ...}
    """
    if player.age > 23:
        return {s: 0 for s in SKILL_NAMES}

    changes: dict[str, int] = {}

    for skill in SKILL_NAMES:
        current = getattr(player.skills, skill)
        if current >= 7:
            changes[skill] = 0
            continue

        # Growth probability scales with:
        # - Youth factor (16-18 grow fastest)
        # - Playing time
        # - Potential ceiling
        # - Training intensity
        # - Form (positive form = better development)

        youth_factor = max(0.1, (24 - player.age) / 8.0)  # 16yo = 1.0, 23yo = 0.125
        play_factor = min(1.0, appearances / 20.0)          # 20+ games = maximum
        potential_factor = potential / 100.0                  # 100 = guaranteed
        form_factor = max(0.3, 1.0 + player.form / 100.0)   # Positive form helps

        growth_chance = (
            0.15                    # Base 15% chance per skill
            * youth_factor
            * (0.5 + play_factor)   # 50% even without games (training)
            * potential_factor
            * form_factor
            * training_intensity
        )

        if random.random() < growth_chance:
            increment = 1
            # Rare double growth for very high potential + young
            if potential >= 85 and player.age <= 18 and random.random() < 0.1:
                increment = 2
            new_val = min(7, current + increment)
            setattr(player.skills, skill, new_val)
            changes[skill] = new_val - current
        else:
            changes[skill] = 0

    total_growth = sum(changes.values())
    if total_growth > 0:
        logger.info(
            f"📈 {player.full_name} development: "
            + ", ".join(f"{s}+{v}" for s, v in changes.items() if v > 0)
        )

    return changes


def default_academy_configs(
    clubs: list[dict[str, str]],
) -> list[AcademyConfig]:
    """Generate default academy configs from a list of clubs.

    Args:
        clubs: List of dicts with 'name', 'code', and optionally 'division'.

    Returns:
        List of AcademyConfig with sensible defaults.
    """
    # Tier 3 clubs (elite academies)
    _ELITE = {
        "Manchester United", "Manchester City", "Liverpool", "Chelsea",
        "Arsenal", "Tottenham", "Newcastle United",
    }

    configs = []
    for club in clubs:
        name = club["name"]
        code = club.get("code", name[:3].upper())
        division = club.get("division", 2)

        if name in _ELITE:
            tier = 3
            prospects = 3
        elif division <= 1:
            tier = 2
            prospects = 2
        elif division <= 2:
            tier = 2
            prospects = 1
        else:
            tier = 1
            prospects = 1

        # Tranmere Rovers: always at least tier 2, always 3 prospects
        if name == "Tranmere Rovers":
            tier = max(2, tier)
            prospects = 3

        nationality = "Wales" if name in _WELSH_CLUBS else "England"

        configs.append(AcademyConfig(
            club_name=name,
            club_code=code,
            tier=tier,
            nationality=nationality,
            prospects_per_season=prospects,
        ))

    return configs
