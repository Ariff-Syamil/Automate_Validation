"""Unit tests for validation GUI execution result mapping."""

from __future__ import annotations

import subprocess
import datetime as dt
from pathlib import Path
from types import SimpleNamespace

import yaml

from automation.gui import executor
from automation.gui import run_store


def _write_gui_cases(root: Path, cases: list[dict]) -> None:
    path = root / "automate_5" / "gui" / "test_cases.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"test_cases": cases}
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_gui_case(root: Path, *, status: str = "Ready", dependency: list[str] | None = None) -> None:
    _write_gui_cases(
        root,
        [
            {
                "test_case_id": "TC-GUI-999",
                "test_name": "Executor mapping test",
                "automation_status": status,
                "dependency": dependency,
            }
        ],
    )


def _patch_roots(monkeypatch, tmp_path: Path) -> None:
    automation_dir = tmp_path / "automation" / "gui"
    automation_dir.mkdir(parents=True, exist_ok=True)
    automate5_root = tmp_path / "Automate5"
    for rel in ("automate5/__init__.py", "backend/vla_client.py", "gui/main_window.py"):
        target = automate5_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    (automation_dir / "execution_map.yaml").write_text("test_cases: {}\n", encoding="utf-8")
    monkeypatch.setattr(executor, "VALIDATION_ROOT", tmp_path)
    monkeypatch.setattr(executor, "AUTOMATION_DIR", automation_dir)
    monkeypatch.setattr(executor, "DEFAULT_AUTOMATE5_ROOT", automate5_root)
    monkeypatch.setattr(executor, "_python_executable", lambda _root: Path("python"))


def test_run_store_defaults_to_full_bounded_work_week_universe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "REPO_ROOT", tmp_path)

    state = run_store.load_runs("automate_5")

    assert state["work_weeks"][0] == "WW01"
    assert state["work_weeks"][-1] == "WW52"
    assert len(state["work_weeks"]) == 52


def test_run_store_preserves_run_name_and_full_week_universe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "REPO_ROOT", tmp_path)
    state = {
        "year": 2026,
        "work_weeks": ["WW17"],
        "runs": [
            {
                "test_case_id": "TC-GUI-999",
                "date": "2026-06-30",
                "work_week": "WW27",
                "result": "PASS",
                "run_name": "Smoke_1",
            },
        ],
    }

    run_store.save_runs("automate_5", state)

    data = yaml.safe_load((tmp_path / "automate_5" / "runs.yaml").read_text(encoding="utf-8"))
    assert data["work_weeks"][0] == "WW01"
    assert data["work_weeks"][-1] == "WW52"
    assert data["runs"][0]["run_name"] == "Smoke_1"


def test_timeline_display_work_weeks_pad_record_span() -> None:
    from scripts import gui as gui_script

    weeks = gui_script.display_work_weeks_for_runs([
        {"work_week": "WW25"},
        {"work_week": "WW35"},
    ], minimum_columns=10)

    assert weeks[0] == "WW24"
    assert weeks[-1] == "WW36"


def test_timeline_display_work_weeks_expand_balanced_to_minimum_columns() -> None:
    from scripts import gui as gui_script

    weeks = gui_script.display_work_weeks_for_runs([
        {"work_week": "WW25"},
    ], minimum_columns=7)

    assert weeks == ["WW22", "WW23", "WW24", "WW25", "WW26", "WW27", "WW28"]


def test_timeline_display_work_weeks_use_current_week_without_records() -> None:
    from scripts import gui as gui_script

    today = dt.date(2026, 6, 30)
    current_week = today.isocalendar().week

    assert gui_script.display_work_weeks_for_runs([], today=today, minimum_columns=6) == [
        f"WW{current_week - 1:02d}",
        f"WW{current_week:02d}",
        f"WW{current_week + 1:02d}",
        f"WW{current_week + 2:02d}",
        f"WW{current_week + 3:02d}",
        f"WW{current_week + 4:02d}",
    ]


def test_timeline_display_work_weeks_are_bounded() -> None:
    from scripts import gui as gui_script

    assert gui_script.display_work_weeks_for_runs(
        [{"work_week": "WW01"}],
        minimum_columns=8,
    ) == ["WW01", "WW02", "WW03", "WW04", "WW05", "WW06", "WW07", "WW08"]
    assert gui_script.display_work_weeks_for_runs(
        [{"work_week": "WW52"}],
        minimum_columns=8,
    ) == ["WW45", "WW46", "WW47", "WW48", "WW49", "WW50", "WW51", "WW52"]


