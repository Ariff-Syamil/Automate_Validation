"""MainWindow integration tests with lightweight panel/presenter doubles."""

from __future__ import annotations

import sys
from types import ModuleType

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget

from tests.framework.base import TestCaseFramework, scenario


class _BaseBridge(QObject):
    base_nav_clicked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.base_active_section = "base"


class _VlaBridge(QObject):
    vla_nav_clicked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.vla_active_section = "vla"


class _AnalyticBridge(QObject):
    analytic_nav_clicked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.analytic_active_section = "analysis"


class _Panel(QWidget):
    bridge_type = QObject

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.bridge = self.bridge_type()
        self.registered_controller = None

    def register_camera_sinks(self, controller) -> None:
        self.registered_controller = controller


class _BasePanel(_Panel):
    bridge_type = _BaseBridge


class _VlaPanel(_Panel):
    bridge_type = _VlaBridge


class _AnalyticPanel(_Panel):
    bridge_type = _AnalyticBridge


class _Presenter:
    def __init__(self, bridge) -> None:
        self.bridge = bridge
        self._camera_controller = object()
        self.shutdown_called = False

    def shutdown(self) -> None:
        self.shutdown_called = True

    def start_policy_server(self) -> None:
        return None


def _install_fake_module(monkeypatch, name: str, **attrs) -> None:
    module = ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)


class TestMainWindowIntegration(TestCaseFramework):
    @scenario("main_window_nav_sync", "MainWindow routes nav and syncs active sections")
    def test_main_window_navigation_and_shutdown(self, monkeypatch) -> None:
        _install_fake_module(
            monkeypatch,
            "gui.panels.base_design.base_view",
            BasePanel=_BasePanel,
        )
        _install_fake_module(
            monkeypatch,
            "gui.panels.base_design.base_presenter",
            BasePanelPresenter=_Presenter,
        )
        _install_fake_module(monkeypatch, "gui.panels.vla_design.view", VlaPanel=_VlaPanel)
        _install_fake_module(monkeypatch, "gui.panels.vla_design.presenter", VlaPanelPresenter=_Presenter)
        _install_fake_module(
            monkeypatch,
            "gui.panels.analytic_design.view",
            AnalyticPanel=_AnalyticPanel,
        )
        _install_fake_module(
            monkeypatch,
            "gui.panels.analytic_design.presenter",
            AnalyticPanelPresenter=_Presenter,
        )
        from gui.main_window import MainWindow

        app = QApplication.instance() or QApplication(sys.argv[:1])
        window = MainWindow()
        try:
            window.base_panel.bridge.base_nav_clicked.emit("vla")
            assert window.currentIndex() == window.PAGE_VLA
            assert window.base_panel.bridge.base_active_section == "vla"
            assert window.vla_panel.bridge.vla_active_section == "vla"
            assert window.analytic_panel.bridge.analytic_active_section == "vla"

            window.vla_panel.bridge.vla_nav_clicked.emit("analysis")
            assert window.currentIndex() == window.PAGE_ANALYTIC

            window.analytic_panel.bridge.analytic_nav_clicked.emit("base")
            assert window.currentIndex() == window.PAGE_BASE

            window.close()
            assert window.base_presenter.shutdown_called is True
        finally:
            window.deleteLater()
            app.processEvents()
