# Automate Stack Validation

Test case and test step database for validating Automate stack implementations across **Software**, **Mechanical**, **Holoscan FPGA**, and **Multi Axis Motor Control FPGA** subcomponents.

Includes a **PyQt6 desktop GUI** for browsing, adding, filtering, and recording test results, plus a **CLI** for scripting and CI. Reports can be exported as Markdown tables or CSV for import into Confluence.

---

## Repository Structure

```
automate_validation/
├── README.md
├── requirements.txt
├── schema/
│   └── test_case_schema.json        # JSON Schema defining test case fields
├── templates/
│   └── test_case_template.yaml      # Blank template for new test cases
├── scripts/
│   ├── manage_tests.py              # CLI tool: validate, report, record results
│   └── gui.py                       # PyQt6 desktop GUI
└── automate_5/                      # ← Current implementation round
    ├── software/
    │   └── test_cases.yaml
    ├── mechanical/
    │   └── test_cases.yaml
    ├── holoscan_fpga/
    │   └── test_cases.yaml
    └── multi_axis_motor_control_fpga/
        └── test_cases.yaml
```

When the next Automate version begins (e.g. Automate 6), create a new top-level folder `automate_6/` with the same four subcomponent subdirectories.

---

## Test Case Fields

Every test case entry contains these fields:

| Field | Type | Description |
|---|---|---|
| `test_id` | string | Unique ID using the prefix convention below |
| `title` | string | Short descriptive name |
| `subcomponent` | string | One of `software`, `mechanical`, `holoscan_fpga`, `multi_axis_motor_control_fpga` |
| `description` | string | Detailed explanation of what the test validates |
| `dependencies` | list | Test IDs or prerequisites that must pass first |
| `test_steps` | list | Ordered steps, each with `step_number`, `action`, `expected_result` |
| `success_criteria` | string | What constitutes a **pass** |
| `failure_criteria` | string | What constitutes a **fail** |
| `executed` | bool | `true` if the test has been run |
| `result` | string/null | `pass`, `fail`, or `null` (not yet executed) |
| `execution_date` | string/null | Date of last execution (`YYYY-MM-DD`) |
| `executed_by` | string/null | Name of the person who ran the test |
| `notes` | string | Additional observations |

---

## Test ID Convention

Each subcomponent has a prefix. IDs are sequential, zero-padded to 3 digits.

| Subcomponent | Prefix | Example |
|---|---|---|
| Software | `SW` | `SW-001` |
| Mechanical | `MECH` | `MECH-001` |
| Holoscan FPGA | `HFPGA` | `HFPGA-001` |
| Multi Axis Motor Control FPGA | `MAMC` | `MAMC-001` |

---

## Getting Started

### Prerequisites

```bash
pip install -r requirements.txt
```

### Launch the GUI (recommended)

```bash
python scripts/gui.py
```

The GUI provides:

- **Sortable test case table** — view all tests across subcomponents with color-coded pass/fail/pending badges
- **Filters** — narrow by subcomponent, execution status, or result
- **Detail view** — double-click any test to see full description, steps, criteria, and execution history
- **Add test case** — form with auto-generated test ID, dynamic step rows, and input validation
- **Record result** — mark any test as pass/fail with your name, date (auto-filled), and notes
- **Version selector** — switch between Automate versions from the dropdown
- **Summary bar** — live counts of passed, failed, and pending tests

> **Note:** If `python` doesn't find PyQt6, use the venv directly:
> ```bash
> .venv\Scripts\activate     # Windows
> python scripts/gui.py
> ```

### CLI Usage

#### Validate test case files

#### Validate test case files

Checks all YAML files for required fields, correct ID prefixes, and duplicates:

```bash
python scripts/manage_tests.py validate automate_5
```

#### Generate a report

**Markdown** (paste directly into Confluence):

```bash
python scripts/manage_tests.py report automate_5
```

**CSV** (import into Confluence or spreadsheet):

```bash
python scripts/manage_tests.py report automate_5 --format csv -o report.csv
```

#### Record a test result

```bash
python scripts/manage_tests.py record automate_5 SW-001 pass --by "Jane Doe" --notes "All services up in 42s"
```

This updates the YAML file in-place, setting `executed: true`, `result: pass`, today's date, and the tester name.

