"""Root Cause Analysis automation CLI."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from x_make_graphviz_x import GraphvizBuilder


@dataclass(frozen=True)
class Branch:
    name: str
    description: str
    sub_causes: list[str]


@dataclass(frozen=True)
class Phase:
    title: str
    goal: str
    exit: str
    tactics: str


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-") or "rca"


def _load_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def _coerce_dot_binary(dot_binary: Path | str | None) -> str | None:
    if dot_binary is None:
        return None
    return str(Path(dot_binary))


def _build_phase_flow(phases: list[Phase], *, dot_binary: Path | str | None = None) -> GraphvizBuilder:
    builder = GraphvizBuilder(directed=True, dot_binary=_coerce_dot_binary(dot_binary))
    builder.graph_attr(rankdir="LR")
    builder.node_defaults(shape="box", style="rounded,filled", fillcolor="#e8f4fd", fontname="Inter")

    builder.add_node(
        "start",
        label="",
        shape="circle",
        width=0.3,
        style="filled",
        fillcolor="#1f78b4",
    )

    phase_ids: list[str] = []
    previous = "start"
    for idx, phase in enumerate(phases, start=1):
        node_id = f"phase_{idx}"
        label_lines = [phase.title]
        if phase.goal:
            label_lines.append(phase.goal)
        builder.add_node(node_id, label="\n".join(label_lines))
        builder.add_edge(previous, node_id)
        previous = node_id
        phase_ids.append(node_id)

    builder.add_node(
        "end",
        label="Green",
        shape="doublecircle",
        fillcolor="#c1f2c7",
    )
    builder.add_edge(previous, "end")
    if phase_ids:
        builder.rank(tuple(phase_ids))
    return builder


def _build_ishikawa(effect: str, branches: list[Branch], *, dot_binary: Path | str | None = None) -> GraphvizBuilder:
    builder = GraphvizBuilder(directed=True, dot_binary=_coerce_dot_binary(dot_binary))
    builder.graph_attr(rankdir="LR", splines="ortho")
    builder.node_defaults(shape="box", style="rounded", fontname="Inter")

    builder.add_node(
        "effect",
        label=effect,
        shape="ellipse",
        style="filled",
        fillcolor="#ffe9cc",
    )

    for branch in branches:
        branch_id = _slugify(branch.name)
        branch_label = branch.name
        if branch.description:
            branch_label = f"{branch.name}\n{branch.description}"
        builder.add_node(branch_id, label=branch_label)
        builder.add_edge(branch_id, "effect")
        for idx, cause in enumerate(branch.sub_causes, start=1):
            cause_id = f"{branch_id}_{idx}"
            builder.add_node(cause_id, label=cause)
            builder.add_edge(branch_id, cause_id)
    return builder


def _export(builder: GraphvizBuilder, basename: Path) -> tuple[str, Path, Path | None]:
    dot_source = builder.dot_source()
    dot_path = basename.with_suffix(".dot")
    dot_path.parent.mkdir(parents=True, exist_ok=True)
    dot_path.write_text(dot_source, encoding="utf-8")
    svg_path_str = builder.to_svg(str(basename))
    svg_path = Path(svg_path_str) if svg_path_str else None
    return dot_source, dot_path, svg_path


def _as_branches(raw: Iterable[dict[str, Any]]) -> list[Branch]:
    result: list[Branch] = []
    for item in raw:
        result.append(
            Branch(
                name=item.get("title", "Unnamed Branch"),
                description=item.get("description", ""),
                sub_causes=list(item.get("sub_causes", [])),
            )
        )
    return result


def _as_phases(raw: Iterable[dict[str, Any]]) -> list[Phase]:
    result: list[Phase] = []
    for item in raw:
        result.append(
            Phase(
                title=item.get("title", "Phase"),
                goal=item.get("goal", ""),
                exit=item.get("exit", ""),
                tactics=item.get("tactics", ""),
            )
        )
    return result


def _graphviz_block(name: str, dot_source: str) -> str:
    return f"```graphviz name={name} hook=diagram.graphviz\n{dot_source.strip()}\n```"


def _make_image_ref(images_prefix: str | None, subdir: str | None, filename: str) -> str:
    parts: list[str] = []
    if images_prefix:
        parts.append(images_prefix)
    if subdir:
        parts.append(subdir)
    parts.append(filename)
    return "/".join(part for part in parts if part)


def _markdown(
    payload: dict[str, Any],
    slug: str,
    *,
    phase_dot: str,
    ishikawa_dot: str,
    images_prefix: str | None,
    subdir: str | None,
) -> str:
    incident = payload.get("incident", {})
    phase_flow = payload.get("phase_flow", {})
    backlog = payload.get("backlog", [])
    actions = payload.get("actions", [])
    title = incident.get("title", "Root Cause Analysis")
    summary = incident.get("summary", incident.get("effect", ""))
    context_items = incident.get("context", {})

    phase_img = _make_image_ref(images_prefix, subdir, f"{slug}-phase-flow.svg")
    ishikawa_img = _make_image_ref(images_prefix, subdir, f"{slug}-ishikawa.svg")

    lines: list[str] = [f"# {title}", "", summary, ""]

    if context_items:
        lines.append("## Operational Context")
        for key, value in context_items.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    lines.append("## Phase Flow (Rendered)")
    lines.append(f"![Phase Flow]({phase_img})")
    lines.append("")
    lines.append(_graphviz_block("phase_flow", phase_dot))
    lines.append("")

    lines.append("## Ishikawa Diagram (Rendered)")
    lines.append(f"![Ishikawa]({ishikawa_img})")
    lines.append("")
    lines.append(_graphviz_block("ishikawa", ishikawa_dot))
    lines.append("")

    phases = phase_flow.get("phases", [])
    if phases:
        lines.append("## Phase Detail")
        lines.append("| Phase | Exit Criteria | Primary Tactics |")
        lines.append("| --- | --- | --- |")
        for phase in phases:
            lines.append(
                f"| {phase.get('title', 'Phase')} | {phase.get('exit', '')} | {phase.get('tactics', '')} |"
            )
        lines.append("")

    if backlog:
        lines.append("## Immediate Backlog")
        for item in backlog:
            owner = item.get("owner", "")
            status = item.get("status", "")
            prefix = f"[{status}] " if status else ""
            suffix = f" — {owner}" if owner else ""
            lines.append(f"- {prefix}{item.get('item', '')}{suffix}")
        lines.append("")

    if actions:
        lines.append("## Remediation Tracker")
        lines.append("| Item | Owner | Status | ETA | Notes |")
        lines.append("| --- | --- | --- | --- | --- |")
        for action in actions:
            lines.append(
                "| {item} | {owner} | {status} | {eta} | {notes} |".format(
                    item=action.get("item", ""),
                    owner=action.get("owner", ""),
                    status=action.get("status", ""),
                    eta=action.get("eta", ""),
                    notes=action.get("notes", ""),
                )
            )
        lines.append("")

    return "\n".join(line.rstrip() for line in lines if line is not None)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Root Cause Analysis automation")
    parser.add_argument("--input", type=Path, required=True, help="JSON payload describing the incident")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for rendered diagrams")
    parser.add_argument("--subdir", type=str, default=None, help="Optional subdirectory under --output-dir")
    parser.add_argument("--slug", type=str, help="Override slug for output filenames")
    parser.add_argument("--images-prefix", type=str, default="images", help="Relative prefix for markdown image links")
    parser.add_argument("--dot-binary", type=Path, help="Explicit dot executable path")
    parser.add_argument("--emit-markdown", action="store_true", help="Print markdown summary to stdout")
    parser.add_argument("--markdown-path", type=Path, help="Write markdown to file")
    args = parser.parse_args(argv)

    payload = _load_payload(args.input)

    incident = payload.get("incident", {})
    slug = args.slug or incident.get("slug") or _slugify(incident.get("title", "root-cause"))

    fishbone = payload.get("fishbone")
    if not fishbone:
        raise SystemExit("payload missing 'fishbone' section")
    phase_flow = payload.get("phase_flow")
    if not phase_flow:
        raise SystemExit("payload missing 'phase_flow' section")

    branches = _as_branches(fishbone.get("branches", []))
    phases = _as_phases(phase_flow.get("phases", []))
    effect = fishbone.get("effect") or incident.get("effect") or "Effect"

    dot_binary = args.dot_binary

    target_dir = args.output_dir
    if args.subdir:
        target_dir = target_dir / args.subdir

    phase_builder = _build_phase_flow(phases, dot_binary=dot_binary)
    phase_dot, phase_dot_path, phase_svg_path = _export(phase_builder, target_dir / f"{slug}-phase-flow")
    print(f"wrote {phase_dot_path}")
    if phase_svg_path:
        print(f"wrote {phase_svg_path}")
    else:
        print("dot binary missing; phase SVG not created")

    ish_builder = _build_ishikawa(effect, branches, dot_binary=dot_binary)
    ish_dot, ish_dot_path, ish_svg_path = _export(ish_builder, target_dir / f"{slug}-ishikawa")
    print(f"wrote {ish_dot_path}")
    if ish_svg_path:
        print(f"wrote {ish_svg_path}")
    else:
        print("dot binary missing; ishikawa SVG not created")

    if args.emit_markdown or args.markdown_path:
        markdown = _markdown(
            payload,
            slug,
            phase_dot=phase_dot,
            ishikawa_dot=ish_dot,
            images_prefix=args.images_prefix,
            subdir=args.subdir,
        )
        if args.emit_markdown:
            print(markdown)
        if args.markdown_path:
            args.markdown_path.write_text(markdown, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
