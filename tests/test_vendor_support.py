"""Tests for vendored Graphviz helpers."""

from __future__ import annotations

from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from x_make_graphviz_x import vendor_support


def test_find_vendored_dot_binary_skips_non_windows(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(vendor_support, "_is_windows", lambda: False)

    assert vendor_support.find_vendored_dot_binary() is None


def test_find_vendored_dot_binary_returns_path(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(vendor_support, "_is_windows", lambda: True)

    result = vendor_support.find_vendored_dot_binary()

    assert result is not None
    assert result.name.lower() in ("dot", "dot.exe")
    assert result.exists()
    assert Path(result).is_file()


def test_vendored_dot_binaries_sorted(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(vendor_support, "_is_windows", lambda: True)
    binaries = vendor_support.vendored_dot_binaries()

    assert binaries == tuple(sorted(binaries))
