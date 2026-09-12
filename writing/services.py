"""Cite checking for manuscripts: \\cite{...} keys vs the manuscript bibliography."""

import re

from literature.services import render_bibtex, run_bib_report

CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|parencite|textcite|autocite|footcite|fullcite|nocite)"
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


def duplicate_manuscript(source, title: str = "", project=None, *, bibliography: bool = True):
    """#446 (backlog #128): a fresh manuscript from an existing one — every source file (text and
    assets), the venue limits and, by default, the bibliography links. Compile state, revisions,
    comments and submission events stay with the original; the copy starts as an idea."""
    from django.core.files.base import ContentFile
    from django.db import transaction

    from .models import Manuscript, ManuscriptFile, ManuscriptReference

    has_files = source.files.exists()
    with transaction.atomic():
        copy = Manuscript.objects.create(
            project=project or source.project,
            title=(title or f"Copy of {source.title}")[:400],
            status=Manuscript.Status.IDEA,
            target_venue=source.target_venue,
            abstract=source.abstract,
            repo_url=source.repo_url,
            # with a source tree the main file's save fills latex_source; without one the
            # alias sync builds main.tex from it — never both, or main.tex would exist twice
            latex_source="" if has_files else source.latex_source,
            venue_limits=dict(source.venue_limits or {}),
        )
        _copy_tree(source, copy, ManuscriptFile, ContentFile)
        if bibliography:
            for link in source.manuscriptreference_set.all():
                ManuscriptReference.objects.create(
                    manuscript=copy,
                    reference=link.reference,
                    cite_key_override=link.cite_key_override,
                )
    return copy


def _copy_tree(source, copy, ManuscriptFile, ContentFile):
    # the main file last, so the alias sync sees the whole tree
    for f in sorted(source.files.all(), key=lambda f: f.is_main):
        row = ManuscriptFile(
            manuscript=copy, path=f.path, kind=f.kind, content=f.content, is_main=f.is_main
        )
        if f.kind == ManuscriptFile.Kind.ASSET and f.asset:
            with f.asset.open("rb") as src:
                row.asset.save(f.asset.name.rsplit("/", 1)[-1], ContentFile(src.read()), save=False)
        row.save()
