"""JSON contracts for x_make_graphviz_x."""

from __future__ import annotations

import sys as _sys
from typing import TYPE_CHECKING

_NODE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "label": {"type": ["string", "null"]},
        "attributes": {"type": "object"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

_EDGE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "source": {"type": "string"},
        "target": {"type": "string"},
        "attributes": {"type": "object"},
    },
    "required": ["source", "target"],
    "additionalProperties": True,
}

INPUT_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "x_make_graphviz_x input",
    "type": "object",
    "properties": {
        "command": {"const": "x_make_graphviz_x"},
        "parameters": {
            "type": "object",
            "properties": {
                "directed": {"type": "boolean"},
                "engine": {"type": ["string", "null"], "minLength": 1},
                "graph_attributes": {"type": "object"},
                "nodes": {"type": "array", "items": _NODE_SCHEMA, "minItems": 1},
                "edges": {"type": "array", "items": _EDGE_SCHEMA},
                "export": {
                    "type": "object",
                    "properties": {
                        "enable": {"type": "boolean"},
                        "filename": {"type": ["string", "null"]},
                        "directory": {"type": ["string", "null"]},
                    },
                    "required": ["enable"],
                    "additionalProperties": False,
                },
            },
            "required": ["nodes", "edges"],
            "additionalProperties": False,
        },
    },
    "required": ["command", "parameters"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "x_make_graphviz_x output",
    "type": "object",
    "properties": {
        "status": {"enum": ["success", "failure"]},
        "dot_source": {"type": "string"},
        "svg_path": {"type": ["string", "null"]},
        "report_path": {"type": ["string", "null"]},
    },
    "required": ["status", "dot_source"],
    "additionalProperties": True,
}

ERROR_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "x_make_graphviz_x error",
    "type": "object",
    "properties": {
        "status": {"const": "failure"},
        "message": {"type": "string"},
        "details": {"type": "object"},
    },
    "required": ["status", "message"],
    "additionalProperties": True,
}

# Preserve legacy import path "json_contracts" for downstream tooling.
if not TYPE_CHECKING:
    _sys.modules.setdefault("json_contracts", _sys.modules[__name__])

__all__ = ["ERROR_SCHEMA", "INPUT_SCHEMA", "OUTPUT_SCHEMA"]