def test_timeline_display_work_weeks_full_range_is_not_expanded() -> None:
    from scripts import gui as gui_script

    weeks = gui_script.display_work_weeks_for_runs([
        {"work_week": "WW01"},
        {"work_week": "WW52"},
    ], minimum_columns=60)

    assert weeks[0] == "WW01"
    assert weeks[-1] == "WW52"
    assert len(weeks) == 52


def test_next_unnamed_run_name_uses_next_available_suffix() -> None:
    from scripts import gui as gui_script

    assert gui_script.next_unnamed_run_name([
        {"run_name": "unnamed_1"},
        {"run_name": "Unnamed_2"},
        {"run_name": "Smoke_1"},
    ]) == "unnamed_3"


def test_validation_report_summary_groups_results_by_module_prefix() -> None:
    from scripts import gui as gui_script

    summary = gui_script.validation_report_summary(
        [
            {"test_case_id": "TC-GUI-001", "date": "2026-06-30", "result": "PASS"},
            {"test_case_id": "TC-SW-001", "date": "2026-06-30", "result": "FAIL"},
            {"test_case_id": "TC-SYS-001", "date": "2026-06-30", "result": "BLOCKED"},
        ],
        ["TC-GUI-001", "TC-GUI-002", "TC-SW-001", "TC-SYS-001"],
    )

    rows_by_module = {row["module"]: row for row in summary["rows"]}
    assert rows_by_module["GUI"]["total"] == 2
    assert rows_by_module["GUI"]["pass"] == 1
    assert rows_by_module["GUI"]["blocked"] == 1
    assert rows_by_module["Software"]["fail"] == 1
    assert rows_by_module["System"]["blocked"] == 1
    assert summary["total"] == {
        "module": "Total",
        "prefix": "",
        "total": 4,
        "pass": 1,
        "fail": 1,
        "blocked": 2,
        "pass_percent": 25,
    }


def test_validation_report_html_escapes_dynamic_labels() -> None:
    from scripts import gui as gui_script

    report = gui_script.build_validation_html_report(
        version="automate_5",
        runs=[],
        test_case_ids=["TC-GUI-001"],
        work_weeks=["WW26"],
        run_names=["Real <Run> & 1"],
        report_date=dt.date(2026, 6, 24),
    )

    assert "Validation Test Report" in report
    assert "Automate 5 - Validation Suite" in report
    assert "WW26" in report
    assert "Real &lt;Run&gt; &amp; 1" in report
    assert "Real <Run> & 1" not in report
    assert "<b>1</b> Blocked" in report


def test_validation_report_html_includes_module_rows_and_totals() -> None:
    from scripts import gui as gui_script

    report = gui_script.build_validation_html_report(
        version="automate_5",
        runs=[
            {"test_case_id": "TC-GUI-001", "date": "2026-06-30", "result": "PASS"},
            {"test_case_id": "TC-GUI-002", "date": "2026-06-30", "result": "FAIL"},
        ],
        test_case_ids=["TC-GUI-001", "TC-GUI-002", "TC-GUI-003"],
        work_weeks=["WW25", "WW26"],
        run_names=[],
        report_date=dt.date(2026, 6, 30),
    )

    assert "WW25-WW26" in report
    assert "Run: All Runs" in report
    assert "GUI <span" in report
    assert "3 tests - 33% pass" in report
    assert "<b>1</b> Passed" in report
    assert "<b>1</b> Failed" in report
    assert "<b>1</b> Blocked" in report


def test_reveal_in_file_explorer_selects_file_on_windows(tmp_path: Path, monkeypatch) -> None:
    from scripts import gui as gui_script

    commands: list[list[str]] = []
    output_path = tmp_path / "result.csv"
    output_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(gui_script.sys, "platform", "win32")
    monkeypatch.setattr(gui_script.subprocess, "Popen", lambda command: commands.append(command))

    gui_script.reveal_in_file_explorer(output_path)

    assert commands == [["explorer.exe", "/select,", str(output_path.resolve())]]


def test_run_case_blocks_unknown_test_case(tmp_path: Path, monkeypatch) -> None:
    _patch_roots(monkeypatch, tmp_path)
    recorded: list[tuple] = []
    monkeypatch.setattr(executor, "append_run", lambda *args, **kwargs: recorded.append((args, kwargs)))

    result = executor.run_case("automate_5", "TC-GUI-404")

    assert result.result == "BLOCKED"
    assert "Unknown test case ID" in result.notes
    assert recorded and recorded[-1][0][2] == "BLOCKED"


def test_run_case_blocks_not_ready_case(tmp_path: Path, monkeypatch) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_gui_case(tmp_path, status="Not Ready")

    result = executor.run_case("automate_5", "TC-GUI-999", record=False)

    assert result.result == "BLOCKED"
    assert result.notes == "Automation status is Not Ready."


