"""
Generate an animated demo SVG showing the Automate Validation tool workflow.

Run:  python demo/generate_demo.py
Out:  demo/demo.svg
"""

import html
from pathlib import Path

# ── Layout ──────────────────────────────────────────────────────────────────
WIDTH = 820
TITLE_BAR_H = 38
PAD = 24
LINE_H = 20
FONT = "Cascadia Code, Consolas, Menlo, monospace"
FONT_UI = "Segoe UI, system-ui, -apple-system, sans-serif"
FONT_SIZE = 13
RADIUS = 10

# ── Palette (Catppuccin Mocha — matches the GUI) ───────────────────────────
BG        = "#1e1e2e"
SURFACE   = "#181825"
BORDER    = "#313244"
FG        = "#cdd6f4"
DIM       = "#6c7086"
WHITE     = "#cdd6f4"
GREEN     = "#a6e3a1"
YELLOW    = "#f9e2af"
BLUE      = "#89b4fa"
CYAN      = "#89dceb"
MAGENTA   = "#cba6f7"
RED       = "#f38ba8"
PEACH     = "#fab387"
TITLE_BG  = "#313244"
TITLE_FG  = "#a6adc8"
ACCENT    = "#89b4fa"
BADGE_BG  = "#89b4fa"
BADGE_FG  = "#1e1e2e"

# ── Animation timing ───────────────────────────────────────────────────────
STEP_DUR = 5.0
FADE_DUR = 0.6
NUM_STEPS = 5
TOTAL_DUR = STEP_DUR * NUM_STEPS


def esc(text):
    return html.escape(text)


def mono(text, color=FG):
    return f'<tspan fill="{color}">{esc(text)}</tspan>'


