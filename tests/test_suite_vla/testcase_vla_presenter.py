"""VLA presenter frame-caching tests (Plan step 4).

Pass criteria
─────────────
test_vla_caches_latest_camera_frame
    Driving ``VlaPanelBridge.vla_register_cam1_video_sink`` with a stub sink,
    then emitting one ``videoFrameChanged`` carrying a valid frame whose
    ``toImage()`` returns a non-null ``QImage``, must result in:
      - ``presenter._last_frame is not None``;
      - the cached image's dimensions matching the synthetic source;
      - the cache being populated only after the registration round-trip.

The stub sink and stub frame duck-type ``QVideoSink`` and ``QVideoFrame`` so
the test runs without Qt Multimedia hardware. Only ``isValid()`` and
``toImage()`` are required by the presenter's handler.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from gui.panels.vla_design.presenter import VlaPanelPresenter
from gui.panels.vla_design.view import VlaPanelBridge
from tests.framework.base import TestCaseFramework, scenario


_FRAME_W = 320
_FRAME_H = 240


class _StubVideoSink(QObject):
    """Stand-in for QVideoSink. Emits ``videoFrameChanged`` with any payload."""

    videoFrameChanged = Signal(object)


class _StubVideoFrame:
    """Duck-typed QVideoFrame: only ``isValid`` and ``toImage`` are touched."""

    def __init__(self, image: QImage, valid: bool = True) -> None:
        self._image = image
        self._valid = valid

    def isValid(self) -> bool:  # noqa: N802 — Qt naming
        return self._valid

    def toImage(self) -> QImage:  # noqa: N802 — Qt naming
        return self._image


def _make_synthetic_image(w: int = _FRAME_W, h: int = _FRAME_H) -> QImage:
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(0x336699)
    return img


class TestVlaPresenterFrameCaching(TestCaseFramework):
    """Presenter must cache the latest CAM1 frame for the VLA inference path."""

    @scenario(
        "vla_caches_latest_camera_frame",
        "After QML sink registration, the next videoFrameChanged populates _last_frame",
    )
    def test_vla_caches_latest_camera_frame(self, qtbot) -> None:
        bridge = VlaPanelBridge()
        presenter = VlaPanelPresenter(bridge)

        try:
            # Sanity: nothing cached before the sink is registered.
            assert presenter._last_frame is None
            self.log("baseline: _last_frame is None before sink registration")

            sink = _StubVideoSink()
            bridge.vla_register_cam1_video_sink(sink)
            self.log("registered stub CAM1 video sink with bridge")

            image = _make_synthetic_image()
            frame = _StubVideoFrame(image)

            with qtbot.waitSignal(sink.videoFrameChanged, timeout=2000):
                sink.videoFrameChanged.emit(frame)

            cached = presenter._last_frame
            assert cached is not None, "presenter._last_frame must be populated"
            self.log(f"cached frame size = {cached.width()} x {cached.height()}")
            assert cached.width() == _FRAME_W
            assert cached.height() == _FRAME_H
            assert cached is image
        finally:
            presenter.shutdown()

    @scenario(
        "vla_frame_cache_throttled_to_15_fps",
        "Bursts of frames within the throttle window do not overwrite the cache",
    )
    def test_vla_frame_cache_is_throttled(self, qtbot) -> None:
        bridge = VlaPanelBridge()
        presenter = VlaPanelPresenter(bridge)
        try:
            sink = _StubVideoSink()
            bridge.vla_register_cam1_video_sink(sink)

            first = _make_synthetic_image()
            second = _make_synthetic_image(w=64, h=48)

            # First frame populates the cache.
            sink.videoFrameChanged.emit(_StubVideoFrame(first))
            qtbot.wait(5)
            assert presenter._last_frame is first

            # Immediate follow-up arrives well under the 1/15 s window and
            # must be dropped silently — cache still holds the first image.
            sink.videoFrameChanged.emit(_StubVideoFrame(second))
            qtbot.wait(5)
            assert presenter._last_frame is first, (
                "second frame within the throttle window must not replace the cache"
            )
            self.log("throttle window held the first frame against an immediate follow-up")

            # Wait past the throttle interval and emit again — cache updates.
            time.sleep(1.0 / 15.0 + 0.02)
            sink.videoFrameChanged.emit(_StubVideoFrame(second))
            qtbot.wait(5)
            assert presenter._last_frame is second
            assert presenter._last_frame.width() == 64
            self.log("after throttle window expired, cache updated to the second frame")
        finally:
            presenter.shutdown()
