"""Per-suite test configuration loaded from config.yaml next to suite tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class TestConfig(BaseModel):
    """Suite metadata: tags, environment gates, mocks list, CI policy."""

    suite_name: str
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    environment: dict[str, Any] = Field(default_factory=dict)
    mocks: list[str] = Field(default_factory=list)
    skip_in_ci: bool = False

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v.strip()] if v.strip() else []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    @classmethod
    def from_yaml(cls, path: Path) -> TestConfig:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)


def discover_suite_config_paths(tests_root: Path) -> list[Path]:
    """Return every config.yaml under tests/test_suite_*/."""
    return sorted(tests_root.glob("test_suite_*/config.yaml"))
