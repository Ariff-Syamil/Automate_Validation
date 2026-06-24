"""Tests for Automate5 suite configuration discovery and environment gates."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.framework import env_checks
from tests.framework.config import TestConfig, discover_suite_config_paths


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_test_config_from_yaml_defaults_and_tag_coercion(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    _write_yaml(path, {"suite_name": "demo", "tags": "unit"})

    cfg = TestConfig.from_yaml(path)

    assert cfg.suite_name == "demo"
    assert cfg.tags == ["unit"]
    assert cfg.description == ""
    assert cfg.environment == {}
    assert cfg.mocks == []
    assert cfg.skip_in_ci is False


def test_test_config_rejects_missing_suite_name(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    _write_yaml(path, {"tags": ["unit"]})

    with pytest.raises(ValueError, match="suite_name"):
        TestConfig.from_yaml(path)


def test_discover_suite_config_paths_sorted(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "test_suite_b" / "config.yaml", {"suite_name": "b"})
    _write_yaml(tmp_path / "test_suite_a" / "config.yaml", {"suite_name": "a"})
    _write_yaml(tmp_path / "not_a_suite" / "config.yaml", {"suite_name": "ignored"})

    paths = discover_suite_config_paths(tmp_path)

    assert [p.parent.name for p in paths] == ["test_suite_a", "test_suite_b"]


def test_environment_requires_display_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env_checks, "display_available", lambda: False)

    skip, reason = env_checks.environment_blocks_run({"requires_display": True})

    assert skip is True
    assert "requires_display" in reason


def test_environment_allows_when_display_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env_checks, "display_available", lambda: True)

    assert env_checks.environment_blocks_run({"requires_display": True}) == (False, "")
    assert env_checks.environment_blocks_run({}) == (False, "")
