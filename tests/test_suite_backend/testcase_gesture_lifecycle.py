"""Gesture controller lifecycle tests and deterministic helper tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from tests.framework.base import TestCaseFramework, scenario
from tests._paths import AUTOMATE5_ROOT


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

    instances: list["_FakeGestureWorker"] = []

    def __init__(self, *_args, **_kwargs) -> None:
        super().__init__()
        self.started = False
        self.stopped_called = False
        self.reset_called = False
        self.submitted: list[QImage] = []
        self.terminated = False
        _FakeGestureWorker.instances.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped_called = True
        self.started = False

    def wait(self, _timeout: int | None = None) -> None:
        return None

    def isRunning(self) -> bool:
        return self.started

    def terminate(self) -> None:
        self.terminated = True
        self.started = False

    def deleteLater(self) -> None:
        return None

    def reset_tracking(self) -> None:
        self.reset_called = True

    def submit_frame(self, image: QImage) -> None:
        self.submitted.append(image)


_fake_worker_module = ModuleType("backend.gesture_worker")
_fake_worker_module.GestureWorker = _FakeGestureWorker
sys.modules.setdefault("backend.gesture_worker", _fake_worker_module)

from backend import gesture_controller as gesture_controller_module  # noqa: E402
from backend.gesture_controller import GestureController  # noqa: E402


def _load_real_gesture_worker_module():
    pytest.importorskip("cv2")
    pytest.importorskip("mediapipe")
    path = AUTOMATE5_ROOT / "backend" / "gesture_worker.py"
    spec = importlib.util.spec_from_file_location("_real_gesture_worker_for_tests", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _landmarks(extended: set[int], *, thumb_extended: bool = False) -> SimpleNamespace:
    points = [SimpleNamespace(x=0.5, y=0.5) for _ in range(21)]
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        points[pip].y = 0.6
        points[tip].y = 0.4 if tip in extended else 0.8
    points[5].x = 0.3
    points[17].x = 0.7
    points[3].x = 0.5
    points[4].x = 0.2 if thumb_extended else 0.8
    points[0].x = 0.0
    points[0].y = 0.0
    return SimpleNamespace(landmark=points)


class TestGestureControllerLifecycle(TestCaseFramework):
    @pytest.fixture(autouse=True)
    def _fake_worker(self, monkeypatch: pytest.MonkeyPatch):
        _FakeGestureWorker.instances.clear()
        monkeypatch.setattr(gesture_controller_module, "GestureWorker", _FakeGestureWorker)

    @scenario("start_stop_idempotent", "GestureController start/stop lifecycle is deterministic")
    def test_start_stop_idempotent(self) -> None:
        controller = GestureController()

        controller.start_recognition()
        controller.start_recognition()
        worker = _FakeGestureWorker.instances[0]
        controller.stop_recognition()

        assert len(_FakeGestureWorker.instances) == 1
        assert worker.started is False
        assert worker.stopped_called is True
        assert controller.is_enabled is False

    @scenario("signal_forwarding", "GestureController forwards worker signals")
    def test_signal_forwarding_and_error_stop(self) -> None:
        controller = GestureController()
        events: list[tuple] = []
        controller.gesture_detected.connect(lambda code, hand: events.append(("gesture", code, hand)))
        controller.motor_selected.connect(lambda motor: events.append(("motor", motor)))
        controller.speed_changed.connect(lambda speed: events.append(("speed", speed)))
        controller.stopped.connect(lambda stopped: events.append(("stopped", stopped)))
        controller.error_occurred.connect(lambda msg: events.append(("error", msg)))

        controller.start_recognition()
        worker = _FakeGestureWorker.instances[0]
        worker.gesture_detected.emit(241, "Left")
        worker.motor_selected.emit("1")
        worker.speed_changed.emit(0.75)
        worker.stopped.emit(True)
        worker.error_occurred.emit("boom")

        assert events == [
            ("gesture", 241, "Left"),
            ("motor", "1"),
            ("speed", 0.75),
            ("stopped", True),
            ("error", "boom"),
        ]
        assert controller.is_enabled is False
        assert worker.stopped_called is True

    @scenario("frame_reset_delegation", "GestureController delegates frames and reset")
    def test_process_frame_and_reset_delegation(self) -> None:
        controller = GestureController()
        image = QImage(2, 2, QImage.Format.Format_RGB32)

        controller.process_frame(image)
        controller.start_recognition()
        worker = _FakeGestureWorker.instances[0]
        controller.process_frame(image)
        controller.reset_tracking()

        assert worker.submitted == [image]
        assert worker.reset_called is True


class TestGestureHelpers(TestCaseFramework):
    @scenario("synthetic_finger_count", "Gesture helper counts synthetic fingers")
    def test_count_extended_fingers_and_fist(self) -> None:
        real_worker = _load_real_gesture_worker_module()
        fist = _landmarks(set(), thumb_extended=False)
        five = _landmarks({8, 12, 16, 20}, thumb_extended=True)

        assert real_worker.count_extended_fingers(fist, "Left") == 0
        assert real_worker.is_fist(fist, "Left") is True
        assert real_worker.count_extended_fingers(five, "Left") == 5
        assert real_worker.is_fist(five, "Left") is False

    @scenario("synthetic_pinch_speed", "Gesture pinch speed handles zero and non-zero geometry")
    def test_calc_pinch_speed(self) -> None:
        real_worker = _load_real_gesture_worker_module()
        zero_ref = _landmarks(set())
        zero_ref.landmark[5].x = 0.0
        zero_ref.landmark[5].y = 0.0
        spread = _landmarks({8}, thumb_extended=True)
        spread.landmark[5].x = 1.0
        spread.landmark[8].x = 1.0
        spread.landmark[8].y = 1.0
        spread.landmark[4].x = 0.0
        spread.landmark[4].y = 0.0

        assert real_worker.calc_pinch_speed(zero_ref) == 0.0
        assert real_worker.calc_pinch_speed(spread) > 0.5
