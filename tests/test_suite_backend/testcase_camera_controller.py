"""Camera controller backend tests that are safe without real cameras."""

from __future__ import annotations

from backend.camera_controller import enumerate_video_inputs as enumerate_qt_video_inputs
from backend.hololink_camera_controller import enumerate_video_inputs as enumerate_hololink_inputs
from tests.framework.base import TestCaseFramework, scenario


class TestCameraEnumeration(TestCaseFramework):
    @scenario("qt_camera_enumerate", "Qt camera enumeration returns aligned lists")
    def test_qt_camera_enumerate_returns_aligned_lists(self) -> None:
        labels, devices = enumerate_qt_video_inputs()

        assert isinstance(labels, list)
        assert isinstance(devices, list)
        assert len(labels) == len(devices)

    @scenario("hololink_camera_enumerate", "Hololink exposes two IMX274 sensor slots")
    def test_hololink_camera_enumerate_returns_fixed_slots(self) -> None:
        labels, devices = enumerate_hololink_inputs()

        assert labels == ["IMX274 Sensor 0", "IMX274 Sensor 1"]
        assert devices == [None, None]
