"""Tests for runtime/environment guardrails."""

from __future__ import annotations

import importlib.util

import pytest

from swos420.utils.runtime import validate_runtime


def test_validate_runtime_accepts_supported_python():
    validate_runtime(min_python=(3, 12), required_modules=(), python_version=(3, 12))


def test_validate_runtime_rejects_unsupported_python():
    with pytest.raises(RuntimeError) as exc:
        validate_runtime(min_python=(3, 12), required_modules=(), python_version=(3, 11))

    message = str(exc.value)
    assert "Python >=3.12" in message
    assert "3.11" in message


def test_validate_runtime_rejects_missing_modules(monkeypatch: pytest.MonkeyPatch):
    original_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str):
        if name == "missing_pkg":
            return None
        return original_find_spec(name)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    with pytest.raises(RuntimeError) as exc:
        validate_runtime(
            min_python=(3, 12),
            required_modules=("json", "missing_pkg"),
            python_version=(3, 12),
        )

    message = str(exc.value)
    assert "missing_pkg" in message
    assert "pip install -e" in message
