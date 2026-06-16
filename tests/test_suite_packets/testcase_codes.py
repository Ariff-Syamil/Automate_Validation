"""Unit tests for automate5.codes (Subsystem, PhaseCode, ErrorCode) and CodedError.

Bare pytest functions — no TestCaseFramework subclass, so they bypass
suite-level skip_in_ci gating and always run.  The packets suite config
(`tests/test_suite_packets/config.yaml`) sets skip_in_ci=false, so they
also participate in the `python -m tests packets` tag-filtered run.
"""

from __future__ import annotations

import pytest

from automate5 import CodedError, ErrorCode, PhaseCode, Subsystem
from automate5.codes.gesture_code import GestureCode


def test_subsystem_values() -> None:
    assert int(Subsystem.GUI) == 1
    assert int(Subsystem.MOTOR) == 6


def test_phase_code_range() -> None:
    assert int(PhaseCode.GUI_INIT) == 99
    assert int(PhaseCode.CAPTURE) == 100
    # Pipeline is contiguous 100–105; transport/control phases run 114–117.
    assert int(PhaseCode.JOINT_WRITE) == 105
    assert int(PhaseCode.PLAY) == 114
    assert int(PhaseCode.STOP) == 116
    assert int(PhaseCode.RESET) == 117
    assert int(PhaseCode.GUI_TEST_AUTOMATION) == 200


def test_error_code_includes_diagram_spelling() -> None:
    assert ErrorCode.V42L_OPS_FAIL.name == "V42L_OPS_FAIL"
    assert int(ErrorCode.ERR_V4L2_EIO) == 10000
    # Added fault codes (taxonomy kept; new codes appended).
    assert int(ErrorCode.SERVICE_WORKER_FAIL) == 10015
    assert int(ErrorCode.ARM_CALIBRATION_MISSING) == 10016
    assert int(ErrorCode.CAMERA_CONFIG_FAIL) == 10017


def test_coded_error_str_and_code() -> None:
    err = CodedError(ErrorCode.ERR_ZMQ_TIMEOUT, "no reply")
    assert err.code == ErrorCode.ERR_ZMQ_TIMEOUT
    assert "ERR_ZMQ_TIMEOUT" in str(err)
    assert "10002" in str(err)
    with pytest.raises(CodedError) as excinfo:
        raise err
    assert excinfo.value.code == ErrorCode.ERR_ZMQ_TIMEOUT


def test_enum_values_are_unique() -> None:
    for enum_cls in (Subsystem, PhaseCode, ErrorCode, GestureCode):
        values = [int(member) for member in enum_cls]
        assert len(values) == len(set(values)), f"{enum_cls.__name__} has duplicate values"


def test_subsystem_complete_mapping() -> None:
    assert {member.name: int(member) for member in Subsystem} == {
        "GUI": 1,
        "HOLOLINK": 3,
        "VLA": 4,
        "COMProtocol": 5,
        "MOTOR": 6,
        "ROBOT_ARM": 7,
        "SERVICE": 8,
    }


def test_phase_code_pipeline_order() -> None:
    assert int(PhaseCode.GUI_INIT) == 99
    assert [int(member) for member in PhaseCode if 100 <= int(member) < 200] == list(
        range(100, 118)
    )
    assert int(PhaseCode.GUI_TEST_AUTOMATION) == 200


def test_gesture_code_values() -> None:
    assert {member.name: int(member) for member in GestureCode} == {
        "GESTURE_ONE": 241,
        "GESTURE_TWO": 242,
        "GESTURE_THREE": 243,
        "GESTURE_FOUR": 244,
        "GESTURE_FIVE": 245,
        "GESTURE_PINCH_OPEN": 246,
        "GESTURE_PINCH_CLOSE": 247,
        "GESTURE_FIST": 248,
    }


@pytest.mark.parametrize("code", list(ErrorCode))
def test_coded_error_string_contains_code_name_and_value(code: ErrorCode) -> None:
    err = CodedError(code, "diagnostic")

    text = str(err)

    assert err.code is code
    assert code.name in text
    assert str(int(code)) in text
