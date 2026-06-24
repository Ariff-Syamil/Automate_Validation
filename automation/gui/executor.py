"""Execute one Automate5 TC-GUI pytest case and record the result."""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from tests._paths import DEFAULT_AUTOMATE5_ROOT, require_automate5_root

from .run_store import append_run

VALIDATION_ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_DIR = Path(__file__).resolve().parent
DEFAULT_TEST_MODULE = "tests/test_suite_gui/testcase_tc_gui_automation.py"


@dataclass(frozen=True)
class ExecutionResult:
    test_case_id: str
    result: str
    notes: str
    command: str = ""
    duration_seconds: float | None = None


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _load_gui_cases(version: str) -> dict[str, dict]:
    path = VALIDATION_ROOT / version / "gui" / "test_cases.yaml"
    data = _load_yaml(path)
    return {
        str(tc.get("test_case_id")): tc
        for tc in data.get("test_cases", [])
        if isinstance(tc, dict) and tc.get("test_case_id")
    }


def _load_execution_overrides() -> dict[str, dict]:
    data = _load_yaml(AUTOMATION_DIR / "execution_map.yaml")
    raw_cases = data.get("test_cases") or {}
    return raw_cases if isinstance(raw_cases, dict) else {}


def _default_pytest_target(test_case_id: str) -> str:
    suffix = test_case_id.split("-")[-1].lower()
    return f"{DEFAULT_TEST_MODULE}::test_tc_gui_{suffix}"


def _automate5_root() -> Path:
    root = Path(os.environ.get("AUTOMATE5_ROOT", str(DEFAULT_AUTOMATE5_ROOT))).resolve()
    return require_automate5_root(root)


def _pytest_root() -> Path:
    return Path(os.environ.get("AUTOMATE_VALIDATION_ROOT", str(VALIDATION_ROOT))).resolve()


def _python_executable(root: Path) -> Path:
    candidate = root / ".venv" / "bin" / "python"
    if candidate.exists():
        return candidate
    candidate = root / ".venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return candidate
    return Path(os.environ.get("PYTHON", "python"))


def _summarize_output(output: str, limit: int = 3500) -> str:
    text = output.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _is_pytest_skip(output: str, returncode: int) -> bool:
    if returncode != 0:
        return False
    return bool(re.search(r"\bskipped\b", output, flags=re.IGNORECASE)) and not bool(
        re.search(r"\bfailed\b", output, flags=re.IGNORECASE)
    )


def _dependencies(tc: dict) -> list[str]:
    raw = tc.get("dependency") or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [str(dep).strip() for dep in raw if str(dep).strip()]


def _hardware_note(tc: dict) -> str:
    env = str(tc.get("test_environment_ci_hil") or "").strip().upper()
    if env != "HIL":
        return ""
    return (
        "Dependency is marked HIL/hardware environment; result may require physical "
        "hardware or configured hardware mocks."
    )


def _automation_unavailable_reason(tc: dict) -> str:
    status = str(tc.get("automation_status") or "").strip()
    if status == "Not Ready":
        return "Automation status is Not Ready."
    readiness = str(tc.get("automation_readiness") or "").strip()
    if readiness and readiness not in {"Automatable", "Semi-Automatable"}:
        return f"Automation is not available: automation_readiness is {readiness}."
    return ""


def _join_notes(*parts: str) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip())


def run_case(
    version: str,
    test_case_id: str,
    *,
    executed_by: str = "",
    record: bool = True,
) -> ExecutionResult:
    return _run_case(
        version,
        test_case_id,
        executed_by=executed_by,
        record=record,
        dependency_stack=[],
        triggered_by="",
    )


