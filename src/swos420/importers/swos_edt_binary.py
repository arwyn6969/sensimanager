"""Binary reader/writer for SWOS 96/97 .EDT team data files.

Parses the native game binary format — 684 bytes per team, 38 bytes per player.
Skills are packed as 4-bit nibbles within a 5-byte block.

Format reference:
    https://swoes.info — Whiteulver SWOS Data Editor specification
    https://github.com/anoxic83/AG_SWSEdt — Delphi/Pascal reference impl

Usage:
    from swos420.importers.swos_edt_binary import read_edt, write_edt

    teams = read_edt("path/to/TEAM.EDT")
    write_edt(teams, "path/to/TEAM_OUT.EDT")
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────
TEAM_BLOCK_SIZE = 684
TEAM_HEADER_SIZE = 76
PLAYER_RECORD_SIZE = 38
PLAYERS_PER_TEAM = 16
PLAYER_NAME_MAX = 22  # 22 chars + null terminator in 23 bytes
TEAM_NAME_MAX = 15     # 15 chars + null in 16 bytes
COACH_NAME_MAX = 23    # 23 chars + null in 24 bytes

# Skill order in the packed nibble block
SKILL_ORDER = ("passing", "velocity", "heading", "tackling",
               "control", "speed", "finishing")

# SWOS position encoding (bits 5-7 of position/hair byte)
POSITION_MAP = {
    0: "GK",
    1: "RB",
    2: "LB",
    3: "CB",
    4: "RW",
    5: "LW",
    6: "RM",
    7: "LM",
    8: "CM",
    9: "AM",   # Attacking midfield
    10: "RF",   # Right forward
    11: "LF",   # Left forward
    12: "CF",
    13: "ST",
    14: "ST",   # Second striker variant
    15: "SW",   # Sweeper
}
POSITION_MAP_REVERSE = {v: k for k, v in POSITION_MAP.items()}
# Handle duplicates — prefer lower index
POSITION_MAP_REVERSE["ST"] = 13


# ── Data Classes ─────────────────────────────────────────────────────────

@dataclass
class EdtPlayer:
    """A single player from an EDT file."""

    name: str = ""
    nationality: int = 0
    shirt_number: int = 1
    position: str = "CM"
    face_type: int = 0      # bits 0-4 of position/hair byte
    skills: dict[str, int] = field(default_factory=lambda: {
        s: 3 for s in SKILL_ORDER
    })
    value: int = 0           # 0-15 packed in nibble pair (12-bit)
    cards_injuries: int = 0  # career mode byte
    league_goals: int = 0
    cup_goals: int = 0
    unknown_bytes: bytes = b"\x00\x00\x00"  # trailing 3 career bytes


@dataclass
class EdtKitColors:
    """5-byte kit colour definition."""

    shirt_type: int = 0
    color1: int = 0
    color2: int = 0
    short_color: int = 0
    sock_color: int = 0

    def to_bytes(self) -> bytes:
        return bytes([self.shirt_type, self.color1, self.color2,
                      self.short_color, self.sock_color])

    @classmethod
    def from_bytes(cls, data: bytes) -> EdtKitColors:
        return cls(
            shirt_type=data[0], color1=data[1], color2=data[2],
            short_color=data[3], sock_color=data[4],
        )


@dataclass
class EdtTeam:
    """A team from an EDT file — 684 bytes total."""

    country: int = 0
    team_index: int = 0
    general_number: int = 0
    name: str = "Unknown"
    tactic_index: int = 0
    division: int = 0
    home_kit: EdtKitColors = field(default_factory=EdtKitColors)
    away_kit: EdtKitColors = field(default_factory=EdtKitColors)
    coach_name: str = "Coach"
    player_order: list[int] = field(default_factory=lambda: list(range(16)))
    players: list[EdtPlayer] = field(default_factory=list)
    unknown_byte_4: int = 0
    unknown_bytes_21_23: bytes = b"\x00\x00\x00"


# ── Skill Packing ────────────────────────────────────────────────────────

def _pack_skills_value(skills: dict[str, int], value: int) -> bytes:
    """Pack 7 skills + value into 5 bytes (10 nibbles = 40 bits).

    Layout (big-endian nibble order):
        byte 0: [passing high][velocity high]
        byte 1: [heading high][tackling high]
        byte 2: [control high][speed high]
        byte 3: [finishing high][value_hi]
        byte 4: [value_mid][value_lo]  (12-bit value across 3 nibbles?)

    NOTE: The exact nibble packing varies between SWOS versions.
    This implementation follows the most common AG_SWSEdt convention:
        7 skills as nibbles (28 bits) + value as 12-bit int (12 bits) = 40 bits.
    """
    nibbles = []
    for skill_name in SKILL_ORDER:
        nibbles.append(min(15, max(0, skills.get(skill_name, 3))))

    # Value as 12-bit (3 nibbles)
    val = min(4095, max(0, value))
    nibbles.append((val >> 8) & 0x0F)
    nibbles.append((val >> 4) & 0x0F)
    nibbles.append(val & 0x0F)

    # Pack 10 nibbles into 5 bytes
    result = bytearray(5)
    for i in range(5):
        hi = nibbles[i * 2]
        lo = nibbles[i * 2 + 1]
        result[i] = (hi << 4) | lo
    return bytes(result)


def _unpack_skills_value(data: bytes) -> tuple[dict[str, int], int]:
    """Unpack 5 bytes into 7 skills + 12-bit value."""
    nibbles = []
    for byte_val in data[:5]:
        nibbles.append((byte_val >> 4) & 0x0F)
        nibbles.append(byte_val & 0x0F)

    skills = {}
    for i, skill_name in enumerate(SKILL_ORDER):
        skills[skill_name] = nibbles[i]

    # Value from nibbles 7, 8, 9 (12-bit)
    value = (nibbles[7] << 8) | (nibbles[8] << 4) | nibbles[9]
    return skills, value


# ── Position/Hair Byte ───────────────────────────────────────────────────

def _pack_position_face(position: str, face_type: int) -> int:
    """Pack position (bits 5-7) and face/hair (bits 0-4) into 1 byte."""
    pos_code = POSITION_MAP_REVERSE.get(position, 8)  # default CM
    return ((pos_code & 0x0F) << 4) | (face_type & 0x0F)


def _unpack_position_face(byte_val: int) -> tuple[str, int]:
    """Unpack position and face/hair from 1 byte."""
    pos_code = (byte_val >> 4) & 0x0F
    face_type = byte_val & 0x0F
    position = POSITION_MAP.get(pos_code, "CM")
    return position, face_type


# ── String I/O ───────────────────────────────────────────────────────────

def _read_string(data: bytes, max_len: int) -> str:
    """Read a null-terminated ASCII string from fixed-size field."""
    end = data.find(b"\x00")
    if end == -1:
        end = max_len
    return data[:end].decode("ascii", errors="replace").strip()


def _write_string(text: str, field_size: int) -> bytes:
    """Write a null-terminated ASCII string into a fixed-size field."""
    encoded = text[:field_size - 1].encode("ascii", errors="replace")
    return encoded.ljust(field_size, b"\x00")


# ── Player I/O ───────────────────────────────────────────────────────────

def _read_player(data: bytes) -> EdtPlayer:
    """Parse 38 bytes into an EdtPlayer."""
    assert len(data) >= PLAYER_RECORD_SIZE, f"Need {PLAYER_RECORD_SIZE}B, got {len(data)}B"

    nationality = data[0]
    _unknown1 = data[1]
    shirt_number = data[2]
    name = _read_string(data[3:25], PLAYER_NAME_MAX)
    cards_injuries = data[25]
    position, face_type = _unpack_position_face(data[26])
    _unknown2 = data[27]
    skills, value = _unpack_skills_value(data[28:33])
    league_goals = data[33]
    cup_goals = data[34]
    unknown_tail = bytes(data[35:38])

    return EdtPlayer(
        name=name,
        nationality=nationality,
        shirt_number=shirt_number,
        position=position,
        face_type=face_type,
        skills=skills,
        value=value,
        cards_injuries=cards_injuries,
        league_goals=league_goals,
        cup_goals=cup_goals,
        unknown_bytes=unknown_tail,
    )


def _write_player(player: EdtPlayer) -> bytes:
    """Serialize an EdtPlayer to 38 bytes."""
    buf = bytearray(PLAYER_RECORD_SIZE)
    buf[0] = player.nationality & 0xFF
    buf[1] = 0  # unknown
    buf[2] = player.shirt_number & 0xFF
    buf[3:25] = _write_string(player.name, PLAYER_NAME_MAX + 1)[:22]  # 22 bytes in field
    buf[25] = player.cards_injuries & 0xFF
    buf[26] = _pack_position_face(player.position, player.face_type)
    buf[27] = 0  # unknown
    buf[28:33] = _pack_skills_value(player.skills, player.value)
    buf[33] = player.league_goals & 0xFF
    buf[34] = player.cup_goals & 0xFF
    buf[35:38] = player.unknown_bytes[:3]
    return bytes(buf)


# ── Team I/O ─────────────────────────────────────────────────────────────

def _read_team(data: bytes) -> EdtTeam:
    """Parse 684 bytes into an EdtTeam."""
    assert len(data) >= TEAM_BLOCK_SIZE, f"Need {TEAM_BLOCK_SIZE}B, got {len(data)}B"

    country = data[0]
    team_index = data[1]
    general_number = struct.unpack(">H", data[2:4])[0]  # big-endian uint16
    unknown_4 = data[4]
    name = _read_string(data[5:21], TEAM_NAME_MAX + 1)
    unknown_21_23 = bytes(data[21:24])
    tactic_index = data[24]
    division = data[25]
    home_kit = EdtKitColors.from_bytes(data[26:31])
    away_kit = EdtKitColors.from_bytes(data[31:36])
    coach_name = _read_string(data[36:60], COACH_NAME_MAX + 1)
    player_order = list(data[60:76])

    players = []
    for i in range(PLAYERS_PER_TEAM):
        offset = TEAM_HEADER_SIZE + i * PLAYER_RECORD_SIZE
        player_data = data[offset:offset + PLAYER_RECORD_SIZE]
        players.append(_read_player(player_data))

    return EdtTeam(
        country=country,
        team_index=team_index,
        general_number=general_number,
        name=name,
        tactic_index=tactic_index,
        division=division,
        home_kit=home_kit,
        away_kit=away_kit,
        coach_name=coach_name,
        player_order=player_order,
        players=players,
        unknown_byte_4=unknown_4,
        unknown_bytes_21_23=unknown_21_23,
    )


def _write_team(team: EdtTeam) -> bytes:
    """Serialize an EdtTeam to 684 bytes."""
    buf = bytearray(TEAM_BLOCK_SIZE)
    buf[0] = team.country & 0xFF
    buf[1] = team.team_index & 0xFF
    struct.pack_into(">H", buf, 2, team.general_number)
    buf[4] = team.unknown_byte_4 & 0xFF
    buf[5:21] = _write_string(team.name, TEAM_NAME_MAX + 1)
    buf[21:24] = team.unknown_bytes_21_23[:3]
    buf[24] = team.tactic_index & 0xFF
    buf[25] = team.division & 0xFF
    buf[26:31] = team.home_kit.to_bytes()
    buf[31:36] = team.away_kit.to_bytes()
    buf[36:60] = _write_string(team.coach_name, COACH_NAME_MAX + 1)
    for i, idx in enumerate(team.player_order[:16]):
        buf[60 + i] = idx & 0xFF

    for i, player in enumerate(team.players[:PLAYERS_PER_TEAM]):
        offset = TEAM_HEADER_SIZE + i * PLAYER_RECORD_SIZE
        buf[offset:offset + PLAYER_RECORD_SIZE] = _write_player(player)

    # Pad remaining slots with empty players
    for i in range(len(team.players), PLAYERS_PER_TEAM):
        offset = TEAM_HEADER_SIZE + i * PLAYER_RECORD_SIZE
        buf[offset:offset + PLAYER_RECORD_SIZE] = _write_player(EdtPlayer())

    return bytes(buf)


# ── Public API ───────────────────────────────────────────────────────────

def read_edt(path: str | Path) -> list[EdtTeam]:
    """Read an EDT file and return all teams.

    Args:
        path: Path to the .EDT file.

    Returns:
        List of EdtTeam objects.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file is malformed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"EDT file not found: {path}")

    data = path.read_bytes()
    if len(data) < 2:
        raise ValueError(f"EDT file too small: {len(data)} bytes")

    num_teams = struct.unpack("<H", data[:2])[0]  # little-endian team count
    expected_size = 2 + num_teams * TEAM_BLOCK_SIZE
    if len(data) < expected_size:
        raise ValueError(
            f"EDT file truncated: expected {expected_size} bytes for "
            f"{num_teams} teams, got {len(data)}"
        )

    teams = []
    for i in range(num_teams):
        offset = 2 + i * TEAM_BLOCK_SIZE
        team_data = data[offset:offset + TEAM_BLOCK_SIZE]
        teams.append(_read_team(team_data))

    return teams


