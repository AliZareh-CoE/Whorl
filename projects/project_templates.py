"""Code-defined project scaffolds (file-workspace epic #30, slice 7).

Instantiating a project from a template lays down an organized, expandable folder
structure with starter files — the "a place for everything" value, in folder form.
Lives here (no DB table) so the templates version with the code, mirroring
writing/templates_gallery.py. Each starter file is markdown that explains what lives
where, so an empty project already documents itself.

#438: a template is also a *plan* — `plan` is a plans.outline Markdown outline (phases →
milestones → tasks), `questions` starter research questions and `themes` review-matrix
columns; all three are laid down only when the project has none yet.
"""

TEMPLATES = {
    "empirical": {
        "name": "Empirical study",
        "description": "Hypothesis-driven study: literature, data, analysis, manuscript.",
        "plan": (
            "# Literature & hypotheses\n"
            "> Read into the question until the hypotheses are falsifiable.\n"
            "- [ ] Annotated bibliography (the 30 papers that matter)\n"
            "- [ ] Hypotheses registered in the ledger\n"
            "# Design & pilot\n"
            "> Decide the paradigm; pilot until the measure behaves.\n"
            "- [ ] Protocol v1 written\n"
            "- [ ] Pilot run (n small) and analysed\n"
            "  - [ ] Ethics / approval in place\n"
            "- [ ] Pre-registration filed\n"
            "# Data collection\n"
            "- [ ] Full sample collected\n"
            "- [ ] Data dictionary complete\n"
            "# Analysis & write-up\n"
            "- [ ] Pre-registered analysis run\n"
            "- [ ] Figures final\n"
            "- [ ] Manuscript submitted\n"
        ),
        "questions": [
            "What is the effect we expect, and what result would falsify it?",
            "What is the smallest sample that can answer this?",
        ],
        "themes": ["Theory", "Method", "Key finding", "Limitation"],
        "folders": [
            "literature",
            "data/raw",
            "data/processed",
            "analysis",
            "manuscript/figures",
            "protocols",
            "notes",
        ],
        "files": {
            "README.md": "# {name}\n\n## Research question\n_What are we trying to answer?_\n\n"
            "## Layout\n- `literature/` — papers & reading notes\n- `data/` — raw and processed\n"
            "- `analysis/` — scripts, results, figures\n- `manuscript/` — the write-up\n"
            "- `protocols/` — how experiments are run\n- `notes/` — working notes\n",
            "data/DATA-DICTIONARY.md": "# Data dictionary\n\n| field | type | description |\n"
            "|---|---|---|\n",
            "analysis/analysis-log.md": "# Analysis log\n\nDated entries: what was run, what came out.\n",
            "protocols/protocol-v1.md": "# Protocol v1\n\n## Setup\n\n## Steps\n\n## Notes\n",
        },
    },
    "review": {
        "name": "Theory / review paper",
        "description": "Literature synthesis: sources, themes, and the manuscript.",
        "plan": (
            "# Scope & search\n"
            "> Fix the question, the inclusion criteria and where to look.\n"
            "- [ ] Inclusion criteria written down\n"
            "- [ ] Search strategy run and logged\n"
            "# Screening & extraction\n"
            "- [ ] Titles and abstracts screened\n"
            "- [ ] Review matrix filled (papers × themes)\n"
            "# Synthesis\n"
            "- [ ] Themes settled, gaps named\n"
            "- [ ] Related-work draft from the matrix\n"
            "# Write-up\n"
            "- [ ] Full draft\n"
            "- [ ] Submitted\n"
        ),
        "questions": [
            "What do the papers agree on, and where do they contradict each other?",
            "Which claims rest on a single study?",
        ],
        "themes": ["Claim", "Evidence type", "Population", "Open problem"],
        "folders": ["literature", "synthesis", "manuscript/figures", "notes"],
        "files": {
            "README.md": "# {name}\n\nA review / theory paper.\n\n- `literature/` — the corpus\n"
            "- `synthesis/` — themes, matrices, arguments\n- `manuscript/` — the draft\n",
            "synthesis/review-matrix.md": "# Review matrix\n\n| paper | theme A | theme B |\n"
            "|---|---|---|\n",
        },
    },
    "software": {
        "name": "Software / dataset project",
        "description": "A tool or dataset release: docs, evaluation, and a paper.",
        "plan": (
            "# Design\n"
            "> What it does, for whom, and what it must never do.\n"
            "- [ ] Design note agreed\n"
            "- [ ] Evaluation plan (what we measure)\n"
            "# Build\n"
            "- [ ] Minimal working version\n"
            "- [ ] Documentation for a stranger\n"
            "# Evaluate\n"
            "- [ ] Benchmarks run and recorded\n"
            "- [ ] Comparison with the alternatives\n"
            "# Release & paper\n"
            "- [ ] Tagged release\n"
            "- [ ] Paper submitted\n"
        ),
        "questions": [
            "What is the one measurement that shows this is better than the alternatives?",
        ],
        "themes": ["Approach", "Benchmark", "Result"],
        "folders": ["src-notes", "data", "docs", "evaluation", "paper"],
        "files": {
            "README.md": "# {name}\n\nA software / dataset project.\n\n- `src-notes/` — design notes\n"
            "- `data/` — datasets\n- `docs/` — documentation\n- `evaluation/` — benchmarks\n"
            "- `paper/` — the write-up\n",
            "evaluation/benchmarks.md": "# Benchmarks\n\nWhat we measure and the numbers.\n",
        },
    },
    "minimal": {
        "name": "Minimal",
        "description": "Just a notes folder and a README — grow it yourself.",
        "plan": "# Getting started\n- [ ] Write down the question\n",
        "questions": [],
        "themes": [],
        "folders": ["notes"],
        "files": {"README.md": "# {name}\n\nStart here.\n"},
    },
}


def template_choices():
    """[(key, label), ...] for a form ChoiceField; the empty choice = no scaffold."""
    return [("", "Empty project")] + [(k, v["name"]) for k, v in TEMPLATES.items()]


def template_list():
    """Serializable list for the API / SPA picker."""
    return [
        {
            "key": k,
            "name": v["name"],
            "description": v["description"],
            "folders": v["folders"],
            # #438: the plan, questions and themes the template lays down
            "phases": sum(1 for line in v.get("plan", "").splitlines() if line.startswith("#")),
            "milestones": sum(
                1 for line in v.get("plan", "").splitlines() if line.startswith("- [")
            ),
            "questions": len(v.get("questions", [])),
            "themes": len(v.get("themes", [])),
        }
        for k, v in TEMPLATES.items()
    ]
