"""Skip-gated HIL acceptance checks for optional real hardware/services."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

from backend.camera_controller import enumerate_video_inputs
from tests.framework.base import TestCaseFramework, scenario
from tests._paths import AUTOMATE5_ROOT


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is not set; skipping optional HIL test")
    return value


class TestHilGates(TestCaseFramework):
    @scenario("real_usb_camera_available", "Real USB camera enumeration")
    def test_real_usb_camera_available(self) -> None:
        _require_env("AUTOMATE5_HIL_CAMERA")

        labels, devices = enumerate_video_inputs()

        assert labels
        assert devices

    @scenario("hololink_board_reachable", "Hololink board discovery gate")
    def test_hololink_board_reachable(self) -> None:
        ip = _require_env("AUTOMATE5_HIL_HOLOLINK_IP")
        try:
            import hololink as hololink_module
        except ImportError:
            pytest.skip("hololink package is not installed")

        channel = hololink_module.Enumerator.find_channel(
            channel_ip=ip,
            timeout=hololink_module.Timeout(1.5),
        )

        assert channel is not None

    @scenario("gesture_assets_present", "MediaPipe gesture model and videos present")
    def test_gesture_assets_present(self) -> None:
        _require_env("AUTOMATE5_HIL_GESTURE")
        repo_root = AUTOMATE5_ROOT
        required = [
            repo_root / "models" / "hand_landmarker.task",
            repo_root / "gui" / "assets" / "LeftHand_GestureVideo.mp4",
            repo_root / "gui" / "assets" / "RightHand_GestureVideo.mp4",
        ]

        missing = [str(path) for path in required if not path.is_file()]

        assert missing == []

    @scenario("vla_service_reachable", "VLA/ZMQ service TCP reachability gate")
    def test_vla_service_reachable(self) -> None:
        host = _require_env("AUTOMATE5_HIL_VLA_HOST")
        port = int(_require_env("AUTOMATE5_HIL_VLA_PORT"))

        with socket.create_connection((host, port), timeout=2.0) as sock:
            assert sock is not None
