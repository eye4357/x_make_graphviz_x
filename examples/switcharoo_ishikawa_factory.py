"""Factory helpers for the Switcharoo Ishikawa diagrams."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from x_make_graphviz_x import GraphvizBuilder

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

AttrValue = str | int | float | bool | None


def _pop_port(attrs: dict[str, AttrValue], key: str) -> str | None:
    value = attrs.pop(key, None)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    label: str | None = None
    attributes: dict[str, AttrValue] = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeSpec:
    source: str
    target: str
    label: str | None = None
    attributes: dict[str, AttrValue] = field(default_factory=dict)


@dataclass(frozen=True)
class DiagramSpec:
    name: str
    filename: str
    graph_attrs: dict[str, AttrValue] = field(default_factory=dict)
    directed: bool = True
    nodes: Sequence[NodeSpec] = field(default_factory=tuple)
    edges: Sequence[EdgeSpec] = field(default_factory=tuple)
    node_defaults: dict[str, AttrValue] = field(default_factory=dict)
    edge_defaults: dict[str, AttrValue] = field(default_factory=dict)
    rank_groups: Sequence[Sequence[str]] = field(default_factory=tuple)


def _coerce_dot_binary(dot_binary: Path | str | None) -> str | None:
    if dot_binary is None:
        return None
    return str(Path(dot_binary))


def _apply_rank_groups(
    builder: GraphvizBuilder, groups: Sequence[Sequence[str]]
) -> None:
    for group in groups:
        builder.rank(tuple(group))


def _build_diagram(
    spec: DiagramSpec, *, dot_binary: Path | str | None = None
) -> GraphvizBuilder:
    builder = GraphvizBuilder(
        directed=spec.directed, dot_binary=_coerce_dot_binary(dot_binary)
    )
    if spec.graph_attrs:
        builder.graph_attr(**spec.graph_attrs)
    if spec.node_defaults:
        builder.node_defaults(**spec.node_defaults)
    if spec.edge_defaults:
        builder.edge_defaults(**spec.edge_defaults)
    for node in spec.nodes:
        builder.add_node(node.node_id, label=node.label, **node.attributes)
    _apply_rank_groups(builder, spec.rank_groups)
    for edge in spec.edges:
        attrs = dict(edge.attributes)
        from_port = _pop_port(attrs, "from_port")
        to_port = _pop_port(attrs, "to_port")
        builder.add_edge(
            edge.source,
            edge.target,
            label=edge.label,
            from_port=from_port,
            to_port=to_port,
            **attrs,
        )
    return builder


def _export_spec(
    spec: DiagramSpec,
    output_dir: Path,
    *,
    dot_binary: Path | str | None = None,
) -> tuple[str, Path, Path | None]:
    builder = _build_diagram(spec, dot_binary=dot_binary)
    dot_source = builder.dot_source()
    output_dir.mkdir(parents=True, exist_ok=True)
    dot_path = output_dir / f"{spec.filename}.dot"
    dot_path.write_text(dot_source, encoding="utf-8")
    svg_path_str = builder.to_svg(str(output_dir / spec.filename))
    svg_path = Path(svg_path_str) if svg_path_str else None
    return dot_source, dot_path, svg_path


def _markdown_block(name: str, dot_source: str) -> str:
    return (
        f"```graphviz name={name} hook=diagram.graphviz\n"
        f"{dot_source.strip()}\n"
        "```"
    )


def _phase_flow_spec() -> DiagramSpec:
    return DiagramSpec(
        name="switcharoo_phase_flow",
        filename="switcharoo-phase-flow",
        graph_attrs={"rankdir": "LR"},
        node_defaults={
            "shape": "box",
            "style": "rounded,filled",
            "fillcolor": "#e8f4fd",
            "fontname": "Inter",
        },
        nodes=(
            NodeSpec(
                "start",
                label="",
                attributes={
                    "shape": "circle",
                    "width": 0.3,
                    "style": "filled",
                    "fillcolor": "#1f78b4",
                },
            ),
            NodeSpec("A", label="Phase A\nEvidence Integrity"),
            NodeSpec("B", label="Phase B\nTemplate Validation"),
            NodeSpec("C", label="Phase C\nCache Hygiene"),
            NodeSpec("D", label="Phase D\nRelease Safeguards"),
            NodeSpec(
                "end",
                label="Green",
                attributes={"shape": "doublecircle", "fillcolor": "#c1f2c7"},
            ),
        ),
        edges=(
            EdgeSpec("start", "A"),
            EdgeSpec("A", "B"),
            EdgeSpec("B", "C"),
            EdgeSpec("C", "D"),
            EdgeSpec("D", "end"),
        ),
        rank_groups=(("A", "B", "C", "D"),),
    )


def _ishikawa_spec() -> DiagramSpec:
    nodes: list[NodeSpec] = [
        NodeSpec(
            "effect",
            label="Digest stale\n(Nov snapshot after Dec run)",
            attributes={
                "shape": "ellipse",
                "style": "filled",
                "fillcolor": "#ffe9cc",
                "fontname": "Inter",
            },
        ),
        NodeSpec("data", label="Data Inputs\ncontext/json not refreshed"),
        NodeSpec("template", label="Template Logic\nstatic summary text"),
        NodeSpec("cache", label="Cache / Build\nold artifacts copied over"),
        NodeSpec("fs", label="Filesystem / Clock\nmultiple digests, skew"),
        NodeSpec("tooling", label="Tooling\nrun_switcharoo bypass clean"),
        NodeSpec("process", label="Process\nno checksum gate"),
        NodeSpec("data_sub1", label="visitor_failures_context.json cached"),
        NodeSpec("data_sub2", label="make_all_summary.json not regenerated"),
        NodeSpec("template_sub1", label="template embeds Nov strings"),
        NodeSpec("template_sub2", label="no timestamp assertion"),
        NodeSpec("cache_sub1", label="fast-path skip resets"),
        NodeSpec("cache_sub2", label="artifact mirror overwrites fresh file"),
        NodeSpec("fs_sub1", label="UTC vs local confusion"),
        NodeSpec("fs_sub2", label="parallel copies under evidence/"),
        NodeSpec("tooling_sub1", label="run_make_all_switcharoo omits clean step"),
        NodeSpec("tooling_sub2", label="factory CLI reuses process state"),
        NodeSpec("process_sub1", label="no digest checksum gate"),
        NodeSpec("process_sub2", label="manual edits bypass review"),
    ]
    edges: list[EdgeSpec] = [
        EdgeSpec("data", "effect"),
        EdgeSpec("template", "effect"),
        EdgeSpec("cache", "effect"),
        EdgeSpec("fs", "effect"),
        EdgeSpec("tooling", "effect"),
        EdgeSpec("process", "effect"),
        EdgeSpec("data", "data_sub1"),
        EdgeSpec("data", "data_sub2"),
        EdgeSpec("template", "template_sub1"),
        EdgeSpec("template", "template_sub2"),
        EdgeSpec("cache", "cache_sub1"),
        EdgeSpec("cache", "cache_sub2"),
        EdgeSpec("fs", "fs_sub1"),
        EdgeSpec("fs", "fs_sub2"),
        EdgeSpec("tooling", "tooling_sub1"),
        EdgeSpec("tooling", "tooling_sub2"),
        EdgeSpec("process", "process_sub1"),
        EdgeSpec("process", "process_sub2"),
    ]
    return DiagramSpec(
        name="switcharoo_ishikawa",
        filename="switcharoo-ishikawa",
        graph_attrs={"rankdir": "LR", "splines": "ortho"},
        node_defaults={"shape": "box", "style": "rounded", "fontname": "Inter"},
        nodes=tuple(nodes),
        edges=tuple(edges),
    )


SPECS: tuple[DiagramSpec, ...] = (_phase_flow_spec(), _ishikawa_spec())


@dataclass(frozen=True)
class FactoryOptions:
    output_dir: Path | None
    subdir: str | None
    dot_binary: Path | None
    emit_markdown: bool
    markdown_path: Path | None


def _emit_markdown(specs: Iterable[tuple[DiagramSpec, str]]) -> str:
    blocks = [_markdown_block(spec.name, dot_source) for spec, dot_source in specs]
    return "\n\n".join(blocks)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Switcharoo Ishikawa diagram factory")
    parser.add_argument(
        "--output-dir", type=Path, help="Directory for .dot/.svg artifacts"
    )
    parser.add_argument(
        "--subdir",
        type=str,
        default=None,
        help="Optional subdirectory under output dir",
    )
    parser.add_argument("--dot-binary", type=Path, help="Explicit dot executable path")
    parser.add_argument(
        "--emit-markdown", action="store_true", help="Print fenced graphviz blocks"
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        help="Write fenced graphviz blocks to a file",
    )
    return parser


def _parse_options(
    argv: Sequence[str] | None,
) -> tuple[argparse.ArgumentParser, FactoryOptions]:
    parser = _build_parser()
    args = parser.parse_args(argv)
    options = FactoryOptions(
        output_dir=args.output_dir,
        subdir=args.subdir,
        dot_binary=args.dot_binary,
        emit_markdown=bool(args.emit_markdown),
        markdown_path=args.markdown_path,
    )
    return parser, options


def _target_directory(options: FactoryOptions) -> Path | None:
    if options.output_dir is None:
        return None
    if options.subdir:
        return options.output_dir / options.subdir
    return options.output_dir


def main(argv: Sequence[str] | None = None) -> int:
    _parser, options = _parse_options(argv)

    rendered: list[tuple[DiagramSpec, str]] = []
    target_dir = _target_directory(options)

    if target_dir is not None:
        for spec in SPECS:
            dot_source, dot_path, svg_path = _export_spec(
                spec, target_dir, dot_binary=options.dot_binary
            )
            rendered.append((spec, dot_source))
            print(f"wrote {dot_path}")
            if svg_path:
                print(f"wrote {svg_path}")
            else:
                print("dot binary missing; SVG not created")
    else:
        for spec in SPECS:
            builder = _build_diagram(spec, dot_binary=options.dot_binary)
            rendered.append((spec, builder.dot_source()))

    if options.emit_markdown or options.markdown_path:
        blocks = _emit_markdown(rendered)
        if options.emit_markdown:
            print(blocks)
        if options.markdown_path:
            options.markdown_path.write_text(blocks, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SPECS",
    "AttrValue",
    "DiagramSpec",
    "EdgeSpec",
    "NodeSpec",
    "main",
]
