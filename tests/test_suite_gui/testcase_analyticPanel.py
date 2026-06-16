"""GUI scenarios for AnalyticPanel — bridge + QML compile checks (mirrors Base panel tests)."""

from __future__ import annotations

import sys
from pathlib import Path

from tests.framework.base import TestCaseFramework, scenario
from tests._paths import AUTOMATE5_ROOT


class TestAnalyticPanel(TestCaseFramework):
    # config.yaml is loaded from this file's directory (test_suite_gui/).

    @scenario("bridge_defaults", "AnalyticPanelBridge initialises with sensible defaults")
    def test_bridge_defaults(self) -> None:
        """Verify the Python bridge for the analytics panel constructs without QQuickWidget."""
        from PySide6.QtCore import QCoreApplication

        from gui.panels.analytic_design.view import AnalyticPanelBridge

        app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
        self.log("test_bridge_defaults: creating AnalyticPanelBridge")
        bridge = AnalyticPanelBridge()

        assert bridge.analytic_active_section == "analysis"
        assert bridge.analytic_display_mode == "both"
        assert 0.15 <= bridge.analytic_split_ratio <= 0.85
        assert abs(bridge.analytic_split_ratio - 0.55) < 1e-6

        self.log(
            f"test_bridge_defaults: OK (mode={bridge.analytic_display_mode}, "
            f"split={bridge.analytic_split_ratio})"
        )
        bridge.deleteLater()
        app.processEvents()

    @scenario("qml_source", "analytic_panel.qml exists and imports AppComponents")
    def test_qml_source(self) -> None:
        """File-level sanity without scene graph render."""
        repo_root = AUTOMATE5_ROOT
        qml_path = repo_root / "gui" / "panels" / "analytic_design" / "qml" / "analytic_panel.qml"
        self.log(f"test_qml_source: checking {qml_path}")

        assert qml_path.is_file(), f"Missing QML: {qml_path}"
        text = qml_path.read_text(encoding="utf-8")
        assert "import AppComponents" in text, "analytic_panel.qml must import AppComponents"
        assert "analytic_bridge" in text, "analytic_panel.qml must reference analytic_bridge"
        self.log("test_qml_source: OK")

    @scenario("qml_loads", "analytic_panel.qml parses and resolves all imports")
    def test_qml_loads(self) -> None:
        """QQmlComponent to Ready — no .create() (avoids scene graph / Windows offscreen issues)."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlComponent, QQmlEngine

        app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])

        repo_root = AUTOMATE5_ROOT
        qml_path = repo_root / "gui" / "panels" / "analytic_design" / "qml" / "analytic_panel.qml"
        components_path = repo_root / "gui" / "components"

        engine = QQmlEngine()
        engine.addImportPath(str(components_path.resolve()))

        self.log(f"test_qml_loads: compiling {qml_path}")
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_path.resolve())))

        for _ in range(200):
            if component.status() != QQmlComponent.Status.Loading:
                break
            app.processEvents()

        errors = [f"{e.url().toString()}:{e.line()}:{e.column()} {e.description()}"
                  for e in component.errors()]
        assert component.status() == QQmlComponent.Status.Ready, (
            "analytic_panel.qml failed to load:\n  " + "\n  ".join(errors)
        )
        self.log("test_qml_loads: OK (component Ready, imports resolved)")

        engine.deleteLater()
        app.processEvents()
