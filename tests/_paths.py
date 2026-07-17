"""Shared paths for external Automate5 validation tests."""

from __future__ import annotations

import os
from pathlib import Path


VALIDATION_ROOT = Path(__file__).resolve().parents[1]


def _candidate_roots() -> tuple[Path, ...]:
    workspace_home = VALIDATION_ROOT.parents[1]
    return (
        workspace_home / "Automate5",
        workspace_home / "automate5",
        workspace_home / "KinNamWorkspace" / "automate5",
        VALIDATION_ROOT.parent / "automate5",
        VALIDATION_ROOT.parent / "Automate5",
    )


def _looks_like_automate5(root: Path) -> bool:
    return (
        (root / "automate5" / "__init__.py").is_file()
        and (root / "backend" / "vla_client.py").is_file()
        and (root / "gui" / "main_window.py").is_file()
    )


def _default_automate5_root() -> Path:
    for candidate in _candidate_roots():
        if _looks_like_automate5(candidate):
            return candidate
    return _candidate_roots()[0]


DEFAULT_AUTOMATE5_ROOT = _default_automate5_root()
AUTOMATE5_ROOT = Path(os.environ.get("AUTOMATE5_ROOT", DEFAULT_AUTOMATE5_ROOT)).resolve()


def require_automate5_root(root: Path = AUTOMATE5_ROOT) -> Path:
    """Return a validated Automate5 checkout path, or fail with actionable detail."""
    missing = [
        str(rel)
        for rel in (
            Path("automate5/__init__.py"),
            Path("backend/vla_client.py"),
            Path("gui/main_window.py"),
        )
        if not (root / rel).is_file()
    ]
    if missing:
        raise RuntimeError(
            f"AUTOMATE5_ROOT does not point at an Automate5 checkout: {root}. "
            f"Missing: {', '.join(missing)}"
        )
    return root


def module_file_within_automate5(module: object, root: Path = AUTOMATE5_ROOT) -> Path:
    """Return module.__file__ only when it was imported from the target checkout."""
    file_attr = getattr(module, "__file__", None)
    if not file_attr:
        raise AssertionError(f"{getattr(module, '__name__', module)!r} has no __file__")
    module_path = Path(file_attr).resolve()
    try:
        module_path.relative_to(root)
    except ValueError as exc:
        raise AssertionError(
            f"{getattr(module, '__name__', module)!r} was imported from {module_path}, "
            f"outside AUTOMATE5_ROOT {root}"
        ) from exc
    return module_path
