"""Base class for suite tests: loads config.yaml beside the test module, env gates."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, TypeVar

import pytest

from tests._session import get_active_config
from tests.framework.config import TestConfig
from tests.framework.env_checks import environment_blocks_run

F = TypeVar("F", bound=Callable[..., object])


def scenario(scenario_id: str, description: str = "") -> Callable[[F], F]:
    """
    Mark a test method as a named scenario (for docs and optional CLI filtering).

    scenario_id should match the suffix of test_<id> when using the default naming
    convention (e.g. scenario_id \"action1\" -> def test_action1).
    """

    def decorator(fn: F) -> F:
        fn.__scenario_id__ = scenario_id  # type: ignore[attr-defined]
        fn.__scenario_description__ = description  # type: ignore[attr-defined]
        return pytest.mark.scenario(scenario_id)(fn)  # type: ignore[return-value]

    return decorator


def _config_path_for_class(cls: type) -> Path:
    mod = sys.modules.get(cls.__module__)
    file = getattr(mod, "__file__", None) if mod else None
    if not file:
        return Path.cwd() / "config.yaml"
    return Path(file).resolve().parent / "config.yaml"


class TestCaseFramework:
    """Load per-suite config from config.yaml in the same directory as the test module."""

    config: ClassVar[TestConfig | None] = None

    @classmethod
    def setup_class(cls) -> None:
        cfg_path = _config_path_for_class(cls)
        if not cfg_path.is_file():
            pytest.skip(f"Missing suite config: {cfg_path}")
        cls.config = TestConfig.from_yaml(cfg_path)
        if cls.config.skip_in_ci and os.environ.get("CI", "").lower() in {"1", "true", "yes"}:
            pytest.skip("skip_in_ci is true in suite config and CI is set")
        skip, reason = environment_blocks_run(cls.config.environment)
        if skip:
            pytest.skip(reason)

    @classmethod
    def teardown_class(cls) -> None:
        """Override in subclasses to release class-wide resources."""

    def setup_method(self) -> None:
        """Override in subclasses for per-test setup."""

    def teardown_method(self) -> None:
        """Override in subclasses for per-test cleanup."""

    @property
    def suite_dir(self) -> Path:
        """Directory for this suite (contains config.yaml)."""
        return _config_path_for_class(type(self)).parent

    def log(self, message: str) -> None:
        """
        Append a line to this suite's run log (written into log.txt after the session).

        Use for step traces inside tests/helpers. Exceptions still fail the test immediately;
        pytest captures the traceback into log.txt under \"--- Failures ---\".
        """
        cfg = get_active_config()
        if cfg is None:
            return
        stamp = datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]
        buf: list[str] = cfg._suite_run_logs[self.suite_dir]  # type: ignore[attr-defined]
        buf.append(f"[{stamp}] {message}")
