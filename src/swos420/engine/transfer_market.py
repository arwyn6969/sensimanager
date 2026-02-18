"""Transfer Market — sealed-bid auction system for player transfers.

Handles transfer windows, bid submission, resolution, budget validation,
squad-size limits, and free agent generation. Used by AI managers and
the PettingZoo environment action space.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

from swos420.models.player import (
    SWOSPlayer, Skills, Position, generate_base_id, SKILL_NAMES,
    SWOS_SQUAD_SIZE, hex_tier_value,
)

logger = logging.getLogger(__name__)

# Squad constraints
MIN_SQUAD_SIZE = SWOS_SQUAD_SIZE  # Authentic SWOS 16-player squads
MAX_SQUAD_SIZE = 30


@dataclass
class TransferBid:
    """A single sealed bid for a listed player."""
    buyer_code: str
    player_id: str
    amount: int
    accepted: bool = False


@dataclass
class TransferListing:
    """A player listed on the transfer market."""
    seller_code: str
    player_id: str
    player_name: str
    reserve_price: int
    position: str  # Position value string
    age: int
    skill_total: int
    bids: list[TransferBid] = field(default_factory=list)


@dataclass
class TransferResult:
    """Outcome of a resolved transfer."""
    player_id: str
    player_name: str
    from_club: str
    to_club: str
    fee: int
    success: bool
    reason: str = ""


class TransferMarket:
    """Manages the transfer window lifecycle.

    Usage:
        market = TransferMarket()
        market.open_window(all_teams_state)
        market.list_player("MCI", player_id, 5_000_000)
        market.place_bid("ARS", player_id, 6_000_000)
        results = market.resolve_window()  # highest bid wins
    """

    def __init__(self) -> None:
        self.listings: dict[str, TransferListing] = {}  # player_id → listing
        self.is_open: bool = False
        self._team_budgets: dict[str, int] = {}  # code → budget
        self._team_squad_sizes: dict[str, int] = {}  # code → current squad count
        self._team_wage_bills: dict[str, int] = {}  # code → weekly wage total
        self._results: list[TransferResult] = []

    def open_window(
        self,
        team_budgets: dict[str, int],
        team_squad_sizes: dict[str, int],
        team_wage_bills: dict[str, int] | None = None,
    ) -> None:
        """Open a transfer window with current team financial state.

        Args:
            team_budgets: mapping of team_code → available transfer budget
            team_squad_sizes: mapping of team_code → current squad size
            team_wage_bills: mapping of team_code → weekly wage bill (optional)
        """
        self.listings.clear()
        self._results.clear()
        self._team_budgets = dict(team_budgets)
        self._team_squad_sizes = dict(team_squad_sizes)
        self._team_wage_bills = dict(team_wage_bills or {})
        self.is_open = True
        logger.info("Transfer window opened for %d clubs", len(team_budgets))

    def close_window(self) -> None:
        """Close the window without resolving (use resolve_window to close + resolve)."""
        self.is_open = False

    def list_player(
        self,
        seller_code: str,
        player: SWOSPlayer,
        reserve_price: int | None = None,
    ) -> bool:
        """List a player on the transfer market.

        Args:
            seller_code: Team code of the selling club.
            player: The player to list.
            reserve_price: Minimum acceptable bid. Defaults to 80% of current value.

        Returns:
            True if listed successfully.
        """
        if not self.is_open:
            logger.warning("Cannot list player: window is closed")
            return False

        if player.base_id in self.listings:
            logger.debug("Player %s already listed", player.display_name)
            return False

        # Don't let teams go below minimum squad size
        current_size = self._team_squad_sizes.get(seller_code, MIN_SQUAD_SIZE)
        if current_size <= MIN_SQUAD_SIZE:
            logger.debug("Cannot list %s: squad already at minimum (%d)",
                         player.display_name, current_size)
            return False

        if reserve_price is None:
            reserve_price = int(player.calculate_current_value() * 0.80)

        self.listings[player.base_id] = TransferListing(
            seller_code=seller_code,
            player_id=player.base_id,
            player_name=player.display_name,
            reserve_price=max(25_000, reserve_price),
            position=player.position.value,
            age=player.age,
            skill_total=player.skills.total,
        )
        logger.info("Listed %s (reserve: £%s)", player.display_name, f"{reserve_price:,}")
        return True

    def place_bid(self, buyer_code: str, player_id: str, amount: int) -> bool:
        """Submit a sealed bid for a listed player.

        Args:
            buyer_code: Team code of the buying club.
            player_id: Base ID of the target player.
            amount: Bid amount in £/$SENSI.

        Returns:
            True if bid accepted for consideration.
        """
        if not self.is_open:
            return False

        if player_id not in self.listings:
            logger.debug("Bid rejected: player %s not listed", player_id)
            return False

        listing = self.listings[player_id]

        # Can't bid on your own player
        if listing.seller_code == buyer_code:
            return False

        # Budget check
        budget = self._team_budgets.get(buyer_code, 0)
        if amount > budget:
            logger.debug("Bid rejected: %s budget £%s < bid £%s",
                         buyer_code, f"{budget:,}", f"{amount:,}")
            return False

        # Squad size check — can't exceed max
        buyer_size = self._team_squad_sizes.get(buyer_code, 0)
        if buyer_size >= MAX_SQUAD_SIZE:
            logger.debug("Bid rejected: %s squad full (%d)", buyer_code, buyer_size)
            return False

        # Below reserve is still recorded (might win if only bid)
        bid = TransferBid(buyer_code=buyer_code, player_id=player_id, amount=amount)
        listing.bids.append(bid)
        logger.debug("%s bids £%s for %s", buyer_code, f"{amount:,}", listing.player_name)
        return True

    def resolve_window(self) -> list[TransferResult]:
        """Resolve all listings: highest valid bid wins each player.

        Bids below reserve price are rejected unless there are no
        bids at or above reserve (in which case the player stays).

        Returns:
            List of TransferResult for each listing.
        """
        results: list[TransferResult] = []

        for player_id, listing in self.listings.items():
            if not listing.bids:
                results.append(TransferResult(
                    player_id=player_id,
                    player_name=listing.player_name,
                    from_club=listing.seller_code,
                    to_club="",
                    fee=0,
                    success=False,
                    reason="No bids received",
                ))
                continue

            # Sort bids by amount descending
            valid_bids = sorted(listing.bids, key=lambda b: b.amount, reverse=True)

            # Find highest bid that meets reserve and buyer still has budget
            winner = None
            for bid in valid_bids:
                if bid.amount < listing.reserve_price:
                    continue
                # Re-check budget (may have been spent on another player this window)
                if self._team_budgets.get(bid.buyer_code, 0) >= bid.amount:
                    if self._team_squad_sizes.get(bid.buyer_code, 0) < MAX_SQUAD_SIZE:
                        winner = bid
                        break

            if winner is None:
                results.append(TransferResult(
                    player_id=player_id,
                    player_name=listing.player_name,
                    from_club=listing.seller_code,
                    to_club="",
                    fee=0,
                    success=False,
                    reason="No bids met reserve price or budget constraints",
                ))
                continue

            # Execute transfer
            winner.accepted = True
            fee = winner.amount

            # Update budgets and squad sizes
            self._team_budgets[winner.buyer_code] = (
                self._team_budgets.get(winner.buyer_code, 0) - fee
            )
            self._team_budgets[listing.seller_code] = (
                self._team_budgets.get(listing.seller_code, 0) + fee
            )
            self._team_squad_sizes[winner.buyer_code] = (
                self._team_squad_sizes.get(winner.buyer_code, 0) + 1
            )
            self._team_squad_sizes[listing.seller_code] = (
                self._team_squad_sizes.get(listing.seller_code, 0) - 1
            )

            results.append(TransferResult(
                player_id=player_id,
                player_name=listing.player_name,
                from_club=listing.seller_code,
                to_club=winner.buyer_code,
                fee=fee,
                success=True,
            ))

            logger.info(
                "TRANSFER: %s → %s for £%s (from %s)",
                listing.player_name, winner.buyer_code, f"{fee:,}", listing.seller_code,
            )

        self.is_open = False
        self._results = results
        return results

    @property
    def available_players(self) -> list[TransferListing]:
        """All currently listed players, sorted by skill total descending."""
        return sorted(self.listings.values(), key=lambda x: x.skill_total, reverse=True)

    @property
    def results(self) -> list[TransferResult]:
        """Results from the last resolved window."""
        return list(self._results)

    def get_listing(self, player_id: str) -> TransferListing | None:
        """Get a specific listing by player ID."""
        return self.listings.get(player_id)


def generate_free_agents(
    n: int = 10,
    season: str = "25/26",
    age_range: tuple[int, int] = (18, 33),
    skill_range: tuple[int, int] = (0, 5),  # SWOS 0-7 stored range (free agents are weaker)
) -> list[SWOSPlayer]:
    """Generate unemployed free agent players for the market.

    Skills use authentic SWOS 0-7 stored range.

    Args:
        n: Number of free agents to generate.
        season: Season string for base_id generation.
        age_range: (min_age, max_age) inclusive.
        skill_range: (min_skill, max_skill) for random skill values (0-7).

    Returns:
        List of SWOSPlayer with club_name="Free Agent".
    """
    positions = list(Position)
    agents: list[SWOSPlayer] = []

    for i in range(n):
        age = random.randint(*age_range)
        pos = random.choice(positions)
        skill_vals = {
            s: random.randint(*skill_range) for s in SKILL_NAMES
        }

        # Youth players get a slight bias toward higher potential
        if age <= 21:
            best_skill = max(skill_vals, key=skill_vals.get)  # type: ignore
            skill_vals[best_skill] = min(7, skill_vals[best_skill] + random.randint(1, 2))

        # Use hex-tier value table for authentic stepped economy
        skill_total = sum(skill_vals.values())
        age_mod = max(0.5, 1.0 - (age - 25) * 0.03)
        base_value = int(hex_tier_value(skill_total) * age_mod)

        player = SWOSPlayer(
            base_id=generate_base_id(f"fa_{i}_{random.randint(1, 999999)}", season),
            full_name=f"Free Agent {i+1}",
            display_name=f"FA {i+1:03d}",
            position=pos,
            skills=Skills(**skill_vals),
            age=age,
            base_value=max(25_000, int(base_value)),
            club_name="Free Agent",
            club_code="FA",
        )
        agents.append(player)

    return agents
