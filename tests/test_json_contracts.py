from __future__ import annotations

# ruff: noqa: S101 - assertions express expectations in test cases
import copy
import json
from pathlib import Path
from typing import cast

import pytest

from x_make_common_x.json_contracts import validate_payload, validate_schema
from x_make_graphviz_x.json_contracts import (
    ERROR_SCHEMA,
    INPUT_SCHEMA,
    OUTPUT_SCHEMA,
)
from x_make_graphviz_x.x_cls_make_graphviz_x import main_json

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "json_contracts"
REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def _load_json_object(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        raw: object = json.load(handle)
    if not isinstance(raw, dict):
        message = f"Fixture {path} must contain a JSON object"
        raise TypeError(message)
    return cast("dict[str, object]", raw)


def _load_report_payload(path: Path) -> dict[str, object] | None:
    with path.open("r", encoding="utf-8") as handle:
        raw: object = json.load(handle)
    if isinstance(raw, dict):
        return cast("dict[str, object]", raw)
    return None


SAMPLE_INPUT = _load_json_object(FIXTURE_DIR / "input.json")
SAMPLE_OUTPUT = _load_json_object(FIXTURE_DIR / "output.json")
SAMPLE_ERROR = _load_json_object(FIXTURE_DIR / "error.json")


def test_schemas_are_valid() -> None:
    for schema in (INPUT_SCHEMA, OUTPUT_SCHEMA, ERROR_SCHEMA):
        validate_schema(schema)


def test_sample_payloads_match_schema() -> None:
    validate_payload(SAMPLE_INPUT, INPUT_SCHEMA)
    validate_payload(SAMPLE_OUTPUT, OUTPUT_SCHEMA)
    validate_payload(SAMPLE_ERROR, ERROR_SCHEMA)


def test_existing_reports_align_with_schema() -> None:
    if not REPORTS_DIR.exists():
        pytest.skip("no reports directory for graphviz tool")
    report_files = sorted(REPORTS_DIR.glob("x_make_graphviz_x_run_*.json"))
    if not report_files:
        pytest.skip("no graphviz run reports to validate")
    for report_file in report_files:
        payload = _load_report_payload(report_file)
        if payload is not None:
            validate_payload(payload, OUTPUT_SCHEMA)


def test_main_json_executes_happy_path() -> None:
    result = main_json(SAMPLE_INPUT)
    validate_payload(result, OUTPUT_SCHEMA)
    status_value = result.get("status")
    assert isinstance(status_value, str)
    assert status_value == "success"
    assert "dot_source" in result


def test_main_json_returns_error_for_invalid_payload() -> None:
    invalid = copy.deepcopy(SAMPLE_INPUT)
    parameters = invalid.get("parameters")
    if isinstance(parameters, dict):
        parameters.pop("nodes", None)
    else:
        invalid["parameters"] = dict[str, object]()
    result = main_json(invalid)
    validate_payload(result, ERROR_SCHEMA)
    status_value = result.get("status")
    assert isinstance(status_value, str)
    assert status_value == "failure"
