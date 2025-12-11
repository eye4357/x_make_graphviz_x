"""Tests for the RCA automation CLI."""

# ruff: noqa: S101 - pytest assertions are expected

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from x_make_graphviz_x.examples import rca_tool


class _FakeBuilder:
    """Minimal stub that imitates GraphvizBuilder for CLI tests."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._dot_lines: list[str] = ["digraph G {", "  // fake", "}"]

    def graph_attr(self, **_attrs: Any) -> _FakeBuilder:
        return self

    def node_defaults(self, **_attrs: Any) -> _FakeBuilder:
        return self

    def add_node(self, *_args: Any, **_kwargs: Any) -> _FakeBuilder:
        return self

    def add_edge(self, *_args: Any, **_kwargs: Any) -> _FakeBuilder:
        return self

    def rank(self, *_args: Any, **_kwargs: Any) -> _FakeBuilder:
        return self

    def dot_source(self) -> str:
        return "\n".join(self._dot_lines)

    def to_svg(self, base_path: str) -> str:
        svg_path = Path(f"{base_path}.svg")
        svg_path.write_text("<svg/>", encoding="utf-8")
        return str(svg_path)


def _sample_payload() -> dict[str, Any]:
    return {
        "incident": {
            "title": "Sample RCA",
            "slug": "sample-rca",
            "summary": "demo",
            "effect": "demo effect",
            "context": {"Key": "Value"},
        },
        "phase_flow": {
            "phases": [
                {"title": "Phase A", "exit": "Done", "tactics": "Work"},
            ]
        },
        "fishbone": {
            "effect": "demo effect",
            "branches": [
                {
                    "title": "Branch",
                    "description": "desc",
                    "sub_causes": ["cause"],
                }
            ],
        },
        "backlog": [
            {"item": "Fix", "owner": "Ops", "status": "ready"},
        ],
        "actions": [
            {
                "item": "Wire gate",
                "owner": "Ops",
                "status": "in-progress",
                "eta": "2025-12-12",
                "notes": "tracking",
            }
        ],
    }


def test_markdown_includes_remediation_tracker() -> None:
    payload = _sample_payload()
    markdown = rca_tool._markdown(
        payload,
        slug="sample-rca",
        phase_dot="digraph phase {}",
        ishikawa_dot="digraph fishbone {}",
        images_prefix="images",
        subdir="demo",
    )

    assert "## Remediation Tracker" in markdown
    assert "| Wire gate | Ops | in-progress | 2025-12-12 | tracking |" in markdown


def test_main_exports_artifacts_with_stub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(rca_tool, "GraphvizBuilder", _FakeBuilder)

    payload_path = tmp_path / "payload.json"
    payload_path.write_text(rca_tool.json.dumps(_sample_payload()), encoding="utf-8")

    output_dir = tmp_path / "out"
    markdown_path = tmp_path / "packet.md"

    exit_code = rca_tool.main(
        [
            "--input",
            str(payload_path),
            "--output-dir",
            str(output_dir),
            "--subdir",
            "demo",
            "--images-prefix",
            "images",
            "--emit-markdown",
            "--markdown-path",
            str(markdown_path),
        ]
    )

    assert exit_code == 0

    phase_dot = output_dir / "demo" / "sample-rca-phase-flow.dot"
    ishikawa_dot = output_dir / "demo" / "sample-rca-ishikawa.dot"
    assert phase_dot.exists()
    assert ishikawa_dot.exists()
    assert markdown_path.exists()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "## Remediation Tracker" in markdown
