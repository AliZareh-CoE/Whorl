"""Code-defined project scaffolds (file-workspace epic #30, slice 7).

Instantiating a project from a template lays down an organized, expandable folder
structure with starter files — the "a place for everything" value, in folder form.
Lives here (no DB table) so the templates version with the code, mirroring
writing/templates_gallery.py. Each starter file is markdown that explains what lives
where, so an empty project already documents itself.
"""

TEMPLATES = {
    "empirical": {
        "name": "Empirical study",
        "description": "Hypothesis-driven study: literature, data, analysis, manuscript.",
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
        {"key": k, "name": v["name"], "description": v["description"], "folders": v["folders"]}
        for k, v in TEMPLATES.items()
    ]
