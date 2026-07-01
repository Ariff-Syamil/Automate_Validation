---
name: daily-progress-update
description: Generate a manager-facing daily task progress update in WWxx.xx format. Use only when the user explicitly invokes `/daily-update`, `/daily-progress`, or `/manager-update`; do not trigger for general summaries or ordinary progress-note requests.
---

# Daily Progress Update

Generate one concise manager-facing daily task progress update using the required WW-based format.

Do not trigger this skill proactively. Use it only when the user explicitly types `/daily-update`, `/daily-progress`, or `/manager-update`, with or without a WW value or title hint.

## Trigger Rules

Trigger only when the user message contains one of these slash invocations:

- `/daily-update`
- `/daily-progress`
- `/manager-update`

Do not trigger on natural-language requests such as:

- "make a note"
- "summarize what we did"
- "wrap this up"
- "save this session"
- "log this"
- Any other non-slash phrasing

If the user includes a WW value after the slash command, use it in the report heading exactly as provided, for example `WW26.01`.

If the user does not provide a WW value and it cannot be confidently inferred from the conversation, use `[WWxx.xx]` and mention in the confirmation that the WW value still needs to be filled in.

## Range To Cover

Cover only work that happened since the previous `/daily-update`, `/daily-progress`, or `/manager-update` invocation in the same conversation.

Detection logic:

1. Scan the conversation backwards from the current slash invocation.
2. Find the most recent prior user message that invoked `/daily-update`, `/daily-progress`, or `/manager-update`.
3. Cover everything after that prior invocation, up to but not including the current invocation message.
4. If no prior invocation exists, cover everything from the start of the conversation.

Do not repeat content from previous daily updates. Each update covers a fresh, non-overlapping slice.

If there is not enough information to populate the report, ask the user for the missing task details instead of inventing work.

## Classification Rules

Classify work honestly based on the conversation:

- `Completed Activities`: tasks finished or deliverables created.
- `Work In Progress`: tasks started but not finished, including partial implementation, active debugging, or pending validation.
- `Pending Activities`: tasks known but not started, deferred, or waiting for a future session.
- `Issues / Blockers`: failures, missing inputs, blocked dependencies, tool errors, or risks. Write `None` if no issue or blocker occurred.
- `Plan for Next Working Day`: the next logical tasks based on current status and user intent.

Keep each item short and manager-readable. Prefer concrete task names over implementation details.

## File Naming

Filename pattern:

```text
YYYY-MM-DD_ptNN_daily-progress-update-wwxx-xx.md
```

Rules:

- Date: Use today's actual date from system context. Do not assume or guess.
- Part number: Count prior `/daily-update`, `/daily-progress`, or `/manager-update` invocations in this conversation and add 1 for the current invocation. Format as `pt01`, `pt02`, ..., `pt99`, then `pt100` if needed.
- WW value: If provided, normalize only for the filename by lowercasing and replacing dots with hyphens, for example `WW26.01` becomes `ww26-01`.
- If no WW value is provided, use `wwxx-xx` in the filename.
- Extension: Always use `.md`.

Good examples:

- `2026-06-30_pt01_daily-progress-update-ww26-01.md`
- `2026-06-30_pt02_daily-progress-update-ww26-02.md`

Bad examples:

- `daily-progress-update.md`
- `2026_06_30_pt01_daily_update.md`
- `2026-06-30_pt1_daily-progress-update-ww26-01.md`
- `2026-06-30_daily-progress-update-ww26-01_pt01.md`

## Save Location

Save the generated update under `progress-notes/` at the workspace root:

```text
progress-notes/YYYY-MM-DD_ptNN_daily-progress-update-wwxx-xx.md
```

Create the `progress-notes/` folder if needed. If the user asks for a different path, use that path instead.

## Report Template

Use this exact structure:

```markdown
Please find below my daily task progress update for [WWxx.xx]:

1. Completed Activities:

[Task 1]
[Task 2]
[Task 3]
2. Work In Progress:

[Task 1] - [brief status update]
[Task 2] - [brief status update]
3. Pending Activities:

[Task 1]
[Task 2]
4. Issues / Blockers (if any):

[State "None" if no issues encountered]
5. Plan for Next Working Day:

[Task 1]
[Task 2]
Kindly let me know if any further clarification is required.
```

Replace placeholders with actual task content where known. Preserve the numbering, section names, blank-line rhythm, and closing sentence.

If a section has no items:

- For `Completed Activities`, `Work In Progress`, `Pending Activities`, or `Plan for Next Working Day`, write `None`.
- For `Issues / Blockers (if any)`, write `None`.

## Generation Workflow

When the skill triggers:

1. Verify today's date from system context.
2. Determine the part number by counting prior daily-progress slash invocations in this conversation, then adding 1.
3. Determine the covered range: after the prior invocation, or from conversation start if none exists.
4. Extract completed, in-progress, pending, blocker, and next-day-plan items from the covered range.
5. Use the provided WW value, infer it only if the conversation clearly states it, or keep `[WWxx.xx]`.
6. Generate the markdown content using the report template.
7. Save the file in `progress-notes/` at the workspace root unless the user specified another path.
8. Confirm with a one or two sentence response that includes the relative path, part number, covered range, and whether the WW value was provided or left as `[WWxx.xx]`.

Do not paste the full update contents into chat after saving it unless the user explicitly asks to preview it.

## Quality Rules

- Do not invent completed work, blockers, WW values, or next-day plans.
- Keep the update concise enough to send directly to a manager.
- Use the user's wording for task names when available.
- Convert detailed engineering activity into clear task-progress language.
- Keep the body in English unless the user asks for another language.
- Use today's date for the filename, even if the work happened across multiple days.
- Do not count slash invocations inside code blocks, quoted text, or assistant-generated content.

## Edge Cases

If the user invokes this skill at the start of a conversation with no prior work and no task list, ask for the daily task details before generating a file.

If the user invokes the skill immediately after another daily update with no new work between, tell them there is nothing new since the last daily update and ask whether to proceed or skip.

If a WW value is missing, still generate the file with `[WWxx.xx]` in the report and `wwxx-xx` in the filename, then mention that the WW value should be filled in.
