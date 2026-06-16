"""Current pytest session config (used by TestCaseFramework.log and conftest hooks)."""

from __future__ import annotations

from typing import Any

_active: Any = None


def set_active_config(config: Any) -> None:
    global _active  # noqa: PLW0603
    _active = config


def get_active_config() -> Any:
    return _active
