"""Graphviz diagram builder.

Emits DOT and optionally renders via the graphviz Python package.
Supports directed/undirected graphs, subgraphs/clusters, ranks,
record/HTML labels, ports, and rich attributes.
"""

from __future__ import annotations

import importlib
import logging
import sys as _sys
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

AttrValue = str | int | float | bool | None
AttrMap = dict[str, AttrValue]


class _GraphvizSource(Protocol):
    engine: str | None

    def render(
        self, *, filename: str, format: str, cleanup: bool
    ) -> str: ...


class _GraphvizSourceFactory(Protocol):
    def __call__(self, source: str) -> _GraphvizSource: ...


_LOGGER = logging.getLogger("x_make")


def _info(*args: object) -> None:
    msg = " ".join(str(a) for a in args)
    with suppress(Exception):
        _LOGGER.info("%s", msg)
    printed = False
    with suppress(Exception):
        print(msg)
        printed = True
    if not printed:
        with suppress(Exception):
            _sys.stdout.write(msg + "\n")


def _esc(s: str) -> str:
    return str(s).replace('"', r"\"")


def _attrs(data: Mapping[str, AttrValue] | None) -> str:
    if not data:
        return ""
    pairs: list[str] = []
    for key, value in data.items():
        if value is None:
            continue
        text = "true" if value is True else "false" if value is False else str(value)
        pairs.append(f'{key}="{_esc(text)}"')
    return " [" + ", ".join(pairs) + "]"


class _Subgraph:
    def __init__(
        self,
        name: str,
        *,
        cluster: bool,
        attrs: Mapping[str, AttrValue] | None = None,
    ) -> None:
        self.name = (
            "cluster_" + name if cluster and not name.startswith("cluster_") else name
        )
        self.attrs: AttrMap = dict(attrs) if attrs else {}
        self.nodes: list[str] = []
        self.edges: list[str] = []
        self.raw: list[str] = []

    def dot(self) -> str:
        body: list[str] = []
        if self.attrs:
            body.append("graph" + _attrs(self.attrs))
        body.extend(self.nodes)
        body.extend(self.edges)
        body.extend(self.raw)
        inner = "\n  ".join(body)
        return f"subgraph {self.name} {{\n  {inner}\n}}"


