"""
Automate Validation - Test Case Management Tools

Provides utilities to:
  - Validate test case YAML files against the schema
  - Generate summary reports (Confluence-ready tables in Markdown/CSV)
  - Add new test cases interactively
  - Update test execution results
"""

import argparse
import csv
import io
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "test_case_schema.json"

SUBCOMPONENTS = [
    "software",
    "mechanical",
    "holoscan_fpga",
    "multi_axis_motor_control_fpga",
]

PREFIX_MAP = {
    "software": "SW",
    "mechanical": "MECH",
    "holoscan_fpga": "HFPGA",
    "multi_axis_motor_control_fpga": "MAMC",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_test_cases(yaml_path: Path) -> list[dict]:
    """Load test cases from a YAML file."""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("test_cases", []) if data else []


def save_test_cases(yaml_path: Path, test_cases: list[dict]) -> None:
    """Save test cases back to a YAML file."""
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {"test_cases": test_cases},
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


def discover_test_files(automate_dir: Path) -> dict[str, Path]:
    """Find all test_cases.yaml files under an Automate version directory."""
    found = {}
    for sub in SUBCOMPONENTS:
        p = automate_dir / sub / "test_cases.yaml"
        if p.exists():
            found[sub] = p
    return found


def next_test_id(existing_cases: list[dict], prefix: str) -> str:
    """Compute the next sequential test ID for a given prefix."""
    max_num = 0
    for tc in existing_cases:
        tid = tc.get("test_id", "")
        if tid.startswith(prefix + "-"):
            try:
                num = int(tid.split("-")[1])
                max_num = max(max_num, num)
            except ValueError:
                pass
    return f"{prefix}-{max_num + 1:03d}"


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

def validate_test_cases(automate_version: str) -> bool:
    """Validate all test case files for a given Automate version."""
    automate_dir = REPO_ROOT / automate_version
    if not automate_dir.exists():
        print(f"ERROR: Directory '{automate_dir}' does not exist.")
        return False

    files = discover_test_files(automate_dir)
    if not files:
        print(f"No test case files found under '{automate_dir}'.")
        return False

    all_valid = True
    all_ids = set()

    for sub, path in files.items():
        cases = load_test_cases(path)
        prefix = PREFIX_MAP[sub]
        for tc in cases:
            tid = tc.get("test_id", "<missing>")

            # Check ID format
            if not tid.startswith(prefix + "-"):
                print(f"  WARN: {tid} in {sub} has wrong prefix (expected {prefix}-)")
                all_valid = False

            # Check duplicate IDs
            if tid in all_ids:
                print(f"  ERROR: Duplicate test_id '{tid}'")
                all_valid = False
            all_ids.add(tid)

            # Check required fields
            for field in ["title", "subcomponent", "test_steps", "success_criteria",
                          "failure_criteria", "executed", "result"]:
                if field not in tc:
                    print(f"  ERROR: {tid} missing required field '{field}'")
                    all_valid = False

            # Check test_steps have required sub-fields
            for step in tc.get("test_steps", []):
                for sf in ["step_number", "action", "expected_result"]:
                    if sf not in step:
                        print(f"  ERROR: {tid} step missing '{sf}'")
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

def generate_report(automate_version: str, fmt: str = "markdown") -> str:
    """Generate a summary report of all test cases."""
    automate_dir = REPO_ROOT / automate_version
    files = discover_test_files(automate_dir)

    rows = []
    for sub, path in files.items():
        for tc in load_test_cases(path):
            rows.append({
                "Test ID": tc.get("test_id", ""),
                "Title": tc.get("title", ""),
                "Subcomponent": tc.get("subcomponent", ""),
                "Dependencies": ", ".join(tc.get("dependencies", [])) or "None",
                "# Steps": len(tc.get("test_steps", [])),
                "Executed": "Yes" if tc.get("executed") else "No",
                "Result": (tc.get("result") or "—").upper() if tc.get("result") else "—",
                "Date": tc.get("execution_date") or "—",
                "Executed By": tc.get("executed_by") or "—",
            })

    if fmt == "csv":
        return _to_csv(rows)
    return _to_markdown_table(rows)


def _to_markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "_No test cases found._"
    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append("| " + " | ".join(str(r[h]) for h in headers) + " |")
    return "\n".join(lines)


def _to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Record execution results
# ---------------------------------------------------------------------------

def record_result(automate_version: str, test_id: str, result: str,
                  executed_by: str, notes: str = "") -> None:
    """Mark a test as executed with pass/fail result."""
    if result not in ("pass", "fail"):
        print("ERROR: result must be 'pass' or 'fail'")
        sys.exit(1)

    automate_dir = REPO_ROOT / automate_version
    files = discover_test_files(automate_dir)

    for sub, path in files.items():
        cases = load_test_cases(path)
        for tc in cases:
            if tc["test_id"] == test_id:
                tc["executed"] = True
                tc["result"] = result
                tc["execution_date"] = str(date.today())
                tc["executed_by"] = executed_by
                if notes:
                    tc["notes"] = notes
                save_test_cases(path, cases)
                print(f"Recorded {test_id}: {result} (by {executed_by})")
                return

    print(f"ERROR: Test ID '{test_id}' not found in {automate_version}.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Automate Validation - Test Case Management"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = sub.add_parser("validate", help="Validate test case files")
    p_val.add_argument("version", help="Automate version directory (e.g. automate_5)")

    # report
    p_rep = sub.add_parser("report", help="Generate test summary report")
    p_rep.add_argument("version", help="Automate version directory (e.g. automate_5)")
    p_rep.add_argument("--format", choices=["markdown", "csv"], default="markdown",
                       help="Output format (default: markdown)")
    p_rep.add_argument("--output", "-o", help="Write report to file instead of stdout")

    # record
    p_rec = sub.add_parser("record", help="Record test execution result")
    p_rec.add_argument("version", help="Automate version directory (e.g. automate_5)")
    p_rec.add_argument("test_id", help="Test ID (e.g. SW-001)")
    p_rec.add_argument("result", choices=["pass", "fail"], help="Test result")
    p_rec.add_argument("--by", required=True, help="Name of person who executed the test")
    p_rec.add_argument("--notes", default="", help="Additional notes")

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

    elif args.command == "record":
        record_result(args.version, args.test_id, args.result,
                      executed_by=args.by, notes=args.notes)


if __name__ == "__main__":
    main()
