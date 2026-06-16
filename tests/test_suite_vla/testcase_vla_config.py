"""VLA configuration loader acceptance tests (Plan step 1).

Pass criteria
─────────────
test_vla_config_loads
    With an empty ``vla:`` section (passed as ``{}``), the loader returns a
    fully-populated dict that exposes every key the rest of the integration
    relies on, with sensible defaults.

test_vla_joint_map_defaults
    With an empty ``vla:`` section the loader produces exactly four mapped
    entries (joints 0-3 → node 0 motors 0-3) and joints 4 (``wrist_roll``)
    and 5 (``gripper``) are marked unmapped, matching plan section 2.2.
"""

from __future__ import annotations

from backend.vla_config import load_vla_config
from tests.framework.base import TestCaseFramework, scenario


_REQUIRED_TOP_LEVEL_KEYS = {
    "enabled",
    "mock_mode",
    "policy_host",
    "policy_port",
    "action_horizon",
    "gripper_default_state",
    "joint_map",
    "server",
}

_REQUIRED_SERVER_KEYS = {"launch_cmd", "startup_timeout_s"}


class TestVlaConfig(TestCaseFramework):
    """Acceptance tests for ``backend.vla_config.load_vla_config``."""

    @scenario(
        "vla_config_loads",
        "Empty vla section yields a fully-populated dict with sensible defaults",
    )
    def test_vla_config_loads(self) -> None:
        cfg = load_vla_config({})

        missing = _REQUIRED_TOP_LEVEL_KEYS - set(cfg)
        assert not missing, f"missing top-level VLA config keys: {sorted(missing)}"

        assert isinstance(cfg["enabled"], bool)
        assert isinstance(cfg["mock_mode"], bool)
        assert isinstance(cfg["policy_host"], str) and cfg["policy_host"]
        assert isinstance(cfg["policy_port"], int) and cfg["policy_port"] > 0
        assert isinstance(cfg["action_horizon"], int) and cfg["action_horizon"] > 0
        assert cfg["gripper_default_state"] == "open"

        server = cfg["server"]
        assert isinstance(server, dict)
        missing_server = _REQUIRED_SERVER_KEYS - set(server)
        assert not missing_server, f"missing server keys: {sorted(missing_server)}"
        assert isinstance(server["launch_cmd"], str) and server["launch_cmd"]
        assert isinstance(server["startup_timeout_s"], float)
        assert server["startup_timeout_s"] > 0

        self.log(f"loaded VLA config with {len(cfg)} top-level keys")

    @scenario(
        "vla_joint_map_defaults",
        "Default joint_map maps joints 0-3 to node 0 motors 0-3; 4 and 5 unmapped",
    )
    def test_vla_joint_map_defaults(self) -> None:
        cfg = load_vla_config({})
        joint_map = cfg["joint_map"]

        assert isinstance(joint_map, list)
        assert len(joint_map) == 6, f"expected 6 joint entries, got {len(joint_map)}"

        # Mapped entries — joints 0..3 to node 0 motors 0..3.
        for idx in range(4):
            entry = joint_map[idx]
            assert entry["joint_index"] == idx
            assert entry["mapped"] is True, f"joint {idx} must be mapped"
            assert entry["node"] == 0, f"joint {idx} node mismatch: {entry['node']}"
            assert entry["motor"] == idx, f"joint {idx} motor mismatch: {entry['motor']}"

        # Unmapped entries — wrist_roll (4) and gripper (5).
        for idx in (4, 5):
            entry = joint_map[idx]
            assert entry["joint_index"] == idx
            assert entry["mapped"] is False, f"joint {idx} must be unmapped"
            assert entry["node"] is None
            assert entry["motor"] is None

        names = [e["joint_name"] for e in joint_map]
        assert names[4] == "wrist_roll"
        assert names[5] == "gripper"

        self.log(
            f"joint_map defaults: mapped={[e['joint_index'] for e in joint_map if e['mapped']]} "
            f"unmapped={[e['joint_index'] for e in joint_map if not e['mapped']]}"
        )
