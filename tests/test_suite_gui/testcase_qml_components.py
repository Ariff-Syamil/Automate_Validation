"""Compile checks for high-risk QML components beyond root panels."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtWidgets import QApplication

from tests.framework.base import TestCaseFramework, scenario
from tests._paths import AUTOMATE5_ROOT


_REPO_ROOT = AUTOMATE5_ROOT
_COMPONENTS = [
    "gui/panels/analytic_design/qml/LogsAnalyticsPane.qml",
    "gui/panels/analytic_design/qml/BenchmarkAnalyticsPane.qml",
    "gui/components/AppComponents/LeftRail.qml",
    "gui/components/AppComponents/InspectorDock.qml",
    "gui/components/AppComponents/CameraFeed.qml",
    "gui/components/AppComponents/MotorCard.qml",
    "gui/components/AppComponents/CameraHero.qml",
    "gui/components/AppComponents/NodeView.qml",
]


class TestQmlComponents(TestCaseFramework):
    @scenario("qml_component_sweep", "High-risk AppComponents compile")
    @pytest.mark.parametrize("relative_path", _COMPONENTS, ids=lambda value: Path(value).stem)
    def test_qml_component_compiles(self, relative_path: str) -> None:
        app = QApplication.instance() or QApplication(sys.argv[:1])
        engine = QQmlEngine()
        engine.addImportPath(str((_REPO_ROOT / "gui" / "components").resolve()))
        qml_path = _REPO_ROOT / relative_path

        component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_path.resolve())))
        for _ in range(200):
            if component.status() != QQmlComponent.Status.Loading:
                break
            app.processEvents()
        errors = [f"{e.url().toString()}:{e.line()}:{e.column()} {e.description()}" for e in component.errors()]

        assert component.status() == QQmlComponent.Status.Ready, "\n".join(errors)
        engine.deleteLater()
        app.processEvents()