def _run_case(
    version: str,
    test_case_id: str,
    *,
    executed_by: str,
    record: bool,
    dependency_stack: list[str],
    triggered_by: str,
) -> ExecutionResult:
    cases = _load_gui_cases(version)
    tc = cases.get(test_case_id)
    trigger_note = (
        f"Run because {triggered_by} depends on this test case."
        if triggered_by
        else ""
    )
    if tc is None:
        return _record(
            version,
            test_case_id,
            "BLOCKED",
            _join_notes(trigger_note, f"Unknown test case ID: {test_case_id}"),
            executed_by,
            record=record,
        )

    unavailable_reason = _automation_unavailable_reason(tc)
    if unavailable_reason:
        return _record(
            version,
            test_case_id,
            "BLOCKED",
            _join_notes(trigger_note, _hardware_note(tc), unavailable_reason),
            executed_by,
            record=record,
        )

    if test_case_id in dependency_stack:
        cycle = " -> ".join([*dependency_stack, test_case_id])
        return _record(
            version,
            test_case_id,
            "BLOCKED",
            _join_notes(trigger_note, f"Dependency cycle detected: {cycle}"),
            executed_by,
            record=record,
        )

    failed_dependencies: list[str] = []
    for dep_id in _dependencies(tc):
        dep_result = _run_case(
            version,
            dep_id,
            executed_by=executed_by,
            record=record,
            dependency_stack=[*dependency_stack, test_case_id],
            triggered_by=test_case_id,
        )
        if dep_result.result != "PASS":
            dep_notes = " / ".join(dep_result.notes.splitlines())
            failed_dependencies.append(
                f"{dep_id}={dep_result.result}: {dep_notes}"
            )

    if failed_dependencies:
        return _record(
            version,
            test_case_id,
            "BLOCKED",
            _join_notes(
                trigger_note,
                "Dependency not PASS: " + "; ".join(failed_dependencies),
            ),
            executed_by,
            record=record,
        )

    entry = _load_execution_overrides().get(test_case_id) or {}
    if not isinstance(entry, dict):
        entry = {}

    blocked_reason = entry.get("blocked_reason")
    if blocked_reason:
        return _record(
            version,
            test_case_id,
            "BLOCKED",
            _join_notes(trigger_note, _hardware_note(tc), str(blocked_reason)),
            executed_by,
            record=record,
        )

    pytest_target = entry.get("pytest") or _default_pytest_target(test_case_id)
    root = _automate5_root()
    pytest_root = _pytest_root()
    python = _python_executable(root)
    command = [
        str(python),
        "-m",
        "pytest",
        str(pytest_target),
        "-q",
        "--tb=short",
        "--disable-warnings",
    ]

    env = os.environ.copy()
    env["AUTOMATE5_ROOT"] = str(root)
    env.setdefault("PYTEST_QT_API", "pyside6")
    env.setdefault("QT_QUICK_BACKEND", "software")
    env.setdefault("QSG_RHI_BACKEND", "software")
    pythonpath_parts = [str(pytest_root), str(root)]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    for key, value in (entry.get("env") or {}).items():
        env[str(key)] = str(value)

    started_at = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=str(pytest_root),
            env=env,
            text=True,
            capture_output=True,
            timeout=int(entry.get("timeout_seconds") or 120),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = round(time.perf_counter() - started_at, 3)
        notes = _join_notes(
            trigger_note,
            _hardware_note(tc),
            f"Timed out running pytest target after {exc.timeout}s: {pytest_target}",
        )
        return _record(
            version,
            test_case_id,
            "FAIL",
            notes,
            executed_by,
            " ".join(command),
            record=record,
            duration_seconds=duration,
        )
    except Exception as exc:
        duration = round(time.perf_counter() - started_at, 3)
        notes = _join_notes(
            trigger_note,
            _hardware_note(tc),
            f"Could not start pytest for {pytest_target}: {exc}",
        )
        return _record(
            version,
            test_case_id,
            "FAIL",
            notes,
            executed_by,
            " ".join(command),
            record=record,
            duration_seconds=duration,
        )

    duration = round(time.perf_counter() - started_at, 3)
    combined = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    result = "BLOCKED" if _is_pytest_skip(combined, proc.returncode) else ("PASS" if proc.returncode == 0 else "FAIL")
    notes = _join_notes(
        trigger_note,
        _hardware_note(tc),
        _summarize_output(combined) or f"pytest exited with code {proc.returncode}",
    )
    return _record(
        version,
        test_case_id,
        result,
        notes,
        executed_by,
        " ".join(command),
        record=record,
        duration_seconds=duration,
    )


def _record(
    version: str,
    test_case_id: str,
    result: str,
    notes: str,
    executed_by: str,
    command: str = "",
    *,
    record: bool = True,
    duration_seconds: float | None = None,
) -> ExecutionResult:
    stored_notes = notes if not command else f"{notes}\n\nCommand: {command}"
    if record:
        append_run(
            version,
            test_case_id,
            result,
            notes=stored_notes,
            executed_by=executed_by,
            duration_seconds=duration_seconds,
        )
    return ExecutionResult(
        test_case_id=test_case_id,
        result=result,
        notes=stored_notes,
        command=command,
        duration_seconds=duration_seconds,
    )
