"""Gesture recognition acceptance tests — video-based, no Qt required.

All test parameters (videos, detector settings, must-observe checklists,
pinch threshold) live in `tests/test_suite_gesture/gesture_fixtures.yaml`,
NOT in `configs/gui/gui_configuration.yaml`.  Runtime config is for the
live app; this YAML is for the offline acceptance suite only.

Pass criteria are declarative — each scenario must observe every entry in
its `must_observe` list at least once before the video ends.  Duplicates
are ignored.

If a video or the MediaPipe model file is missing, the corresponding test
is skipped (not failed) so the suite runs in a checkout without assets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
cv2 = pytest.importorskip("cv2")
mp = pytest.importorskip("mediapipe")
import yaml
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from backend.gesture_worker import calc_pinch_speed, count_extended_fingers, is_fist
from tests.framework.base import TestCaseFramework, scenario
from tests._paths import AUTOMATE5_ROOT


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_detector(model_path: Path, settings: dict[str, Any]) -> vision.HandLandmarker:
    """Create a MediaPipe HandLandmarker from the YAML detector block."""
    base_options = python.BaseOptions(model_asset_path=str(model_path))
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=int(settings.get("num_hands", 2)),
        min_hand_detection_confidence=float(settings.get("min_hand_detection_confidence", 0.7)),
        min_hand_presence_confidence=float(settings.get("min_hand_presence_confidence", 0.7)),
        min_tracking_confidence=float(settings.get("min_tracking_confidence", 0.5)),
    )
    return vision.HandLandmarker.create_from_options(options)


def _iter_video_frames(video_path: Path, infer_width: int):
    """Yield resized RGB frames from a video file until the video ends."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            h, w = bgr.shape[:2]
            if w > infer_width:
                scale = infer_width / w
                bgr = cv2.resize(
                    bgr, (infer_width, int(h * scale)),
                    interpolation=cv2.INTER_LINEAR,
                )
            yield cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    finally:
        cap.release()


class _LandmarkContainer:
    """Minimal wrapper so gesture helpers receive a `.landmark` attribute."""

    def __init__(self, landmarks_list) -> None:
        self.landmark = landmarks_list


# ── Test class ────────────────────────────────────────────────────────────────

