"""Graphviz diagram builder (stub).

Provides a lightweight class to build simple graphs. If the `graphviz`
python package is available it will use it to render. Otherwise the
class will emit DOT source to a `.dot` file.

Patterned after other x_cls_make_*_x modules in this repo.
"""

from __future__ import annotations

import importlib
from typing import Any


class x_cls_make_graphviz_x:
    """Simple Graphviz builder stub.

    Methods are intentionally small and safe: they build an internal DOT
    representation and try to render with graphviz if available. Otherwise
    they fall back to writing the DOT source to disk.
    """

    def __init__(self, ctx: object | None = None) -> None:
        """Optional ctx is accepted for future orchestration integration.

        Backwards-compatible: callers that don't pass ctx keep the old behavior.
        If a ctx with a truthy `verbose` attribute is provided the class will
        emit minimal runtime information to stdout to aid debugging.
        """
        self._ctx = ctx
        self._nodes: list[str] = []
        self._edges: list[str] = []
        self._directed: bool = True

    def add_node(
        self, node_id: str, label: str | None = None, **attrs: Any
    ) -> None:
        """Add a node. Attributes are rendered as DOT attributes.

        Example: add_node('A', 'Start')
        """
        label_part = f' label="{label}"' if label is not None else ""
        attr_parts = "".join([f' {k}="{v}"' for k, v in attrs.items()])
        self._nodes.append(f'"{node_id}" [{label_part}{attr_parts}]')

    def add_edge(
        self, src: str, dst: str, label: str | None = None, **attrs: Any
    ) -> None:
        """Add an edge between src and dst.

        If `self._directed` is True a directed edge is used.
        """
        arrow = "->" if self._directed else "--"
        label_part = f' [label="{label}"' if label is not None or attrs else ""
        if label is not None and attrs:
            label_str = f'label="{label}"'
        elif label is not None:
            label_str = f'label="{label}"'
        else:
            label_str = ""

        attr_str = ", ".join([f'{k}="{v}"' for k, v in attrs.items()])
        inner = ", ".join(filter(None, [label_str, attr_str]))
        if inner:
            label_part = f" [{inner}]"
        else:
            label_part = ""

        self._edges.append(f'"{src}" {arrow} "{dst}"{label_part}')

    def _dot_source(self, name: str = "G") -> str:
        kind = "digraph" if self._directed else "graph"
        body = "\n".join(self._nodes + self._edges)
        return f"{kind} {name} {{\n{body}\n}}\n"

    def render(self, output_file: str = "graph", format: str = "png") -> str:
        """Render the graph.

        Attempts to use the `graphviz` package. If unavailable writes DOT to
        `output_file + '.dot'` and returns the DOT source.
        """
        dot = self._dot_source()

        if getattr(self._ctx, "verbose", False):
            # lightweight informational message when running under an orchestrator context
            from x_make_common_x.helpers import info as _info

            _info(
                f"[graphviz] rendering output_file={output_file!r} format={format!r}"
            )

        try:
            _graphviz: Any = importlib.import_module("graphviz")
            g = _graphviz.Source(dot)
            out_path = g.render(
                filename=output_file, format=format, cleanup=True
            )
            # graphviz may return a path-like or Any; ensure we return a str for typing
            return str(out_path)
        except Exception:
            dot_path = f"{output_file}.dot"
            with open(dot_path, "w", encoding="utf-8") as f:
                f.write(dot)
            if getattr(self._ctx, "verbose", False):
                from x_make_common_x.helpers import info as _info

                _info(f"[graphviz] wrote DOT fallback to {dot_path}")
            return dot


def main() -> str:
    g = x_cls_make_graphviz_x()
    g.add_node("A", "Start")
    g.add_node("B", "End")
    g.add_edge("A", "B", "to")
    # Attempt render which will return a path if graphviz is available
    # or the DOT source (string) when graphviz is missing.
    out = g.render(output_file="example", format="dot")
    return out


if __name__ == "__main__":
    from x_make_common_x.helpers import info as _info

    _info(main())
