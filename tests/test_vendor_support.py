"""Tests for vendored Graphviz helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from x_make_graphviz_x import vendor_support

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def test_find_vendored_dot_binary_skips_non_windows(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(vendor_support, "_is_windows", lambda: False)

    if vendor_support.find_vendored_dot_binary() is not None:
        pytest.fail("expected no vendored binary when not running on Windows")


def test_find_vendored_dot_binary_returns_path(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(vendor_support, "_is_windows", lambda: True)

    result = vendor_support.find_vendored_dot_binary()

    if result is None:
        pytest.fail("expected a vendored dot binary when running on Windows")
    binary_name = result.name.lower()
    if binary_name not in ("dot", "dot.exe"):
        pytest.fail(f"unexpected vendored binary name: {binary_name}")
    if not result.exists():
        pytest.fail("vendored binary path should exist")
    if not Path(result).is_file():
        pytest.fail("vendored binary path should reference a file")


def test_vendored_dot_binaries_sorted(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(vendor_support, "_is_windows", lambda: True)
    binaries = vendor_support.vendored_dot_binaries()

    if binaries != tuple(sorted(binaries)):
        pytest.fail("vendored binaries should be returned in sorted order")