class GraphvizBuilder:
    """Rich Graphviz builder."""

    def __init__(self, ctx: object | None = None, *, directed: bool = True) -> None:
        self._ctx = ctx
        self._directed = directed
        self._graph_attrs: AttrMap = {}
        self._node_defaults: AttrMap = {}
        self._edge_defaults: AttrMap = {}
        self._nodes: list[str] = []
        self._edges: list[str] = []
        self._subgraphs: list[_Subgraph] = []
        self._engine: str | None = None  # dot, neato, fdp, sfdp, circo, twopi

    def _is_verbose(self) -> bool:
        value: object = getattr(self._ctx, "verbose", False)
        if isinstance(value, bool):
            return value
        return bool(value)

    # Graph-wide controls

    def directed(self, *, value: bool = True) -> GraphvizBuilder:
        self._directed = value
        return self

    def engine(self, name: str) -> GraphvizBuilder:
        self._engine = name
        return self

    def graph_attr(self, **attrs: AttrValue) -> GraphvizBuilder:
        self._graph_attrs.update(attrs)
        return self

    def node_defaults(self, **attrs: AttrValue) -> GraphvizBuilder:
        self._node_defaults.update(attrs)
        return self

    def edge_defaults(self, **attrs: AttrValue) -> GraphvizBuilder:
        self._edge_defaults.update(attrs)
        return self

    def rankdir(self, dir_: str) -> GraphvizBuilder:
        return self.graph_attr(rankdir=dir_)

    def splines(self, mode: str = "spline") -> GraphvizBuilder:
        return self.graph_attr(splines=mode)

    def overlap(self, mode: str = "false") -> GraphvizBuilder:
        return self.graph_attr(overlap=mode)

    def rank(self, same: Iterable[str]) -> GraphvizBuilder:
        """Create same-rank constraint at top-level."""
        nodes = " ".join(f'"{_esc(n)}"' for n in same)
        self._nodes.append(f"{{ rank = same; {nodes} }}")
        return self

    # Node/edge builders

    def graph_label(
        self,
        label: str,
        *,
        loc: str | None = None,
        fontsize: int | None = None,
    ) -> GraphvizBuilder:
        """Set a graph label with optional location ('t','b','l','r') and font size."""
        self._graph_attrs["label"] = label
        if loc:
            self._graph_attrs["labelloc"] = loc
        if fontsize:
            self._graph_attrs["fontsize"] = fontsize
        return self

    def bgcolor(self, color: str) -> GraphvizBuilder:
        """Set the graph background color."""
        self._graph_attrs["bgcolor"] = color
        return self

    def add_node(
        self,
        node_id: str,
        label: str | None = None,
        **attrs: AttrValue,
    ) -> GraphvizBuilder:
        # Map convenience keys to DOT/SVG hyperlink attributes
        if "url" in attrs and "URL" not in attrs:
            attrs["URL"] = attrs.pop("url")
        if "href" in attrs and "URL" not in attrs:
            attrs["URL"] = attrs.pop("href")
        # ...existing code...
        if label is not None and "label" not in attrs:
            attrs["label"] = label
        self._nodes.append(f'"{_esc(node_id)}"{_attrs(attrs)}')
        return self

    def add_edge(
        self,
        src: str,
        dst: str,
        label: str | None = None,
        from_port: str | None = None,
        to_port: str | None = None,
        **attrs: AttrValue,
    ) -> GraphvizBuilder:
        # Map convenience keys to DOT/SVG hyperlink attributes
        if "url" in attrs and "URL" not in attrs:
            attrs["URL"] = attrs.pop("url")
        if "href" in attrs and "URL" not in attrs:
            attrs["URL"] = attrs.pop("href")
        # ...existing code...
        arrow = "->" if self._directed else "--"
        lhs = f'"{_esc(src)}"{":" + from_port if from_port else ""}'
        rhs = f'"{_esc(dst)}"{":" + to_port if to_port else ""}'
        if label is not None and "label" not in attrs:
            attrs["label"] = label
        self._edges.append(f"{lhs} {arrow} {rhs}{_attrs(attrs)}")
        return self

    def add_raw(self, line: str) -> GraphvizBuilder:
        """Append a raw DOT line at top level (advanced)."""
        self._nodes.append(line)
        return self

    def image_node(
        self,
        node_id: str,
        image_path: str,
        label: str | None = None,
        width: str | None = None,
        height: str | None = None,
        **attrs: AttrValue,
    ) -> GraphvizBuilder:
        """Create an image-backed node (shape='none', image=...)."""
        attrs.setdefault("shape", "none")
        attrs["image"] = image_path
        if width:
            attrs["width"] = width
            attrs.setdefault("fixedsize", "true")
        if height:
            attrs["height"] = height
            attrs.setdefault("fixedsize", "true")
        return self.add_node(node_id, label=label or "", **attrs)

    # Labels helpers

    @staticmethod
    def record_label(fields: Sequence[str] | Sequence[Sequence[str]]) -> str:
        """Build a record label: either flat ['a','b'] or rows [['a','b'],['c']]."""

        def fmt_row(row: Sequence[str]) -> str:
            return " | ".join(_esc(c) for c in row)

        # If rows of fields
        if fields and isinstance(fields[0], (list, tuple)):
            return "{" + "} | {".join(fmt_row(row) for row in fields) + "}"
        # Else flat list of fields
        cells = cast("Sequence[str]", fields)
        return " | ".join(_esc(f) for f in cells)

    @staticmethod
    def html_label(html: str) -> str:
        return f"<<{html}>>"

    # Subgraphs / clusters

    def subgraph(
        self,
        name: str,
        *,
        cluster: bool = False,
        **attrs: AttrValue,
    ) -> _Subgraph:
        sg = _Subgraph(name=name, cluster=cluster, attrs=attrs or None)
        self._subgraphs.append(sg)
        return sg

    def sub_node(
        self,
        sg: _Subgraph,
        node_id: str,
        label: str | None = None,
        **attrs: AttrValue,
    ) -> GraphvizBuilder:
        if label is not None and "label" not in attrs:
            attrs["label"] = label
        sg.nodes.append(f'"{_esc(node_id)}"{_attrs(attrs)}')
        return self

    def sub_edge(
        self,
        sg: _Subgraph,
        src: str,
        dst: str,
        label: str | None = None,
        **attrs: AttrValue,
    ) -> GraphvizBuilder:
        arrow = "->" if self._directed else "--"
        if label is not None and "label" not in attrs:
            attrs["label"] = label
        sg.edges.append(f'"{_esc(src)}" {arrow} "{_esc(dst)}"{_attrs(attrs)}')
        return self

    # DOT emit

    def _dot_source(self, name: str = "G") -> str:
        kind = "digraph" if self._directed else "graph"
        lines: list[str] = []
        if self._graph_attrs:
            lines.append("graph" + _attrs(self._graph_attrs))
        if self._node_defaults:
            lines.append("node" + _attrs(self._node_defaults))
        if self._edge_defaults:
            lines.append("edge" + _attrs(self._edge_defaults))
        lines.extend(self._nodes)
        lines.extend(self._edges)
        lines.extend(sg.dot() for sg in self._subgraphs)
        body = "\n  ".join(lines)
        return f"{kind} {name} {{\n  {body}\n}}\n"

    # Render

    def render(
        self,
        output_file: str = "graph",
        *,
        output_format: str = "png",
    ) -> str:
        dot = self._dot_source()
        if self._is_verbose():
            render_msg = (
                f"[graphviz] rendering output_file={output_file!r} "
                f"format={output_format!r} engine={self._engine or 'dot'}"
            )
            _info(render_msg)
        try:
            graphviz_mod = importlib.import_module("graphviz")
            source_factory = cast(
                "_GraphvizSourceFactory",
                graphviz_mod.Source,
            )
            graphviz_source = source_factory(dot)
            if self._engine:
                with suppress(Exception):
                    graphviz_source.engine = self._engine
            out_path = graphviz_source.render(
                filename=output_file,
                format=output_format,
                cleanup=True,
            )
            return str(out_path)
        except Exception:  # noqa: BLE001 - fallback to DOT is intentional
            dot_path = Path(f"{output_file}.dot")
            dot_path.write_text(dot, encoding="utf-8")
            if self._is_verbose():
                _info(f"[graphviz] wrote DOT fallback to {dot_path}")
            return dot

    # Convenience

    def save_dot(self, path: str) -> str:
        dot = self._dot_source()
        target = Path(path)
        target.write_text(dot, encoding="utf-8")
        return str(target)

    def to_svg(self, output_basename: str = "graph") -> str | None:
        """Render SVG via graphviz if available.

        Returns the SVG path on success or ``None`` when falling back to a DOT file.
        """
        try:
            graphviz_mod = importlib.import_module("graphviz")
        except ImportError:
            dot_path = Path(f"{output_basename}.dot")
            dot_path.write_text(self._dot_source(), encoding="utf-8")
            if self._is_verbose():
                missing_msg = (
                    "[graphviz] python 'graphviz' not available; "
                    "wrote DOT for external svg conversion"
                )
                _info(missing_msg)
            return None
        try:
            source_factory = cast(
                "_GraphvizSourceFactory",
                graphviz_mod.Source,
            )
            src = source_factory(self._dot_source())
            if self._engine:
                with suppress(Exception):
                    src.engine = self._engine
            out_path = src.render(
                filename=output_basename,
                format="svg",
                cleanup=True,
            )
            return str(out_path)
        except Exception:  # noqa: BLE001 - fallback to DOT is intentional
            Path(f"{output_basename}.dot").write_text(
                self._dot_source(),
                encoding="utf-8",
            )
            return None


def main() -> str:
    g = GraphvizBuilder(directed=True).rankdir("LR").node_defaults(shape="box")
    g.add_node("A", "Start")
    g.add_node("B", "End")
    g.add_edge("A", "B", "to", color="blue")
    sg = g.subgraph("cluster_demo", cluster=True, label="Demo")
    g.sub_node(sg, "C", "In cluster")
    g.sub_edge(sg, "C", "B", style="dashed")
    # Generate artifacts: .dot always, .svg when possible
    g.save_dot("example.dot")
    svg = g.to_svg("example")
    return svg or "example.dot"


if __name__ == "__main__":
    _info(main())


x_cls_make_graphviz_x = GraphvizBuilder


__all__ = ["GraphvizBuilder", "x_cls_make_graphviz_x"]
