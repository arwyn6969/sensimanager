"""SWOS420 Stadium Ad Hoarding Manager — Python Engine Integration.

Manages the pitch-perimeter hoarding visuals for the 24/7 streaming pipeline.
Loads active hoarding slots (from on-chain data or local cache), renders them
into the OBS overlay system, and injects sponsor mentions into LLM commentary.

Architecture:
    AdHoarding.sol (on-chain) ↔ ad_manager.py (off-chain) ↔ OBS overlay + LLM commentary

Slot ID encoding: clubId * 100 + position (0–19)
    e.g. Tranmere (clubId=1) → slots 100–119, positions 0–19 around the pitch

Revenue flow:
    Brand pays ETH → 60% club owner, 30% treasury, 10% creator (Arwyn)

Integration points:
    - season_runner.py: call update_demand() after each matchday
    - match_sim.py: call render_hoardings() to add visual data to MatchResult
    - streaming/overlay.html: reads hoardings.json for OBS overlay rendering
    - llm_commentary.py: call get_sponsor_mention() for organic brand drops
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Hoarding Position Layout ────────────────────────────────────────────

# Default positions around a standard pitch (for OBS overlay rendering).
# x,y coordinates are in percentage of pitch width/height.
# Positions 0-5: left touchline, 6-11: right touchline,
#           12-15: behind home goal, 16-19: behind away goal.

DEFAULT_HOARDING_POSITIONS: list[dict[str, Any]] = [
    # Left touchline (6 boards)
    {"pos": 0, "label": "Left-1",  "x": 0,   "y": 15, "width": 16, "side": "left"},
    {"pos": 1, "label": "Left-2",  "x": 0,   "y": 30, "width": 16, "side": "left"},
    {"pos": 2, "label": "Left-3",  "x": 0,   "y": 45, "width": 16, "side": "left"},
    {"pos": 3, "label": "Left-4",  "x": 0,   "y": 60, "width": 16, "side": "left"},
    {"pos": 4, "label": "Left-5",  "x": 0,   "y": 75, "width": 16, "side": "left"},
    {"pos": 5, "label": "Left-6",  "x": 0,   "y": 90, "width": 16, "side": "left"},
    # Right touchline (6 boards)
    {"pos": 6,  "label": "Right-1", "x": 84, "y": 15, "width": 16, "side": "right"},
    {"pos": 7,  "label": "Right-2", "x": 84, "y": 30, "width": 16, "side": "right"},
    {"pos": 8,  "label": "Right-3", "x": 84, "y": 45, "width": 16, "side": "right"},
    {"pos": 9,  "label": "Right-4", "x": 84, "y": 60, "width": 16, "side": "right"},
    {"pos": 10, "label": "Right-5", "x": 84, "y": 75, "width": 16, "side": "right"},
    {"pos": 11, "label": "Right-6", "x": 84, "y": 90, "width": 16, "side": "right"},
    # Behind home goal (4 boards)
    {"pos": 12, "label": "Home-Goal-1", "x": 20, "y": 0, "width": 15, "side": "home_end"},
    {"pos": 13, "label": "Home-Goal-2", "x": 35, "y": 0, "width": 15, "side": "home_end"},
    {"pos": 14, "label": "Home-Goal-3", "x": 50, "y": 0, "width": 15, "side": "home_end"},
    {"pos": 15, "label": "Home-Goal-4", "x": 65, "y": 0, "width": 15, "side": "home_end"},
    # Behind away goal (4 boards)
    {"pos": 16, "label": "Away-Goal-1", "x": 20, "y": 100, "width": 15, "side": "away_end"},
    {"pos": 17, "label": "Away-Goal-2", "x": 35, "y": 100, "width": 15, "side": "away_end"},
    {"pos": 18, "label": "Away-Goal-3", "x": 50, "y": 100, "width": 15, "side": "away_end"},
    {"pos": 19, "label": "Away-Goal-4", "x": 65, "y": 100, "width": 15, "side": "away_end"},
]

# Tier names for display
TIER_NAMES = {1: "League Two", 2: "League One", 3: "Championship", 4: "Premier League"}


# ── Data Models ──────────────────────────────────────────────────────────


@dataclass
class HoardingSlot:
    """A single hoarding slot with its content and metadata."""

    slot_id: int
    club_id: int
    position: int
    content_uri: str  # IPFS/Arweave URI to SVG/PNG
    brand_name: str = ""
    brand_address: str = ""  # Ethereum address of the renter
    expires_at: int = 0  # Unix timestamp
    paid_amount_wei: int = 0
    is_active: bool = True

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def days_remaining(self) -> int:
        remaining = self.expires_at - time.time()
        return max(0, int(remaining / 86400))


@dataclass
class ClubHoardings:
    """All hoarding slots for a single club stadium."""

    club_id: int
    club_name: str
    club_code: str
    tier: int = 1
    max_slots: int = 12
    slots: list[HoardingSlot] = field(default_factory=list)

    @property
    def active_slots(self) -> list[HoardingSlot]:
        return [s for s in self.slots if s.is_active and not s.is_expired]

    @property
    def available_positions(self) -> list[int]:
        occupied = {s.position for s in self.active_slots}
        return [i for i in range(self.max_slots) if i not in occupied]

    @property
    def occupancy_rate(self) -> float:
        if self.max_slots == 0:
            return 0.0
        return len(self.active_slots) / self.max_slots


# ── Ad Manager ───────────────────────────────────────────────────────────


class AdManager:
    """Stadium hoarding manager for the SWOS420 match engine + streaming pipeline.

    Manages hoarding display data, generates overlay JSON for OBS,
    and provides sponsor mention hooks for LLM commentary.

    Usage:
        ad_mgr = AdManager(streaming_dir=Path("streaming"))
        ad_mgr.register_club(1, "Tranmere Rovers", "TRN", tier=2, max_slots=16)
        ad_mgr.add_slot(HoardingSlot(
            slot_id=100, club_id=1, position=0,
            content_uri="ar://abc123/arwyn_hoardings.svg",
            brand_name="Super White Army",
            expires_at=int(time.time()) + 30 * 86400,
        ))
        ad_mgr.render_hoardings(club_id=1)  # writes streaming/hoardings.json
    """

    def __init__(
        self,
        streaming_dir: str | Path | None = None,
        cache_path: str | Path | None = None,
    ):
        """Initialize the Ad Manager.

        Args:
            streaming_dir: Path to the streaming/ directory for overlay JSON output.
            cache_path: Optional path to a local slot cache file (JSON).
        """
        self.streaming_dir = Path(streaming_dir) if streaming_dir else Path("streaming")
        self.cache_path = Path(cache_path) if cache_path else self.streaming_dir / "hoardings_cache.json"
        self.clubs: dict[int, ClubHoardings] = {}
        self.demand_factor: float = 1.0
        self.viewer_count: int = 0
        self._max_viewer_baseline: int = 5000

        # Load cache if exists
        if self.cache_path.exists():
            self._load_cache()

    # ── Club Registration ────────────────────────────────────────────────

    def register_club(
        self,
        club_id: int,
        club_name: str,
        club_code: str,
        tier: int = 1,
        max_slots: int = 12,
    ) -> ClubHoardings:
        """Register a club for hoarding advertising.

        Args:
            club_id: Unique club identifier (matches on-chain clubId).
            club_name: Full club name (e.g. "Tranmere Rovers").
            club_code: Short code (e.g. "TRN").
            tier: Club tier 1-4 (League Two → Premier League).
            max_slots: Number of hoarding positions (12-20).

        Returns:
            The registered ClubHoardings instance.
        """
        club = ClubHoardings(
            club_id=club_id,
            club_name=club_name,
            club_code=club_code,
            tier=min(4, max(1, tier)),
            max_slots=min(20, max(1, max_slots)),
        )
        self.clubs[club_id] = club
        logger.info(
            "Registered club %s (%s) — tier %d, %d slots",
            club_name, club_code, tier, max_slots,
        )
        return club

    # ── Slot Management ──────────────────────────────────────────────────

    def add_slot(self, slot: HoardingSlot) -> None:
        """Add or update a hoarding slot."""
        if slot.club_id not in self.clubs:
            logger.warning("Club %d not registered — slot %d not added", slot.club_id, slot.slot_id)
            return

        club = self.clubs[slot.club_id]
        # Replace existing slot at same position
        club.slots = [s for s in club.slots if s.position != slot.position]
        club.slots.append(slot)
        logger.info(
            "Slot %d: %s at position %d (%s) — expires in %d days",
            slot.slot_id, slot.brand_name, slot.position,
            club.club_name, slot.days_remaining,
        )

    def remove_expired(self) -> int:
        """Remove all expired slots. Returns count removed."""
        removed = 0
        for club in self.clubs.values():
            before = len(club.slots)
            club.slots = [s for s in club.slots if not s.is_expired]
            removed += before - len(club.slots)
        if removed > 0:
            logger.info("Removed %d expired hoarding slots", removed)
        return removed

    def get_active_slots(self, club_id: int) -> list[HoardingSlot]:
        """Get all active (non-expired) slots for a club."""
        if club_id not in self.clubs:
            return []
        return self.clubs[club_id].active_slots

    # ── Rendering (OBS Overlay Output) ───────────────────────────────────

    def render_hoardings(self, club_id: int, output_path: str | Path | None = None) -> dict:
        """Render hoarding data as JSON for OBS overlay consumption.

        Writes a hoardings.json file to the streaming directory that the
        overlay.html can poll and display as perimeter boards.

        Args:
            club_id: The home team's club ID (show their stadium hoardings).
            output_path: Override output path (default: streaming/hoardings.json).

        Returns:
            The generated JSON dict.
        """
        active = self.get_active_slots(club_id)
        club = self.clubs.get(club_id)

        hoarding_data: dict[str, Any] = {
            "club_id": club_id,
            "club_name": club.club_name if club else "Unknown",
            "club_code": club.club_code if club else "???",
            "tier": club.tier if club else 1,
            "total_slots": club.max_slots if club else 0,
            "active_count": len(active),
            "occupancy_rate": club.occupancy_rate if club else 0.0,
            "timestamp": int(time.time()),
            "hoardings": [],
        }

        for slot in active:
            pos_data = DEFAULT_HOARDING_POSITIONS[slot.position] if slot.position < len(
                DEFAULT_HOARDING_POSITIONS
            ) else {"x": 0, "y": 0, "width": 16, "side": "unknown"}

            hoarding_data["hoardings"].append({
                "slot_id": slot.slot_id,
                "position": slot.position,
                "content_uri": slot.content_uri,
                "brand_name": slot.brand_name,
                "days_remaining": slot.days_remaining,
                "layout": {
                    "x_pct": pos_data.get("x", 0),
                    "y_pct": pos_data.get("y", 0),
                    "width_pct": pos_data.get("width", 16),
                    "side": pos_data.get("side", "unknown"),
                    "label": pos_data.get("label", f"Pos-{slot.position}"),
                },
            })

        # Write to streaming directory
        out = Path(output_path) if output_path else self.streaming_dir / "hoardings.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(hoarding_data, indent=2))
        logger.info("Rendered %d hoardings → %s", len(active), out)

        return hoarding_data

    # ── Demand & Pricing Sync ────────────────────────────────────────────

    def update_demand(self, viewer_count: int | None = None) -> float:
        """Update demand factor based on current stream viewers.

        Called after each matchday by season_runner.py to sync
        demand signals back to the on-chain pricing oracle.

        Args:
            viewer_count: Current stream viewer count. If None, uses last known.

        Returns:
            Updated demand factor multiplier.
        """
        if viewer_count is not None:
            self.viewer_count = viewer_count

        # demand_factor = 1 + (viewers / baseline) * 0.8
        # At 0 viewers: 1.0 (bootstrap friendly — accept everything)
        # At 5000 viewers: 1.8
        # At 10000 viewers: 2.6
        self.demand_factor = 1.0 + (
            self.viewer_count / max(1, self._max_viewer_baseline)
        ) * 0.8

        logger.debug(
            "Demand updated: %d viewers → factor %.2f",
            self.viewer_count, self.demand_factor,
        )
        return self.demand_factor

    def calculate_price(
        self,
        club_id: int,
        days: int,
    ) -> float:
        """Calculate rental price in ETH (off-chain estimate, mirrors contract logic).

        Args:
            club_id: Club to advertise with.
            days: Rental duration in days.

        Returns:
            Estimated price in ETH.
        """
        if club_id not in self.clubs:
            return 0.0

        club = self.clubs[club_id]
        base_price = 0.001  # ETH per day

        # Tier multiplier
        tier_mult = {1: 1.0, 2: 1.5, 3: 2.5, 4: 4.0}.get(club.tier, 1.0)

        # Duration premium: 1 + (days / 365) * 1.8
        duration_mult = 1.0 + (days / 365) * 1.8

        # Demand factor
        price = base_price * days * tier_mult * duration_mult * self.demand_factor

        return round(price, 6)

    # ── Commentary Integration ───────────────────────────────────────────

    def get_sponsor_mention(self, club_id: int, event_type: str = "goal") -> str | None:
        """Get an organic sponsor mention for LLM commentary.

        Called by llm_commentary.py when generating match narration.
        Returns a natural-sounding sponsor line, or None if no sponsors.

        Args:
            club_id: The club whose sponsors to mention.
            event_type: Type of event ("goal", "save", "halftime", "fulltime").

        Returns:
            A sponsor mention string, or None.
        """
        active = self.get_active_slots(club_id)
        if not active:
            return None

        # Pick a random sponsor (weighted towards higher-paying ones)
        import random
        slot = random.choice(active)
        brand = slot.brand_name or "our sponsors"

        templates = {
            "goal": [
                f"What a moment — brought to you by {brand}!",
                f"The fans behind the {brand} hoarding are going wild!",
                f"That goal right in front of the {brand} advertising board!",
            ],
            "save": [
                f"Brilliant save — the keeper right under the {brand} board!",
                f"Denied! The {brand}-sponsored end erupts!",
            ],
            "halftime": [
                f"Half-time here, and a reminder this match is brought to you by {brand}.",
                f"Time for a break — check out {brand}, proud stadium partners.",
            ],
            "fulltime": [
                f"Full time! A great advertisement for the game — and for {brand}.",
                f"That's the final whistle. Thanks to {brand} for their support.",
            ],
        }

        lines = templates.get(event_type, templates["goal"])
        return random.choice(lines)

    def get_all_sponsor_names(self, club_id: int) -> list[str]:
        """Get list of all active sponsor brand names for a club."""
        return [s.brand_name for s in self.get_active_slots(club_id) if s.brand_name]

    # ── Revenue Reporting ────────────────────────────────────────────────

    def get_revenue_report(self) -> dict[str, Any]:
        """Generate a revenue report across all clubs."""
        report: dict[str, Any] = {
            "total_clubs": len(self.clubs),
            "total_active_slots": 0,
            "total_available_slots": 0,
            "global_occupancy_rate": 0.0,
            "demand_factor": self.demand_factor,
            "viewer_count": self.viewer_count,
            "clubs": [],
        }

        total_active = 0
        total_possible = 0

        for club in self.clubs.values():
            active_count = len(club.active_slots)
            total_active += active_count
            total_possible += club.max_slots

            report["clubs"].append({
                "club_id": club.club_id,
                "club_name": club.club_name,
                "tier": TIER_NAMES.get(club.tier, "Unknown"),
                "active_slots": active_count,
                "max_slots": club.max_slots,
                "occupancy_rate": f"{club.occupancy_rate:.1%}",
                "available_positions": club.available_positions,
                "sponsors": self.get_all_sponsor_names(club.club_id),
            })

        report["total_active_slots"] = total_active
        report["total_available_slots"] = total_possible - total_active
        if total_possible > 0:
            report["global_occupancy_rate"] = f"{total_active / total_possible:.1%}"

        return report

    # ── Cache Persistence ────────────────────────────────────────────────

    def save_cache(self) -> None:
        """Save current state to local cache file."""
        data: dict[str, Any] = {
            "viewer_count": self.viewer_count,
            "demand_factor": self.demand_factor,
            "clubs": {},
        }

        for cid, club in self.clubs.items():
            data["clubs"][str(cid)] = {
                "club_name": club.club_name,
                "club_code": club.club_code,
                "tier": club.tier,
                "max_slots": club.max_slots,
                "slots": [
                    {
                        "slot_id": s.slot_id,
                        "club_id": s.club_id,
                        "position": s.position,
                        "content_uri": s.content_uri,
                        "brand_name": s.brand_name,
                        "brand_address": s.brand_address,
                        "expires_at": s.expires_at,
                        "paid_amount_wei": s.paid_amount_wei,
                        "is_active": s.is_active,
                    }
                    for s in club.slots
                ],
            }

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(data, indent=2))
        logger.info("Saved hoarding cache → %s", self.cache_path)

    def _load_cache(self) -> None:
        """Load state from local cache file."""
        try:
            data = json.loads(self.cache_path.read_text())
            self.viewer_count = data.get("viewer_count", 0)
            self.demand_factor = data.get("demand_factor", 1.0)

            for cid_str, club_data in data.get("clubs", {}).items():
                cid = int(cid_str)
                club = self.register_club(
                    club_id=cid,
                    club_name=club_data["club_name"],
                    club_code=club_data["club_code"],
                    tier=club_data.get("tier", 1),
                    max_slots=club_data.get("max_slots", 12),
                )
                for sd in club_data.get("slots", []):
                    slot = HoardingSlot(
                        slot_id=sd["slot_id"],
                        club_id=sd["club_id"],
                        position=sd["position"],
                        content_uri=sd["content_uri"],
                        brand_name=sd.get("brand_name", ""),
                        brand_address=sd.get("brand_address", ""),
                        expires_at=sd.get("expires_at", 0),
                        paid_amount_wei=sd.get("paid_amount_wei", 0),
                        is_active=sd.get("is_active", True),
                    )
                    club.slots.append(slot)

            logger.info("Loaded hoarding cache from %s — %d clubs", self.cache_path, len(self.clubs))
        except Exception as e:
            logger.warning("Failed to load hoarding cache: %s", e)
