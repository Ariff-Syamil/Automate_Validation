"""VLA suite: Qt env before any PySide6 import; session-wide QApplication.

Mirrors ``tests/test_suite_gui/conftest.py``. The VLA worker, presenter
glue, and end-to-end smoke tests all need a running Qt event loop because
``VlaInferenceWorker`` and ``VlaPanelPresenter`` use cross-thread queued
signals. The client and config tests do not strictly require Qt, but they
benefit from sharing the same ``QApplication`` so the suite has a single
entry point.
"""

from __future__ import annotations

import os
import sys
import types

# Native display by default; CI can opt in via QT_QPA_PLATFORM=offscreen.
# Must be set before importing PySide6 (this conftest is loaded first).
os.environ.setdefault("PYTEST_QT_API", "pyside6")


def _install_hololink_stub() -> None:
    """Make ``backend.hololink_camera_controller`` importable on dev boxes.

    The production module is Linux-only (depends on the Hololink FPGA SDK).
    The VLA presenter imports it eagerly at module scope, which would break
    every VLA suite test on Windows. The stub is a no-op ``QObject`` exposing
    the minimal surface the presenter touches: ``cam1_live_changed``,
    ``cam2_live_changed``, ``configure_error`` signals and ``apply_preview()``.

    Keep these signals in sync with the production
    ``HololinkCameraController`` (backend/hololink_camera_controller.py); the
    presenter connects every one of them in ``__init__``, so a missing signal
    raises ``AttributeError`` at presenter construction.
    """
    name = "backend.hololink_camera_controller"
    if name in sys.modules:
        return

    from PySide6.QtCore import QObject, Signal

    class _StubHololinkCameraController(QObject):
        cam1_live_changed = Signal(bool)
        cam2_live_changed = Signal(bool)
        configure_error = Signal(str)

        def __init__(self, parent: QObject | None = None) -> None:
            super().__init__(parent)

        def apply_preview(self, *args, **kwargs) -> None:  # noqa: ARG002
            return None

    module = types.ModuleType(name)
    module.HololinkCameraController = _StubHololinkCameraController
    sys.modules[name] = module


_install_hololink_stub()


import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qapp_vla():
    """Create one QApplication for the entire VLA test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    yield app
    app.quit()
