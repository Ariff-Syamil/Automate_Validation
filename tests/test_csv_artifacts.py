"""Validation tests for generated test catalog CSV artifacts."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tests" / "test_catalog.csv"
MATRIX = ROOT / "tests" / "coverage_matrix.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_catalog_csv_schema_and_required_rows() -> None:
    rows = _read_csv(CATALOG)

    assert rows
    assert {
        "suite",
        "tags",
        "test_id",
        "test_name",
        "pytest_node",
        "test_type",
        "module",
        "priority",
        "ci_hil",
        "expected_result",
    } <= set(rows[0])
    assert any(row["test_id"] == "TC-GUI-001" for row in rows)
    assert any("testcase_packets.py" in row["pytest_node"] for row in rows)


def test_coverage_matrix_schema_and_csv_alignment() -> None:
    catalog_ids = {row["test_id"] for row in _read_csv(CATALOG)}
    matrix = _read_csv(MATRIX)

    assert matrix
    assert {
        "test_id",
        "suite",
        "architecture_area",
        "module_under_test",
        "pytest_node",
        "coverage_status",
        "ci_eligible",
        "hil_required",
        "notes",
    } <= set(matrix[0])
    assert {row["test_id"] for row in matrix} == catalog_ids


def test_catalog_pytest_nodes_reference_existing_files() -> None:
    for row in _read_csv(CATALOG):
        node = row["pytest_node"]
        path_text = node.split("::", 1)[0]
        if not path_text.endswith(".py"):
            continue
        assert (ROOT / path_text).is_file(), f"missing pytest file for {row['test_id']}: {path_text}"
