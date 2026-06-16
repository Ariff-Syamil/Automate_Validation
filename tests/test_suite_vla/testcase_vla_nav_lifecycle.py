"""VLA nav-away lifecycle tests (Plan step 7).

Four scenarios verify the wire-up in ``VlaPanelPresenter.__init__``:

- test_nav_away_stops_server
- test_nav_away_during_startup_stops_subprocess
- test_nav_back_does_not_auto_start
- test_nav_away_cancels_in_flight_inference

All four use stub supervisor / stub worker so the test does not depend on
the concrete subprocess-managing supervisor; the test only checks that
the presenter routes the active-section change to the right side effects.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from gui.panels.vla_design.presenter import VlaPanelPresenter
from gui.panels.vla_design.view import VlaPanelBridge
from tests.framework.base import TestCaseFramework, scenario


# ── Stubs ────────────────────────────────────────────────────────────────


class _StubSupervisor(QObject):
    state_changed        = Signal(str)
    state_detail_changed = Signal(str)
    started              = Signal()
    start_failed         = Signal(str)

    def __init__(self, state: str = "ready", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._state_detail = ""
        self.start_calls = 0
        self.stop_calls = 0
        self.reset_calls = 0
        # Bookkeeping for the "subprocess torn down" test.
        self.subprocess_terminated = False

    @property
    def state(self) -> str:
        return self._state

    @property
    def state_detail(self) -> str:
        return self._state_detail

    def start(self) -> None:
        self.start_calls += 1
        self._state = "starting"
        self.state_changed.emit("starting")

    def stop(self) -> None:
        self.stop_calls += 1
        # Mimic the real supervisor: subprocess is terminated regardless of
        # which state we are in; the stop-from-starting test reads this flag.
        if self._state in ("starting", "ready"):
            self.subprocess_terminated = True
        self._state = "offline"
        self._state_detail = ""
        self.state_changed.emit("offline")
        self.state_detail_changed.emit("")

    def reset(self) -> None:
        self.reset_calls += 1

    def _set_state(self, value: str) -> None:
        self._state = value
        self.state_changed.emit(value)


class _StubWorker(QObject):
    action_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.jobs: list[tuple] = []
        self.cancel_calls = 0

    def submit(self, prompt, frame_rgb, joint_state) -> int:
        self.jobs.append((prompt, frame_rgb, joint_state))
        return len(self.jobs)

    def cancel(self) -> None:
        self.cancel_calls += 1

    def shutdown(self) -> None:
        pass


def _build_presenter(state: str = "ready"):
    bridge = VlaPanelBridge()
    supervisor = _StubSupervisor(state=state)
    worker = _StubWorker()
    presenter = VlaPanelPresenter(bridge, supervisor=supervisor, worker=worker)
    presenter._last_frame = QImage(8, 8, QImage.Format.Format_RGB888)
    presenter._last_frame.fill(0)
    bridge.vla_server_state = supervisor.state
    return bridge, supervisor, worker, presenter


# ── Test class ───────────────────────────────────────────────────────────


class TestVlaNavLifecycle(TestCaseFramework):

    @scenario(
        "nav_away_stops_server",
        "Supervisor=ready: changing section to 'base' calls supervisor.stop()",
    )
    def test_nav_away_stops_server(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="ready")
        try:
            bridge.vla_active_section = "base"
            assert supervisor.stop_calls == 1, (
                f"expected 1 stop() call on nav-away, got {supervisor.stop_calls}"
            )
            assert bridge.vla_busy == "idle"
            assert worker.cancel_calls == 1
        finally:
            presenter.shutdown()

    @scenario(
        "nav_away_during_startup_stops_subprocess",
        "Supervisor=starting: nav-away tears the subprocess down before ready",
    )
    def test_nav_away_during_startup_stops_subprocess(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="starting")
        try:
            assert not supervisor.subprocess_terminated
            bridge.vla_active_section = "base"
            assert supervisor.stop_calls == 1
            assert supervisor.subprocess_terminated, (
                "supervisor.stop() must have torn down the subprocess"
            )
            assert supervisor.state == "offline"
        finally:
            presenter.shutdown()

    @scenario(
        "nav_back_does_not_auto_start",
        "Returning to the VLA panel does not call supervisor.start() on its own",
    )
    def test_nav_back_does_not_auto_start(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="offline")
        try:
            # Nav away then back; no prompt has been submitted.
            bridge.vla_active_section = "base"
            initial_starts = supervisor.start_calls
            bridge.vla_active_section = "vla"
            assert supervisor.start_calls == initial_starts, (
                "supervisor.start() must not be called on nav-back without a prompt"
            )
        finally:
            presenter.shutdown()

    @scenario(
        "nav_away_cancels_in_flight_inference",
        "Nav-away while playback is running stops the timer and clears _action_chunk",
    )
    def test_nav_away_cancels_in_flight_inference(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="ready")
        try:
            # Prime an in-flight action chunk so the timer is running.
            chunk = np.zeros((16, 6), dtype=np.float32)
            chunk[:, 0] = np.linspace(0.0, 30.0, 16, dtype=np.float32)
            presenter._handle_action_ready(chunk)
            assert presenter._action_chunk is not None
            assert presenter._action_timer.isActive()

            bridge.vla_active_section = "base"

            assert presenter._action_chunk is None, "playback chunk must be cleared on nav-away"
            assert not presenter._action_timer.isActive(), "playback timer must be stopped"
            assert presenter._vla_driving is False
            assert worker.cancel_calls == 1
            assert bridge.vla_busy == "idle"
        finally:
            presenter.shutdown()
