"""Environment gates declared in suite config.yaml (e.g. requires_display)."""

from __future__ import annotations

import os
import sys
from typing import Any


def display_available() -> bool:
    """Best-effort check for a usable GUI display (GUI tests only)."""
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    # Windows and other platforms: assume a session is available.
    return True


def environment_blocks_run(environment: dict[str, Any]) -> tuple[bool, str]:
    """
    Return (should_skip, reason).

    If environment.requires_display is true and no display is available, skip.
    """
    if environment.get("requires_display") and not display_available():
        return True, "requires_display is set but no display was detected (DISPLAY/WAYLAND_DISPLAY)"
    return False, ""
