"""
Automate Validation - Test Case Management Tools

Provides utilities to:
  - Validate test case YAML files against the Excel-aligned schema
  - Generate summary reports (Confluence-ready tables in Markdown / CSV)

The YAML schema mirrors the column headers in Automate5_Test_Cases.xlsx
(sheet 'Automate5_Test_Cases'), snake-cased.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from collections import Counter
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "test_case_schema.json"

# Subcomponent folders under an Automate version directory.
SUBCOMPONENTS: list[str] = [
    "software",
    "mechanical",
    "holoscan_fpga",
    "multi_axis_motor_control_fpga",
    "gui",
]

DISPLAY_NAMES: dict[str, str] = {
    "software": "Software",
    "mechanical": "Mechanical",
    "holoscan_fpga": "Holoscan FPGA",
    "multi_axis_motor_control_fpga": "Multi Axis Motor Control FPGA",
    "gui": "GUI",
}

# Allowed Test Case ID prefixes per subcomponent folder. Prefixes come from
# the Excel `Legend` tab plus a few additional ones used in the data.
ALLOWED_PREFIXES: dict[str, tuple[str, ...]] = {
    "software": ("TC-SW", "TC-SYS"),
    "mechanical": ("TC-HW",),
    "holoscan_fpga": ("TC-FPGA", "TC-VLA"),
    "multi_axis_motor_control_fpga": ("TC-MAMC",),
    "gui": ("TC-GUI",),
}

# Default prefix used when generating new IDs from the GUI / template.
DEFAULT_PREFIX: dict[str, str] = {
    "software": "TC-SW",
    "mechanical": "TC-HW",
    "holoscan_fpga": "TC-FPGA",
    "multi_axis_motor_control_fpga": "TC-MAMC",
    "gui": "TC-GUI",
}

REQUIRED_FIELDS: tuple[str, ...] = ("test_case_id", "test_name")

ALL_FIELDS: tuple[str, ...] = (
    "test_case_id",
    "owner",
    "component",
    "dependency",
    "precondition",
    "test_name",
    "description",
    "steps",
    "expected_result",
    "fail_conditions",
    "priority",
    "severity",
    "automation_readiness",
    "automation_status",
    "test_environment_ci_hil",
    "observations",
    "jira_link",
    "next_action_if_fail",
)

ID_PATTERN = re.compile(r"^TC-[A-Z]+-\d+$")

VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
VALID_SEVERITIES = {"Critical", "Major", "Minor"}
VALID_AUTOMATION_READINESS = {"Automatable", "Semi-Automatable", "Manual"}
VALID_AUTOMATION_STATUS = {"Ready", "Not Ready", "In Progress", "Blocked"}
VALID_TEST_ENVIRONMENTS = {"CI", "HIL"}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_test_cases(yaml_path: Path) -> list[dict]:
    """Load test cases from a YAML file."""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("test_cases", []) if data else []


def save_test_cases(yaml_path: Path, test_cases: list[dict]) -> None:
    """Save test cases back to a YAML file (overwrites)."""
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"test_cases": test_cases},
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=100,
        )


def discover_test_files(automate_dir: Path) -> dict[str, Path]:
    """Find all `test_cases.yaml` files under an Automate version directory."""
    found: dict[str, Path] = {}
    for sub in SUBCOMPONENTS:
        p = automate_dir / sub / "test_cases.yaml"
        if p.exists():
            found[sub] = p
    return found


def id_prefix(test_case_id: str) -> str:
    """Return the prefix portion of a Test Case ID (e.g. 'TC-FPGA-001' -> 'TC-FPGA')."""
    parts = test_case_id.split("-")
    if len(parts) <= 1:
        return test_case_id
    return "-".join(parts[:-1])


def next_test_id(existing_cases: list[dict], prefix: str, pad: int = 3) -> str:
    """Compute the next sequential test_case_id for a given prefix.

    Looks at all existing IDs sharing the prefix and returns prefix-(max+1)
    zero-padded to `pad` digits. Honours a wider existing pad if present.
    """
    max_num = 0
    used_pad = pad
    for tc in existing_cases:
        tid = (tc.get("test_case_id") or "").strip()
        if id_prefix(tid) != prefix:
            continue
        num_part = tid.split("-")[-1]
        try:
            max_num = max(max_num, int(num_part))
            used_pad = max(used_pad, len(num_part))
        except ValueError:
            continue
    return f"{prefix}-{max_num + 1:0{used_pad}d}"


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

def _is_str_or_none(value) -> bool:
    return value is None or isinstance(value, str)


def _is_str_list_or_none(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, list):
        return False
    return all(isinstance(v, str) for v in value)


def validate_test_cases(automate_version: str) -> bool:
    """Validate all test case files for a given Automate version.

    Returns True iff every file passes all checks.
    """
    automate_dir = REPO_ROOT / automate_version
    if not automate_dir.exists():
        print(f"ERROR: Directory '{automate_dir}' does not exist.")
        return False

    files = discover_test_files(automate_dir)
    if not files:
        print(f"No test case files found under '{automate_dir}'.")
        return False

    all_valid = True
    seen_ids: dict[str, str] = {}  # test_case_id -> subcomponent
    cases_by_sub = {sub: load_test_cases(path) for sub, path in files.items()}
    known_ids = {
        tc.get("test_case_id")
        for cases in cases_by_sub.values()
        for tc in cases
        if tc.get("test_case_id")
    }

    for sub, path in files.items():
        cases = cases_by_sub[sub]
        allowed = ALLOWED_PREFIXES.get(sub, ())
        for tc in cases:
            tid = (tc.get("test_case_id") or "<missing>").strip()

            for field in REQUIRED_FIELDS:
                if not tc.get(field):
                    print(f"  ERROR [{sub}] {tid}: missing required field '{field}'")
                    all_valid = False

            if tid != "<missing>" and not ID_PATTERN.match(tid):
                print(
                    f"  ERROR [{sub}] {tid}: test_case_id does not match pattern "
                    f"TC-<PREFIX>-<NN[N]>"
                )
                all_valid = False

            prefix = id_prefix(tid)
            if allowed and prefix not in allowed:
                print(
                    f"  WARN  [{sub}] {tid}: prefix {prefix!r} not in allowed "
                    f"{list(allowed)} for this folder"
                )
                all_valid = False

            if tid in seen_ids and tid != "<missing>":
                print(
                    f"  ERROR [{sub}] {tid}: duplicate test_case_id (also in "
                    f"{seen_ids[tid]})"
                )
                all_valid = False
            elif tid != "<missing>":
                seen_ids[tid] = sub

            for field in ("owner", "component", "precondition", "expected_result",
                          "fail_conditions", "priority", "severity",
                          "automation_readiness", "automation_status",
                          "test_environment_ci_hil", "observations", "jira_link",
                          "next_action_if_fail", "description"):
                if field in tc and not _is_str_or_none(tc[field]):
                    print(f"  ERROR [{sub}] {tid}: '{field}' must be string or null")
                    all_valid = False

            for field in ("dependency", "steps"):
                if field in tc and not _is_str_list_or_none(tc[field]):
                    print(f"  ERROR [{sub}] {tid}: '{field}' must be list of strings or null")
                    all_valid = False

            for dep in (tc.get("dependency") or []):
                if dep not in known_ids:
                    print(f"  ERROR [{sub}] {tid}: dependency {dep!r} is not a known test_case_id")
                    all_valid = False

            enum_checks = (
                ("priority", VALID_PRIORITIES),
                ("severity", VALID_SEVERITIES),
                ("automation_readiness", VALID_AUTOMATION_READINESS),
                ("automation_status", VALID_AUTOMATION_STATUS),
                ("test_environment_ci_hil", VALID_TEST_ENVIRONMENTS),
            )
            for field, allowed_values in enum_checks:
                value = tc.get(field)
                if value not in (None, "") and value not in allowed_values:
                    print(
                        f"  ERROR [{sub}] {tid}: '{field}' must be one of "
                        f"{sorted(allowed_values)}, got {value!r}"
                    )
                    all_valid = False

            unknown = set(tc.keys()) - set(ALL_FIELDS)
            if unknown:
                print(f"  WARN  [{sub}] {tid}: unknown field(s) {sorted(unknown)}")
                all_valid = False

        print(f"  {sub}: {len(cases)} test case(s) checked.")

    if all_valid:
        print("Validation PASSED.")
    else:
        print("Validation FAILED - see errors above.")
    return all_valid


# ---------------------------------------------------------------------------
# Report generation (Confluence-friendly)
# ---------------------------------------------------------------------------

# Mirrors the catalog fields in report/export order.
REPORT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Test Case ID",              "test_case_id"),
    ("Owner",                     "owner"),
    ("Component",                 "component"),
    ("Dependency",                "dependency"),
    ("PreCondition",              "precondition"),
    ("Test Name",                 "test_name"),
    ("Description",               "description"),
    ("Steps",                     "steps"),
    ("Expected Result",           "expected_result"),
    ("Fail Conditions",           "fail_conditions"),
    ("Priority",                  "priority"),
    ("Severity",                  "severity"),
    ("Automation Readiness",      "automation_readiness"),
    ("Automation Status",         "automation_status"),
    ("Test Environment (CI/HIL)", "test_environment_ci_hil"),
    ("Observations",              "observations"),
    ("Jira Link",                 "jira_link"),
    ("Next Action (if Fail)",     "next_action_if_fail"),
)


EMPTY_CELL = "-"


def _format_cell(key: str, value) -> str:
    """Format a YAML field value for tabular output.

    Empty cells render as `EMPTY_CELL`. Lists are joined with separators
    appropriate to the field; pipes inside markdown cells are escaped.
    """
    if value is None or value == "":
        return EMPTY_CELL
    if key == "dependency" and isinstance(value, list):
        return ", ".join(value) if value else EMPTY_CELL
    if key == "steps" and isinstance(value, list):
        return " ; ".join(f"{i}. {s}" for i, s in enumerate(value, 1)) if value else EMPTY_CELL
    if isinstance(value, list):
        return "; ".join(str(v) for v in value) if value else EMPTY_CELL
    return str(value)


def _md_escape(text: str) -> str:
    """Escape characters that would break a Markdown table cell."""
    return text.replace("|", "\\|").replace("\r\n", " ").replace("\n", " ")


def generate_report(automate_version: str, fmt: str = "markdown") -> str:
    """Generate a summary report of all test cases."""
    automate_dir = REPO_ROOT / automate_version
    files = discover_test_files(automate_dir)

    rows: list[dict[str, str]] = []
    for sub, path in files.items():
        for tc in load_test_cases(path):
            row = {header: _format_cell(key, tc.get(key))
                   for header, key in REPORT_COLUMNS}
            rows.append(row)

    if fmt == "csv":
        return _to_csv(rows)
    return _to_markdown_table(rows)


def _to_markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "_No test cases found._"
    headers = [h for h, _ in REPORT_COLUMNS]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append("| " + " | ".join(_md_escape(r[h]) for h in headers) + " |")
    return "\n".join(lines)


def _to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    headers = [h for h, _ in REPORT_COLUMNS]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Summary (priority / automation breakdown)
# ---------------------------------------------------------------------------

def summarise(automate_version: str) -> str:
    """Return a textual summary of priority / automation_status counts."""
    automate_dir = REPO_ROOT / automate_version
    files = discover_test_files(automate_dir)

    priority = Counter()
    auto_status = Counter()
    auto_ready = Counter()
    total = 0
    by_sub: Counter[str] = Counter()

    for sub, path in files.items():
        for tc in load_test_cases(path):
            total += 1
            by_sub[sub] += 1
            priority[tc.get("priority") or "(unset)"] += 1
            auto_status[tc.get("automation_status") or "(unset)"] += 1
            auto_ready[tc.get("automation_readiness") or "(unset)"] += 1

    def _fmt(counter: Counter) -> str:
        if not counter:
            return "(none)"
        return ", ".join(f"{k}: {v}" for k, v in sorted(counter.items()))

    lines = [
        f"Total test cases: {total}",
        "",
        "By subcomponent:",
        *(f"  {DISPLAY_NAMES.get(s, s)}: {by_sub[s]}" for s in SUBCOMPONENTS),
        "",
        f"Priority           {_fmt(priority)}",
        f"Automation status  {_fmt(auto_status)}",
        f"Automation readiness {_fmt(auto_ready)}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Priority / manual run order
# ---------------------------------------------------------------------------

READY_STATUS = "Ready"

RUNBOOKS_DIRNAME = "runbooks"

# Test cases that already have a full hands-on runbook checked in elsewhere
# in the repo instead of the generated `Manual/runbooks/` location. Path is
# relative to the `Manual/` folder (where the generated priority doc lives
# by default) so it renders as a working link instead of duplicating the
# runbook's own step-by-step prose inline.
RUNBOOK_LINKS: dict[str, str] = {
    "TC-FPGA-004": "thor_25g_link_validation/STEPS.md",
}

_PRIORITY_RANK: dict[str, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def load_all_cases(automate_version: str) -> dict[str, dict]:
    """Load every test case for an Automate version into one id-keyed dict.

    Each case is annotated with a `_subcomponent` key recording which
    folder (`software`, `mechanical`, ...) it was loaded from.
    """
    automate_dir = REPO_ROOT / automate_version
    files = discover_test_files(automate_dir)
    cases_by_id: dict[str, dict] = {}
    for sub, path in files.items():
        for tc in load_test_cases(path):
            tc = dict(tc)
            tc["_subcomponent"] = sub
            cases_by_id[tc["test_case_id"]] = tc
    return cases_by_id


def _priority_sort_key(test_case_id: str, cases_by_id: dict[str, dict]) -> tuple[int, str]:
    """Deterministic tie-break order: P0 before P1 before ..., then by ID."""
    priority = cases_by_id[test_case_id].get("priority")
    return (_PRIORITY_RANK.get(priority, len(_PRIORITY_RANK)), test_case_id)


def compute_manual_run_order(cases_by_id: dict[str, dict]) -> list[str]:
    """Order the non-`Ready` ("manual") test cases for hands-on execution.

    Uses a dependency-first depth-first traversal that, the instant a
    case's last dependency becomes satisfied, immediately schedules that
    case and then cascades straight into its own dependents before
    returning to any unrelated branch. That is what keeps a dependency and
    its dependent adjacent in the resulting order instead of scattering
    them across unrelated cases: a manual case that depends on another one
    always ends up run directly after it, with nothing else in between.

    A dependency that points at an already-automated (`Ready`) case is
    treated as satisfied from the start, since Phase 1 (automated cases)
    always runs before any manual case.
    """
    manual_ids = {
        tid for tid, tc in cases_by_id.items() if tc.get("automation_status") != READY_STATUS
    }
    manual_deps: dict[str, list[str]] = {
        tid: [dep for dep in (cases_by_id[tid].get("dependency") or []) if dep in manual_ids]
        for tid in manual_ids
    }
    dependents: dict[str, list[str]] = {tid: [] for tid in manual_ids}
    for tid, deps in manual_deps.items():
        for dep in deps:
            dependents[dep].append(tid)

    def sort_key(tid: str) -> tuple[int, str]:
        return _priority_sort_key(tid, cases_by_id)

    scheduled: set[str] = set()
    order: list[str] = []

    def process(tid: str) -> None:
        if tid in scheduled:
            return
        for dep in sorted(manual_deps[tid], key=sort_key):
            process(dep)
        scheduled.add(tid)
        order.append(tid)
        for dependent in sorted(dependents[tid], key=sort_key):
            ready = dependent not in scheduled and all(
                dep in scheduled for dep in manual_deps[dependent]
            )
            if ready:
                process(dependent)

    roots = [tid for tid in manual_ids if not manual_deps[tid]]
    for tid in sorted(roots, key=sort_key):
        process(tid)
    # Safety net so the function is total even if the graph ever has a node
    # unreachable from any root (should not happen for a valid dependency
    # DAG, but avoids silently dropping a test case).
    for tid in sorted(manual_ids, key=sort_key):
        process(tid)

    return order


def _runbook_rel_path(tid: str, tc: dict) -> str:
    """Path to this case's runbook file, relative to the `Manual/` folder."""
    return RUNBOOK_LINKS.get(tid, f"{RUNBOOKS_DIRNAME}/{tc['_subcomponent']}/{tid}.md")


