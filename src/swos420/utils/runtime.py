"""Runtime validation helpers for CLI entrypoints."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence

MIN_PYTHON = (3, 12)
DEFAULT_REQUIRED_MODULES = (
    "pydantic",
    "pandas",
    "numpy",
    "sqlalchemy",
    "unidecode",
    "requests",
)


def _format_version(version: tuple[int, int]) -> str:
    return f"{version[0]}.{version[1]}"


def validate_runtime(
    min_python: tuple[int, int] = MIN_PYTHON,
    required_modules: Sequence[str] = DEFAULT_REQUIRED_MODULES,
    python_version: tuple[int, int] | None = None,
) -> None:
    """Raise RuntimeError if the interpreter or dependencies are incompatible."""
    current = python_version or (sys.version_info.major, sys.version_info.minor)
    if current < min_python:
        raise RuntimeError(
            "SWOS420 requires Python "
            f">={_format_version(min_python)}, found {_format_version(current)}. "
            "Create a fresh virtualenv and install deps with "
            '`python -m pip install -e ".[dev]"`.'
        )

    missing = [mod for mod in required_modules if importlib.util.find_spec(mod) is None]
    if missing:
        missing_csv = ", ".join(sorted(missing))
        raise RuntimeError(
            "Missing required Python modules: "
            f"{missing_csv}. Install project dependencies with "
            '`python -m pip install -e ".[dev]"`.'
        )
