"""GUI suite: Qt env before any PySide6 import; pytest-qt fixtures."""

from __future__ import annotations

import os
import sys
from types import ModuleType
from pathlib import Path

import yaml

# Native display (no offscreen). Must run before importing PySide6 (conftest loads first).
# For headless CI, set before pytest: QT_QPA_PLATFORM=offscreen (and optionally
# QT_QUICK_BACKEND=software, QSG_RHI_BACKEND=software).
os.environ.setdefault("PYTEST_QT_API", "pyside6")

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from tests._paths import AUTOMATE5_ROOT


def _install_fake_gesture_worker_if_needed() -> None:
    """Keep GUI bridge/presenter tests runnable when MediaPipe/CV is absent."""
    try:
        import cv2  # noqa: F401
        import mediapipe  # noqa: F401
        return
    except ImportError:
        pass

    class _FakeGestureWorker(QObject):
        gesture_detected = Signal(int, str)
        motor_selected = Signal(str)
        speed_changed = Signal(float)
        stopped = Signal(bool)
        frame_ready = Signal(QImage)
        error_occurred = Signal(str)
        left_hand_bbox = Signal(float, float, float, float, bool)
        right_hand_bbox = Signal(float, float, float, float, bool)
        frame_size_changed = Signal(int, int)

        def __init__(self, *_args, **_kwargs) -> None:
            super().__init__()

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def wait(self, _timeout: int | None = None) -> None:
            return None

        def isRunning(self) -> bool:
            return False

        def terminate(self) -> None:
            return None

        def reset_tracking(self) -> None:
            return None

        def submit_frame(self, _image: QImage) -> None:
            return None

    module = ModuleType("backend.gesture_worker")
    module.GestureWorker = _FakeGestureWorker
    sys.modules.setdefault("backend.gesture_worker", module)


_install_fake_gesture_worker_if_needed()


@pytest.fixture(scope="session", autouse=True)
def qapp_gui():
    """Create a global QApplication for the entire GUI test session.
    
    This ensures Qt is initialized before any QWidget creation.
    Using scope="session" and autouse=True means it runs once for all GUI tests.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    yield app


@pytest.fixture(scope="session")
def mock_data_config():
    """Load presenter.mock_data config from gui_configuration.yaml.
    
    Returns dict with keys: enabled, tick_ms, camera_enabled, camera_video_paths.
    This is the single source of truth for mock vs live test routing.
    """
    repo_root = AUTOMATE5_ROOT
    config_path = repo_root / "configs" / "gui" / "gui_configuration.yaml"
    
    if not config_path.exists():
        pytest.fail(f"gui_configuration.yaml not found at {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    
    mock_data = cfg.get("presenter", {}).get("mock_data", {})
    
    # Provide defaults
    return {
        "enabled": mock_data.get("enabled", True),
        "tick_ms": mock_data.get("tick_ms", 500),
        "camera_enabled": mock_data.get("camera_enabled", True),
        "camera_video_paths": mock_data.get("camera_video_paths", []),
    }
