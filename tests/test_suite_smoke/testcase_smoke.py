"""Full-stack smoke tests: imports, packet roundtrip, QApplication offscreen launch."""

from __future__ import annotations

import os

from tests._paths import AUTOMATE5_ROOT, module_file_within_automate5, require_automate5_root
from tests.framework.base import TestCaseFramework, scenario


class TestSmoke(TestCaseFramework):
    """Verifies the application can be imported, packets serialise correctly,
    and PySide6 initialises without crashing under an offscreen platform."""
    @scenario("qapplication_launch", "PySide6 QApplication initialises without crashing (offscreen)")
    def test_qapplication_launch(self) -> None:
        self.log("test_qapplication_launch: begin")

        # Force offscreen platform so no display is required (Docker / CI / headless Linux)
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        import sys

        from PySide6.QtWidgets import QApplication

        # QApplication must be created with argv; reuse existing instance if already created
        app = QApplication.instance() or QApplication(sys.argv[:1])
        assert app is not None, "QApplication failed to initialise"

        self.log(f"test_qapplication_launch: QApplication created — platform={app.platformName()}")

        app.quit()
        self.log("test_qapplication_launch: quit() called successfully")


    @scenario("import_smoke", "Core packages import without errors")
    def test_import_smoke(self) -> None:
        self.log("test_import_smoke: begin")
        require_automate5_root()
        self.log(f"AUTOMATE5_ROOT={AUTOMATE5_ROOT}")

        import automate5
        assert hasattr(automate5, "Subsystem")
        assert hasattr(automate5, "PhaseCode")
        assert hasattr(automate5, "ErrorCode")
        self.log(f"automate5 imported from {module_file_within_automate5(automate5)}")
        self.log("test_import_smoke: automate5 OK")

        import automate5.log
        assert hasattr(automate5.log, "logger")
        self.log(f"automate5.log imported from {module_file_within_automate5(automate5.log)}")
        self.log("test_import_smoke: automate5.log OK")

        import gui.main_window
        self.log(f"gui.main_window imported from {module_file_within_automate5(gui.main_window)}")
        self.log("test_import_smoke: gui.main_window OK")

        self.log("test_import_smoke: all imports passed")
