"""Execute one Automate5 TC-GUI pytest case and record the result."""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from .run_store import append_run, latest_run_per_test_case, load_runs

VALIDATION_ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_DIR = Path(__file__).resolve().parent
DEFAULT_AUTOMATE5_ROOT = VALIDATION_ROOT.parent / "Automate5"
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
    return Path(os.environ.get("AUTOMATE5_ROOT", str(DEFAULT_AUTOMATE5_ROOT))).resolve()


def _pytest_root() -> Path:
    return Path(os.environ.get("AUTOMATE_VALIDATION_ROOT", str(VALIDATION_ROOT))).resolve()


def _python_executable(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return candidate
    return Path(os.environ.get("PYTHON", "python"))


def _dependency_block_reason(version: str, tc: dict) -> str | None:
    dependencies = tc.get("dependency") or []
    if not dependencies:
        return None

    latest = latest_run_per_test_case(load_runs(version).get("runs") or [])
    missing: list[str] = []
    for dep in dependencies:
        dep_latest = latest.get(dep)
        if dep_latest is None or dep_latest.get("result") != "PASS":
            missing.append(dep)
    if missing:
        return "Dependency not PASS: " + ", ".join(missing)
    return None


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


def run_case(
    version: str,
    test_case_id: str,
    *,
    executed_by: str = "",
    record: bool = True,
) -> ExecutionResult:
    cases = _load_gui_cases(version)
    tc = cases.get(test_case_id)
    if tc is None:
        return _record(
            version,
            test_case_id,
            "BLOCKED",
            f"Unknown test case ID: {test_case_id}",
            executed_by,
            record=record,
        )

    if str(tc.get("automation_status") or "") == "Not Ready":
        return _record(
            version,
            test_case_id,
            "BLOCKED",
            "Automation status is Not Ready.",
            executed_by,
            record=record,
        )

    dep_reason = _dependency_block_reason(version, tc)
    if dep_reason:
        return _record(version, test_case_id, "BLOCKED", dep_reason, executed_by, record=record)

    entry = _load_execution_overrides().get(test_case_id) or {}
    if not isinstance(entry, dict):
        entry = {}

    blocked_reason = entry.get("blocked_reason")
    if blocked_reason:
        return _record(
            version,
            test_case_id,
            "BLOCKED",
            str(blocked_reason),
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
        notes = f"Timed out running pytest target after {exc.timeout}s: {pytest_target}"
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
        notes = f"Could not start pytest for {pytest_target}: {exc}"
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
    notes = _summarize_output(combined) or f"pytest exited with code {proc.returncode}"
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
