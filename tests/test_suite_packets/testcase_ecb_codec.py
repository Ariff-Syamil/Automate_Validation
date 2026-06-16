"""Unit tests for ECB wire structs and Thor UDP payload builders."""

from __future__ import annotations

import struct

import pytest

from automate5.packets.ecb_codec import (
    build_ecb_packet,
    build_ecb_udp_payload,
    ecb_message_byte_len,
    pack_ecb_message,
    pack_thor_udp_app_payload,
    thor_udp_payload_byte_len,
    unpack_ecb_message,
    unpack_thor_udp_app_payload,
)
from automate5.packets.ecb_header import (
    ECB_CMD_WR_DWORD,
    ECB_FLAG_RESPONSE_REQUESTED,
    ECB_HEADER_SIZE,
    EcbDataPair,
    ECBHeader,
)
from tests.framework.base import TestCaseFramework, scenario


class TestEcbCodec(TestCaseFramework):
    @scenario("ecb_header_data_pair_roundtrip", "ECB header and data pair roundtrip")
    def test_ecb_header_and_data_pair_roundtrip(self) -> None:
        header = ECBHeader(ECB_CMD_WR_DWORD, ECB_FLAG_RESPONSE_REQUESTED, 7, 0)
        pair = EcbDataPair.from_dword(0x12345678, 0xDEADBEEF)

        assert header.pack() == struct.pack("!BBHH", 0x04, 0x01, 7, 0)
        assert ECBHeader.unpack(header.pack()) == header
        assert pair.pack() == struct.pack("!II", 0x12345678, 0xDEADBEEF)
        assert EcbDataPair.unpack(pair.pack()) == pair
        assert pair.dword_value == 0xDEADBEEF

        with pytest.raises(ValueError, match="ECBHeader expects"):
            ECBHeader.unpack(b"\x00" * (ECB_HEADER_SIZE - 1))
        with pytest.raises(ValueError, match="at least 4 bytes"):
            EcbDataPair.unpack(b"\x00\x01")
        with pytest.raises(ValueError, match="payload length 4"):
            EcbDataPair(0, b"\x01").dword_value

    @scenario("ecb_message_roundtrip", "ECB message and Thor payload roundtrip")
    def test_ecb_message_and_thor_payload_roundtrip(self) -> None:
        header = ECBHeader(ECB_CMD_WR_DWORD, ECB_FLAG_RESPONSE_REQUESTED, 9, 0)
        pair = EcbDataPair.from_dword(0x1000, 0xCAFEBABE)

        body = pack_ecb_message(header, pair)
        parsed_header, parsed_pair = unpack_ecb_message(body)
        payload = pack_thor_udp_app_payload(0xBEEF, header, pair)
        prefix, thor_header, thor_pair = unpack_thor_udp_app_payload(payload)

        assert parsed_header == header
        assert parsed_pair == pair
        assert prefix == 0xBEEF
        assert thor_header == header
        assert thor_pair == pair
        assert ecb_message_byte_len(4) == 14
        assert thor_udp_payload_byte_len(4) == 16

        with pytest.raises(ValueError, match="payload_len"):
            ecb_message_byte_len(-1)
        with pytest.raises(ValueError, match="at least"):
            unpack_ecb_message(body[:5])
        with pytest.raises(ValueError, match="at most one"):
            build_ecb_udp_payload(data=1, payload=b"\x00")

    @scenario("ecb_builders", "Convenience ECB builders preserve defaults and masks")
    def test_builders_default_payload_and_masks(self) -> None:
        payload = build_ecb_udp_payload(address=0xFFFFFFFF + 1)
        prefix, header, pair = unpack_thor_udp_app_payload(payload)
        compat_payload = build_ecb_packet(0x1FFFFFFFF, address=0x200000000, seq=0x1FFFF)
        _, compat_header, compat_pair = unpack_thor_udp_app_payload(compat_payload)

        assert prefix == 0
        assert header.command == ECB_CMD_WR_DWORD
        assert pair.address == 0
        assert pair.dword_value == 0xDEADBEEF
        assert compat_header.sequence == 0xFFFF
        assert compat_pair.address == 0
        assert compat_pair.dword_value == 0xFFFFFFFF
