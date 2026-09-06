---
name: atlas-daily
description: Start or close a research day in Atlas — read the dashboard, pick today's three things, keep the Today list and the inbox honest. Use when the user says "what should I work on", "start my day", "plan today", "end of day", or asks for a status across projects.
---

# Atlas: the daily loop

Atlas is the user's research project manager; you reach it through the `atlas` MCP tools.
Every object lives in exactly one project (a slug like `attention-and-memory`).

## Morning: "what should I work on?"

1. `get_dashboard` — active projects with health, this week's overdue and due items
   everywhere, open todos, the inbox count.
2. `get_week_focus` for the one or two projects that are *behind* or have deadlines
   inside seven days.
3. Propose **at most three** things for today, each tied to a milestone, manuscript
   deadline or reading item. Say why each one, in one line.
4. When the user agrees, `add_todo` for each (short imperative text). Do not add more.

## Inbox triage

`list_inbox` → for each capture, `convert_capture` with the target the hint suggests
(`paper` for DOIs/arXiv ids, `todo` for "todo:" lines, `note`, `milestone`, `decision`).
Ask before converting anything ambiguous; never dismiss a capture you did not convert
unless the user says so.

## Evening: "close the day"

1. `list_todos` — read back what was done; `complete_todo` for anything the user says
   is finished.
2. `get_weekly_review` on Fridays, summarised in five lines: shipped, moved, stuck,
   read, next.
3. Offer to `quick_capture` any loose thought the user mentions so nothing is lost.

## When something is broken

`get_diagnostics` (add `network=true` to probe the update feed) returns the same report as
the app's Diagnostics page — quote its `text` field when the user asks why a compile, an
update or the terminal failed.

## Conventions

- Prefer reading tools first; write only what the user asked for.
- Never delete or overwrite plans, notes or references without an explicit "yes".
- Refer to projects by name, not slug, when talking to the user.
