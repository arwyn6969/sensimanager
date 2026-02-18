"""Tests for SWOS EDT binary reader/writer (swos_edt_binary.py)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from swos420.importers.swos_edt_binary import (
    PLAYER_RECORD_SIZE,
    PLAYERS_PER_TEAM,
    SKILL_ORDER,
    TEAM_BLOCK_SIZE,
    EdtKitColors,
    EdtPlayer,
    EdtTeam,
    _pack_position_face,
    _pack_skills_value,
    _read_player,
    _unpack_position_face,
    _unpack_skills_value,
    _write_player,
    dict_to_edt_player,
    edt_player_to_dict,
    read_edt,
    write_edt,
)


# ── Skill Packing Tests ─────────────────────────────────────────────────

class TestSkillPacking:
    """Tests for 4-bit nibble skill packing/unpacking."""

    def test_round_trip_all_zeros(self):
        skills = {s: 0 for s in SKILL_ORDER}
        packed = _pack_skills_value(skills, 0)
        assert len(packed) == 5
        unpacked_skills, unpacked_value = _unpack_skills_value(packed)
        assert unpacked_skills == skills
        assert unpacked_value == 0

    def test_round_trip_all_max(self):
        skills = {s: 15 for s in SKILL_ORDER}
        packed = _pack_skills_value(skills, 4095)
        unpacked_skills, unpacked_value = _unpack_skills_value(packed)
        assert unpacked_skills == skills
        assert unpacked_value == 4095

    def test_round_trip_mixed(self):
        skills = {
            "passing": 7, "velocity": 12, "heading": 3, "tackling": 9,
            "control": 15, "speed": 0, "finishing": 5,
        }
        packed = _pack_skills_value(skills, 2048)
        unpacked_skills, unpacked_value = _unpack_skills_value(packed)
        assert unpacked_skills == skills
        assert unpacked_value == 2048

    def test_clamps_above_15(self):
        skills = {s: 20 for s in SKILL_ORDER}
        packed = _pack_skills_value(skills, 5000)
        unpacked_skills, unpacked_value = _unpack_skills_value(packed)
        for val in unpacked_skills.values():
            assert 0 <= val <= 15
        assert 0 <= unpacked_value <= 4095

    def test_clamps_below_zero(self):
        skills = {s: -5 for s in SKILL_ORDER}
        packed = _pack_skills_value(skills, -10)
        unpacked_skills, unpacked_value = _unpack_skills_value(packed)
        for val in unpacked_skills.values():
            assert val == 0
        assert unpacked_value == 0

    def test_packed_size_always_5(self):
        for v in [0, 1, 100, 4095]:
            skills = {s: v % 16 for s in SKILL_ORDER}
            assert len(_pack_skills_value(skills, v)) == 5


# ── Position/Face Byte Tests ────────────────────────────────────────────

class TestPositionFace:
    """Tests for position/hair byte packing."""

    def test_round_trip_gk(self):
        packed = _pack_position_face("GK", 5)
        pos, face = _unpack_position_face(packed)
        assert pos == "GK"
        assert face == 5

    def test_round_trip_cm(self):
        packed = _pack_position_face("CM", 0)
        pos, face = _unpack_position_face(packed)
        assert pos == "CM"
        assert face == 0

    def test_round_trip_st(self):
        packed = _pack_position_face("ST", 15)
        pos, face = _unpack_position_face(packed)
        assert pos == "ST"
        assert face == 15

    def test_unknown_position_defaults_to_cm(self):
        packed = _pack_position_face("CDM", 0)  # CDM not in SWOS
        pos, _ = _unpack_position_face(packed)
        assert pos == "CM"  # default fallback


# ── Player I/O Tests ─────────────────────────────────────────────────────

class TestPlayerIO:
    """Tests for 38-byte player serialization."""

    def _make_player(self, **overrides) -> EdtPlayer:
        defaults = {
            "name": "R.Van Basten",
            "nationality": 10,
            "shirt_number": 9,
            "position": "ST",
            "face_type": 3,
            "skills": {s: 14 for s in SKILL_ORDER},
            "value": 1500,
        }
        defaults.update(overrides)
        return EdtPlayer(**defaults)

    def test_round_trip_player(self):
        player = self._make_player()
        data = _write_player(player)
        assert len(data) == PLAYER_RECORD_SIZE

        restored = _read_player(data)
        assert restored.name == player.name
        assert restored.shirt_number == player.shirt_number
        assert restored.position == player.position
        assert restored.skills == player.skills
        assert restored.nationality == player.nationality

    def test_name_truncation(self):
        long_name = "Alexandros Papadopoulos-Smith Junior"
        player = self._make_player(name=long_name)
        data = _write_player(player)
        restored = _read_player(data)
        assert len(restored.name) <= 22

    def test_empty_name(self):
        player = self._make_player(name="")
        data = _write_player(player)
        restored = _read_player(data)
        assert restored.name == ""

    def test_career_fields_preserved(self):
        player = self._make_player(
            league_goals=15, cup_goals=7,
            cards_injuries=3,
        )
        data = _write_player(player)
        restored = _read_player(data)
        assert restored.league_goals == 15
        assert restored.cup_goals == 7
        assert restored.cards_injuries == 3


# ── Team I/O Tests ───────────────────────────────────────────────────────

class TestTeamIO:
    """Tests for 684-byte team serialization."""

    def _make_team(self, num_players: int = 16) -> EdtTeam:
        players = []
        for i in range(num_players):
            players.append(EdtPlayer(
                name=f"Player {i+1}",
                shirt_number=i + 1,
                position="CM" if i > 0 else "GK",
                skills={s: 7 for s in SKILL_ORDER},
                value=100 + i,
            ))
        return EdtTeam(
            country=1,
            team_index=0,
            general_number=42,
            name="Test FC",
            tactic_index=2,
            division=1,
            coach_name="Sir Bobby",
            player_order=list(range(16)),
            players=players,
        )

    def test_write_creates_correct_size(self):
        from swos420.importers.swos_edt_binary import _write_team
        team = self._make_team()
        data = _write_team(team)
        assert len(data) == TEAM_BLOCK_SIZE

    def test_round_trip_team(self):
        from swos420.importers.swos_edt_binary import _read_team, _write_team
        team = self._make_team()
        data = _write_team(team)
        restored = _read_team(data)
        assert restored.name == "Test FC"
        assert restored.country == 1
        assert restored.general_number == 42
        assert restored.tactic_index == 2
        assert restored.coach_name == "Sir Bobby"
        assert len(restored.players) == PLAYERS_PER_TEAM
        assert restored.players[0].name == "Player 1"
        assert restored.players[0].position == "GK"
        assert restored.players[15].name == "Player 16"

    def test_partial_squad_pads_to_16(self):
        from swos420.importers.swos_edt_binary import _read_team, _write_team
        team = self._make_team(num_players=11)
        assert len(team.players) == 11
        data = _write_team(team)
        assert len(data) == TEAM_BLOCK_SIZE
        restored = _read_team(data)
        assert len(restored.players) == PLAYERS_PER_TEAM
        # Last 5 should be empty padding
        assert restored.players[15].name == ""


# ── File I/O Tests ───────────────────────────────────────────────────────

class TestFileIO:
    """Tests for EDT file read/write."""

    def _make_teams(self, count: int = 4) -> list[EdtTeam]:
        teams = []
        for i in range(count):
            players = [
                EdtPlayer(
                    name=f"Team{i+1} Player{j+1}",
                    shirt_number=j + 1,
                    position="GK" if j == 0 else "CM",
                    skills={s: (j + i) % 16 for s in SKILL_ORDER},
                    value=(i * 100) + j,
                )
                for j in range(16)
            ]
            teams.append(EdtTeam(
                name=f"Team {i+1}",
                country=i,
                team_index=i,
                general_number=i * 10,
                coach_name=f"Coach {i+1}",
                player_order=list(range(16)),
                players=players,
            ))
        return teams

    def test_round_trip_file(self, tmp_path):
        teams = self._make_teams(4)
        edt_path = tmp_path / "test.edt"
        write_edt(teams, edt_path)

        restored = read_edt(edt_path)
        assert len(restored) == 4
        assert restored[0].name == "Team 1"
        assert restored[3].name == "Team 4"
        assert restored[0].players[0].name == "Team1 Player1"
        assert restored[2].players[5].name == "Team3 Player6"

    def test_file_size_correct(self, tmp_path):
        teams = self._make_teams(8)
        edt_path = tmp_path / "test.edt"
        write_edt(teams, edt_path)
        file_size = edt_path.stat().st_size
        expected = 2 + 8 * TEAM_BLOCK_SIZE
        assert file_size == expected

    def test_single_team(self, tmp_path):
        teams = self._make_teams(1)
        edt_path = tmp_path / "single.edt"
        write_edt(teams, edt_path)
        restored = read_edt(edt_path)
        assert len(restored) == 1
        assert restored[0].name == "Team 1"

    def test_empty_teams(self, tmp_path):
        edt_path = tmp_path / "empty.edt"
        write_edt([], edt_path)
        restored = read_edt(edt_path)
        assert len(restored) == 0

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_edt("/nonexistent/path/team.edt")

    def test_truncated_file(self, tmp_path):
        edt_path = tmp_path / "truncated.edt"
        # Write header claiming 5 teams but only provide 1
        import struct
        data = struct.pack("<H", 5) + b"\x00" * TEAM_BLOCK_SIZE
        edt_path.write_bytes(data)
        with pytest.raises(ValueError, match="truncated"):
            read_edt(edt_path)

    def test_too_small_file(self, tmp_path):
        edt_path = tmp_path / "tiny.edt"
        edt_path.write_bytes(b"\x01")
        with pytest.raises(ValueError, match="too small"):
            read_edt(edt_path)

    def test_skills_preserved_across_file(self, tmp_path):
        """Verify nibble packing survives full file round-trip."""
        player = EdtPlayer(
            name="Skill Test",
            skills={
                "passing": 15, "velocity": 0, "heading": 7,
                "tackling": 8, "control": 3, "speed": 12, "finishing": 1,
            },
            value=3000,
        )
        team = EdtTeam(name="Skill FC", players=[player])
        edt_path = tmp_path / "skills.edt"
        write_edt([team], edt_path)

        restored = read_edt(edt_path)[0]
        assert restored.players[0].skills == player.skills
        assert restored.players[0].value == player.value


# ── Conversion Helper Tests ──────────────────────────────────────────────

class TestConversionHelpers:
    """Tests for EDT ↔ dict/SWOSPlayer conversions."""

    def test_edt_to_dict(self):
        player = EdtPlayer(
            name="Test Player",
            position="ST",
            shirt_number=9,
            skills={s: 14 for s in SKILL_ORDER},
            value=500,
        )
        d = edt_player_to_dict(player)
        assert d["full_name"] == "Test Player"
        assert d["position"] == "ST"
        # Skills should be halved (0-15 → 0-7)
        assert all(v == 7 for v in d["skills"].values())
        # Display skills should be preserved (0-15)
        assert all(v == 14 for v in d["skills_display"].values())

    def test_dict_to_edt(self):
        d = {
            "full_name": "Test Player",
            "position": "GK",
            "shirt_number": 1,
            "skills": {s: 5 for s in SKILL_ORDER},  # 0-7 stored
            "value": 200,
        }
        player = dict_to_edt_player(d)
        assert player.name == "Test Player"
        assert player.position == "GK"
        # Skills should be doubled (0-7 → 0-15)
        assert all(v == 10 for v in player.skills.values())

    def test_dict_round_trip(self):
        original = {
            "full_name": "Marco Van Basten",
            "position": "CF",
            "shirt_number": 9,
            "skills": {"passing": 6, "velocity": 7, "heading": 5,
                       "tackling": 2, "control": 7, "speed": 5, "finishing": 7},
            "value": 1000,
        }
        edt_player = dict_to_edt_player(original)
        back = edt_player_to_dict(edt_player)
        assert back["full_name"] == original["full_name"]
        assert back["position"] == original["position"]
        assert back["skills"] == original["skills"]


# ── Kit Colors Tests ─────────────────────────────────────────────────────

class TestKitColors:
    """Tests for kit colour serialization."""

    def test_round_trip(self):
        kit = EdtKitColors(shirt_type=3, color1=10, color2=5,
                          short_color=7, sock_color=2)
        data = kit.to_bytes()
        assert len(data) == 5
        restored = EdtKitColors.from_bytes(data)
        assert restored.shirt_type == 3
        assert restored.color1 == 10
        assert restored.color2 == 5