def test_run_case_runs_dependencies_before_requested_case(tmp_path: Path, monkeypatch) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_gui_cases(
        tmp_path,
        [
            {
                "test_case_id": "TC-GUI-001",
                "test_name": "Dependency",
                "automation_status": "Ready",
                "dependency": None,
            },
            {
                "test_case_id": "TC-GUI-999",
                "test_name": "Dependent",
                "automation_status": "Ready",
                "dependency": ["TC-GUI-001"],
            },
        ],
    )
    commands: list[list[str]] = []

    def fake_run(command, *_args, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="1 passed in 0.01s", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = executor.run_case("automate_5", "TC-GUI-999", record=False)

    assert result.result == "PASS"
    assert len(commands) == 2
    assert commands[0][3].endswith("::test_tc_gui_001")
    assert commands[1][3].endswith("::test_tc_gui_999")


def test_dependency_run_records_trigger_note(tmp_path: Path, monkeypatch) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_gui_cases(
        tmp_path,
        [
            {
                "test_case_id": "TC-GUI-001",
                "test_name": "Dependency",
                "automation_status": "Ready",
                "dependency": None,
            },
            {
                "test_case_id": "TC-GUI-999",
                "test_name": "Dependent",
                "automation_status": "Ready",
                "dependency": ["TC-GUI-001"],
            },
        ],
    )
    recorded: list[tuple] = []
    monkeypatch.setattr(executor, "append_run", lambda *args, **kwargs: recorded.append((args, kwargs)))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="1 passed", stderr=""),
    )

    result = executor.run_case("automate_5", "TC-GUI-999")

    assert result.result == "PASS"
    assert recorded[0][0][1] == "TC-GUI-001"
    assert "Run because TC-GUI-999 depends on this test case." in recorded[0][1]["notes"]
    assert recorded[1][0][1] == "TC-GUI-999"


def test_run_case_blocks_when_dependency_automation_unavailable(tmp_path: Path, monkeypatch) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_gui_cases(
        tmp_path,
        [
            {
                "test_case_id": "TC-GUI-001",
                "test_name": "Unavailable dependency",
                "automation_status": "Not Ready",
                "automation_readiness": "Semi-Automatable",
                "test_environment_ci_hil": "HIL",
                "dependency": None,
            },
            {
                "test_case_id": "TC-GUI-999",
                "test_name": "Dependent",
                "automation_status": "Ready",
                "dependency": ["TC-GUI-001"],
            },
        ],
    )

    result = executor.run_case("automate_5", "TC-GUI-999", record=False)

    assert result.result == "BLOCKED"
    assert "Dependency not PASS: TC-GUI-001=BLOCKED" in result.notes
    assert "Run because TC-GUI-999 depends on this test case." in result.notes
    assert "Dependency is marked HIL/hardware environment" in result.notes
    assert "Automation status is Not Ready." in result.notes


def test_not_ready_dependency_is_not_recorded_or_executed(tmp_path: Path, monkeypatch) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_gui_cases(
        tmp_path,
        [
            {
                "test_case_id": "TC-GUI-001",
                "test_name": "Unavailable dependency",
                "automation_status": "Not Ready",
                "dependency": None,
            },
            {
                "test_case_id": "TC-GUI-999",
                "test_name": "Dependent",
                "automation_status": "Ready",
                "dependency": ["TC-GUI-001"],
            },
        ],
    )
    recorded: list[tuple] = []
    commands: list[list[str]] = []
    monkeypatch.setattr(executor, "append_run", lambda *args, **kwargs: recorded.append((args, kwargs)))

    def fake_run(command, *_args, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="1 passed", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = executor.run_case("automate_5", "TC-GUI-999")

    assert result.result == "BLOCKED"
    assert not commands
    assert len(recorded) == 1
    assert recorded[0][0][1] == "TC-GUI-999"
    assert recorded[0][0][2] == "BLOCKED"
    assert "Dependency not PASS: TC-GUI-001=BLOCKED" in result.notes
    assert "Automation status is Not Ready." in result.notes


def test_run_case_maps_pytest_skip_to_blocked(tmp_path: Path, monkeypatch) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_gui_case(tmp_path)

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="1 skipped in 0.01s", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = executor.run_case("automate_5", "TC-GUI-999", record=False)

    assert result.result == "BLOCKED"
    assert "skipped" in result.notes
    assert result.duration_seconds is not None


def test_run_case_maps_timeout_to_fail(tmp_path: Path, monkeypatch) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_gui_case(tmp_path)

    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=3)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = executor.run_case("automate_5", "TC-GUI-999", record=False)

    assert result.result == "FAIL"
    assert "Timed out running pytest target" in result.notes
