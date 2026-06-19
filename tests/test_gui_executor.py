"""Unit tests for validation GUI execution result mapping."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import yaml

from automation.gui import executor


def _write_gui_case(root: Path, *, status: str = "Ready", dependency: list[str] | None = None) -> None:
    path = root / "automate_5" / "gui" / "test_cases.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "test_cases": [
            {
                "test_case_id": "TC-GUI-999",
                "test_name": "Executor mapping test",
                "automation_status": status,
                "dependency": dependency,
            }
        ]
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _patch_roots(monkeypatch, tmp_path: Path) -> None:
    automation_dir = tmp_path / "automation" / "gui"
    automation_dir.mkdir(parents=True, exist_ok=True)
    (automation_dir / "execution_map.yaml").write_text("test_cases: {}\n", encoding="utf-8")
    monkeypatch.setattr(executor, "VALIDATION_ROOT", tmp_path)
    monkeypatch.setattr(executor, "AUTOMATION_DIR", automation_dir)
    monkeypatch.setattr(executor, "DEFAULT_AUTOMATE5_ROOT", tmp_path / "Automate5")
    monkeypatch.setattr(executor, "_python_executable", lambda _root: Path("python"))


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


def test_run_case_blocks_when_dependency_is_not_pass(tmp_path: Path, monkeypatch) -> None:
    _patch_roots(monkeypatch, tmp_path)
    _write_gui_case(tmp_path, dependency=["TC-GUI-001"])
    monkeypatch.setattr(
        executor,
        "load_runs",
        lambda _version: {"runs": [{"test_case_id": "TC-GUI-001", "result": "FAIL"}]},
    )

    result = executor.run_case("automate_5", "TC-GUI-999", record=False)

    assert result.result == "BLOCKED"
    assert result.notes == "Dependency not PASS: TC-GUI-001"


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
