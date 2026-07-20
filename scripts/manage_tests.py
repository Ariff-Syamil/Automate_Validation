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

# Test cases that already have a full hands-on runbook checked in elsewhere
# in the repo. Path is relative to the `Manual/` folder (where the
# generated priority doc lives by default) so it renders as a working link
# instead of duplicating the runbook's own step-by-step prose inline.
RUNBOOK_LINKS: dict[str, str] = {
    "TC-FPGA-004": "thor_25g_link_validation/STEPS.md",
}

# Test cases that are neither automated (`automation_status: Ready`) nor
# covered by a written manual procedure yet. These are excluded from the
# ordered manual checklist (there is nothing to check off) and called out
# separately instead of silently disappearing from the priority doc.
BLOCKED_NO_PROCEDURE: dict[str, str] = {
    "TC-FPGA-010": "../drafts/fpga_ingress_automation/README.md",
    "TC-FPGA-011": "../drafts/fpga_ingress_automation/README.md",
    "TC-FPGA-012": "../drafts/fpga_ingress_automation/README.md",
    "TC-FPGA-013": "../drafts/fpga_ingress_automation/README.md",
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
        tid
        for tid, tc in cases_by_id.items()
        if tc.get("automation_status") != READY_STATUS and tid not in BLOCKED_NO_PROCEDURE
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


def _steps_block(tc: dict) -> str:
    steps = tc.get("steps") or []
    if not steps:
        return "  _(no steps recorded)_"
    return "\n".join(f"  {i}. {step}" for i, step in enumerate(steps, 1))


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

    if tid in RUNBOOK_LINKS:
        lines.append(f"- **Full runbook:** [{RUNBOOK_LINKS[tid]}]({RUNBOOK_LINKS[tid]})")
    else:
        lines.append("- **Steps:**")
        lines.append(_steps_block(tc))

    if tc.get("expected_result"):
        lines.append(f"- **Expected result:** {tc['expected_result']}")
    if tc.get("fail_conditions"):
        lines.append(f"- **Fail conditions:** {tc['fail_conditions']}")
    return "\n".join(lines)


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
        f"(Phase 1) · **{len(manual_order)} manual** (Phase 2) · "
        f"**{len(BLOCKED_NO_PROCEDURE)} blocked** (no procedure yet, see bottom)",
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

    if BLOCKED_NO_PROCEDURE:
        lines.append("---")
        lines.append("")
        lines.append("## Blocked — no automation and no manual procedure yet")
        lines.append("")
        lines.append(
            "These cases are intentionally left out of the checklist above "
            "because there is nothing runnable yet: no working automation "
            "script and no written manual steps."
        )
        lines.append("")
        for tid, ref in sorted(BLOCKED_NO_PROCEDURE.items()):
            tc = cases_by_id.get(tid, {})
            lines.append(
                f"- `{tid}` — {tc.get('test_name') or '(unnamed)'}. "
                f"Tracked at [{ref}]({ref})."
            )
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
        doc = generate_priority_doc(args.version)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(doc)
            print(f"Priority doc written to {args.output}")
        else:
            print(doc)


if __name__ == "__main__":
    main()
