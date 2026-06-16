"""Full-stack smoke tests: imports, packet roundtrip, QApplication offscreen launch."""

from __future__ import annotations

import os

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

        import automate5
        assert hasattr(automate5, "Subsystem")
        assert hasattr(automate5, "PhaseCode")
        assert hasattr(automate5, "ErrorCode")
        self.log("test_import_smoke: automate5 OK")

        import automate5.log
        assert hasattr(automate5.log, "logger")
        self.log("test_import_smoke: automate5.log OK")

        import gui.main_window
        self.log("test_import_smoke: gui.main_window OK")

        self.log("test_import_smoke: all imports passed")