def write_edt(teams: list[EdtTeam], path: str | Path) -> None:
    """Write teams to an EDT file.

    Args:
        teams: List of EdtTeam objects to write.
        path: Output path for the .EDT file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    buf = bytearray()
    buf.extend(struct.pack("<H", len(teams)))

    for team in teams:
        buf.extend(_write_team(team))

    path.write_bytes(bytes(buf))


# ── Conversion Helpers ───────────────────────────────────────────────────

def edt_player_to_dict(player: EdtPlayer) -> dict:
    """Convert an EdtPlayer to a flat dictionary for integration.

    Returns a dict compatible with SWOSPlayer construction.
    """
    return {
        "full_name": player.name,
        "position": player.position,
        "shirt_number": player.shirt_number,
        "nationality_code": player.nationality,
        "skills": {k: min(7, v // 2) for k, v in player.skills.items()},
        "skills_display": dict(player.skills),  # 0-15 scale
        "face_type": player.face_type,
        "value": player.value,
    }


def dict_to_edt_player(data: dict) -> EdtPlayer:
    """Convert a flat dictionary back to an EdtPlayer.

    Accepts skills in 0-7 stored range and converts to 0-15 for EDT.
    """
    skills_stored = data.get("skills", {})
    skills_display = {}
    for skill_name in SKILL_ORDER:
        stored_val = skills_stored.get(skill_name, 3)
        skills_display[skill_name] = min(15, stored_val * 2)

    return EdtPlayer(
        name=data.get("full_name", "")[:PLAYER_NAME_MAX],
        nationality=data.get("nationality_code", 0),
        shirt_number=data.get("shirt_number", 1),
        position=data.get("position", "CM"),
        face_type=data.get("face_type", 0),
        skills=skills_display,
        value=data.get("value", 0),
    )
