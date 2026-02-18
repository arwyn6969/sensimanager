"""Fixture generator — round-robin scheduling for league seasons.

Uses the circle method to produce balanced home/away fixtures where
every team plays every other team twice (home and away).
"""

from __future__ import annotations

import random
from typing import TypeVar

T = TypeVar("T")


def generate_round_robin(teams: list[T], shuffle: bool = True) -> list[list[tuple[T, T]]]:
    """Generate a full round-robin schedule (home & away).

    Args:
        teams: List of team identifiers (codes, names, or objects).
        shuffle: Randomize team order before generating fixtures.

    Returns:
        List of matchdays, where each matchday is a list of (home, away) tuples.
        Total matchdays = (n-1) * 2 for n teams.

    Raises:
        ValueError: If fewer than 2 teams provided.
    """
    if len(teams) < 2:
        raise ValueError(f"Need at least 2 teams, got {len(teams)}")

    team_list = list(teams)
    if shuffle:
        random.shuffle(team_list)

    # Pad to even number with a "BYE" sentinel
    has_bye = len(team_list) % 2 != 0
    if has_bye:
        team_list.append(None)  # type: ignore

    n = len(team_list)
    half = n // 2

    # First half: generate (n-1) rounds using circle method
    first_half: list[list[tuple[T, T]]] = []
    rotation = list(team_list)

    for _ in range(n - 1):
        matchday = []
        for i in range(half):
            home = rotation[i]
            away = rotation[n - 1 - i]
            if home is not None and away is not None:
                matchday.append((home, away))
        first_half.append(matchday)

        # Rotate: fix position 0, rotate rest clockwise
        rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]

    # Second half: reverse home/away
    second_half: list[list[tuple[T, T]]] = []
    for matchday in first_half:
        second_half.append([(away, home) for home, away in matchday])

    return first_half + second_half


def matches_per_season(num_teams: int) -> int:
    """Calculate total matches per team in a double round-robin."""
    return (num_teams - 1) * 2


def total_matchdays(num_teams: int) -> int:
    """Total matchdays in a double round-robin season."""
    n = num_teams if num_teams % 2 == 0 else num_teams + 1
    return (n - 1) * 2
