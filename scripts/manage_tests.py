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


if __name__ == "__main__":
    main()
