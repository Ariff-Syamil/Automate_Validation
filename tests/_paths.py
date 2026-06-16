"""Shared paths for external Automate5 validation tests."""

from __future__ import annotations

import os
from pathlib import Path


VALIDATION_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTOMATE5_ROOT = VALIDATION_ROOT.parent / "Automate5"
AUTOMATE5_ROOT = Path(os.environ.get("AUTOMATE5_ROOT", DEFAULT_AUTOMATE5_ROOT)).resolve()
