---

## name: progress-notes description: Generate a structured markdown progress note documenting a work session. Use this skill ONLY when the user explicitly types the slash-command-style invocation `/notes` or `/progress-notes` (e.g. "/note", "/progress-note", "/note wrap up today's work"). Do NOT trigger on phrases like "make a note," "summarize," "what did we do," or any natural-language progress-summary requests — only the explicit `/notes` or `/progress-notes` invocation. The skill produces a single dated `.md` file covering everything that happened in the conversation since the last time the skill was invoked (or since the start of the conversation, if it has not been invoked yet), following the strict naming format `YYYY-MM-DD_ptNN_kebab-case-descriptive-title.md`. Always verify today's actual date before writing the filename.

# progress-notes

A skill for generating structured progress notes from a work session.

The user invokes this skill with `/note` or `/progress-note`. It produces a single dated markdown file documenting what was done, why, what problems were hit, and any concepts that were clarified — covering only the work since the skill was last invoked in the same conversation.

The user does not want this skill to fire on natural language. It must only fire on the explicit slash invocation.

---

## When to trigger

**Trigger only when the user's message contains:**

- `/notes` (with or without follow-up text)
- `/progress-notes` (with or without follow-up text)

**Do NOT trigger on:**

- "make a note"
- "summarize what we did"
- "wrap this up"
- "save this session"
- "log this"
- Any other natural-language phrasing

The user has explicitly stated they do not want this skill to fire on natural language. Only the slash invocation activates it.

If the user types `/notes <some title hint>` or `/progress-notes <some title hint>`, treat the text after the slash command as a hint for the file's title.

---

## Range of content to cover

Cover only the work that happened **since the last invocation of this skill in the current conversation**.

Detection logic:

1. Scan the conversation backwards from the user's current `/note` or `/progress-note` message
2. Find the most recent prior message where the user invoked `/note` or `/progress-note`
3. Cover everything that happened **after** that prior invocation, up to and including the current invocation
4. If no prior invocation exists in the conversation, cover everything from the start of the conversation up to the current invocation

Do not repeat content from previous notes. Each note covers a fresh, non-overlapping slice of the conversation.

If the range is so small that there's nothing meaningful to summarize (e.g., the user invoked `/note` twice in a row with no work between), tell the user clearly that there's nothing new to document since the last note, and ask whether they want to proceed anyway or skip.

---

## File naming format

Filename pattern: `YYYY-MM-DD_ptNN_kebab-case-descriptive-title.md`

Where `NN` is a 1-indexed counter of how many times this skill has been invoked in the **current conversation** (including the current invocation itself), zero-padded to a minimum of 2 digits. The counter resets per conversation — a fresh conversation always starts at `_pt01`.

The part number sits **between the date and the title** so that when the folder is sorted alphabetically, files appear in chronological order of invocation (date → part → title), not title-first order.

Rules:

- **Date** — use today's actual date. **Always verify today's date by checking the system context** (the current date is provided in the system prompt as "The current date is..."). Do not assume or guess.
- **Part number** — 1-indexed, zero-padded to 2 digits (`pt01`, `pt02`, ..., `pt09`, `pt10`, `pt11`, ..., `pt99`). If the count somehow exceeds 99, expand to 3 digits (`pt100`). The current invocation IS counted: the first time `/note` is used in a conversation, the file uses `pt01`.
- **Title** — 3 to 6 lowercase words, hyphen-separated, descriptive of the session topic
- **Title generation** — derive from the dominant theme of the covered range. If the user provided a hint after the slash command, use that hint as the basis for the title.
- **Spaces and underscores** — the title portion uses kebab-case (hyphens). The two underscores in the filename are between date-and-part and between part-and-title. No other underscores.
- Always `.md` extension

### Why this exact ordering

Files in any explorer (Windows, macOS, Linux, GitHub) sort alphabetically. With this filename pattern:

1. **Date** is leftmost — files from different days group together by day
2. **Part number** is next — within the same day, files appear in invocation order (because zero-padding makes alphabetical sort match numeric sort)
3. **Title** is rightmost — only matters as a tiebreaker if two notes had the same date and part number, which won't happen in practice

This means scanning a notes folder reads as a chronological diary.

### How to determine the current part number

