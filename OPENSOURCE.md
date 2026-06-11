# Open-source brainstorm — the road to a thousand stars

Living document (Owner idea #8). The loop and the owner both add thoughts; ideas that mature
become backlog slices.

## Positioning

- **One-liner:** "Atlas — the self-hosted research workbench. Plans, papers, notes, and
  manuscripts in one calm place, with an AI collaborator built in."
- The wedge: nothing open-source combines *project plans + reference manager + knowledge
  graph + writing pipeline + MCP*. Zotero does references, Obsidian does notes, Notion does
  plans — Atlas does the researcher's whole loop.
- The demo that sells it: add a paper by DOI → it appears in the reading queue → read it in
  the browser → highlight a sentence → it becomes a note in the graph → cite it in a
  manuscript → cite-checker validates the .tex. One unbroken 60-second GIF.
- Second demo: Claude (via MCP) checking off milestones and adding papers by DOI in chat.

## Star-worthiness checklist (becomes slices later)

- [x] LICENSE — AGPL-3.0 (cycle 28; rationale in DECISIONS.md)
- [x] One-command install — `docker compose --profile app up -d --build` runs web+worker+db+redis (cycle 29)
- [x] README with hero screenshots, feature grid, comparison table (cycle 28; GIF still todo)
- [ ] Demo instance or `seed_demo`-powered screenshot tour
- [x] CONTRIBUTING.md (cycle 28); issue + PR templates + architecture invariants (cycle 82)
- [ ] Docs site (mkdocs-material) with the MCP setup guide front and center
- [ ] Launch posts: HN (Show HN), r/selfhosted, r/PhD, r/AcademicPsychology, lobste.rs
- [ ] Name check: "Atlas" is crowded — consider a distinctive rename before launch

## Raw ideas

- The MCP angle is the most timely hook — "your research manager is also an MCP server" is a
  headline feature no incumbent has.
- Ship a tiny hosted read-only demo seeded with `seed_demo` so people can click before installing.
- Blog post: "I let Claude build and run my research lab's PM tool" — the build story itself
  is launch content.
