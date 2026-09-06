---
name: atlas-plan
description: Shape and track a research plan in Atlas — phases, milestones, tasks, dates, research questions and decisions, plus roadmap health. Use when the user mentions a plan, phases, milestones, deadlines, a roadmap, "where are we", or wants to record a decision.
---

# Atlas: plans

A project is driven by a written plan: phases → milestones → optional tasks. Progress
rolls up from milestones. Questions and decisions hang off the project.

## Read the plan

- `get_project_overview` — current phase, next milestones, recent decisions, health.
- `get_plan` (structured) or `get_plan_outline` (Markdown with `{#id}` tokens).
- `get_roadmap` — inferred windows and health per phase (behind / on track / blocked /
  overdue); `get_week_focus` for what matters this week.

## Change the plan

1. Edit the Markdown from `get_plan_outline`. Keep every `{#id}` token on lines you are
   not deleting — a token is how Atlas knows a milestone moved rather than was replaced.
2. `set_plan_outline` with `dry_run=true` first and show the user the preview
   (created / updated / removed). Apply only after a "yes".
3. `set_phase_dates` for target windows; `complete_milestone` when the user says a
   milestone is done (never on your own inference).

## Questions and decisions

- Research questions live on the plan; keep their status (open / partially answered /
  answered / abandoned) in step with the evidence.
- Record decisions the moment the user makes one: title, the situation, what was
  decided, what was rejected and why — via `add_note` only if the decision tool is not
  present in this Atlas; otherwise use the project's decision log through the API.

## Conventions

- Dates are ISO (`2026-09-30`). Ask for the year if it is ambiguous.
- Prefer fewer, larger milestones with clear completion criteria over task soup.
