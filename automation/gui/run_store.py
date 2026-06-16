"""Shared run-record persistence for GUI automation."""

from __future__ import annotations

import datetime as _dt
import uuid
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORK_WEEKS: tuple[str, ...] = tuple(f"WW{n:02d}" for n in range(17, 30))
RUN_RESULTS: tuple[str, ...] = (
    "PASS",
    "FAIL",
    "NOT RUN",
    "IN PROGRESS",
    "BLOCKED",
)


def runs_path(version: str) -> Path:
    return REPO_ROOT / version / "runs.yaml"


def _coerce_duration_seconds(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return round(seconds, 3)


def normalise_run(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    tid = (raw.get("test_case_id") or "").strip()
    week = (raw.get("work_week") or "").strip()
    if not tid or not week:
        return None

    date = raw.get("date")
    if isinstance(date, (_dt.date, _dt.datetime)):
        date = date.isoformat()[:10]
    elif date is not None:
        date = str(date).strip()

    result = (raw.get("result") or "NOT RUN").strip().upper()
    if result not in RUN_RESULTS:
        result = "NOT RUN"

    clean = {
        "id": str(raw.get("id") or uuid.uuid4().hex[:12]),
        "test_case_id": tid,
        "date": date or "",
        "work_week": week,
        "result": result,
        "notes": (raw.get("notes") or "").strip(),
        "jira_link": (raw.get("jira_link") or "").strip(),
        "executed_by": (raw.get("executed_by") or "").strip(),
        "created_at": str(raw.get("created_at") or _dt.datetime.now().isoformat(timespec="seconds")),
    }
    duration = _coerce_duration_seconds(raw.get("duration_seconds"))
    if duration is not None:
        clean["duration_seconds"] = duration
    return clean


def load_runs(version: str) -> dict:
    path = runs_path(version)
    if path.exists():
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    try:
        year = int(data.get("year") or _dt.date.today().year)
    except (TypeError, ValueError):
        year = _dt.date.today().year

    runs: list[dict] = []
    for raw in data.get("runs") or []:
        clean = normalise_run(raw)
        if clean is not None:
            runs.append(clean)

    return {
        "year": year,
        "work_weeks": list(data.get("work_weeks") or DEFAULT_WORK_WEEKS),
        "runs": runs,
    }


def save_runs(version: str, state: dict) -> None:
    path = runs_path(version)
    path.parent.mkdir(parents=True, exist_ok=True)

    runs_clean: list[dict] = []
    for raw in state.get("runs") or []:
        clean = normalise_run(raw)
        if clean is not None:
            runs_clean.append(clean)

    payload = {
        "year": int(state.get("year") or _dt.date.today().year),
        "work_weeks": list(state.get("work_weeks") or DEFAULT_WORK_WEEKS),
        "runs": runs_clean,
    }

    banner = (
        "# =============================================================================\n"
        "# Automate 5 - Test-Case Run Records\n"
        "# =============================================================================\n"
        "# Append-only log of test-case executions. Edit/delete is done via the GUI's\n"
        "# Timeline view. The Timeline is purely a visualisation of these records.\n"
        "# =============================================================================\n\n"
    )
    body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(banner + body, encoding="utf-8")


def current_work_week(date: _dt.date, valid_weeks: list[str]) -> str | None:
    candidate = f"WW{date.isocalendar().week:02d}"
    return candidate if candidate in valid_weeks else None


def latest_run_per_test_case(runs: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for run in runs:
        tid = run.get("test_case_id")
        if not tid:
            continue
        key = (run.get("date") or "", run.get("created_at") or "")
        existing = latest.get(tid)
        if existing is None or key > (existing.get("date") or "", existing.get("created_at") or ""):
            latest[tid] = run
    return latest


def append_run(
    version: str,
    test_case_id: str,
    result: str,
    *,
    notes: str = "",
    executed_by: str = "",
    jira_link: str = "",
    date: _dt.date | None = None,
    duration_seconds: float | None = None,
) -> dict:
    state = load_runs(version)
    run_date = date or _dt.date.today()
    weeks = list(state.get("work_weeks") or DEFAULT_WORK_WEEKS)
    week = current_work_week(run_date, weeks) or (weeks[0] if weeks else f"WW{run_date.isocalendar().week:02d}")

    record = {
        "id": uuid.uuid4().hex[:12],
        "test_case_id": test_case_id,
        "date": run_date.isoformat(),
        "work_week": week,
        "result": result.upper(),
        "notes": notes,
        "jira_link": jira_link,
        "executed_by": executed_by,
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    duration = _coerce_duration_seconds(duration_seconds)
    if duration is not None:
        record["duration_seconds"] = duration
    state["runs"] = [*(state.get("runs") or []), record]
    save_runs(version, state)
    return record
