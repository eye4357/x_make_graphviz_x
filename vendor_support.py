"""Helpers for working with vendored Graphviz distributions."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path


def _package_root() -> Path:
    return Path(__file__).resolve().parent


def _vendor_root() -> Path:
    return _package_root() / "vendor"


def _iter_paths(root: Path, patterns: Iterable[str]) -> list[Path]:
    candidates: list[Path] = []
    if not root.exists():
        return candidates
    for pattern in patterns:
        candidates.extend(root.rglob(pattern))
    return candidates


def _normalize_candidates(candidates: Iterable[Path]) -> tuple[Path, ...]:
    normalized: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not resolved.is_file():
            continue
        if resolved in seen:
            continue
        normalized.append(resolved)
        seen.add(resolved)
    return tuple(sorted(normalized))


@lru_cache(maxsize=1)
def vendored_dot_binaries() -> tuple[Path, ...]:
    """Return every vendored Graphviz `dot` binary bundled with this package."""

    vendor_root = _vendor_root()
    patterns = ("dot.exe", "dot")
    return _normalize_candidates(_iter_paths(vendor_root, patterns))


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def find_vendored_dot_binary(*, windows_only: bool = True) -> Path | None:
    """Return the preferred vendored dot binary if available."""

    if windows_only and not _is_windows():
        return None

    binaries = vendored_dot_binaries()
    if not binaries:
        return None

    if windows_only:
        for candidate in binaries:
            if candidate.suffix.lower() == ".exe":
                return candidate
        return None

    return binaries[0]


__all__ = ["find_vendored_dot_binary", "vendored_dot_binaries"]
