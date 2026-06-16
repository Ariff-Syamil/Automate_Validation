"""CI-safe HololinkCameraController lifecycle tests using fakes."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject

from backend import hololink_camera_controller as hcc
from tests.framework.base import TestCaseFramework, scenario


class _ImmediateThread:
    """Thread test double that runs target synchronously."""

    instances: list[_ImmediateThread] = []

    def __init__(self, target, name: str = "", daemon: bool = False):
        self._target = target
        self.name = name
        self.daemon = daemon
        self._alive = False
        _ImmediateThread.instances.append(self)

    def start(self) -> None:
        self._alive = True
        try:
            self._target()
        finally:
            self._alive = False

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout: float | None = None) -> None:
        self._alive = False


@dataclass
class _FakeApp:
    hololink_ip: str
    camera_mode_idx: int
    optical_black: int
    exposure: float
    digital_gain: int
    publisher_refs: list
    cam_mode: int
    sensor_idx_slot0: int
    sensor_idx_slot1: int
    receiver_affinity_slot0: set[int] | None = None
    receiver_affinity_slot1: set[int] | None = None
    ob_rows_top: int | None = None
    ob_rows_bottom: int | None = None
    skip_reset: bool = False
    on_bridge_initialized: object | None = None
    target_fps: int = 15

    instances: list["_FakeApp"] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if _FakeApp.instances is None:
            _FakeApp.instances = []
        _FakeApp.instances.append(self)

    def request_stop(self) -> None:
        return None

    def run(self) -> None:
        if callable(self.on_bridge_initialized):
            self.on_bridge_initialized()


class TestHololinkController(TestCaseFramework):
    @scenario("resolve_affinity", "Hololink receiver affinity resolution")
    def test_resolve_affinity(self, monkeypatch) -> None:
        monkeypatch.setattr(hcc.os, "cpu_count", lambda: 8)

        assert hcc._resolve_affinity(0, {}) == {6}
        assert hcc._resolve_affinity(1, {}) == {7}
        assert hcc._resolve_affinity(0, {"receiver_affinity": {"slot0": [2, "3"]}}) == {2, 3}
        assert hcc._resolve_affinity(1, {"receiver_affinity": {"slot1": []}}) is None

    @scenario("register_sinks", "Hololink sink registration creates publishers")
    def test_register_sinks_creates_publishers(self) -> None:
        controller = hcc.HololinkCameraController()

        controller.register_sinks([None, None])

        assert len(controller._slot_sinks) == 2
        assert len(controller._slot_publishers) == 2
        assert all(isinstance(pub, QObject) for pub in controller._slot_publishers)

    @scenario("apply_preview_lifecycle", "Hololink apply_preview builds app and emits live signals")
    def test_apply_preview_lifecycle_with_fake_app(self, monkeypatch) -> None:
        _ImmediateThread.instances.clear()
        _FakeApp.instances = []
        monkeypatch.setattr(hcc.threading, "Thread", _ImmediateThread)
        monkeypatch.setattr(hcc, "_HololinkDualCamApp", _FakeApp)
        controller = hcc.HololinkCameraController()
        live_events: list[tuple[str, bool]] = []
        controller.cam1_live_changed.connect(lambda value: live_events.append(("cam1", value)))
        controller.cam2_live_changed.connect(lambda value: live_events.append(("cam2", value)))

        controller.apply_preview(1, 0, 1, {"ip": "10.0.0.2", "mode": 2}, target_fps=0)

        assert _FakeApp.instances
        app = _FakeApp.instances[-1]
        assert app.hololink_ip == "10.0.0.2"
        assert app.cam_mode == 1
        assert app.sensor_idx_slot0 == 0
        assert app.sensor_idx_slot1 == 1
        assert app.target_fps == 1
        assert controller.last_error is None
        assert ("cam1", True) in live_events
        assert ("cam2", True) in live_events

    @scenario("configure_debounce", "Hololink configure is ignored while transition is alive")
    def test_apply_preview_debounce(self) -> None:
        class _AliveThread:
            def is_alive(self) -> bool:
                return True

        controller = hcc.HololinkCameraController()
        controller._transition_thread = _AliveThread()  # type: ignore[assignment]

        controller.apply_preview(0, 0, 1, {"ip": "10.0.0.2"})

        assert controller._cam_app is None
