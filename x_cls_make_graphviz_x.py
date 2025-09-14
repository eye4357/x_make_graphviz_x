"""Graphviz diagram builder.

Emits DOT and optionally renders via the graphviz Python package.
Supports directed/undirected graphs, subgraphs/clusters, ranks,
record/HTML labels, ports, and rich attributes.
"""

from __future__ import annotations

import importlib
from typing import Any, Iterable, Optional
import logging
import sys as _sys
import os

_LOGGER = logging.getLogger("x_make")


def _info(*args: object) -> None:
    msg = " ".join(str(a) for a in args)
    try:
        _LOGGER.info("%s", msg)
    except Exception:
        pass
    try:
        print(msg)
    except Exception:
        try:
            _sys.stdout.write(msg + "\n")
        except Exception:
            pass


def _esc(s: str) -> str:
    return str(s).replace('"', r"\"")


def _attrs(d: dict[str, Any] | None) -> str:
    if not d:
        return ""
    pairs = []
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, bool):
            v = "true" if v else "false"
        pairs.append(f'{k}="{_esc(v)}"')
    return " [" + ", ".join(pairs) + "]"


class _Subgraph:
    def __init__(
        self, name: str, cluster: bool, attrs: dict[str, Any] | None = None
    ) -> None:
        self.name = (
            "cluster_" + name
            if cluster and not name.startswith("cluster_")
            else name
        )
        self.attrs = attrs or {}
        self.nodes: list[str] = []
        self.edges: list[str] = []
        self.raw: list[str] = []

    def dot(self) -> str:
        body = []
        if self.attrs:
            body.append("graph" + _attrs(self.attrs))
        body.extend(self.nodes)
        body.extend(self.edges)
        body.extend(self.raw)
        inner = "\n  ".join(body)
        return f"subgraph {self.name} {{\n  {inner}\n}}"


