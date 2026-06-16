"""Focused wire-format tests for UDP/EtherCAT packet value objects."""

from __future__ import annotations

import struct

import pytest

from automate5.packets.ether_motor_packet import EthercatMotorCommand, EthercatMotorStatus
from automate5.packets.udp_header import UDP_HEADER_SIZE, UDP_LENGTH_MAX, UDP_LENGTH_MIN, UdpHeader
from automate5.packets.vla_ethercat_packet import VlaEthercatPacket
from tests.framework.base import TestCaseFramework, scenario


class TestPacketWireFormats(TestCaseFramework):
    @scenario("udp_header_roundtrip", "UDP header pack/unpack and bounds")
    def test_udp_header_roundtrip_and_bounds(self) -> None:
        header = UdpHeader(1234, 5678, UDP_HEADER_SIZE + 9, 0xABCD)

        raw = header.pack()

        assert raw == struct.pack("!4H", 1234, 5678, 17, 0xABCD)
        assert UdpHeader.unpack(raw) == header
        with pytest.raises(ValueError, match="Expected 8 bytes"):
            UdpHeader.unpack(raw + b"\x00")
        with pytest.raises(ValueError, match="length"):
            UdpHeader(1, 2, UDP_LENGTH_MIN - 1, 0)
        with pytest.raises(ValueError, match="uint16"):
            UdpHeader(1, 2, UDP_LENGTH_MAX + 1, 0)

    @scenario("ethercat_command_roundtrip", "EtherCAT command payload roundtrip")
    def test_ethercat_command_roundtrip_and_validation(self) -> None:
        command = EthercatMotorCommand(True, False, 3, 10, 180, 1500)

        raw = command.pack()
        unpacked = EthercatMotorCommand.unpack(raw)

        assert raw == struct.pack("!3B3H", 1, 0, 3, 10, 180, 1500)
        assert len(raw) == 9
        assert unpacked == command
        with pytest.raises(ValueError, match="new_command"):
            EthercatMotorCommand(2, False, 3, 10, 180, 1500)
        with pytest.raises(ValueError, match="mode_of_operation"):
            EthercatMotorCommand(True, False, 256, 10, 180, 1500)

    @scenario("ethercat_status_flags", "EtherCAT status flag and telemetry decode")
    def test_ethercat_status_flags_and_telemetry(self) -> None:
        # byte42: moving, rpm_lock, stopped, driver_fault.
        # byte43: ecb_fault. byte45: in_progress, complete, encoder_link.
        raw = struct.pack("!3B x HHI", 0b10011001, 0b00000001, 0b11100000, 321, 45, 123456)

        status = EthercatMotorStatus.unpack(raw)

        assert status.motor_moving is True
        assert status.rpm_lock is True
        assert status.motor_stopped is True
        assert status.driver_fault is True
        assert status.ecb_fault is True
        assert status.operation_in_progress is True
        assert status.operation_complete is True
        assert status.encoder_link_status is True
        assert status.current_speed_rpm == 321
        assert status.current_position_angle == 45
        assert status.encoder_count == 123456

    @scenario("vla_ethercat_packet_layout", "VLA/EtherCAT composite packet layout")
    def test_vla_ethercat_packet_layout_and_length_guard(self) -> None:
        header = UdpHeader(1234, 5678, 17, 0xABCD)
        command = EthercatMotorCommand(True, False, 3, 10, 180, 1500)
        packet = VlaEthercatPacket(header, command)

        raw = packet.pack()

        assert len(raw) == 17
        assert raw[:8] == header.pack()
        assert raw[8:] == command.pack()
        assert VlaEthercatPacket.unpack(raw) == packet
        with pytest.raises(ValueError, match="Expected 17 bytes"):
            VlaEthercatPacket.unpack(raw[:-1])
