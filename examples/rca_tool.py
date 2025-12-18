"""Root Cause Analysis automation CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from x_make_graphviz_x import GraphvizBuilder
from x_make_graphviz_x.vendor_support import find_vendored_dot_binary

MISSING_FISHBONE_ERROR = "payload missing 'fishbone' section"
MISSING_PHASE_FLOW_ERROR = "payload missing 'phase_flow' section"
ENV_EVIDENCE_ROOT = "MAKE_GRAPHVIZ_EVIDENCE_ROOT"
FALLBACK_RELEASE = "0.20.15"


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


@dataclass(frozen=True)
class MarkdownArtifacts:
    phase_dot: str
    ishikawa_dot: str
    images_prefix: str | None = None
    subdir: str | None = None


@dataclass(frozen=True)
class CLIOptions:
    input_path: Path
    output_dir: Path | None
    subdir: str | None
    slug_override: str | None
    images_prefix: str
    dot_binary: Path | None
    emit_markdown: bool
    markdown_path: Path | None


@dataclass(frozen=True)
class RenderPlan:
    output_dir: Path
    subdir: str | None
    markdown_path: Path | None
    defaulted_output_dir: bool
    defaulted_subdir: bool
    defaulted_markdown_path: bool

    @property
    def artifact_root(self) -> Path:
        if self.subdir:
            return self.output_dir / self.subdir
        return self.output_dir


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_release(name: str) -> tuple[int, ...] | None:
    parts = name.split(".")
    if not parts:
        return None
    try:
        return tuple(int(part) for part in parts)
    except ValueError:
        return None


def _latest_release_dir(base: Path) -> Path | None:
    if not base.exists():
        return None
    candidates: list[tuple[tuple[int, ...], Path]] = []
    for entry in base.iterdir():
        if not entry.is_dir():
            continue
        version = _parse_release(entry.name)
        if version is not None:
            candidates.append((version, entry))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _default_evidence_root() -> Path:
    override = os.environ.get(ENV_EVIDENCE_ROOT)
    if override:
        return Path(override)
    workspace_root = _workspace_root()
    search_roots = [
        workspace_root / "x_0_make_all_x" / "Change Control",
        workspace_root / "Change Control",
    ]
    for base in search_roots:
        release_dir = _latest_release_dir(base)
        if release_dir is not None:
            return release_dir / "evidence" / "graphviz_rca"
    return (
        workspace_root
        / "x_0_make_all_x"
        / "Change Control"
        / FALLBACK_RELEASE
        / "evidence"
        / "graphviz_rca"
    )


_NON_SEQUENCE_TYPES = (str, bytes, bytearray)


def _coerce_mapping(value: object | None) -> dict[str, object]:
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, entry in value.items():
            if isinstance(key, str):
                result[key] = entry
            else:
                result[str(key)] = entry
        return result
    return {}


def _coerce_mapping_list(value: object | None) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    if isinstance(value, Sequence) and not isinstance(value, _NON_SEQUENCE_TYPES):
        for item in value:
            mapping = _coerce_mapping(item)
            if mapping:
                entries.append(mapping)
    return entries


def _coerce_str(value: object | None, default: str = "") -> str:
    if isinstance(value, str):
        return value
    return default


def _coerce_optional_str(value: object | None) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _coerce_str_list(value: object | None) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, _NON_SEQUENCE_TYPES):
        return [item if isinstance(item, str) else str(item) for item in value]
    return []


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-") or "rca"


def _load_payload(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if isinstance(data, Mapping):
        result: dict[str, object] = {}
        for key, entry in data.items():
            if isinstance(key, str):
                result[key] = entry
            else:
                result[str(key)] = entry
        return result
    message = "RCA payload must be a JSON object"
    raise ValueError(message)


def _coerce_dot_binary(dot_binary: Path | str | None) -> str | None:
    if dot_binary is None:
        vendored = find_vendored_dot_binary()
        if vendored is None:
            return None
        return str(vendored)
    return str(Path(dot_binary))


def _build_phase_flow(
    phases: list[Phase], *, dot_binary: Path | str | None = None
) -> GraphvizBuilder:
    builder = GraphvizBuilder(directed=True, dot_binary=_coerce_dot_binary(dot_binary))
    builder.graph_attr(rankdir="LR")
    builder.node_defaults(
        shape="box", style="rounded,filled", fillcolor="#e8f4fd", fontname="Inter"
    )

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


def _build_ishikawa(
    effect: str, branches: list[Branch], *, dot_binary: Path | str | None = None
) -> GraphvizBuilder:
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


def _as_branches(raw: Iterable[Mapping[str, object]]) -> list[Branch]:
    return [
        Branch(
            name=_coerce_str(item.get("title"), "Unnamed Branch"),
            description=_coerce_str(item.get("description")),
            sub_causes=_coerce_str_list(item.get("sub_causes")),
        )
        for item in raw
    ]


def _as_phases(raw: Iterable[Mapping[str, object]]) -> list[Phase]:
    return [
        Phase(
            title=_coerce_str(item.get("title"), "Phase"),
            goal=_coerce_str(item.get("goal")),
            exit=_coerce_str(item.get("exit")),
            tactics=_coerce_str(item.get("tactics")),
        )
        for item in raw
    ]


def _graphviz_block(name: str, dot_source: str) -> str:
    return f"```graphviz name={name} hook=diagram.graphviz\n{dot_source.strip()}\n```"


def _make_image_ref(
    images_prefix: str | None, subdir: str | None, filename: str
) -> str:
    parts: list[str] = []
    if images_prefix:
        parts.append(images_prefix)
    if subdir:
        parts.append(subdir)
    parts.append(filename)
    return "/".join(part for part in parts if part)


def _markdown(
    payload: Mapping[str, object],
    slug: str,
    *,
    artifacts: MarkdownArtifacts,
) -> str:
    incident = _coerce_mapping(payload.get("incident"))
    phase_flow = _coerce_mapping(payload.get("phase_flow"))
    backlog_items = _coerce_mapping_list(payload.get("backlog"))
    action_items = _coerce_mapping_list(payload.get("actions"))
    title = _coerce_str(incident.get("title"), "Root Cause Analysis")
    summary = _coerce_str(incident.get("summary"), _coerce_str(incident.get("effect")))
    context_items = _coerce_mapping(incident.get("context"))

    phase_img = _make_image_ref(
        artifacts.images_prefix, artifacts.subdir, f"{slug}-phase-flow.svg"
    )
    ishikawa_img = _make_image_ref(
        artifacts.images_prefix, artifacts.subdir, f"{slug}-ishikawa.svg"
    )

    lines: list[str] = [f"# {title}", "", summary, ""]

    if context_items:
        lines.append("## Operational Context")
        for key, value in context_items.items():
            value_str = _coerce_str(value)
            lines.append(f"- **{key}**: {value_str}")
        lines.append("")

    lines.append("## Phase Flow (Rendered)")
    lines.append(f"![Phase Flow]({phase_img})")
    lines.append("")
    lines.append(_graphviz_block("phase_flow", artifacts.phase_dot))
    lines.append("")

    lines.append("## Ishikawa Diagram (Rendered)")
    lines.append(f"![Ishikawa]({ishikawa_img})")
    lines.append("")
    lines.append(_graphviz_block("ishikawa", artifacts.ishikawa_dot))
    lines.append("")

    phases_section = _coerce_mapping_list(phase_flow.get("phases"))
    if phases_section:
        lines.append("## Phase Detail")
        lines.append("| Phase | Exit Criteria | Primary Tactics |")
        lines.append("| --- | --- | --- |")
        lines.extend(
            "| {title} | {exit} | {tactics} |".format(
                title=_coerce_str(phase.get("title"), "Phase"),
                exit=_coerce_str(phase.get("exit")),
                tactics=_coerce_str(phase.get("tactics")),
            )
            for phase in phases_section
        )
        lines.append("")

    if backlog_items:
        lines.append("## Immediate Backlog")
        for item in backlog_items:
            owner = _coerce_str(item.get("owner"))
            status = _coerce_str(item.get("status"))
            prefix = f"[{status}] " if status else ""
            suffix = f" — {owner}" if owner else ""
            lines.append(f"- {prefix}{_coerce_str(item.get('item'))}{suffix}")
        lines.append("")

    if action_items:
        lines.append("## Remediation Tracker")
        lines.append("| Item | Owner | Status | ETA | Notes |")
        lines.append("| --- | --- | --- | --- | --- |")
        lines.extend(
            "| {item} | {owner} | {status} | {eta} | {notes} |".format(
                item=_coerce_str(action.get("item")),
                owner=_coerce_str(action.get("owner")),
                status=_coerce_str(action.get("status")),
                eta=_coerce_str(action.get("eta")),
                notes=_coerce_str(action.get("notes")),
            )
            for action in action_items
        )
        lines.append("")

    return "\n".join(line.rstrip() for line in lines if line is not None)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Root Cause Analysis automation")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="JSON payload describing the incident",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory for rendered diagrams; defaults to the latest Change Control "
            "evidence tree if omitted"
        ),
    )
    parser.add_argument(
        "--subdir",
        type=str,
        default=None,
        help="Optional subdirectory under --output-dir",
    )
    parser.add_argument("--slug", type=str, help="Override slug for output filenames")
    parser.add_argument(
        "--images-prefix",
        type=str,
        default="images",
        help="Relative prefix for markdown image links",
    )
    parser.add_argument("--dot-binary", type=Path, help="Explicit dot executable path")
    parser.add_argument(
        "--emit-markdown",
        action="store_true",
        help="Print markdown summary to stdout",
    )
    parser.add_argument(
        "--markdown-path",
        type=Path,
        help=(
            "Write markdown to file; defaults to the sibling evidence folder when "
            "--output-dir is inferred"
        ),
    )
    return parser


def _parse_cli_options(
    argv: Sequence[str] | None,
) -> tuple[argparse.ArgumentParser, CLIOptions]:
    parser = _build_parser()
    args = parser.parse_args(argv)
    options = CLIOptions(
        input_path=args.input,
        output_dir=args.output_dir,
        subdir=args.subdir,
        slug_override=args.slug,
        images_prefix=args.images_prefix,
        dot_binary=args.dot_binary,
        emit_markdown=bool(args.emit_markdown),
        markdown_path=args.markdown_path,
    )
    return parser, options


def _resolve_render_plan(slug: str, options: CLIOptions) -> RenderPlan:
    target_dir = options.output_dir or (_default_evidence_root() / "images")
    defaulted_output_dir = options.output_dir is None

    resolved_subdir = options.subdir or slug
    defaulted_subdir = not options.subdir

    markdown_path = options.markdown_path
    defaulted_markdown_path = False
    if markdown_path is None and defaulted_output_dir:
        markdown_path = target_dir.parent / f"{slug}.md"
        defaulted_markdown_path = True

    return RenderPlan(
        output_dir=target_dir,
        subdir=resolved_subdir,
        markdown_path=markdown_path,
        defaulted_output_dir=defaulted_output_dir,
        defaulted_subdir=defaulted_subdir,
        defaulted_markdown_path=defaulted_markdown_path,
    )


def _log_plan_defaults(plan: RenderPlan) -> None:
    if plan.defaulted_output_dir:
        print(
            "[rca_tool] --output-dir not supplied; defaulting to"
            f" {plan.output_dir}. Override via --output-dir or set {ENV_EVIDENCE_ROOT}.",
        )
    if plan.defaulted_subdir:
        print(
            "[rca_tool] using slug-based sub-directory"
            f" '{plan.subdir}' to isolate artifacts.",
        )
    if plan.defaulted_markdown_path and plan.markdown_path:
        print(
            "[rca_tool] --markdown-path not supplied; writing markdown to"
            f" {plan.markdown_path}.",
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser, options = _parse_cli_options(argv)

    try:
        payload = _load_payload(options.input_path)
    except ValueError as exc:
        parser.error(str(exc))

    incident = _coerce_mapping(payload.get("incident"))
    slug = (
        options.slug_override
        or _coerce_str(incident.get("slug"))
        or _slugify(_coerce_str(incident.get("title"), "root-cause"))
    )

    fishbone = _coerce_mapping(payload.get("fishbone"))
    if not fishbone:
        raise SystemExit(MISSING_FISHBONE_ERROR)
    phase_flow = _coerce_mapping(payload.get("phase_flow"))
    if not phase_flow:
        raise SystemExit(MISSING_PHASE_FLOW_ERROR)

    branches = _as_branches(_coerce_mapping_list(fishbone.get("branches")))
    phases = _as_phases(_coerce_mapping_list(phase_flow.get("phases")))
    effect = (
        _coerce_str(fishbone.get("effect"))
        or _coerce_str(incident.get("effect"))
        or "Effect"
    )

    plan = _resolve_render_plan(slug, options)
    _log_plan_defaults(plan)

    phase_builder = _build_phase_flow(phases, dot_binary=options.dot_binary)
    phase_dot, phase_dot_path, phase_svg_path = _export(
        phase_builder, plan.artifact_root / f"{slug}-phase-flow"
    )
    print(f"wrote {phase_dot_path}")
    if phase_svg_path:
        print(f"wrote {phase_svg_path}")
    else:
        print("dot binary missing; phase SVG not created")

    ish_builder = _build_ishikawa(effect, branches, dot_binary=options.dot_binary)
    ish_dot, ish_dot_path, ish_svg_path = _export(
        ish_builder, plan.artifact_root / f"{slug}-ishikawa"
    )
    print(f"wrote {ish_dot_path}")
    if ish_svg_path:
        print(f"wrote {ish_svg_path}")
    else:
        print("dot binary missing; ishikawa SVG not created")

    if options.emit_markdown or plan.markdown_path:
        markdown = _markdown(
            payload,
            slug,
            artifacts=MarkdownArtifacts(
                phase_dot=phase_dot,
                ishikawa_dot=ish_dot,
                images_prefix=options.images_prefix,
                subdir=plan.subdir,
            ),
        )
        if options.emit_markdown:
            print(markdown)
        if plan.markdown_path:
            plan.markdown_path.write_text(markdown, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
