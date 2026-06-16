"""VLA prompt handler acceptance tests (Plan step 5).

Eight scenarios from plan section 4 step 5:

- test_prompt_starts_server_when_down
- test_prompt_reuses_ready_server
- test_prompt_blocked_when_panel_inactive
- test_empty_prompt_is_ignored
- test_prompt_without_frame_autostarts_camera_and_defers
- test_prompt_without_frame_times_out
- test_prompt_after_error_state_auto_resets
- test_prompt_blocked_when_start_fails_twice
- test_joint_state_padding_shape

Tests inject lightweight stubs for the supervisor and worker so the
presenter is exercised in isolation; the real subprocess-managing
supervisor is the responsibility of Step 7.
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
    """Stand-in for ``VlaServerSupervisorBase``.

    Records ``start()`` / ``reset()`` / ``stop()`` calls; the test drives
    state transitions explicitly via ``_set_state``.
    """

    state_changed        = Signal(str)
    state_detail_changed = Signal(str)
    started              = Signal()
    start_failed         = Signal(str)

    def __init__(self, state: str = "offline", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._state_detail = ""
        self.start_calls = 0
        self.reset_calls = 0
        self.stop_calls = 0

    @property
    def state(self) -> str:
        return self._state

    @property
    def state_detail(self) -> str:
        return self._state_detail

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1

    def reset(self) -> None:
        self.reset_calls += 1
        self._state = "offline"
        self._state_detail = ""
        self.state_changed.emit(self._state)
        self.state_detail_changed.emit(self._state_detail)

    # test-only helpers
    def _set_state(self, value: str, detail: str = "") -> None:
        self._state = value
        self._state_detail = detail
        self.state_changed.emit(value)
        self.state_detail_changed.emit(detail)

    def simulate_start_failed(self, reason: str) -> None:
        self._set_state("error", reason)
        self.start_failed.emit(reason)


class _StubWorker(QObject):
    """Stand-in for ``VlaInferenceWorker``. Records submitted jobs."""

    action_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.jobs: list[tuple[str, np.ndarray, np.ndarray]] = []

    def submit(self, prompt, frame_rgb, joint_state) -> int:
        self.jobs.append((prompt, frame_rgb, joint_state))
        return len(self.jobs)

    def cancel(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


class _StubCamera(QObject):
    """Stand-in for ``HololinkCameraController`` — never touches hardware.

    Records ``apply_preview`` (Configure) calls so tests can assert the
    presenter auto-started the camera, and reports ``is_live()`` from a flag
    the test controls.
    """

    cam1_live_changed = Signal(bool)
    cam2_live_changed = Signal(bool)

    def __init__(self, live: bool = False, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._live = live
        self.apply_calls = 0

    def is_live(self) -> bool:
        return self._live

    def apply_preview(self, *args, **kwargs) -> None:
        self.apply_calls += 1
        self._live = True

    def shutdown(self) -> None:
        pass


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_frame(w: int = 64, h: int = 48) -> QImage:
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(0x808080)
    return img


def _build_presenter(state: str = "ready"):
    bridge = VlaPanelBridge()
    supervisor = _StubSupervisor(state=state)
    worker = _StubWorker()
    presenter = VlaPanelPresenter(bridge, supervisor=supervisor, worker=worker)
    presenter._last_frame = _make_frame()
    # bridge mirrors the supervisor state seeded in __init__; align it here
    # so tests that flip the state via _set_state see consistent values.
    bridge.vla_server_state = supervisor.state
    bridge.vla_server_state_detail = supervisor.state_detail
    return bridge, supervisor, worker, presenter


# ── Test class ───────────────────────────────────────────────────────────


class TestVlaPromptHandler(TestCaseFramework):
    """Acceptance tests for ``VlaPanelPresenter._handle_prompt_submitted``."""

    @scenario(
        "prompt_starts_server_when_down",
        "Offline supervisor: prompt triggers exactly one supervisor.start() call",
    )
    def test_prompt_starts_server_when_down(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="offline")
        presenter._handle_prompt_submitted("pick up the red block")
        assert supervisor.start_calls == 1
        assert worker.jobs == [], "job must be deferred until started() fires"
        assert bridge.vla_busy == "starting_server"

    @scenario(
        "prompt_reuses_ready_server",
        "Ready supervisor: no start() call; the worker receives the job directly",
    )
    def test_prompt_reuses_ready_server(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="ready")
        presenter._handle_prompt_submitted("ok")
        assert supervisor.start_calls == 0
        assert len(worker.jobs) == 1
        assert bridge.vla_busy == "inferring"

    @scenario(
        "prompt_blocked_when_panel_inactive",
        "Hidden panel: prompt is dropped; no server start, no worker job",
    )
    def test_prompt_blocked_when_panel_inactive(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="offline")
        bridge.vla_active_section = "base"
        presenter._handle_prompt_submitted("ignored")
        assert supervisor.start_calls == 0
        assert worker.jobs == []

    @scenario(
        "empty_prompt_is_ignored",
        "Empty prompt: no worker job, no error surfaced",
    )
    def test_empty_prompt_is_ignored(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="ready")
        for blank in ("", "   ", "\t\n"):
            presenter._handle_prompt_submitted(blank)
        assert worker.jobs == []
        assert supervisor.start_calls == 0
        assert bridge.vla_last_error == ""

    @scenario(
        "prompt_without_frame_autostarts_camera_and_defers",
        "Missing camera frame: prompt auto-starts the camera, defers, then runs on first frame",
    )
    def test_prompt_without_frame_autostarts_camera_and_defers(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="ready")
        # Swap in a hardware-free camera stub (off) so the auto-start path is
        # exercised without touching the real Hololink pipeline.
        camera = _StubCamera(live=False, parent=presenter)
        presenter._camera_controller = camera
        presenter._last_frame = None

        presenter._handle_prompt_submitted("test")

        # Deferred: camera auto-started, no inference yet, prompt held.
        assert camera.apply_calls == 1, "camera must be auto-started when off"
        assert worker.jobs == [], "inference must wait for the first frame"
        assert supervisor.start_calls == 0
        assert presenter._prompt_awaiting_camera == "test"
        assert bridge.vla_busy == "starting_camera"
        assert bridge.vla_last_error == ""

        # First frame arrives → the deferred prompt runs.
        presenter._last_frame = _make_frame()
        presenter._resume_prompt_after_camera()
        assert presenter._prompt_awaiting_camera is None
        assert len(worker.jobs) == 1
        assert bridge.vla_busy == "inferring"

    @scenario(
        "prompt_without_frame_times_out",
        "Missing camera frame: prompt is aborted with an error if no frame arrives in time",
    )
    def test_prompt_without_frame_times_out(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="ready")
        camera = _StubCamera(live=False, parent=presenter)
        presenter._camera_controller = camera
        presenter._last_frame = None

        presenter._handle_prompt_submitted("test")
        assert presenter._prompt_awaiting_camera == "test"

        # Simulate the wait timer firing with still no frame.
        presenter._on_camera_wait_timeout()
        assert presenter._prompt_awaiting_camera is None
        assert worker.jobs == []
        assert supervisor.start_calls == 0
        assert bridge.vla_busy == "idle"
        assert "camera" in bridge.vla_last_error.lower()

    @scenario(
        "prompt_after_error_state_auto_resets",
        "Error state: prompt triggers reset() then start()",
    )
    def test_prompt_after_error_state_auto_resets(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="ready")
        supervisor._set_state("error", "previous attempt timed out")
        presenter._handle_prompt_submitted("retry")
        assert supervisor.reset_calls == 1, "supervisor must be reset before retry"
        assert supervisor.start_calls == 1, "supervisor must be restarted after reset"
        assert worker.jobs == [], "job must wait for started() after reset"

    @scenario(
        "prompt_blocked_when_start_fails_twice",
        "Two-attempt failure: no worker job; bridge surfaces a non-empty failure detail",
    )
    def test_prompt_blocked_when_start_fails_twice(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="offline")
        presenter._handle_prompt_submitted("test")
        # Simulate the supervisor's two-attempt failure path.
        supervisor.simulate_start_failed(
            "attempt 1: port refused; attempt 2: timeout after 60s"
        )
        assert worker.jobs == []
        assert bridge.vla_busy == "idle"
        assert bridge.vla_server_state == "error"
        assert bridge.vla_server_state_detail, "failure detail must be non-empty"
        assert bridge.vla_last_error, "vla_last_error must surface the failure reason"

    @scenario(
        "joint_state_padding_shape",
        "Joint state has shape (6,) with zeros at indices 4 (wrist_roll) and 5 (gripper)",
    )
    def test_joint_state_padding_shape(self) -> None:
        bridge, supervisor, worker, presenter = _build_presenter(state="ready")
        # Populate node 0 motors 0..3 with distinct, parseable angle labels.
        for motor_idx, deg in enumerate((10.0, -20.5, 30.0, 45.25)):
            presenter.update_motor_data(
                node=0,
                index=motor_idx,
                rpm=0.0,
                speed="0 m/s",
                position="0 mm",
                angle=f"{deg}°",
                torque="0 Nm",
            )
        presenter._handle_prompt_submitted("ok")
        assert len(worker.jobs) == 1
        _, _, joint_state = worker.jobs[0]
        assert joint_state.shape == (6,)
        assert joint_state.dtype == np.float32
        np_expected = np.array([10.0, -20.5, 30.0, 45.25, 0.0, 0.0], dtype=np.float32)
        assert np.allclose(joint_state, np_expected), (
            f"expected {np_expected.tolist()}, got {joint_state.tolist()}"
        )
        # Indices 4 and 5 are the dropped slots — must be exactly zero.
        assert joint_state[4] == 0.0
        assert joint_state[5] == 0.0