def _phase1_table(cases_by_id: dict[str, dict], sub: str) -> str:
    rows = sorted(
        (tc for tc in cases_by_id.values() if tc["_subcomponent"] == sub
         and tc.get("automation_status") == READY_STATUS),
        key=lambda tc: tc["test_case_id"],
    )
    if not rows:
        return "_No automated cases in this subcomponent yet._"
    lines = [
        "| Test Case ID | Test Name | Component | Priority |",
        "|---|---|---|---|",
    ]
    for tc in rows:
        lines.append(
            f"| {tc['test_case_id']} | {tc.get('test_name') or '-'} | "
            f"{tc.get('component') or '-'} | {tc.get('priority') or '-'} |"
        )
    return "\n".join(lines)


def _phase2_entry(index: int, tid: str, cases_by_id: dict[str, dict]) -> str:
    tc = cases_by_id[tid]
    deps = tc.get("dependency") or []
    manual_deps = [d for d in deps if d in cases_by_id and cases_by_id[d].get("automation_status") != READY_STATUS]
    automated_deps = [d for d in deps if d not in manual_deps]

    lines = [f"### {index}. `{tid}` — {tc.get('test_name') or '(unnamed)'}", ""]
    lines.append(
        f"- [ ] **Component:** {tc.get('component') or '-'} &nbsp;·&nbsp; "
        f"**Priority:** {tc.get('priority') or '-'} &nbsp;·&nbsp; "
        f"**Jira:** {tc.get('jira_link') or '-'}"
    )
    if manual_deps:
        lines.append(
            f"- **Run immediately after:** {', '.join(f'`{d}`' for d in manual_deps)} "
            "— do not run any other test case between that one finishing and this one starting."
        )
    if automated_deps:
        lines.append(
            f"- **Also depends on (already covered in Phase 1):** "
            f"{', '.join(f'`{d}`' for d in automated_deps)}"
        )
    if tc.get("precondition"):
        lines.append(f"- **Precondition:** {tc['precondition']}")

    runbook_path = _runbook_rel_path(tid, tc)
    label = "Full runbook" if tid in RUNBOOK_LINKS else "Runbook"
    if _has_path_to_automation(tid, tc):
        label += " (includes Path to Automation)"
    lines.append(f"- **{label}:** [{runbook_path}]({runbook_path})")

    if tc.get("expected_result"):
        lines.append(f"- **Expected result:** {tc['expected_result']}")
    if tc.get("fail_conditions"):
        lines.append(f"- **Fail conditions:** {tc['fail_conditions']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-case runbooks (Manual Procedure + Path to Automation)
# ---------------------------------------------------------------------------

# Bespoke, research-backed "Path to Automation" content for the handful of
# cases that already have real domain research behind them elsewhere in the
# repo (the Thor 25G runbook, and the FPGA ingress automation draft),
# instead of the generic templates further below.
_INGRESS_QUESTIONS: dict[int, str] = {
    1: "What IP address and UDP destination port does the ingress-path "
       "firmware listen on for the current reference-design bitstream? "
       "Static, or does it need DHCP/ARP setup from Thor first?",
    2: "Does the firmware's ingress parser expect the ECB-wrapped frame "
       "(`automate5/packets/ecb_codec.py` format), or a raw/unwrapped UDP "
       "payload?",
    3: "When you validate manually today, how do you actually inspect "
       "SGDMA/firmware state after sending a packet — UART print, "
       "JTAG/debug-bridge memory read, register dump command? Share one "
       "literal example of the real output.",
    4: "If UART is the channel: what's the COM port naming convention, "
       "baud rate, and can you paste one real captured log line showing a "
       "successful SGDMA capture?",
    5: "When a wrong-port or malformed packet is dropped today, is there "
       "any observable signal (counter, log line, LED) confirming it was "
       "dropped vs. silently ignored?",
    6: "Is there a soft/register-level reset available, or is the Bellwin "
       "USB power-cycle path the only reset mechanism?",
}

_INGRESS_QUESTION_IDS: dict[str, list[int]] = {
    "TC-FPGA-010": [1, 2, 3, 4],
    "TC-FPGA-011": [1, 2, 3, 4],
    "TC-FPGA-012": [1, 2, 3, 4, 5],
    "TC-FPGA-013": [1, 2, 3, 4, 6],
}

_INGRESS_IMPLEMENTATION_STEPS: list[str] = [
    "Get answers to the open questions above from whoever owns the "
    "ingress-path firmware + Thor stimulus side (e.g. Sheng Li / Seow Jie).",
    "Replace the placeholder/guessed pieces in "
    "`drafts/fpga_ingress_automation/stimulus.py` and `readback.py` with "
    "the confirmed behavior.",
    "Move the contents into `automation/fpga/` + `tests/test_suite_fpga/`, "
    "following the same pattern as `automation/gui/` + "
    "`tests/test_suite_gui/`.",
    "Flip `automation_status` from `Not Ready` to `Ready` only once the "
    "previous step is done and a real run has produced a genuine PASS.",
    "(Optional) Extend `automation/gui/executor.py`'s dispatch so these "
    "cases are triggerable the same way `TC-GUI-*` cases are today.",
]

_THOR_QUESTIONS: list[str] = [
    "Is Thor's QSFP already reflashed for 25GbE (`ODMDATA` / DTB patched), "
    "or still default 10GbE?",
    "Which physical SFP28 leg(s) of the breakout cable are actually "
    "connected to the Avant-X board?",
    "JetPack/Jetson Linux version on this Thor unit (tuning commands "
    "differ slightly by release)?",
    "Do you have `sudo`/SSH access to this Thor unit, or does someone "
    "else operate it?",
    "Is there a scriptable way to capture `ethtool` / `tcpdump` / counter "
    "output over SSH so Steps 0-3 of the runbook could run unattended, "
    "leaving only Step 4's throughput judgement call to a human?",
]

_THOR_IMPLEMENTATION_STEPS: list[str] = [
    "Confirm the open items above with whoever owns this Thor unit (see "
    "the \"Open items to confirm\" table in "
    "`Manual/thor_25g_link_validation/README.md`).",
    "Wrap the `ethtool` / `tcpdump` / `ethtool -S` commands from "
    "`Manual/thor_25g_link_validation/STEPS.md` in an SSH-driven script "
    "(e.g. paramiko/fabric) that parses `Speed:` / `Link detected:` / "
    "counters instead of requiring a human to read terminal output.",
    "Keep the `iperf3` throughput step (Step 4) as a human judgement call, "
    "per the known Thor software-path throughput ceiling caveat, unless a "
    "numeric pass band is agreed with the FPGA owner.",
    "Land the script under `automation/fpga/` + `tests/test_suite_fpga/`, "
    "and flip `automation_status` to `Ready` only once verified against "
    "real hardware.",
]


def _has_path_to_automation(tid: str, tc: dict) -> bool:
    """Whether this case gets a "Path to Automation" section.

    True for every `In Progress` case, plus the `Not Ready` FPGA ingress
    cases that already have a real (if unverified) automation draft to
    point at.
    """
    return tc.get("automation_status") == "In Progress" or tid in _INGRESS_QUESTION_IDS


def _generic_questions(tc: dict) -> list[str]:
    """Template open-question set, parameterized by env + readiness.

    Used for every `In Progress` case that doesn't have bespoke,
    research-backed content above (i.e. everything except `TC-FPGA-004`).
    """
    env = tc.get("test_environment_ci_hil")
    readiness = tc.get("automation_readiness")
    component = tc.get("component") or "this area"

    if readiness == "Manual":
        return [
            "Which of this case's prerequisite subsystems already have "
            "their own automated check, so a human only needs to start "
            f"the {component} portion once every dependency's latest "
            "`runs.yaml` entry is a PASS?",
            "Is there a scriptable way to capture the evidence this case "
            "relies on (logs, latency numbers, transported values), even "
            "if the final pass/fail judgement itself stays human?",
            "Given `automation_readiness` is already `Manual`, is full "
            "automation actually the goal here, or should this case "
            "simply be treated as \"as automated as it will get\" once "
            "prerequisite-checking and evidence-capture are scripted?",
        ]
    if env == "CI" and readiness == "Automatable":
        return [
            f"Does a draft pytest already exist for {component} (check "
            "`tests/` and this case's `observations` field), and if so, "
            "what's failing or missing to make it pass reliably in CI?",
            "What mock/fixture data does this case need (sample frames, "
            "config files, golden vectors) that isn't committed yet?",
            "Does it depend on real hardware state at all, or can it run "
            "fully headless in CI once the fixture/mocks exist?",
        ]
    if env == "HIL" and readiness == "Automatable":
        return [
            f"Is there already a draft script/fixture for {component}, "
            "and if so, what's blocking it from a verified passing run on "
            "real hardware?",
            "What's the exact pass/fail measurement source (counter, "
            "register, log) for this case, and is it already "
            "machine-readable?",
            "Is there a safe way to run this repeatedly without a human "
            "present, or does hardware setup (cabling, bitstream load, "
            "power-on) require a human step every time?",
        ]
    # HIL + Semi-Automatable is the most common remaining combination.
    return [
        f"Which parts of {component} can already be driven by a "
        "scriptable API/SDK/CLI, and which genuinely need a human at the "
        "bench (physical setup, visual/audible judgement)?",
        "What's today's pass/fail signal, and is there a sensor/log/"
        "counter equivalent that could replace the human observation?",
        "Is there a safe way to simulate or mock the hardware response "
        "for a CI-only smoke check, even if the full HIL case still needs "
        "a human?",
    ]


def _generic_implementation_steps(tc: dict) -> list[str]:
    """Implementation-steps counterpart to `_generic_questions`."""
    env = tc.get("test_environment_ci_hil")
    readiness = tc.get("automation_readiness")

    if readiness == "Manual":
        return [
            "Script the prerequisite-check (this case's `dependency` "
            "list) so a human only starts the manual portion once every "
            "dependency's latest run is a PASS.",
            "Instrument logging (see "
            "`tests/test_suite_log/testcase_runtime_logger.py` for the "
            "pattern) so the human only has to judge the final result, "
            "not manually record every intermediate signal.",
            "Treat this as fully covered once the previous two steps "
            "land; don't force `automation_status` toward `Ready` if a "
            "human judgement call will always remain.",
        ]
    if env == "CI" and readiness == "Automatable":
        return [
            "Add or finish the pytest module under the matching "
            "`tests/test_suite_*/` folder, following the structure of an "
            "existing passing suite in the same area.",
            "Commit any missing fixture data referenced by the test.",
            "Run `pytest` locally, confirm it's green, then flip "
            "`automation_status` to `Ready`.",
        ]
    if env == "HIL" and readiness == "Automatable":
        return [
            "Confirm the open questions above with this case's owner.",
            "Script the setup/measurement/pass-fail logic under a "
            "`tests/test_suite_*/` module, following the fixture patterns "
            "already used in `tests/test_suite_backend/`.",
            "Run it once against real hardware, record the result in "
            "`automate_5/runs.yaml`, and flip `automation_status` to "
            "`Ready` only after that passes.",
        ]
    return [
        "Script whatever is answered \"yes\" to the scriptable-parts "
        "question above into a HIL test module (see "
        "`tests/test_suite_hil/testcase_hil_gates.py` for the pattern).",
        "Keep a required manual sign-off step for whatever remains "
        "human-only, especially where `severity` is `Critical`.",
        "Run once for real, record the result, and flip "
        "`automation_status` to `Ready` only for the parts that are "
        "genuinely automated (or keep it `Semi-Automatable` permanently "
        "if a human step will always remain).",
    ]


def _path_to_automation_section(tid: str, tc: dict) -> str:
    """Render the "Path to Automation" section for a case that has one."""
    lines = [
        "## Path to Automation",
        "",
        f"Current state: `automation_readiness` "
        f"{tc.get('automation_readiness') or '-'}, `automation_status` "
        f"{tc.get('automation_status') or '-'}.",
        "",
    ]
    if tid == "TC-FPGA-004":
        lines.append(
            "A manual procedure already exists and is grounded in real "
            "NVIDIA Jetson AGX Thor documentation/forum reports — see "
            "[../thor_25g_link_validation/README.md]"
            "(../thor_25g_link_validation/README.md)."
        )
        lines.append("")
        questions, steps = _THOR_QUESTIONS, _THOR_IMPLEMENTATION_STEPS
    elif tid in _INGRESS_QUESTION_IDS:
        lines.append(
            "Pseudo-code already drafted in "
            "[../../drafts/fpga_ingress_automation/]"
            "(../../drafts/fpga_ingress_automation/) (`stimulus.py`, "
            "`readback.py`, `test_tc_fpga_ingress.py`) but unverified "
            "against real hardware."
        )
        lines.append("")
        questions = [_INGRESS_QUESTIONS[i] for i in _INGRESS_QUESTION_IDS[tid]]
        steps = _INGRESS_IMPLEMENTATION_STEPS
    else:
        questions = _generic_questions(tc)
        steps = _generic_implementation_steps(tc)

    lines.append("**Open Questions:**")
    lines.append("")
    lines.extend(f"{i}. {q}" for i, q in enumerate(questions, 1))
    lines.append("")
    lines.append("**Implementation steps once answered:**")
    lines.append("")
    lines.extend(f"{i}. {s}" for i, s in enumerate(steps, 1))
    return "\n".join(lines)


def _dependency_lines(tid: str, cases_by_id: dict[str, dict]) -> list[str]:
    tc = cases_by_id[tid]
    deps = tc.get("dependency") or []
    manual_deps = [
        d for d in deps if d in cases_by_id and cases_by_id[d].get("automation_status") != READY_STATUS
    ]
    automated_deps = [d for d in deps if d not in manual_deps]
    lines: list[str] = []
    if manual_deps:
        lines.append(
            f"**Run immediately after:** {', '.join(f'`{d}`' for d in manual_deps)} "
            "— do not run any other test case between that one finishing and this one starting."
        )
    if automated_deps:
        lines.append(
            "**Also depends on (covered in Phase 1, already automated):** "
            f"{', '.join(f'`{d}`' for d in automated_deps)}"
        )
    if not deps:
        lines.append("**Dependency:** None.")
    return lines


def _manual_procedure_section(tid: str, tc: dict) -> str:
    if tid == "TC-FPGA-004":
        return (
            "## Manual Procedure\n\n"
            "This case already has a full hands-on runbook grounded in "
            "real Jetson AGX Thor documentation — see "
            "[../thor_25g_link_validation/STEPS.md]"
            "(../thor_25g_link_validation/STEPS.md) (and "
            "[../thor_25g_link_validation/README.md]"
            "(../thor_25g_link_validation/README.md) for context/caveats) "
            "rather than duplicating it here."
        )

    lines = ["## Manual Procedure", ""]
    if tc.get("severity") == "Critical":
        lines.append(
            "**Safety note:** this is a Critical-severity case — follow "
            "your bench's standard safety procedure (clear boundary, "
            "E-stop armed, etc.) before starting."
        )
        lines.append("")
    lines.append(f"**Precondition:** {tc.get('precondition') or 'None recorded.'}")
    lines.append("")
    steps = tc.get("steps") or []
    if steps:
        lines.extend(f"{i}. {step}" for i, step in enumerate(steps, 1))
    else:
        lines.append("_(No steps recorded in `test_cases.yaml` yet.)_")
    lines.append("")
    if tc.get("expected_result"):
        lines.append(f"**Record as PASS if:** {tc['expected_result']}")
    if tc.get("fail_conditions"):
        lines.append(f"**Record as FAIL if:** {tc['fail_conditions']}")
    if tc.get("next_action_if_fail"):
        lines.append(f"**If it fails:** {tc['next_action_if_fail']}")
    lines.append("")
    lines.append("### Recording the result")
    lines.append("")
    lines.append(
        "Once done, add an entry to `automate_5/runs.yaml` consistent "
        "with existing entries for this case, e.g.:"
    )
    lines.append("")
    lines.append("```yaml")
    lines.append(f"- test_case_id: {tid}")
    lines.append("  date: 'YYYY-MM-DD'")
    lines.append("  work_week: WWxx")
    lines.append("  result: PASS   # or FAIL / BLOCKED")
    lines.append(
        f"  notes: 'Manual run per Manual/{RUNBOOKS_DIRNAME}/"
        f"{tc['_subcomponent']}/{tid}.md.'"
    )
    lines.append(f"  jira_link: {tc.get('jira_link') or 'null'}")
    lines.append("```")
    return "\n".join(lines)


def generate_case_runbook(tid: str, cases_by_id: dict[str, dict]) -> str:
    """Render the full standalone runbook file content for one test case."""
    tc = cases_by_id[tid]
    lines = [
        f"# {tid} — {tc.get('test_name') or '(unnamed)'}",
        "",
        f"**Component:** {tc.get('component') or '-'} &nbsp;·&nbsp; "
        f"**Priority:** {tc.get('priority') or '-'} &nbsp;·&nbsp; "
        f"**Severity:** {tc.get('severity') or '-'} &nbsp;·&nbsp; "
        f"**Jira:** {tc.get('jira_link') or '-'}",
    ]
    lines.extend(_dependency_lines(tid, cases_by_id))
    lines.append("")
    lines.append(_manual_procedure_section(tid, tc))
    lines.append("")
    if _has_path_to_automation(tid, tc):
        lines.append(_path_to_automation_section(tid, tc))
        lines.append("")
    return "\n".join(lines)


def write_case_runbooks(automate_version: str, out_dir: Path) -> list[Path]:
    """Write `Manual/runbooks/<subcomponent>/<TC-ID>.md` for every case that
    isn't `automation_status: Ready` yet.

    `TC-FPGA-004` still gets a file here (for its "Path to Automation"
    section) even though its Manual Procedure lives at
    `Manual/thor_25g_link_validation/` instead of being duplicated inline.
    """
    cases_by_id = load_all_cases(automate_version)
    written: list[Path] = []
    for tid, tc in cases_by_id.items():
        if tc.get("automation_status") == READY_STATUS:
            continue
        content = generate_case_runbook(tid, cases_by_id)
        path = out_dir / tc["_subcomponent"] / f"{tid}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def generate_priority_doc(automate_version: str) -> str:
    """Generate the two-phase run-priority Markdown for an Automate version.

    Phase 1 lists every `automation_status: Ready` case (has a real
    automation script) grouped by subcomponent - run these first. Phase 2
    is an ordered checklist of every other case ("manual" for now) in a
    dependency-safe order, see `compute_manual_run_order`.
    """
    cases_by_id = load_all_cases(automate_version)
    total = len(cases_by_id)
    ready_ids = [tid for tid, tc in cases_by_id.items() if tc.get("automation_status") == READY_STATUS]
    manual_order = compute_manual_run_order(cases_by_id)

    lines: list[str] = [
        f"# {automate_version} — Test Case Run Priority",
        "",
        "Generated by `python scripts/manage_tests.py priority "
        f"{automate_version} -o Manual/PRIORITY.md`. Regenerate this file "
        "whenever `test_cases.yaml` changes instead of editing it by hand.",
        "",
        f"- **{total} total test cases** — **{len(ready_ids)} automated** "
        f"(Phase 1) · **{len(manual_order)} manual** (Phase 2), each with "
        "its own runbook under `Manual/runbooks/`",
        "- **Run order:** all of Phase 1 first, then Phase 2 top to bottom. "
        "Within Phase 2, a case tagged \"Run immediately after\" must be run "
        "right after that dependency, with no other test case in between.",
        "",
        "---",
        "",
        "## Phase 1 — Automated (run first)",
        "",
        "These already have a working automation script "
        "(`automation_status: Ready`). Run them via `pytest`, "
        "`run.bat validate`, or the GUI's Run Test action "
        "(`automation/gui/executor.py`) before touching any manual case "
        "below.",
        "",
    ]
    for sub in SUBCOMPONENTS:
        lines.append(f"### {DISPLAY_NAMES.get(sub, sub)}")
        lines.append("")
        lines.append(_phase1_table(cases_by_id, sub))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Phase 2 — Manual (run after Phase 1, in this exact order)")
    lines.append("")
    lines.append(
        "Every case below still needs a human to execute it "
        "(`automation_status` is `In Progress` or `Not Ready`). Work "
        "through them **top to bottom**; do not skip ahead or interleave "
        "with a different case's dependency chain."
    )
    lines.append("")
    for i, tid in enumerate(manual_order, 1):
        lines.append(_phase2_entry(i, tid, cases_by_id))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automate Validation - Test Case Management"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="Validate test case files")
    p_val.add_argument("version", help="Automate version directory (e.g. automate_5)")

    p_rep = sub.add_parser("report", help="Generate test summary table")
    p_rep.add_argument("version", help="Automate version directory (e.g. automate_5)")
    p_rep.add_argument("--format", choices=["markdown", "csv"], default="markdown",
                       help="Output format (default: markdown)")
    p_rep.add_argument("--output", "-o", help="Write report to file instead of stdout")

    p_sum = sub.add_parser("summary", help="Show priority / automation status counts")
    p_sum.add_argument("version", help="Automate version directory (e.g. automate_5)")

    p_pri = sub.add_parser(
        "priority",
        help="Generate the two-phase (automated-first, then manual) run-priority Markdown",
    )
    p_pri.add_argument("version", help="Automate version directory (e.g. automate_5)")
    p_pri.add_argument("--output", "-o", help="Write the doc to file instead of stdout")
    p_pri.add_argument(
        "--write-runbooks",
        metavar="DIR",
        help="Also (re)generate one runbook file per non-Ready test case "
             "under DIR/<subcomponent>/<TC-ID>.md (e.g. Manual/runbooks)",
    )

    args = parser.parse_args()

    if args.command == "validate":
        success = validate_test_cases(args.version)
        sys.exit(0 if success else 1)

    elif args.command == "report":
        report = generate_report(args.version, fmt=args.format)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"Report written to {args.output}")
        else:
            print(report)

    elif args.command == "summary":
        print(summarise(args.version))

    elif args.command == "priority":
        if args.write_runbooks:
            written = write_case_runbooks(args.version, Path(args.write_runbooks))
            print(f"Wrote {len(written)} runbook(s) under {args.write_runbooks}/")

        doc = generate_priority_doc(args.version)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(doc)
            print(f"Priority doc written to {args.output}")
        else:
            print(doc)


if __name__ == "__main__":
    main()