class x_cls_make_graphviz_x:
    """Rich Graphviz builder."""

    def __init__(
        self, ctx: object | None = None, directed: bool = True
    ) -> None:
        self._ctx = ctx
        self._directed = directed
        self._graph_attrs: dict[str, Any] = {}
        self._node_defaults: dict[str, Any] = {}
        self._edge_defaults: dict[str, Any] = {}
        self._nodes: list[str] = []
        self._edges: list[str] = []
        self._subgraphs: list[_Subgraph] = []
        self._engine: str | None = None  # dot, neato, fdp, sfdp, circo, twopi

    # Graph-wide controls

    def directed(self, value: bool = True) -> "x_cls_make_graphviz_x":
        self._directed = value
        return self

    def engine(self, name: str) -> "x_cls_make_graphviz_x":
        self._engine = name
        return self

    def graph_attr(self, **attrs: Any) -> "x_cls_make_graphviz_x":
        self._graph_attrs.update(attrs)
        return self

    def node_defaults(self, **attrs: Any) -> "x_cls_make_graphviz_x":
        self._node_defaults.update(attrs)
        return self

    def edge_defaults(self, **attrs: Any) -> "x_cls_make_graphviz_x":
        self._edge_defaults.update(attrs)
        return self

    def rankdir(self, dir_: str) -> "x_cls_make_graphviz_x":
        return self.graph_attr(rankdir=dir_)

    def splines(self, mode: str = "spline") -> "x_cls_make_graphviz_x":
        return self.graph_attr(splines=mode)

    def overlap(self, mode: str = "false") -> "x_cls_make_graphviz_x":
        return self.graph_attr(overlap=mode)

    def rank(self, same: Iterable[str]) -> "x_cls_make_graphviz_x":
        """Create same-rank constraint at top-level."""
        nodes = " ".join(f'"{_esc(n)}"' for n in same)
        self._nodes.append(f"{{ rank = same; {nodes} }}")
        return self

    # Node/edge builders

    def add_node(
        self, node_id: str, label: str | None = None, **attrs: Any
    ) -> "x_cls_make_graphviz_x":
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
        **attrs: Any,
    ) -> "x_cls_make_graphviz_x":
        arrow = "->" if self._directed else "--"
        lhs = f'"{_esc(src)}"{":" + from_port if from_port else ""}'
        rhs = f'"{_esc(dst)}"{":" + to_port if to_port else ""}'
        if label is not None and "label" not in attrs:
            attrs["label"] = label
        self._edges.append(f"{lhs} {arrow} {rhs}{_attrs(attrs)}")
        return self

    # Labels helpers

    @staticmethod
    def record_label(fields: list[str] | list[list[str]]) -> str:
        """Build a record label: either flat ['a','b'] or rows [['a','b'],['c']]."""
        def fmt_row(row: list[str]) -> str:
            return " | ".join(_esc(c) for c in row)

        if fields and isinstance(fields[0], list):
            return "{" + "} | {".join(fmt_row(r) for r in fields) + "}"
        return " | ".join(_esc(f) for f in fields)  # type: ignore[arg-type]

    @staticmethod
    def html_label(html: str) -> str:
        return f"<<{html}>>"

    # Subgraphs / clusters

    def subgraph(
        self, name: str, cluster: bool = False, **attrs: Any
    ) -> _Subgraph:
        sg = _Subgraph(name=name, cluster=cluster, attrs=attrs or None)
        self._subgraphs.append(sg)
        return sg

    def sub_node(
        self,
        sg: _Subgraph,
        node_id: str,
        label: str | None = None,
        **attrs: Any,
    ) -> "x_cls_make_graphviz_x":
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
        **attrs: Any,
    ) -> "x_cls_make_graphviz_x":
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
        for sg in self._subgraphs:
            lines.append(sg.dot())
        body = "\n  ".join(lines)
        return f"{kind} {name} {{\n  {body}\n}}\n"

    # Render

    def render(self, output_file: str = "graph", format: str = "png") -> str:
        dot = self._dot_source()
        if getattr(self._ctx, "verbose", False):
            _info(
                f"[graphviz] rendering output_file={output_file!r} format={format!r} engine={self._engine or 'dot'}"
            )
        try:
            _graphviz: Any = importlib.import_module("graphviz")
            g = _graphviz.Source(dot)
            if self._engine:
                try:
                    g.engine = self._engine
                except Exception:
                    # fallback to layout attribute if engine not supported by graphviz.Source
                    pass
            out_path = g.render(filename=output_file, format=format, cleanup=True)
            return str(out_path)
        except Exception:
            dot_path = f"{output_file}.dot"
            with open(dot_path, "w", encoding="utf-8") as f:
                f.write(dot)
            if getattr(self._ctx, "verbose", False):
                _info(f"[graphviz] wrote DOT fallback to {dot_path}")
            return dot

    # Convenience

    def save_dot(self, path: str) -> str:
        dot = self._dot_source()
        with open(path, "w", encoding="utf-8") as f:
            f.write(dot)
        return path

    def to_svg(self, output_basename: str = "graph") -> str | None:
        """Render SVG via graphviz if available. Returns SVG path or None on fallback."""
        try:
            _graphviz: Any = importlib.import_module("graphviz")
        except Exception:
            # ensure DOT exists for external conversion, even if graphviz python package is missing
            self.save_dot(f"{output_basename}.dot")
            if getattr(self._ctx, "verbose", False):
                _info(
                    "[graphviz] python 'graphviz' not available; wrote DOT for external svg conversion"
                )
            return None
        try:
            src = _graphviz.Source(self._dot_source())
            if self._engine:
                try:
                    src.engine = self._engine
                except Exception:
                    pass
            out_path = src.render(
                filename=output_basename, format="svg", cleanup=True
            )
            return str(out_path)
        except Exception:
            # on failure, still persist DOT for manual conversion
            self.save_dot(f"{output_basename}.dot")
            return None


def main() -> str:
    g = x_cls_make_graphviz_x(directed=True).rankdir("LR").node_defaults(shape="box")
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
