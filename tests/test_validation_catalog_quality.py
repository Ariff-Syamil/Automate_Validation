"""Quality gates for the validation YAML catalog and GUI execution mapping."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
AUTOMATE_5 = ROOT / "automate_5"
EXECUTION_MAP = ROOT / "automation" / "gui" / "execution_map.yaml"

SUBCOMPONENTS = (
    "software",
    "mechanical",
    "holoscan_fpga",
    "multi_axis_motor_control_fpga",
    "gui",
)
QUALITY_REQUIRED_FIELDS = (
    "owner",
    "component",
    "precondition",
    "test_name",
    "description",
    "steps",
    "expected_result",
    "fail_conditions",
    "priority",
    "severity",
    "automation_readiness",
    "automation_status",
    "test_environment_ci_hil",
    "observations",
    "next_action_if_fail",
)
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
VALID_SEVERITIES = {"Critical", "Major", "Minor"}
VALID_READINESS = {"Automatable", "Semi-Automatable", "Manual"}
VALID_STATUS = {"Ready", "Not Ready", "In Progress", "Blocked"}
VALID_ENVIRONMENTS = {"CI", "HIL"}


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _test_case_files() -> list[Path]:
    return [
        AUTOMATE_5 / subcomponent / "test_cases.yaml"
        for subcomponent in SUBCOMPONENTS
        if (AUTOMATE_5 / subcomponent / "test_cases.yaml").is_file()
    ]


def _catalog_cases() -> list[tuple[Path, dict]]:
    cases: list[tuple[Path, dict]] = []
    for path in _test_case_files():
        for test_case in _load_yaml(path).get("test_cases") or []:
            cases.append((path, test_case))
    return cases


def _execution_overrides() -> dict[str, dict]:
    return _load_yaml(EXECUTION_MAP).get("test_cases") or {}


def _default_gui_target(test_case_id: str) -> str:
    suffix = test_case_id.rsplit("-", 1)[-1].lower()
    return f"tests/test_suite_gui/testcase_tc_gui_automation.py::test_tc_gui_{suffix}"


def _target_exists(target: str) -> bool:
    path_text, *symbols = target.split("::")
    path = ROOT / path_text
    if not path.is_file():
        return False
    if not symbols:
        return True

    tree = ast.parse(path.read_text(encoding="utf-8"))
    current_nodes: list[ast.AST] = list(tree.body)
    for symbol in symbols:
        match = next(
            (
                node
                for node in current_nodes
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == symbol
            ),
            None,
        )
        if match is None:
            return False
        current_nodes = list(getattr(match, "body", []))
    return True


def test_catalog_quality_fields_are_complete() -> None:
    missing: list[str] = []
    for path, test_case in _catalog_cases():
        test_case_id = test_case.get("test_case_id", "<missing>")
        for field in QUALITY_REQUIRED_FIELDS:
            value = test_case.get(field)
            if value in (None, "", []):
                missing.append(f"{path.parent.name}/{test_case_id}: {field}")

    assert not missing, "Missing quality metadata:\n" + "\n".join(missing)


def test_catalog_enums_use_supported_values() -> None:
    errors: list[str] = []
    enum_fields = {
        "priority": VALID_PRIORITIES,
        "severity": VALID_SEVERITIES,
        "automation_readiness": VALID_READINESS,
        "automation_status": VALID_STATUS,
        "test_environment_ci_hil": VALID_ENVIRONMENTS,
    }
    for path, test_case in _catalog_cases():
        test_case_id = test_case.get("test_case_id", "<missing>")
        for field, allowed in enum_fields.items():
            value = test_case.get(field)
            if value not in allowed:
                errors.append(f"{path.parent.name}/{test_case_id}: {field}={value!r}")

    assert not errors, "Invalid enum values:\n" + "\n".join(errors)


def test_catalog_dependencies_reference_known_test_cases() -> None:
    cases = _catalog_cases()
    known_ids = {test_case.get("test_case_id") for _, test_case in cases}
    missing: list[str] = []

    for path, test_case in cases:
        test_case_id = test_case.get("test_case_id", "<missing>")
        for dependency in test_case.get("dependency") or []:
            if dependency not in known_ids:
                missing.append(f"{path.parent.name}/{test_case_id}: {dependency}")

    assert not missing, "Unknown dependency references:\n" + "\n".join(missing)


def test_ready_gui_cases_have_executable_pytest_target() -> None:
    overrides = _execution_overrides()
    missing_targets: list[str] = []

    for _path, test_case in _catalog_cases():
        test_case_id = test_case.get("test_case_id") or ""
        if not test_case_id.startswith("TC-GUI-"):
            continue
        if test_case.get("automation_status") != "Ready":
            continue

        target = (overrides.get(test_case_id) or {}).get("pytest") or _default_gui_target(test_case_id)
        if not _target_exists(target):
            missing_targets.append(f"{test_case_id}: {target}")

    assert not missing_targets, "Ready TC-GUI cases without pytest target:\n" + "\n".join(missing_targets)


def test_execution_map_targets_are_valid_and_intentional() -> None:
    errors: list[str] = []
    for test_case_id, entry in _execution_overrides().items():
        if not re.fullmatch(r"TC-GUI-\d+", test_case_id):
            errors.append(f"{test_case_id}: expected TC-GUI-* key")
            continue
        target = entry.get("pytest")
        if target and not _target_exists(target):
            errors.append(f"{test_case_id}: missing pytest target {target}")

    assert not errors, "Invalid execution map entries:\n" + "\n".join(errors)
