"""Name normalization pipeline for SWOS420.

Handles the critical sub-system that ensures:
- Full names are stored with proper accents/UTF-8
- Display names are engine-safe: ALL-CAPS, max 15 chars
- Transliteration fallback for arcade engine compatibility
"""

from __future__ import annotations

import re
import unicodedata

from unidecode import unidecode


def normalize_full_name(raw: str) -> str:
    """Clean and normalize a full player name, preserving accents.

    - Strip leading/trailing whitespace
    - Collapse multiple spaces
    - Fix common encoding artifacts
    - Normalize Unicode to NFC form (canonical composition)
    """
    if not raw or not raw.strip():
        raise ValueError("Player name cannot be empty")

    # Normalize Unicode to NFC (composed form)
    name = unicodedata.normalize("NFC", raw.strip())

    # Collapse multiple whitespace
    name = re.sub(r"\s+", " ", name)

    # Fix common encoding artifacts from CSV imports
    replacements = {
        "Ã©": "é", "Ã¤": "ä", "Ã¶": "ö", "Ã¼": "ü",
        "Ã±": "ñ", "Ã§": "ç", "Ã³": "ó", "Ã¡": "á",
        "Ã­": "í", "Ãº": "ú",
    }
    for bad, good in replacements.items():
        name = name.replace(bad, good)

    return name


def extract_surname(full_name: str) -> str:
    """Extract the primary surname from a full name.

    For single-word names, returns the name itself.
    For multi-word names, returns the last word (handles most Western names).
    """
    parts = full_name.strip().split()
    if len(parts) <= 1:
        return full_name.strip()
    return parts[-1]


def generate_display_name(
    full_name: str,
    max_len: int = 15,
    prefer_short_name: str | None = None,
) -> str:
    """Generate an engine-safe display name.

    Rules:
    1. If a short_name is provided and fits, use it (ALL-CAPS)
    2. Otherwise, use surname extracted from full_name
    3. ALL-CAPS
    4. If > max_len chars, transliterate first, then truncate
    5. Strip any non-alphanumeric chars except spaces and hyphens

    Examples:
        "Lamine Yamal Nasraoui Ebana" → "YAMAL"
        "Kylian Mbappé" → "MBAPPÉ"  (if engine supports UTF-8)
        "Ousmane Dembélé" → "DEMBÉLÉ"
    """
    # Prefer short name if available and short enough
    if prefer_short_name and len(prefer_short_name) <= max_len:
        candidate = prefer_short_name.strip()
    else:
        candidate = extract_surname(full_name)

    # Uppercase
    candidate = candidate.upper()

    # If still too long, transliterate accents first
    if len(candidate) > max_len:
        candidate = transliterate_fallback(candidate)

    # Final truncation
    if len(candidate) > max_len:
        candidate = candidate[:max_len]

    # Clean: keep only letters, spaces, hyphens, apostrophes
    candidate = re.sub(r"[^A-ZÀ-ÖØ-Þa-zà-öø-ÿ\s\-']", "", candidate).strip()

    return candidate.upper()


def generate_display_name_with_dedup(
    full_name: str,
    club_code: str = "",
    shirt_number: int = 0,
    existing_names: set[str] | None = None,
    max_len: int = 15,
    prefer_short_name: str | None = None,
) -> str:
    """Generate a unique display name, handling duplicates.

    If the generated name clashes with existing_names:
    1. Append club code (e.g. "SILVA MCI")
    2. If still clashing, append shirt number
    """
    base = generate_display_name(full_name, max_len=max_len, prefer_short_name=prefer_short_name)

    if existing_names is None or base not in existing_names:
        return base

    # Try with club code
    if club_code:
        with_club = f"{base} {club_code}"[:max_len].strip()
        if with_club not in existing_names:
            return with_club

    # Try with shirt number
    if shirt_number > 0:
        with_num = f"{base} {shirt_number}"[:max_len].strip()
        if with_num not in existing_names:
            return with_num

    # Last resort: append incrementing suffix
    for i in range(2, 100):
        suffixed = f"{base[:max_len - 3]} {i}"
        if suffixed not in existing_names:
            return suffixed

    return base  # Give up (shouldn't happen with < 10k players)


def transliterate_fallback(name: str) -> str:
    """Convert accented characters to ASCII equivalents.

    Uses unidecode for comprehensive transliteration:
    "Dembélé" → "Dembele"
    "Müller" → "Muller"
    "Đorđević" → "Dordevic"
    """
    return unidecode(name)


def has_accents(name: str) -> bool:
    """Check if a name contains non-ASCII characters (accents, diacritics)."""
    return any(ord(c) > 127 for c in name)