When the skill triggers, scan the conversation history backwards from the current `/note` or `/progress-note` invocation message. Count every prior message in the same conversation that contained `/note` or `/progress-note` as a slash invocation. Add 1 (for the current invocation). That's `N`. Format as 2 digits with a leading zero if needed.

Examples:

- First `/note` ever in this conversation → `N = 1` → `pt01`
- Second `/note` in this conversation → `N = 2` → `pt02`
- Tenth `/note` in this conversation → `N = 10` → `pt10`
- Hundredth `/note` (unlikely but possible) → `N = 100` → `pt100`

Do NOT count occurrences of `/note` that appear inside code blocks, quoted text, or generated content from earlier responses. Only count actual user-message-level invocations of the skill.

### Examples of good filenames

- `2026-05-01_pt01_docker-stack-compose-and-tags.md` (first note in a conversation)
- `2026-05-01_pt02_mcp-config-and-validation.md` (second note in same conversation)
- `2026-05-01_pt03_finishing-stage-six.md` (third note in same conversation)
- `2026-05-01_pt15_late-night-debugging.md` (fifteenth note in same conversation)
- `2026-05-12_pt01_research-spike-on-vector-databases.md` (first note in a NEW conversation, even if same day as prior notes)

When sorted alphabetically in any folder, the files above appear in correct chronological order.

### Examples of bad filenames (avoid)

- `2026-05-01_pt01_progress.md` (title too generic)
- `progress-notes-2026-05-01_pt01.md` (date should come first, before everything else)
- `2026-05-01-pt01-docker-stack.md` (separators must be `_`, not `-`, between date/part/title)
- `2026_05_01_pt01_docker.md` (date format wrong, must use hyphens within the date itself)
- `2026-05-01_pt01_Docker_Stack_Notes.md` (title must be lowercase kebab-case)
- `2026-05-01_pt1_docker-stack.md` (must be zero-padded to 2 digits — use `pt01` not `pt1`)
- `2026-05-01_docker-stack_pt01.md` (part number must come BEFORE the title, not after)
- `2026-05-01_docker-stack.md` (missing the `ptNN` segment entirely)
- `2026-05-01_part01_docker-stack.md` (must be `pt`, not `part`)

---

## File template

Use this exact structure. Section headings are required. Section bodies should be filled with detail proportional to what actually happened — do not pad if a section has nothing to cover (in that case, write a single line acknowledging it: e.g., "No errors encountered this session.").

```markdown
# <Title in human-readable form>

> Date: YYYY-MM-DD
> Project / Stage: <auto-detect from context — e.g., "Framework 1 — Stage 5", or "General learning — TypeScript", or "Personal project — recipe app"; if unclear, write "General work">
> Topic: <one-line summary of what this session covered, ~10-15 words>

## What we accomplished

<Bullet list of concrete deliverables. What now exists or works that didn't before? Files created, services running, configs written, problems solved, decisions made. Be specific — not "set up Docker" but "wrote docker-compose.yml defining three services and brought them up".>

## Walkthrough — what we did and why

<Detailed prose explanation of each major step, in roughly chronological order, with reasoning. The key word is *why*. Do not just list what happened; explain why each step was necessary and what alternatives were considered or rejected. Use subheadings for distinct topics if the session covered multiple. Aim for the depth of explanation that would let the user (or someone else cloning the repo / reading the notes) understand the rationale, not just reproduce the steps.>

## Problems hit and how we fixed them

<For each significant error, pitfall, or confusion encountered, document it as a subsection:>

### <Short error name or symptom>

- **What happened:** <description of the failure mode, exact error message if any>
- **Why it happened:** <root cause explanation>
- **How we fixed it:** <the actual fix, with commands or steps if applicable>
- **Lesson learned:** <what to remember to avoid hitting this again>

<Repeat for each problem. If there were no problems, write "No errors encountered this session.">

## Concepts clarified

<Topics where the user asked "why" or "how does this work" — explained in their resolved form. This is the place to capture the conceptual understanding that emerged, not just the practical steps. If the user did not ask conceptual questions in this range, write "No new concepts clarified this session.">

## Where things stand now

<Concrete current state. File tree (only the relevant parts), running services, configured tools, tagged checkpoints, anything that captures "the project is in this state right now." This section should be readable as a standalone status snapshot.>

## What's next

<Preview of the next logical step or stage. What's the immediate next action? What's blocked or waiting? What should future-self remember to pick up?>
```

---

## Generation workflow

When the skill triggers:

