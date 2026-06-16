"""Benchmark tests: packet throughput, CSV export, and report formatting."""

from __future__ import annotations

from pathlib import Path

from automate5 import Subsystem, PhaseCode
from automate5.benchmark import Benchmark
from automate5.packets.ether_motor_packet import EthercatMotorCommand
from automate5.packets.udp_header import UdpHeader
from automate5.packets.vla_ethercat_packet import VlaEthercatPacket

from tests.framework.base import TestCaseFramework, scenario


class TestBenchmark(TestCaseFramework):
    """Measures packet pack/unpack throughput and validates benchmark utilities."""

    @scenario("packet_throughput", "VlaEthercatPacket pack/unpack x10000")
    def test_packet_throughput(self) -> None:
        bench = Benchmark()
        pkt = VlaEthercatPacket(
            header=UdpHeader(1234, 5678, 17, 0xABCD),
            command=EthercatMotorCommand(True, False, 3, 10, 180, 1500),
        )

        with bench.measure(Subsystem.COMProtocol, PhaseCode.ETHERCAT, "pack x10000"):
            for _ in range(10_000):
                pkt.pack()

        raw = pkt.pack()
        with bench.measure(Subsystem.COMProtocol, PhaseCode.CANFD, "unpack x10000"):
            for _ in range(10_000):
                VlaEthercatPacket.unpack(raw)

        self.log(bench.report())

        assert len(bench.entries) == 2
        for entry in bench.entries:
            assert entry.elapsed_ms > 0

    @scenario("csv_export", "Benchmark results export to CSV")
    def test_csv_export(self, tmp_path: Path) -> None:
        bench = Benchmark()
        pkt = VlaEthercatPacket(
            header=UdpHeader(1234, 5678, 17, 0xABCD),
            command=EthercatMotorCommand(True, False, 3, 10, 180, 1500),
        )

        with bench.measure(Subsystem.COMProtocol, PhaseCode.ETHERCAT, "pack x100"):
            for _ in range(100):
                pkt.pack()

        csv_path = tmp_path / "bench.csv"
        bench.to_csv(csv_path)

        assert csv_path.exists()
        lines = csv_path.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "subsystem,phase,label,elapsed_ms,timestamp"
        assert "COMProtocol" in lines[1]
        assert "ETHERCAT" in lines[1]

        self.log(f"CSV exported to {csv_path} ({len(lines)} lines)")

    @scenario("report_format", "Benchmark report contains header, separator, and total")
    def test_report_format(self) -> None:
        bench = Benchmark()

        with bench.measure(Subsystem.VLA, PhaseCode.INFER, "dummy inference"):
            total = sum(range(1000))  # trivial work
            _ = total

        report = bench.report()
        assert "=== Benchmark Report ===" in report
        assert "Subsystem" in report
        assert "Phase" in report
        assert "Total" in report
        assert "VLA" in report
        assert "INFER" in report

        self.log(report)

    @scenario("empty_report", "Benchmark report handles zero entries")
    def test_empty_report(self) -> None:
        bench = Benchmark()
        report = bench.report()
        assert "no entries recorded" in report
        self.log(report)

    @scenario("entries_returns_copy", "Benchmark entries property returns a copy")
    def test_entries_returns_copy(self) -> None:
        bench = Benchmark()
        with bench.measure(Subsystem.GUI, PhaseCode.GUI_INIT, "init"):
            _ = sum(range(10))

        entries = bench.entries
        entries.clear()

        assert len(entries) == 0
        assert len(bench.entries) == 1

    @scenario("empty_csv_export", "Benchmark exports header-only CSV when empty")
    def test_empty_csv_export(self, tmp_path: Path) -> None:
        bench = Benchmark()
        csv_path = tmp_path / "empty.csv"

        bench.to_csv(csv_path)

        assert csv_path.read_text(encoding="utf-8").splitlines() == [
            "subsystem,phase,label,elapsed_ms,timestamp"
        ]

    @scenario("exception_path", "Benchmark does not record incomplete spans after exception")
    def test_measure_exception_path_does_not_record_entry(self) -> None:
        bench = Benchmark()

        try:
            with bench.measure(Subsystem.VLA, PhaseCode.INFER, "raises"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass

        assert bench.entries == []
