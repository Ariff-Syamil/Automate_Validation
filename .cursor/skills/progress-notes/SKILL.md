---
name: progress-notes
description: Generate a structured markdown progress note for a work session. Use only when the user explicitly invokes `/notes` or `/progress-notes`; do not use for natural-language summary requests such as "make a note", "summarize", or "what did we do".
---

# Progress Notes

Generate one dated markdown progress note that documents the work since the last progress-note invocation in the current conversation.

Do not trigger this skill proactively. Use it only when the user explicitly types `/notes` or `/progress-notes`, with or without a title hint.

## Trigger Rules

Trigger only when the user message contains one of these slash invocations:

- `/notes`
- `/progress-notes`

Do not trigger on natural-language requests such as:

- "make a note"
- "summarize what we did"
- "wrap this up"
- "save this session"
- "log this"
- Any other non-slash phrasing

If the user types `/notes <title hint>` or `/progress-notes <title hint>`, use the text after the slash command as the basis for the filename title.

## Range To Cover

Cover only work that happened since the previous `/notes` or `/progress-notes` invocation in the same conversation.

Detection logic:

1. Scan the conversation backwards from the current `/notes` or `/progress-notes` message.
2. Find the most recent prior user message that invoked `/notes` or `/progress-notes`.
3. Cover everything after that prior invocation, up to but not including the current invocation message.
4. If no prior invocation exists, cover everything from the start of the conversation.

Do not repeat content from previous notes. Each note covers a fresh, non-overlapping slice.

If there is nothing meaningful to summarize, tell the user there is nothing new to document since the last note and ask whether to proceed with a near-empty note or skip.

## File Naming

Filename pattern:

```text
YYYY-MM-DD_ptNN_kebab-case-descriptive-title.md
```

Rules:

- Date: Use today's actual date from system context. Do not assume or guess.
- Part number: Count prior `/notes` or `/progress-notes` invocations in this conversation and add 1 for the current invocation. Format as `pt01`, `pt02`, ..., `pt99`, then `pt100` if needed.
- Title: Use 3 to 6 lowercase words in kebab-case. Derive it from the dominant theme, unless the user provided a title hint.
- Separators: Use underscores only between date, part, and title. Use hyphens inside the date and title.
- Extension: Always use `.md`.

Good examples:

- `2026-05-01_pt01_docker-stack-compose-and-tags.md`
- `2026-05-01_pt02_mcp-config-and-validation.md`
- `2026-05-01_pt03_finishing-stage-six.md`

Bad examples:

- `progress-notes-2026-05-01_pt01.md`
- `2026-05-01-pt01-docker-stack.md`
- `2026_05_01_pt01_docker.md`
- `2026-05-01_pt1_docker-stack.md`
- `2026-05-01_docker-stack_pt01.md`

## Save Location

Save the generated note under `progress-notes/` at the workspace root:

```text
progress-notes/YYYY-MM-DD_ptNN_kebab-case-descriptive-title.md
```

Create the `progress-notes/` folder if needed. If the user asks for a different path, use that path instead.

## Note Template

Use this exact structure:

```markdown
# <Title in human-readable form>

> Date: YYYY-MM-DD
> Project / Stage: <auto-detect from context, or "General work" if unclear>
> Topic: <one-line summary of what this session covered>

## What we accomplished

<Bullet list of concrete deliverables. Be specific about files, configs, services, tests, decisions, or problems solved.>

## Walkthrough - what we did and why

<Chronological prose explanation of each major step. Focus on why each step mattered, not just what happened. Use subheadings if the session covered multiple topics.>

## Problems hit and how we fixed them

<For each significant issue, use this structure. If there were no problems, write "No errors encountered this session.">

### <Short error name or symptom>

- **What happened:** <description of the failure mode, including exact error text if useful>
- **Why it happened:** <root cause explanation>
- **How we fixed it:** <actual fix, including commands or steps if applicable>
- **Lesson learned:** <what to remember next time>

## Concepts clarified

<Concepts the user asked about and the resolved explanation. If none, write "No new concepts clarified this session.">

## Where things stand now

<Concrete current state: relevant files, running services, configured tools, checkpoints, or status snapshot.>

## What's next

<Immediate next action, blockers, or what future work should pick up.>
```

## Generation Workflow

When the skill triggers:

1. Verify today's date from system context.
2. Determine the part number by counting prior `/notes` or `/progress-notes` user invocations in this conversation, then adding 1.
3. Determine the covered range: after the prior invocation, or from conversation start if none exists.
4. Choose a descriptive 3 to 6 word kebab-case title, using the user's hint if provided.
5. Generate the markdown content using the template.
6. Save the file in `progress-notes/` at the workspace root unless the user specified another path.
7. Confirm with a one or two sentence response that includes the relative path, part number, and covered range.

Do not paste the full note contents into chat after saving it.

## Quality Rules

- Capture why decisions were made, not just what changed.
- Do not invent problems, concepts, files, commands, or decisions.
- Keep the note proportional to the actual session.
- Match the user's language for the body content. Keep the filename in English kebab-case.
- Use today's date for the filename, even if the work happened across multiple days.
- Do not count `/notes` or `/progress-notes` occurrences inside code blocks, quoted text, or assistant-generated content.

## Edge Cases

If the user invokes `/notes` or `/progress-notes` at the start of a conversation with no prior work, tell them there is nothing to document yet and ask if they meant to invoke it after some work.

If the user invokes the skill immediately after another progress note with no new work between, tell them there is nothing new since the last note and ask whether to proceed or skip.

If the title hint does not match the actual work, use the hint for the filename but write the body honestly. If the mismatch is severe, mention it briefly in the confirmation.
