"""Pytest hooks: register suite markers, apply tags, and write per-suite log.txt."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from automation.log_consolidation import consolidate_logs
from tests._paths import AUTOMATE5_ROOT, VALIDATION_ROOT, require_automate5_root
from tests._session import get_active_config, set_active_config
from tests.framework.config import TestConfig, discover_suite_config_paths


require_automate5_root()

for _path in (AUTOMATE5_ROOT, VALIDATION_ROOT):
    _text = str(_path)
    while _text in sys.path:
        sys.path.remove(_text)
    sys.path.insert(0, _text)

os.environ.setdefault("AUTOMATE5_ROOT", str(AUTOMATE5_ROOT))


def pytest_configure(config: pytest.Config) -> None:
    tests_root = Path(config.rootpath) / "tests"
    tags: set[str] = set()
    for path in discover_suite_config_paths(tests_root):
        cfg = TestConfig.from_yaml(path)
        tags.update(t.lower() for t in cfg.tags)
        tags.add(cfg.suite_name.lower())
    for tag in sorted(tags):
        config.addinivalue_line("markers", f"{tag}: automarked from tests/**/config.yaml")
    config.addinivalue_line("markers", "scenario(id): scenario id from @scenario decorator")
    # suite_dir -> {nodeid: outcome} (last write wins; teardown failure overrides passed)
    config._suite_outcomes = defaultdict(dict)  # type: ignore[attr-defined]
    config._suite_run_logs = defaultdict(list)  # type: ignore[attr-defined]
    config._suite_failure_text = defaultdict(dict)  # type: ignore[attr-defined]


def pytest_sessionstart(session: pytest.Session) -> None:
    set_active_config(session.config)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        path = getattr(item, "path", None)
        if path is None:
            continue
        cfg_path = path.parent / "config.yaml"
        if not cfg_path.is_file():
            continue
        cfg = TestConfig.from_yaml(cfg_path)
        for tag in cfg.tags:
            safe = tag.replace("-", "_")
            if not safe.isidentifier():
                continue
            item.add_marker(getattr(pytest.mark, safe))


def _failure_text(report: pytest.TestReport) -> str:
    if getattr(report, "longreprtext", None):
        return str(report.longreprtext)
    lr = getattr(report, "longrepr", None)
    return str(lr) if lr else ""


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Record final outcome per node id under the suite directory (test file parent)."""
    session_cfg = get_active_config()
    if session_cfg is None:
        return
    path = getattr(report, "path", None)
    if path is None:
        fspath = getattr(report, "fspath", None)
        if fspath is None:
            return
        path = Path(str(fspath))
    suite_dir = Path(path).resolve().parent
    outcomes: dict[str, str] = session_cfg._suite_outcomes[suite_dir]  # type: ignore[attr-defined]
    failures: dict[str, str] = session_cfg._suite_failure_text[suite_dir]  # type: ignore[attr-defined]
    nodeid = report.nodeid
    if report.when == "setup" and report.failed:
        outcomes[nodeid] = "failed"
        text = _failure_text(report)
        if text:
            failures[nodeid] = text
    elif report.when == "call":
        outcomes[nodeid] = report.outcome
        if report.failed:
            text = _failure_text(report)
            if text:
                failures[nodeid] = text
    elif report.when == "teardown" and report.failed:
        outcomes[nodeid] = "failed"
        text = _failure_text(report)
        if text:
            prev = failures.get(nodeid, "")
            failures[nodeid] = (prev + "\n--- teardown failure ---\n" if prev else "") + text


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Overwrite tests/test_suite_*/log.txt for each suite that ran tests this session."""
    cfg = session.config
    set_active_config(None)

    # Every process that imports automate5.log (i.e. most test sessions here)
    # gets its own timestamped RuntimeLogger file pair under VALIDATION_ROOT
    # / "logs". Fold this session's files into per-day archives so they don't
    # pile up as one file pair per run.
    consolidate_logs(VALIDATION_ROOT / "logs")

    suite_outcomes: dict[Path, dict[str, str]] = getattr(cfg, "_suite_outcomes", {})
    suite_run_logs: dict[Path, list[str]] = getattr(cfg, "_suite_run_logs", {})
    suite_failures: dict[Path, dict[str, str]] = getattr(cfg, "_suite_failure_text", {})
    if not suite_outcomes:
        return
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    for suite_dir, outcomes in sorted(
        suite_outcomes.items(),
        key=lambda kv: str(kv[0]),
    ):
        if not outcomes:
            continue
        if not (suite_dir / "config.yaml").is_file():
            continue
        lines = [
            "Test run log (overwritten each run)",
            f"Finished: {stamp}",
            f"Suite directory: {suite_dir}",
            "",
            "Results:",
        ]
        any_failed = any(o == "failed" for o in outcomes.values())
        for nodeid in sorted(outcomes.keys()):
            outcome = outcomes[nodeid]
            lines.append(f"  {outcome.upper():8}  {nodeid}")

        run_lines = suite_run_logs.get(suite_dir) or []
        if run_lines:
            lines.extend(["", "--- Suite run log (TestCaseFramework.log) ---", *run_lines])

        failures = suite_failures.get(suite_dir) or {}
        failed_nodeids = [nid for nid, out in outcomes.items() if out == "failed"]
        if failed_nodeids and failures:
            lines.append("")
            lines.append("--- Failures (exceptions; first failure stops that test) ---")
            for nodeid in sorted(failed_nodeids):
                text = failures.get(nodeid)
                if not text:
                    continue
                lines.append("")
                lines.append(nodeid)
                lines.append(text.rstrip())

        lines.extend(
            [
                "",
                f"OVERALL: {'FAILED' if any_failed else 'PASSED'}",
            ]
        )
        log_path = suite_dir / "log.txt"
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
