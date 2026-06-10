"""Cite checking for manuscripts: \\cite{...} keys vs the manuscript bibliography."""

import re

from literature.services import render_bibtex, run_bib_report

CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|parencite|textcite|autocite|footcite|fullcite)"
    r"\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]+)\}"
)


def parse_cite_keys(tex: str) -> set[str]:
    keys = set()
    for match in CITE_RE.finditer(tex or ""):
        for key in match.group(1).split(","):
            key = key.strip()
            if key and key != "*":
                keys.add(key)
    return keys


def check_citations(manuscript, tex: str) -> dict:
    """Compare \\cite keys in the .tex against the manuscript bibliography."""
    cited = parse_cite_keys(tex)
    bib_keys = {
        link.cite_key for link in manuscript.manuscriptreference_set.select_related("reference")
    }
    return {
        "cited": sorted(cited),
        "missing_from_bib": sorted(cited - bib_keys),
        "uncited_in_bib": sorted(bib_keys - cited),
        "matched": sorted(cited & bib_keys),
    }


def export_manuscript_bib(manuscript) -> str:
    entries = []
    for link in manuscript.manuscriptreference_set.select_related("reference").order_by(
        "reference__bibtex_key"
    ):
        entries.append(render_bibtex(link.reference, key_override=link.cite_key_override))
    return "\n\n".join(entries)


def manuscript_bib_report(manuscript, include_network_checks: bool = False) -> dict:
    references = [link.reference for link in manuscript.manuscriptreference_set.all()]
    return run_bib_report(references, include_network_checks=include_network_checks)
