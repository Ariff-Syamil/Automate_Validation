"""Headless ControlLoop contract scenarios (terminal / CI).

The production ControlLoop orchestrator is not implemented yet.  These tests
pin the expected contract around observation shape, fake ZMQ exchange, action
validation, packet encoding, and coded error paths so the future implementation
has executable acceptance criteria instead of placeholder ``assert True`` calls.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from automate5 import CodedError, ErrorCode
from automate5.packets.ether_motor_packet import EthercatMotorCommand
from automate5.packets.udp_header import UdpHeader
from automate5.packets.vla_ethercat_packet import VlaEthercatPacket
from tests.framework.base import TestCaseFramework, scenario


@dataclass
class FakeZmqService:
    response: dict | None = None
    fail_timeout: bool = False

    def request(self, observation: dict) -> dict:
        if self.fail_timeout:
            raise CodedError(ErrorCode.ERR_ZMQ_TIMEOUT, "policy server timeout")
        if "prompt" not in observation or "telemetry" not in observation:
            raise CodedError(ErrorCode.ACTION_SHAPE_INVALID, "bad observation")
        return self.response or {
            "new_command": True,
            "direction": False,
            "mode_of_operation": 3,
            "number_of_rotations": 1,
            "angle": 90,
            "speed_rpm": 1200,
        }


class TestControlLoop(TestCaseFramework):
    def create_observation(self) -> dict:
        return {
            "prompt": "Pick up the red block",
            "image": {"format": "rgb", "width": 320, "height": 240},
            "telemetry": {"motors": [{"id": "M1", "rpm": 0.0, "angle": 0.0}]},
        }

    def send_zmq_request(self, service: FakeZmqService, observation: dict) -> dict:
        return service.request(observation)

    def verify_action_chunk(self, action: dict) -> VlaEthercatPacket:
        required = {
            "new_command",
            "direction",
            "mode_of_operation",
            "number_of_rotations",
            "angle",
            "speed_rpm",
        }
        if set(action) != required:
            raise CodedError(ErrorCode.ACTION_SHAPE_INVALID, "action chunk keys mismatch")
        command = EthercatMotorCommand(**action)
        header = UdpHeader(1234, 5678, 17, 0)
        return VlaEthercatPacket(header, command)

    def verify_error_codes(self, exc: CodedError, code: ErrorCode) -> None:
        assert exc.code is code
        assert code.name in str(exc)

    @scenario("zmq_roundtrip", "Observation -> ZMQ -> action chunk")
    def test_zmq_roundtrip(self) -> None:
        observation = self.create_observation()
        action = self.send_zmq_request(FakeZmqService(), observation)
        packet = self.verify_action_chunk(action)

        assert observation["image"]["format"] == "rgb"
        assert len(packet.pack()) == 17
        assert packet.command.speed_rpm == 1200

    @scenario("error_handling", "ErrorCode parsing path")
    def test_error_handling(self) -> None:
        observation = self.create_observation()

        with pytest.raises(CodedError) as timeout:
            self.send_zmq_request(FakeZmqService(fail_timeout=True), observation)
        self.verify_error_codes(timeout.value, ErrorCode.ERR_ZMQ_TIMEOUT)

        with pytest.raises(CodedError) as shape:
            self.verify_action_chunk({"speed_rpm": 1})
        self.verify_error_codes(shape.value, ErrorCode.ACTION_SHAPE_INVALID)
