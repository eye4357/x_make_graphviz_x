"""Tests for the Graphviz builder utilities."""

# ruff: noqa: S101 - assertions are appropriate in test modules

from __future__ import annotations

import importlib
from pathlib import Path
from subprocess import CompletedProcess
from typing import TYPE_CHECKING, NoReturn

from x_cls_make_graphviz_x import GraphvizBuilder

if TYPE_CHECKING:
    from collections.abc import Sequence

    from _pytest.monkeypatch import MonkeyPatch


def test_save_dot_includes_configuration(tmp_path: Path) -> None:
    builder = (
        GraphvizBuilder(directed=False)
        .graph_attr(rankdir="LR")
        .node_defaults(shape="box")
        .edge_defaults(color="gray")
    )
    builder.add_node("alice", label="Alice", tooltip="Owner")
    builder.add_edge("alice", "bob", label="knows", weight=2)

    target = tmp_path / "team.dot"
    saved_path = builder.save_dot(str(target))
    dot_source = Path(saved_path).read_text(encoding="utf-8")

    assert dot_source.startswith("graph G {")
    assert 'graph [rankdir="LR"]' in dot_source
    assert 'node [shape="box"]' in dot_source
    assert 'edge [color="gray"]' in dot_source
    assert '"alice" [tooltip="Owner", label="Alice"]' in dot_source
    assert '"alice" -- "bob"' in dot_source
    assert 'label="knows"' in dot_source
    assert 'weight="2"' in dot_source


def test_to_svg_falls_back_when_dot_missing(tmp_path: Path) -> None:
    builder = GraphvizBuilder()

    output_base = tmp_path / "diagram"
    result = builder.to_svg(str(output_base))

    assert result is None
    dot_file = Path(f"{output_base}.dot")
    assert dot_file.exists()
    assert "digraph" in dot_file.read_text(encoding="utf-8")
    last = builder.get_last_export_result()
    assert last is not None
    assert last.succeeded is False


def test_to_svg_uses_shared_exporter(tmp_path: Path) -> None:
    dot_binary = tmp_path / "dot.exe"
    dot_binary.write_text("binary", encoding="utf-8")

    def runner(command: Sequence[str]) -> CompletedProcess[str]:
        Path(command[-1]).write_text("<svg />", encoding="utf-8")
        return CompletedProcess(list(command), 0, stdout="ok", stderr="")

    builder = GraphvizBuilder(runner=runner, dot_binary=str(dot_binary))
    builder.add_node("a")

    output_base = tmp_path / "diagram"
    result = builder.to_svg(str(output_base))

    assert result is not None
    assert result == str(tmp_path / "diagram.svg")
    svg_path = Path(result)
    assert svg_path.exists()
    last = builder.get_last_export_result()
    assert last is not None
    assert last.succeeded is True


def test_render_falls_back_to_dot(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    builder = GraphvizBuilder()

    def fake_import(_name: str, _package: str | None = None) -> NoReturn:
        raise RuntimeError from None

    monkeypatch.setattr(importlib, "import_module", fake_import)

    output_base = tmp_path / "diagram"
    output = builder.render(output_file=str(output_base), output_format="png")

    dot_file = Path(f"{output_base}.dot")
    assert dot_file.exists()
    assert output == dot_file.read_text(encoding="utf-8")
