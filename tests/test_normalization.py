"""Tests for name normalization pipeline."""

import pytest

from swos420.normalization.pipeline import (
    extract_surname,
    generate_display_name,
    generate_display_name_with_dedup,
    has_accents,
    normalize_full_name,
    transliterate_fallback,
)


class TestNormalizeFullName:
    def test_basic(self):
        assert normalize_full_name("  Erling Haaland  ") == "Erling Haaland"

    def test_collapse_spaces(self):
        assert normalize_full_name("Kylian  Mbappé   Lottin") == "Kylian Mbappé Lottin"

    def test_preserve_accents(self):
        result = normalize_full_name("Ousmane Dembélé")
        assert "é" in result

    def test_unicode_normalization(self):
        # NFC composed form
        name = normalize_full_name("Dembélé")
        assert len(name) == 7  # should be composed, not decomposed

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_full_name("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            normalize_full_name("   ")


class TestExtractSurname:
    def test_multi_word(self):
        assert extract_surname("Erling Braut Haaland") == "Haaland"

    def test_single_word(self):
        assert extract_surname("Pelé") == "Pelé"

    def test_hyphenated(self):
        assert extract_surname("Trent Alexander-Arnold") == "Alexander-Arnold"


class TestGenerateDisplayName:
    def test_basic_surname(self):
        name = generate_display_name("Erling Braut Haaland")
        assert name == "HAALAND"

    def test_uppercase(self):
        name = generate_display_name("Kylian Mbappé")
        assert name == name.upper()

    def test_max_length(self):
        name = generate_display_name("Lamine Yamal Nasraoui Ebana")
        assert len(name) <= 15

    def test_accents_preserved_if_short(self):
        name = generate_display_name("Ousmane Dembélé")
        assert name == "DEMBÉLÉ"

    def test_prefer_short_name(self):
        name = generate_display_name(
            "Vinícius José Paixão de Oliveira Júnior",
            prefer_short_name="Vinícius Jr",
        )
        assert name == "VINÍCIUS JR"

    def test_long_name_truncated(self):
        name = generate_display_name("Superlongplayernamethatexceedslimit")
        assert len(name) <= 15


class TestDisplayNameDedup:
    def test_no_clash(self):
        name = generate_display_name_with_dedup("Erling Haaland")
        assert name == "HAALAND"

    def test_with_clash_adds_club(self):
        existing = {"SILVA"}
        name = generate_display_name_with_dedup(
            "Bernardo Silva", club_code="MCI", existing_names=existing
        )
        assert "MCI" in name

    def test_with_clash_adds_number(self):
        existing = {"SILVA", "SILVA MCI"}
        name = generate_display_name_with_dedup(
            "Bernardo Silva", club_code="MCI", shirt_number=20, existing_names=existing
        )
        assert "20" in name


class TestTransliterate:
    def test_accents_removed(self):
        assert transliterate_fallback("Dembélé") == "Dembele"

    def test_umlaut(self):
        assert transliterate_fallback("Müller") == "Muller"

    def test_ascii_unchanged(self):
        assert transliterate_fallback("Kane") == "Kane"


class TestHasAccents:
    def test_with_accents(self):
        assert has_accents("Mbappé") is True

    def test_without_accents(self):
        assert has_accents("Kane") is False