1. **Verify today's date** from the system context. The current date is in the system prompt as a line like "The current date is Friday, May 01, 2026." Use that. Do not assume.
2. **Determine the part number.** Scan the conversation history backwards from the current message. Count how many prior messages contained `/note` or `/progress-note` as a user-issued slash invocation (do not count occurrences inside code blocks, quoted text, or assistant-generated content). Add 1 to that count to include the current invocation. Format as 2 digits with leading zero if needed (e.g., 1 becomes `01`, 5 becomes `05`, 10 becomes `10`, 25 becomes `25`).
3. **Determine the range to cover.** Find the previous `/note` or `/progress-note` invocation, if any. Cover only the messages between that point and now (exclusive of the prior invocation, inclusive of work up to but not including the current invocation message). If no prior invocation exists, cover everything from the start of the conversation.
4. **Decide the title.** If the user provided a title hint after the slash command, use it as the basis. Otherwise, derive a 3-6 word kebab-case title from the dominant theme of the range.
5. **Generate the file content** using the template below. Fill each section based on the content of the covered range. Do not hallucinate content not present in the conversation. If a section genuinely has nothing to put in it, use the placeholder line specified in the template.
6. **Save the file in Cursor** using the `Write` tool. Prefer `progress-notes/` at the workspace root (create the folder if needed): `progress-notes/YYYY-MM-DD_ptNN_kebab-case-descriptive-title.md`. If there is no workspace or the user asked for a different path, use the path they specify; otherwise save under the open project's root.
7. **Confirm** — Tell the user the saved relative path so they can open the file in the editor.
8. **Brief confirmation message** — one or two sentences max, telling the user the file was generated, what part number it is, what range it covered, and where it was saved. Do not repeat the file's contents in the chat.

Example confirmation: "Generated `progress-notes/2026-05-01_pt02_mcp-config-walkthrough.md` (second note in this conversation, covering work since the previous `/note`). Open it in the editor from the file tree."

---

## Important behavior rules

- **Do not generate this file proactively.** Only when explicitly invoked with `/note` or `/progress-note`.
- **Do not repeat content from previous notes** in the same conversation. Each invocation produces a non-overlapping slice.
- **Save location** — Default to `progress-notes/` under the workspace root. If unclear, ask once before writing.
- **Do not invent problems** if none happened. The "Problems hit" section should reflect what actually went wrong in the conversation.
- **Do not invent concepts** if none were clarified. The "Concepts clarified" section should reflect what was actually explained or unpacked.
- **Be honest about scope.** If the covered range is short or shallow, the note will be short. Don't pad.
- **Match the user's existing convention.** If the user has had previous notes generated in the conversation that establish a particular style or terminology, mirror it.
- **Date discipline.** The filename's date is *today's actual date*, not the date of any work being summarized. Even if the work being summarized happened across multiple days, the filename uses the current date (the date of writing).

---

## Quality bar — what good looks like

A good progress note:

- Could be read 6 months later and still make sense without the original conversation
- Captures *why*, not just *what*
- Surfaces problems honestly, including the user's own missteps and the corrections
- Names concepts in terms the user actually used or had explained to them
- Matches the user's existing tone and depth from prior notes in the same project
- Filename is descriptive enough that scanning a folder of these tells you which session covered which topic

A bad progress note:

- Reads like a generic changelog ("Made changes to compose file. Ran some commands.")
- Skips the reasoning behind decisions
- Glosses over errors as if everything went smoothly
- Repeats material from previous notes in the same conversation
- Has a vague filename like `progress.md` or `today.md`

---

## Edge cases

**User invokes `/note` at the very start of a conversation with no prior work:**
Tell them there's nothing to document yet and ask if they meant to invoke after some work.

**User invokes `/note` immediately after another `/note` with no work in between:**
Tell them there's nothing new since the last note. Ask whether they want to proceed with a near-empty note or skip.

**User invokes `/note <hint>` with a hint that doesn't match the actual content:**
Use the hint for the title, but write the body honestly based on what actually happened. If the mismatch is severe, briefly note it in the confirmation message.

**Multi-day conversations spanning several `/note` calls:**
Each note's filename uses today's actual date (date of generation). The body covers only the slice since the previous invocation, regardless of how many calendar days that spans.

**Conversation is in a non-English language:**
Match the user's language for the body content. The filename remains in English kebab-case (since it's a filename).