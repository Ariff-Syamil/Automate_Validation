"""Presenter arm-actuation + continuous-loop tests (mock-only).

Verifies the two capabilities added on top of the reused framework:

- test_write_goal_called_per_timestep — every action step is forwarded to the
  physical-arm controller via write_goal (mirrors holoscan-vla-work's
  RobotActionOp), in addition to driving the GUI gauges.
- test_continuous_loop_resubmits — when a chunk finishes while the task is
  running, the presenter re-submits a fresh inference job (continuous motion,
  as in holoscan-vla-work).

A fake arm and a counting stub worker are injected so nothing touches hardware,
a model, or the network.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from gui.panels.vla_design.presenter import VlaPanelPresenter
from gui.panels.vla_design.view import VlaPanelBridge
from tests.framework.base import TestCaseFramework, scenario


class _StubSupervisor(QObject):
    state_changed        = Signal(str)
    state_detail_changed = Signal(str)
    started              = Signal()
    start_failed         = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = "ready"
        self._state_detail = ""

    @property
    def state(self) -> str:
        return self._state

    @property
    def state_detail(self) -> str:
        return self._state_detail

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def reset(self) -> None:
        pass


class _CountingWorker(QObject):
    action_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.submissions: list[tuple] = []

    def submit(self, prompt, frame_rgb, joint_state) -> int:
        self.submissions.append((prompt, frame_rgb, joint_state))
        return len(self.submissions)

    def cancel(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


class _FakeArm:
    """Always-connected fake SO-101 controller capturing written goals."""

    def __init__(self) -> None:
        self.enabled = True
        self.is_connected = True
        self.goals: list[np.ndarray] = []
        self.state = np.zeros(6, dtype=np.float32)

    def connect(self) -> bool:
        self.is_connected = True
        return True

    def read_state(self) -> np.ndarray:
        return self.state.copy()

    def write_goal(self, step) -> None:
        self.goals.append(np.asarray(step, dtype=np.float32).copy())

    def disconnect(self) -> None:
        self.is_connected = False


def _build_presenter(worker: QObject | None = None) -> tuple[VlaPanelBridge, VlaPanelPresenter, _FakeArm]:
    bridge = VlaPanelBridge()
    arm = _FakeArm()
    presenter = VlaPanelPresenter(
        bridge,
        supervisor=_StubSupervisor(),
        worker=worker if worker is not None else _CountingWorker(),
        arm=arm,
    )
    presenter._action_timer.setInterval(1)
    presenter._last_frame = QImage(8, 8, QImage.Format.Format_RGB888)
    presenter._last_frame.fill(0)
    return bridge, presenter, arm


class TestVlaArmPlayback(TestCaseFramework):
    """Acceptance tests for arm actuation and the continuous re-inference loop."""

    @scenario(
        "write_goal_called_per_timestep",
        "Each action step is forwarded to the arm via write_goal with the full 6-joint vector",
    )
    def test_write_goal_called_per_timestep(self, qtbot) -> None:
        bridge, presenter, arm = _build_presenter()
        try:
            chunk = np.arange(8 * 6, dtype=np.float32).reshape(8, 6)
            presenter._handle_action_ready(chunk)
            qtbot.waitUntil(lambda: presenter._action_chunk is None, timeout=2000)

            assert len(arm.goals) == 8, (
                f"expected 8 write_goal calls (one per step), got {len(arm.goals)}"
            )
            for i, goal in enumerate(arm.goals):
                assert goal.shape == (6,)
                assert np.array_equal(goal, chunk[i])
            self.log(f"arm received {len(arm.goals)} full 6-joint goals")
        finally:
            presenter.shutdown()

    @scenario(
        "continuous_loop_resubmits",
        "When a chunk finishes while running, the presenter re-submits a fresh inference job",
    )
    def test_continuous_loop_resubmits(self, qtbot) -> None:
        worker = _CountingWorker()
        bridge, presenter, arm = _build_presenter(worker=worker)
        try:
            # Simulate an active task (as the prompt handler would set up).
            presenter._vla_running = True
            presenter._active_prompt = "move the blue dice"

            chunk = np.zeros((3, 6), dtype=np.float32)
            presenter._handle_action_ready(chunk)

            # The chunk plays out, then _on_chunk_complete re-dispatches once.
            qtbot.waitUntil(lambda: len(worker.submissions) >= 1, timeout=2000)

            assert worker.submissions, "continuous loop did not re-submit after the chunk"
            prompt, frame_rgb, joint_state = worker.submissions[0]
            assert prompt == "move the blue dice"
            assert frame_rgb.shape == (8, 8, 3)
            assert joint_state.shape == (6,)
            self.log(f"continuous loop re-submitted {len(worker.submissions)} job(s)")

            # Stop ends the loop: no further re-submissions.
            presenter._handle_stop_clicked()
            count_after_stop = len(worker.submissions)
            qtbot.wait(50)
            assert len(worker.submissions) == count_after_stop, (
                "loop kept re-submitting after Stop"
            )
            assert presenter._vla_running is False
            self.log("Stop halted the continuous loop")
        finally:
            presenter.shutdown()
