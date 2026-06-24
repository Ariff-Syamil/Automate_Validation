"""Per-suite test configuration loaded from config.yaml next to suite tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import yaml


@dataclass
class TestConfig:
    """Suite metadata: tags, environment gates, mocks list, CI policy."""

    __test__: ClassVar[bool] = False

    suite_name: str
    tags: list[str] = field(default_factory=list)
    description: str = ""
    environment: dict[str, Any] = field(default_factory=dict)
    mocks: list[str] = field(default_factory=list)
    skip_in_ci: bool = False

    @staticmethod
    def _coerce_tags(v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v.strip()] if v.strip() else []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    @staticmethod
    def _coerce_mapping(v: Any, field_name: str) -> dict[str, Any]:
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError(f"{field_name} must be a mapping")
        return v

    @staticmethod
    def _coerce_list(v: Any, field_name: str) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError(f"{field_name} must be a list")
        return [str(x) for x in v]

    @classmethod
    def from_yaml(cls, path: Path) -> TestConfig:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{path} must contain a mapping")
        suite_name = str(data.get("suite_name") or "").strip()
        if not suite_name:
            raise ValueError("suite_name is required")
        return cls(
            suite_name=suite_name,
            tags=cls._coerce_tags(data.get("tags")),
            description=str(data.get("description") or ""),
            environment=cls._coerce_mapping(data.get("environment"), "environment"),
            mocks=cls._coerce_list(data.get("mocks"), "mocks"),
            skip_in_ci=bool(data.get("skip_in_ci", False)),
        )


def discover_suite_config_paths(tests_root: Path) -> list[Path]:
    """Return every config.yaml under tests/test_suite_*/."""
    return sorted(tests_root.glob("test_suite_*/config.yaml"))
