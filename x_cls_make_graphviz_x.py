"""Graphviz diagram builder.

Emits DOT and optionally renders via the graphviz Python package.
Supports directed/undirected graphs, subgraphs/clusters, ranks,
record/HTML labels, ports, and rich attributes.
"""

# ruff: noqa: A002 - retain parameter name parity with graphviz API

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys as _sys
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Protocol, cast

from jsonschema import ValidationError

from x_make_common_x.exporters import (
    CommandRunner,
    ExportResult,
    export_graphviz_to_svg,
)
from x_make_common_x.json_contracts import validate_payload
from x_make_graphviz_x.json_contracts import INPUT_SCHEMA, OUTPUT_SCHEMA

if TYPE_CHECKING:
    from collections.abc import Iterable

AttrValue = str | int | float | bool | None
AttrMap = dict[str, AttrValue]


class _GraphvizSource(Protocol):
    engine: str | None

    def render(self, *, filename: str, format: str, cleanup: bool) -> str: ...


class _GraphvizSourceFactory(Protocol):
    def __call__(self, source: str) -> _GraphvizSource: ...


_LOGGER = logging.getLogger("x_make")


@dataclass(slots=True)
class _JsonCLIArgs:
    use_stdin: bool
    json_file: str | None


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

    def __init__(
        self,
        ctx: object | None = None,
        *,
        directed: bool = True,
        runner: CommandRunner | None = None,
        dot_binary: str | None = None,
    ) -> None:
        self._ctx = ctx
        self._directed = directed
        self._graph_attrs: AttrMap = {}
        self._node_defaults: AttrMap = {}
        self._edge_defaults: AttrMap = {}
        self._nodes: list[str] = []
        self._edges: list[str] = []
        self._subgraphs: list[_Subgraph] = []
        self._engine: str | None = None  # dot, neato, fdp, sfdp, circo, twopi
        self._runner: CommandRunner | None = runner
        self._dot_binary: str | None = dot_binary
        self._last_export_result: ExportResult | None = None

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

    def dot_source(self) -> str:
        """Return the generated DOT source."""

        return self._dot_source()

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
        target_path = Path(output_basename)
        if target_path.suffix:
            stem = target_path.stem
            output_dir = target_path.parent or Path()
        else:
            stem = target_path.name
            output_dir = target_path.parent or Path()
        result = export_graphviz_to_svg(
            self._dot_source(),
            output_dir=output_dir,
            stem=stem,
            graphviz_path=self._dot_binary,
            runner=self._runner,
        )
        self._last_export_result = result
        if result.succeeded and result.output_path is not None:
            return str(result.output_path)
        if self._is_verbose():
            _info(
                "[graphviz] dot export failed; retained DOT at",
                str((output_dir / f"{stem}.dot").resolve()),
            )
        return None

    def get_last_export_result(self) -> ExportResult | None:
        return self._last_export_result


def _coerce_attr_map(value: object) -> AttrMap:
    if not isinstance(value, Mapping):
        return {}
    attrs: AttrMap = {}
    typed = cast("Mapping[str, object]", value)
    for key, raw in typed.items():
        attrs[str(key)] = cast("AttrValue", raw)
    return attrs


def _normalize_nodes(
    builder: GraphvizBuilder,
    nodes: Sequence[object],
) -> None:
    for entry in nodes:
        if not isinstance(entry, Mapping):
            continue
        node_id_obj = entry.get("id")
        if not isinstance(node_id_obj, str) or not node_id_obj:
            continue
        label_obj = entry.get("label")
        label: str | None
        if isinstance(label_obj, str):
            label = label_obj
        elif label_obj is None:
            label = None
        else:
            label = str(label_obj)
        attrs = _coerce_attr_map(entry.get("attributes"))
        node_attrs: Mapping[str, AttrValue] = attrs
        builder.add_node(node_id_obj, label=label, **node_attrs)


def _normalize_edges(
    builder: GraphvizBuilder,
    edges: Sequence[object],
) -> None:
    for entry in edges:
        if not isinstance(entry, Mapping):
            continue
        source = entry.get("source")
        target = entry.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        label_obj = entry.get("label")
        label: str | None
        if isinstance(label_obj, str):
            label = label_obj
        elif label_obj is None:
            label = None
        else:
            label = str(label_obj)
        attrs = _coerce_attr_map(entry.get("attributes"))
        edge_attrs = dict(attrs)
        from_port_obj = edge_attrs.pop("from_port", None)
        to_port_obj = edge_attrs.pop("to_port", None)
        from_port = from_port_obj if isinstance(from_port_obj, str) else None
        to_port = to_port_obj if isinstance(to_port_obj, str) else None
        builder.add_edge(
            source,
            target,
            label=label,
            from_port=from_port,
            to_port=to_port,
            **edge_attrs,
        )


def _failure_payload(
    message: str, *, details: Mapping[str, object] | None = None
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "failure",
        "message": message,
    }
    if details:
        payload["details"] = dict(details)
    return payload


