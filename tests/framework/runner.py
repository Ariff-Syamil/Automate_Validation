"""CLI entry that forwards to pytest with -m / -k expressions."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _class_keyword_from_shorthand(name: str) -> str:
    """BasePanel -> TestBasePanel for pytest -k."""
    n = name.strip()
    if not n:
        return n
    if n.lower().startswith("test"):
        return n
    return f"Test{n[0].upper()}{n[1:]}" if len(n) > 1 else f"Test{n.upper()}"


def _collect_known_tags(tests_root: Path) -> set[str]:
    from tests.framework.config import TestConfig, discover_suite_config_paths

    tags: set[str] = set()
    for path in discover_suite_config_paths(tests_root):
        cfg = TestConfig.from_yaml(path)
        tags.update(t.lower() for t in cfg.tags)
        tags.add(cfg.suite_name.lower())
    return tags


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tests",
        description="Run Automate5 tests (wraps pytest).",
    )
    p.add_argument(
        "target",
        nargs="?",
        default="",
        help="Optional: suite tag (e.g. GUI) or class shorthand (BasePanel, ControlLoop).",
    )
    p.add_argument("--all", action="store_true", help="Run tests (useful with a target for clarity).")
    p.add_argument("--tag", action="append", default=[], help="Extra marker filter (repeatable).")
    p.add_argument("--scenario", default="", help="Scenario id (e.g. action1 -> test_action1).")
    return p


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    """Parse known args; remaining tokens are forwarded to pytest."""
    parser = build_parser()
    ns, rest = parser.parse_known_args(argv)
    if rest and rest[0] == "--":
        rest = rest[1:]
    return ns, rest


def main(argv: list[str] | None = None) -> int:
    import sys

    import pytest

    argv = argv if argv is not None else sys.argv[1:]
    args, pytest_extra = parse_args(argv)
    os.chdir(_repo_root())
    tests_root = _repo_root() / "tests"
    known_tags = _collect_known_tags(tests_root)

    # Default: full suite
    if not args.target and not args.tag and not args.scenario and not pytest_extra:
        return int(pytest.main([str(tests_root), "-q"]))

    pytest_argv: list[str] = [str(tests_root)]

    mark_parts: list[str] = [t.lower() for t in (args.tag or [])]
    target_raw = (args.target or "").strip()
    target_lower = target_raw.lower()
    if target_raw and target_lower in known_tags:
        mark_parts.append(target_lower)

    if mark_parts:
        pytest_argv.extend(["-m", " and ".join(mark_parts)])

    if target_raw and target_lower not in known_tags:
        pytest_argv.extend(["-k", _class_keyword_from_shorthand(target_raw)])

    if args.scenario:
        sid = args.scenario.strip()
        method_kw = sid if sid.startswith("test_") else f"test_{sid}"
        if "-k" in pytest_argv:
            idx = pytest_argv.index("-k") + 1
            pytest_argv[idx] = f"({pytest_argv[idx]}) and {method_kw}"
        else:
            pytest_argv.extend(["-k", method_kw])

    pytest_argv.append("-q")
    pytest_argv.extend(pytest_extra)

    return int(pytest.main(pytest_argv))
