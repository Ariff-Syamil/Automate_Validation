"""RuntimeLogger dual-sink logging tests."""

from __future__ import annotations

import json
from pathlib import Path

from automate5.codes import ErrorCode, PhaseCode, Subsystem
from automate5.log.runtime_logger import RuntimeLogger
from tests.framework.base import TestCaseFramework, scenario


class TestRuntimeLogger(TestCaseFramework):
    @scenario("dual_sink_write", "RuntimeLogger writes .log and .jsonl records")
    def test_dual_sink_write(self, tmp_path: Path) -> None:
        logger = RuntimeLogger(stem="run", log_dir=tmp_path / "logs")

        logger.error(
            Subsystem.MOTOR,
            "motor failed",
            phase=PhaseCode.JOINT_WRITE,
            code=ErrorCode.RISCV_MOTOR_FAIL,
        )

        human = logger.log_path.read_text(encoding="utf-8")
        records = [json.loads(line) for line in logger.jsonl_path.read_text(encoding="utf-8").splitlines()]
        record = records[0]
        assert "[ERROR]" in human
        assert "[MOTOR" in human
        assert "[JOINT_WRITE]" in human
        assert "[RISCV_MOTOR_FAIL]" in human
        assert record["level"] == "ERROR"
        assert record["subsystem"] == "MOTOR"
        assert record["sub_id"] == int(Subsystem.MOTOR)
        assert record["phase_id"] == int(PhaseCode.JOINT_WRITE)
        assert record["code"] == int(ErrorCode.RISCV_MOTOR_FAIL)
        assert record["message"] == "motor failed"

    @scenario("convenience_methods", "RuntimeLogger convenience methods preserve levels")
    def test_convenience_methods_and_log_dir_creation(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "missing" / "logs"
        logger = RuntimeLogger(stem="levels", log_dir=log_dir)

        logger.debug(Subsystem.GUI, "debug")
        logger.info(Subsystem.GUI, "info")
        logger.warn(Subsystem.VLA, "warn", phase=PhaseCode.INFER)
        logger.error(Subsystem.VLA, "error", code=ErrorCode.ERR_ZMQ_TIMEOUT)

        records = [json.loads(line) for line in logger.jsonl_path.read_text(encoding="utf-8").splitlines()]
        assert logger.log_path == log_dir / "levels.log"
        assert logger.jsonl_path == log_dir / "levels.jsonl"
        assert [row["level"] for row in records] == ["DEBUG", "INFO", "WARN", "ERROR"]
        assert records[2]["phase"] == "INFER"
        assert records[3]["code_name"] == "ERR_ZMQ_TIMEOUT"