---

## How to Add a New Test Case

### Via the GUI

1. Launch the GUI (`python scripts/gui.py`).
2. Click **"＋ Add Test Case"**.
3. Select the subcomponent — the test ID is auto-generated.
4. Fill in title, description, dependencies, test steps, and pass/fail criteria.
5. Click **Save**. The YAML file is updated automatically.

### Via YAML (manual)

1. Open the `test_cases.yaml` file for the relevant subcomponent under the current Automate version:
   ```
   automate_5/<subcomponent>/test_cases.yaml
   ```

2. Copy the template from `templates/test_case_template.yaml` (or use an existing test case as a starting point).

3. Fill in all required fields:
   - **`test_id`** — Use the next sequential number for the subcomponent prefix (check existing IDs to avoid duplicates).
   - **`title`** — Short, descriptive name.
   - **`subcomponent`** — Must match the folder name.
   - **`description`** — What is being validated and why.
   - **`dependencies`** — List any test IDs that must pass before this test can run. Use `[]` if none.
   - **`test_steps`** — Add one or more steps with `step_number`, `action`, and `expected_result`.
   - **`success_criteria`** / **`failure_criteria`** — Clear, measurable conditions.
   - **`executed`** — Set to `false` for new tests.
   - **`result`** — Set to `null` for new tests.

4. Run validation to catch mistakes:
   ```bash
   python scripts/manage_tests.py validate automate_5
   ```

### Example: Adding a new software test

Append this to `automate_5/software/test_cases.yaml` under the `test_cases:` list:

```yaml
  - test_id: "SW-004"
    title: "Configuration file hot reload"
    subcomponent: "software"
    description: |
      Verify that modifying a configuration file at runtime triggers
      a reload without restarting the service.
    dependencies:
      - "SW-001"
    test_steps:
      - step_number: 1
        action: "Start the target service with default config"
        expected_result: "Service running with default parameters"
      - step_number: 2
        action: "Modify a configuration value in the config file"
        expected_result: "Service detects the change within 5 seconds"
      - step_number: 3
        action: "Verify the service applies the new configuration"
        expected_result: "Service behavior reflects updated config value"
    success_criteria: "Config change detected and applied without service restart within 5s"
    failure_criteria: "Service does not detect change, requires restart, or applies incorrect value"
    executed: false
    result: null
    execution_date: null
    executed_by: null
    notes: ""
```

---

## Adding a New Automate Version

1. Create a new top-level directory (e.g. `automate_6/`).
2. Create subdirectories for each subcomponent:
   ```
   automate_6/
   ├── software/
   │   └── test_cases.yaml
   ├── mechanical/
   │   └── test_cases.yaml
   ├── holoscan_fpga/
   │   └── test_cases.yaml
   └── multi_axis_motor_control_fpga/
       └── test_cases.yaml
   ```
3. Each `test_cases.yaml` should start with:
   ```yaml
   test_cases: []
   ```
   Or copy and adapt test cases from the previous version.
4. All CLI commands accept the version directory name as the first argument:
   ```bash
   python scripts/manage_tests.py validate automate_6
   python scripts/manage_tests.py report automate_6
   ```

---

## Recording Test Results

### Via the GUI

1. Select a test case row in the table.
2. Click **"Record Result"**.
3. Choose Pass or Fail, enter your name, and add optional notes.
4. Click **Save** — the YAML is updated with today's date.

### Via CLI

```bash
python scripts/manage_tests.py record automate_5 SW-001 pass --by "Jane Doe" --notes "All services up in 42s"
```

---

## Confluence Integration

The `report` command outputs Markdown tables that can be pasted into Confluence using the **Markdown macro** or the insert-markup feature. For bulk import, use the CSV format and Confluence's CSV macro or import tools.

### Workflow

1. Run all applicable tests and record results (GUI or `record` command).
2. Generate the report: `python scripts/manage_tests.py report automate_5 --format csv -o automate_5_results.csv`
3. Upload or paste into the target Confluence page.

---

## Contributing

> **Rule: Always update this README** when introducing any structural or functional change to the repository (new scripts, new fields, new subcomponents, workflow changes, etc.). Keep it as the single source of truth for navigating and using this project.