class TestGestureRecognition(TestCaseFramework):
    """Video-based acceptance tests driven by `gesture_fixtures.yaml`."""

    _FIXTURES_FILE = Path(__file__).resolve().parent / "gesture_fixtures.yaml"
    _fixtures_cache: dict[str, Any] | None = None

    # ── shared paths / fixture loading ────────────────────────────────────────

    @classmethod
    def _repo_root(cls) -> Path:
        return AUTOMATE5_ROOT

    @classmethod
    def _load_fixtures(cls) -> dict[str, Any]:
        if cls._fixtures_cache is None:
            if not cls._FIXTURES_FILE.is_file():
                pytest.skip(f"Fixtures file missing: {cls._FIXTURES_FILE}")
            with cls._FIXTURES_FILE.open(encoding="utf-8") as f:
                cls._fixtures_cache = yaml.safe_load(f) or {}
        return cls._fixtures_cache

    @classmethod
    def _detector_settings(cls) -> dict[str, Any]:
        return cls._load_fixtures().get("detector", {})

    @classmethod
    def _scenario_by_id(cls, scenario_id: str) -> dict[str, Any]:
        scenarios = cls._load_fixtures().get("scenarios", []) or []
        for entry in scenarios:
            if entry.get("id") == scenario_id:
                return entry
        pytest.skip(f"Scenario {scenario_id!r} not found in {cls._FIXTURES_FILE}")
        return {}  # unreachable — pytest.skip raises

    @classmethod
    def _model_path(cls) -> Path:
        rel = cls._detector_settings().get("model_path", "models/hand_landmarker.task")
        return cls._repo_root() / rel

    # ── Common scenario driver ────────────────────────────────────────────────

    def _run_scenario(self, scenario_id: str) -> None:
        scn = self._scenario_by_id(scenario_id)
        det_settings = self._detector_settings()

        video_path = self._repo_root() / scn["video"]
        if not video_path.is_file():
            pytest.skip(f"Video not found — place it at: {video_path}")

        model_path = self._model_path()
        if not model_path.is_file():
            pytest.skip(f"MediaPipe model not found: {model_path}")

        hand = scn["hand"]                                # "Left" | "Right"
        kind = scn["kind"]                                # "motor_selection" | "speed_and_stop"
        must_observe = set(scn.get("must_observe", []))
        pinch_split = float(scn.get("pinch_split", 0.5))
        infer_width = int(det_settings.get("infer_width", 320))

        self.log(f"{scenario_id}: begin")
        self.log(f"  video        : {video_path}")
        self.log(f"  model        : {model_path}")
        self.log(f"  hand         : {hand}")
        self.log(f"  kind         : {kind}")
        self.log(f"  must_observe : {sorted(must_observe)}")

        remaining: set[str] = set(must_observe)

        detector = _build_detector(model_path, det_settings)
        try:
            for frame_idx, rgb in enumerate(
                _iter_video_frames(video_path, infer_width), start=1,
            ):
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                results = detector.detect(mp_image)

                if not (results.hand_landmarks and results.handedness):
                    continue

                for hand_landmarks, handedness in zip(
                    results.hand_landmarks, results.handedness,
                ):
                    if handedness[0].category_name != hand:
                        continue

                    lm = _LandmarkContainer(hand_landmarks)

                    if kind == "motor_selection":
                        self._eval_motor_selection(
                            lm, hand, remaining, frame_idx,
                        )
                    elif kind == "speed_and_stop":
                        self._eval_speed_and_stop(
                            lm, hand, remaining, frame_idx, pinch_split,
                        )
                    else:
                        pytest.fail(f"Unknown scenario kind: {kind!r}")

                if not remaining:
                    self.log(
                        f"  all gestures observed by frame {frame_idx} — early exit"
                    )
                    break
        finally:
            detector.close()

        assert not remaining, (
            f"{scenario_id}: video ended without observing {sorted(remaining)} "
            f"(expected all of {sorted(must_observe)})"
        )
        self.log(f"{scenario_id}: PASSED")

    # ── per-kind evaluators ───────────────────────────────────────────────────

    def _eval_motor_selection(
        self, lm: _LandmarkContainer, hand: str,
        remaining: set[str], frame_idx: int,
    ) -> None:
        finger_count = count_extended_fingers(lm, hand)
        if finger_count == 0:
            motor_id = "NONE"
        elif finger_count >= 5:
            motor_id = "ALL"
        else:
            motor_id = str(finger_count)

        if motor_id in remaining:
            remaining.discard(motor_id)
            self.log(
                f"  frame {frame_idx:>5}: {hand.upper():<5} fingers={finger_count}"
                f"  motor={motor_id!r}  still_needed={sorted(remaining)}"
            )

    def _eval_speed_and_stop(
        self, lm: _LandmarkContainer, hand: str,
        remaining: set[str], frame_idx: int, pinch_split: float,
    ) -> None:
        if is_fist(lm, hand):
            if "stop" in remaining:
                remaining.discard("stop")
                self.log(
                    f"  frame {frame_idx:>5}: {hand.upper():<5} fist=STOP"
                    f"  still_needed={sorted(remaining)}"
                )
            return

        speed = calc_pinch_speed(lm)
        if speed < pinch_split and "speed_below_50" in remaining:
            remaining.discard("speed_below_50")
            self.log(
                f"  frame {frame_idx:>5}: {hand.upper():<5} speed={speed:.2f} "
                f"(<{int(pinch_split * 100)}%)  still_needed={sorted(remaining)}"
            )
        elif speed > pinch_split and "speed_above_50" in remaining:
            remaining.discard("speed_above_50")
            self.log(
                f"  frame {frame_idx:>5}: {hand.upper():<5} speed={speed:.2f} "
                f"(>{int(pinch_split * 100)}%)  still_needed={sorted(remaining)}"
            )

    # ── Scenarios (one test method each, IDs match the YAML) ──────────────────

    @scenario(
        "left_hand_motor_selection",
        "Left hand: 1–5 extended fingers must select motors 1, 2, 3, 4 and ALL",
    )
    def test_left_hand_gestures(self) -> None:
        """Scan the left-hand video and assert all five motor selections appear."""
        self._run_scenario("left_hand_motor_selection")

    @scenario(
        "right_hand_speed_stop",
        "Right hand: pinch <50%, pinch >50%, and fist stop must all appear",
    )
    def test_right_hand_gestures(self) -> None:
        """Scan the right-hand video and assert speed-below, speed-above, and stop."""
        self._run_scenario("right_hand_speed_stop")