# ── Step definitions ────────────────────────────────────────────────────────
steps = [
    # Step 1: Launch
    (
        "1", "LAUNCH", "Double-click run.bat or use the command line",
        [
            (0, [("❯ ", DIM), ("run.bat", YELLOW)]),
            (0, []),
            (0, [("  [setup] Virtual environment found ✓", DIM)]),
            (0, [("  [automate_validation] Launching GUI...", GREEN)]),
            (0, []),
            (0, [("  ┌──────────────────────────────────────────────┐", BORDER)]),
            (0, [("  │  ", BORDER), ("Automate Stack Validation", BLUE), ("           │", BORDER)]),
            (0, [("  │  ", BORDER), ("Version: ", DIM), ("Automate 5", WHITE), ("                  │", BORDER)]),
            (0, [("  │  ", BORDER), ("13 test cases loaded", GREEN), ("                 │", BORDER)]),
            (0, [("  └──────────────────────────────────────────────┘", BORDER)]),
        ],
    ),

    # Step 2: Browse & filter
    (
        "2", "BROWSE", "View all test cases — filter by subcomponent or status",
        [
            (0, [("  Subcomponent: ", DIM), ("[All ▾]", CYAN), ("   Status: ", DIM), ("[All ▾]", CYAN), ("   Result: ", DIM), ("[All ▾]", CYAN)]),
            (0, []),
            (0, [("  ID        Title                        Sub         Exec  Result", DIM)]),
            (0, [("  ────────  ───────────────────────────  ──────────  ────  ──────", BORDER)]),
            (0, [("  SW-001    System boot and init         Software    No    ", FG), ("—", DIM)]),
            (0, [("  SW-002    IPC validation               Software    No    ", FG), ("—", DIM)]),
            (0, [("  MECH-001  Chassis structural integrity Mechanical  No    ", FG), ("—", DIM)]),
            (0, [("  HFPGA-001 FPGA bitstream load          Holoscan    No    ", FG), ("—", DIM)]),
            (0, [("  MAMC-001  Motor FPGA bitstream load    MAMC FPGA   No    ", FG), ("—", DIM)]),
            (0, []),
            (0, [("  Showing 13 of 13", DIM), ("    ✓ 0 passed  ✗ 0 failed  ○ 13 pending", DIM)]),
        ],
    ),

    # Step 3: Add new test case
    (
        "3", "ADD TEST", "Click ＋ Add Test Case — fill in the form",
        [
            (0, [("  ┌─ ", BORDER), ("Add New Test Case", BLUE), (" ───────────────────────────┐", BORDER)]),
            (0, [("  │", BORDER)]),
            (0, [("  │  Subcomponent:  ", BORDER), ("[Software ▾]", CYAN)]),
            (0, [("  │  Test ID (auto): ", BORDER), ("SW-004", GREEN)]),
            (0, [("  │  Title:         ", BORDER), ("Config hot reload test", WHITE)]),
            (0, [("  │  Description:   ", BORDER), ("Verify runtime config reload...", FG)]),
            (0, [("  │  Dependencies:  ", BORDER), ("SW-001", PEACH)]),
            (0, [("  │", BORDER)]),
            (0, [("  │  ", BORDER), ("Step 1:", DIM), (" Start service  → ", FG), ("Service running", GREEN)]),
            (0, [("  │  ", BORDER), ("Step 2:", DIM), (" Modify config  → ", FG), ("Change detected", GREEN)]),
            (0, [("  │", BORDER)]),
            (0, [("  │           ", BORDER), ("[  Save  ]", GREEN), ("    [Cancel]", DIM), ("              │", BORDER)]),
            (0, [("  └────────────────────────────────────────────────┘", BORDER)]),
        ],
    ),

    # Step 4: Record result
    (
        "4", "RECORD", "Select a test → Record Result → mark pass or fail",
        [
            (0, [("  ▸ ", ACCENT), ("Selected: ", DIM), ("SW-001 — System boot and initialization", WHITE)]),
            (0, []),
            (0, [("  ┌─ ", BORDER), ("Record Result", BLUE), (" ─────────────────────────────┐", BORDER)]),
            (0, [("  │", BORDER)]),
            (0, [("  │  Result:      ", BORDER), ("[ Pass ▾]", GREEN)]),
            (0, [("  │  Executed by: ", BORDER), ("Jane Doe", WHITE)]),
            (0, [("  │  Notes:       ", BORDER), ("All services up in 42s", FG)]),
            (0, [("  │", BORDER)]),
            (0, [("  │           ", BORDER), ("[  Save  ]", GREEN), ("    [Cancel]", DIM), ("              │", BORDER)]),
            (0, [("  └────────────────────────────────────────────────┘", BORDER)]),
            (0, []),
            (0, [("  ✓ ", GREEN), ("SW-001 updated: ", FG), ("PASS", GREEN), (" by Jane Doe (2026-04-28)", DIM)]),
        ],
    ),

    # Step 5: Export / CLI
    (
        "5", "EXPORT", "Generate reports for Confluence via CLI or batch script",
        [
            (0, [("❯ ", DIM), ("run.bat report", YELLOW)]),
            (0, [("  [automate_validation] Generating Markdown report...", DIM)]),
            (0, []),
            (0, [("  | Test ID  | Title               | Result |", FG)]),
            (0, [("  |----------|---------------------|--------|", BORDER)]),
            (0, [("  | SW-001   | System boot and init| ", FG), ("PASS", GREEN), ("   |", FG)]),
            (0, [("  | SW-002   | IPC validation      | ", FG), ("—", DIM), ("      |", FG)]),
            (0, [("  | MECH-001 | Chassis integrity   | ", FG), ("—", DIM), ("      |", FG)]),
            (0, []),
            (0, [("❯ ", DIM), ("run.bat report csv", YELLOW)]),
            (0, [("  [automate_validation] Generating CSV report...", DIM)]),
            (0, [("  ✓ ", GREEN), ("Saved to automate_5_results.csv", CYAN), (" — paste into Confluence", DIM)]),
        ],
    ),
]


def _render_step_panel(idx, step):
    badge_num, badge_label, description, lines = step
    content_lines = len(lines)
    panel_content_h = max(content_lines * LINE_H + 16, 200)
    panel_h = panel_content_h + 60

    elements = []

    # Panel background
    elements.append(
        f'<rect x="{PAD}" y="0" width="{WIDTH - PAD*2}" height="{panel_h}" '
        f'rx="8" fill="{SURFACE}" stroke="{BORDER}" stroke-width="1"/>'
    )

    # Step badge
    badge_w = 12 + len(badge_label) * 7.8
    elements.append(
        f'<rect x="{PAD + 16}" y="14" width="{badge_w + 28}" height="22" rx="11" fill="{BADGE_BG}"/>'
    )
    elements.append(
        f'<text x="{PAD + 30}" y="29" font-family="{FONT_UI}" font-size="11" '
        f'font-weight="700" fill="{BADGE_FG}" letter-spacing="0.5">'
        f'{esc(badge_num)}  {esc(badge_label)}</text>'
    )

    # Description
    elements.append(
        f'<text x="{PAD + 16 + badge_w + 40}" y="30" font-family="{FONT_UI}" '
        f'font-size="12" fill="{DIM}">{esc(description)}</text>'
    )

    # Separator
    elements.append(
        f'<line x1="{PAD + 16}" y1="44" x2="{WIDTH - PAD - 16}" y2="44" '
        f'stroke="{BORDER}" stroke-width="1"/>'
    )

    # Code lines
    for li, (indent, segments) in enumerate(lines):
        y = 64 + li * LINE_H
        x = PAD + 20 + indent * 16
        if not segments:
            continue
        parts = "".join(mono(t, c) for t, c in segments)
        elements.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" '
            f'font-size="{FONT_SIZE}" fill="{FG}">{parts}</text>'
        )

    # Animation keyframes
    pct_step = 100.0 / NUM_STEPS
    pct_fade = (FADE_DUR / TOTAL_DUR) * 100
    start = idx * pct_step
    fade_in_end = start + pct_fade
    visible_end = (idx + 1) * pct_step - pct_fade
    fade_out_end = (idx + 1) * pct_step
    anim_name = f"step{idx}"

    panel_y = TITLE_BAR_H + 16
    group = (
        f'<g transform="translate(0, {panel_y})" opacity="0" '
        f'style="animation: {anim_name} {TOTAL_DUR}s ease-in-out infinite">\n'
        + "\n".join(f"  {e}" for e in elements)
        + "\n</g>"
    )

    keyframes = (
        f"@keyframes {anim_name} {{\n"
        f"  0%, {start:.1f}% {{ opacity: 0; }}\n"
        f"  {fade_in_end:.1f}% {{ opacity: 1; }}\n"
        f"  {visible_end:.1f}% {{ opacity: 1; }}\n"
        f"  {fade_out_end:.1f}%, 100% {{ opacity: 0; }}\n"
        f"}}"
    )

    return group, keyframes, panel_h