def main_json(
    payload: Mapping[str, object],
    *,
    ctx: object | None = None,
) -> dict[str, object]:
    """Execute the Graphviz builder using the JSON contract."""

    try:
        validate_payload(payload, INPUT_SCHEMA)
    except ValidationError as exc:
        return _failure_payload(
            "input payload failed validation",
            details={
                "error": exc.message,
                "path": [str(part) for part in exc.path],
                "schema_path": [str(part) for part in exc.schema_path],
            },
        )

    parameters_obj = payload.get("parameters", {})
    parameters = cast("Mapping[str, object]", parameters_obj)

    directed_value = parameters.get("directed", True)
    directed = (
        bool(directed_value) if not isinstance(directed_value, bool) else directed_value
    )

    graphviz_path_obj = parameters.get("graphviz_path")
    dot_binary: str | None = None
    if isinstance(graphviz_path_obj, (str, Path)):
        candidate = str(graphviz_path_obj).strip()
        if candidate:
            dot_binary = candidate

    builder = GraphvizBuilder(ctx=ctx, directed=directed, dot_binary=dot_binary)

    engine_obj = parameters.get("engine")
    if isinstance(engine_obj, str) and engine_obj:
        builder.engine(engine_obj)

    graph_attrs_obj = parameters.get("graph_attributes")
    graph_attrs = _coerce_attr_map(graph_attrs_obj)
    if graph_attrs:
        builder.graph_attr(**graph_attrs)

    nodes_obj = parameters.get("nodes", [])
    if isinstance(nodes_obj, Sequence):
        _normalize_nodes(builder, nodes_obj)

    edges_obj = parameters.get("edges", [])
    if isinstance(edges_obj, Sequence):
        _normalize_edges(builder, edges_obj)

    export_obj = parameters.get("export")
    svg_path: str | None = None
    export_metadata: dict[str, object] | None = None
    if isinstance(export_obj, Mapping) and export_obj.get("enable"):
        export_mapping = cast("Mapping[str, object]", export_obj)
        filename_obj = export_mapping.get("filename")
        directory_obj = export_mapping.get("directory")
        filename = (
            filename_obj if isinstance(filename_obj, str) and filename_obj else "graph"
        )
        base = (
            Path(directory_obj)
            if isinstance(directory_obj, str) and directory_obj
            else Path()
        )
        target = base / filename
        svg_result = builder.to_svg(str(target))
        svg_path = svg_result if svg_result else None
        last_export = builder.get_last_export_result()
        if last_export is not None:
            export_metadata = last_export.to_metadata()

    dot_source = builder.dot_source()
    result: dict[str, object] = {
        "status": "success",
        "dot_source": dot_source,
        "svg_path": svg_path,
        "report_path": None,
    }
    if export_metadata is not None:
        result["export_result"] = export_metadata

    try:
        validate_payload(result, OUTPUT_SCHEMA)
    except ValidationError as exc:
        return _failure_payload(
            "generated output failed schema validation",
            details={
                "error": exc.message,
                "path": [str(part) for part in exc.path],
                "schema_path": [str(part) for part in exc.schema_path],
            },
        )
    return result


def _load_json_payload(file_path: str | None) -> Mapping[str, object]:
    def _load(handle: IO[str]) -> Mapping[str, object]:
        raw: object = json.load(handle)
        if not isinstance(raw, dict):
            message = "JSON payload must be an object"
            raise SystemExit(message)
        return cast("dict[str, object]", raw)

    if file_path:
        with Path(file_path).open("r", encoding="utf-8") as handle:
            return _load(handle)
    return _load(_sys.stdin)


def _run_json_cli(args: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(description="x_make_graphviz_x JSON runner")
    parser.add_argument(
        "--json", action="store_true", help="Read JSON payload from stdin"
    )
    parser.add_argument("--json-file", type=str, help="Path to JSON payload file")
    namespace = parser.parse_args(args)
    json_flag_obj = cast("object", getattr(namespace, "json", False))
    json_flag = bool(json_flag_obj)
    json_file_raw = cast("object", getattr(namespace, "json_file", None))
    json_path = json_file_raw if isinstance(json_file_raw, str) else None
    parsed = _JsonCLIArgs(use_stdin=json_flag, json_file=json_path)

    if not (parsed.use_stdin or parsed.json_file):
        parser.error("JSON input required. Use --json for stdin or --json-file <path>.")

    payload = _load_json_payload(parsed.json_file if parsed.json_file else None)
    result = main_json(payload)
    rendered_obj: object = json.dumps(result, indent=2)
    if not isinstance(rendered_obj, str):  # pragma: no cover - defensive
        message = "JSON rendering failed"
        raise SystemExit(message)
    rendered: str = rendered_obj
    _sys.stdout.write(rendered)
    _sys.stdout.write("\n")


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
    _run_json_cli(_sys.argv[1:])


x_cls_make_graphviz_x = GraphvizBuilder

__all__ = ["GraphvizBuilder", "main_json", "x_cls_make_graphviz_x"]