def generate_svg():
    panels = []
    max_panel_h = 0
    all_keyframes = []

    for i, step in enumerate(steps):
        group, kf, ph = _render_step_panel(i, step)
        panels.append(group)
        all_keyframes.append(kf)
        max_panel_h = max(max_panel_h, ph)

    total_h = TITLE_BAR_H + 16 + max_panel_h + 24 + 32

    # Step indicator dots
    dot_y = total_h - 20
    dot_spacing = 28
    dot_start_x = WIDTH / 2 - (NUM_STEPS - 1) * dot_spacing / 2
    dot_elements = []
    dot_keyframes = []

    for i in range(NUM_STEPS):
        cx = dot_start_x + i * dot_spacing
        anim_name = f"dot{i}"
        dot_elements.append(
            f'<circle cx="{cx}" cy="{dot_y}" r="4" fill="{DIM}" '
            f'style="animation: {anim_name} {TOTAL_DUR}s ease-in-out infinite"/>'
        )
        pct_step = 100.0 / NUM_STEPS
        start = i * pct_step
        end = (i + 1) * pct_step
        dot_keyframes.append(
            f"@keyframes {anim_name} {{\n"
            f"  0%, {start:.1f}% {{ fill: {DIM}; r: 4; }}\n"
            f"  {start + 1:.1f}% {{ fill: {ACCENT}; r: 5; }}\n"
            f"  {end - 1:.1f}% {{ fill: {ACCENT}; r: 5; }}\n"
            f"  {end:.1f}%, 100% {{ fill: {DIM}; r: 4; }}\n"
            f"}}"
        )

    # Title bar dots
    dots_svg = (
        f'<circle cx="20" cy="{TITLE_BAR_H//2}" r="6" fill="#ff5f56"/>'
        f'<circle cx="38" cy="{TITLE_BAR_H//2}" r="6" fill="#ffbd2e"/>'
        f'<circle cx="56" cy="{TITLE_BAR_H//2}" r="6" fill="#27c93f"/>'
    )

    title_text = (
        f'<text x="{WIDTH//2}" y="{TITLE_BAR_H//2 + 4}" text-anchor="middle" '
        f'font-family="{FONT_UI}" font-size="12" fill="{TITLE_FG}">'
        f'Automate Stack Validation — Demo Workflow</text>'
    )

    css = "\n".join(all_keyframes + dot_keyframes)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {total_h}"
     width="{WIDTH}" height="{total_h}" role="img"
     aria-label="Animated demo of the Automate Validation tool">
<style>
{css}
</style>

<!-- Background -->
<rect width="{WIDTH}" height="{total_h}" rx="{RADIUS}" fill="{BG}"/>

<!-- Title bar -->
<rect width="{WIDTH}" height="{TITLE_BAR_H}" rx="{RADIUS}" fill="{TITLE_BG}"/>
<rect y="{TITLE_BAR_H - RADIUS}" width="{WIDTH}" height="{RADIUS}" fill="{TITLE_BG}"/>
{dots_svg}
{title_text}

<!-- Step panels (animated) -->
{"".join(panels)}

<!-- Step indicator dots -->
{"".join(dot_elements)}

</svg>"""

    out_path = Path(__file__).parent / "demo.svg"
    out_path.write_text(svg, encoding="utf-8")
    print(f"Generated {out_path} ({len(svg):,} bytes)")


if __name__ == "__main__":
    generate_svg()
