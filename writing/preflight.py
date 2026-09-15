"""Submission pre-flight (#466): "is this paper ready to send?" answered from real data.

Every check reads what Atlas already knows — the compile state and diagnostics, the cite
check, the offline bib checkers, the venue budget, the source tree — and answers one of
``ok`` / ``warn`` / ``fail`` / ``skip`` with a one-line detail and, where the studio has a
place to fix it, a ``fix`` pointer (a sidebar tab, a file:line, or the compile action). The
manuscript is *ready* when nothing fails; warnings are judgment calls the author sees and
may accept. Nothing here talks to the network unless ``network=True`` (DOI resolution and
retraction checks through the bib report).
"""

from __future__ import annotations

import re

from django.utils import timezone

INCLUDEGRAPHICS = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
IMAGE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg", ".tif", ".tiff")
LEFTOVER = re.compile(
    r"%\s*(?:TODO|FIXME|XXX|HACK)\b|\\todo(?:\[[^\]]*\])?\{|\\textcolor\{red\}|\?\?"
)
FAILING_WARNING = re.compile(
    r"undefined|multiply defined|Citation .* undefined|There were undefined", re.IGNORECASE
)


def _tex_files(manuscript) -> list:
    return list(manuscript.files.filter(kind="tex").order_by("path"))


def _source(manuscript, files) -> str:
    return "\n".join(f.content for f in files) if files else (manuscript.latex_source or "")


def _check(key, label, state, detail, fix=None) -> dict:
    row = {"key": key, "label": label, "state": state, "detail": detail}
    if fix:
        row["fix"] = fix
    return row


def check_metadata(manuscript) -> list[dict]:
    rows = []
    if not manuscript.target_venue:
        rows.append(
            _check(
                "venue",
                "Target venue",
                "warn",
                "No target venue set — limits and the cover letter need one.",
                {"kind": "settings"},
            )
        )
    else:
        rows.append(_check("venue", "Target venue", "ok", manuscript.target_venue))
    days = manuscript.days_to_deadline
    if manuscript.deadline is None:
        rows.append(
            _check("deadline", "Deadline", "warn", "No deadline set.", {"kind": "settings"})
        )
    elif days is not None and days < 0:
        rows.append(
            _check(
                "deadline",
                "Deadline",
                "fail",
                f"The deadline passed {-days} day{'s' if days != -1 else ''} ago ({manuscript.deadline}).",
                {"kind": "settings"},
            )
        )
    elif days is not None and days <= 3:
        rows.append(
            _check(
                "deadline",
                "Deadline",
                "warn",
                f"{days} day{'s' if days != 1 else ''} left ({manuscript.deadline}).",
            )
        )
    else:
        rows.append(
            _check("deadline", "Deadline", "ok", f"{days} days left ({manuscript.deadline}).")
        )
    if not manuscript.abstract.strip():
        rows.append(
            _check(
                "abstract",
                "Abstract",
                "warn",
                "No abstract on the manuscript record — submission forms ask for one.",
                {"kind": "settings"},
            )
        )
    else:
        rows.append(
            _check("abstract", "Abstract", "ok", f"{len(manuscript.abstract.split())} words.")
        )
    return rows


def check_compile(manuscript) -> list[dict]:
    from .compile import source_hash

    status = manuscript.compile_status
    if status != "ok" or not manuscript.compiled_pdf:
        detail = {
            "failed": "The last compile failed — fix the errors and compile again.",
            "running": "A compile is running; check again when it finishes.",
        }.get(status, "Never compiled — there is no PDF to submit.")
        return [_check("compile", "Compiled PDF", "fail", detail, {"kind": "compile"})]
    fresh = manuscript.compiled_source_hash and manuscript.compiled_source_hash == source_hash(
        manuscript
    )
    if not fresh:
        return [
            _check(
                "compile",
                "Compiled PDF",
                "warn",
                "The PDF is older than the source — compile once more before submitting.",
                {"kind": "compile"},
            )
        ]
    when = manuscript.compiled_at.strftime("%Y-%m-%d %H:%M") if manuscript.compiled_at else "now"
    return [
        _check("compile", "Compiled PDF", "ok", f"Up to date with the source (compiled {when}).")
    ]


def check_diagnostics(manuscript) -> list[dict]:
    diags = list(manuscript.compile_diagnostics or [])
    errors = [d for d in diags if d.get("level") == "error"]
    warnings = [d for d in diags if d.get("level") == "warning"]
    fatal = [d for d in warnings if FAILING_WARNING.search(d.get("message", ""))]
    rows = []
    if errors:
        first = errors[0]
        rows.append(
            _check(
                "errors",
                "Compile errors",
                "fail",
                f"{len(errors)} error{'s' if len(errors) != 1 else ''} — first: {first.get('message', '')[:120]}",
                _loc(first) or {"kind": "problems"},
            )
        )
    else:
        rows.append(
            _check(
                "errors",
                "Compile errors",
                "ok" if diags or manuscript.compile_status == "ok" else "skip",
                "None in the last compile."
                if manuscript.compile_status == "ok"
                else "No compile yet.",
            )
        )
    if fatal:
        first = fatal[0]
        rows.append(
            _check(
                "undefined",
                "Undefined references",
                "fail",
                f"{len(fatal)} undefined citation/reference warning{'s' if len(fatal) != 1 else ''} — first: {first.get('message', '')[:120]}",
                _loc(first) or {"kind": "problems"},
            )
        )
    elif warnings:
        rows.append(
            _check(
                "undefined",
                "Undefined references",
                "ok",
                "None; "
                + f"{len(warnings)} other warning{'s' if len(warnings) != 1 else ''} (overfull boxes and the like) remain.",
                {"kind": "problems"},
            )
        )
    else:
        rows.append(
            _check(
                "undefined",
                "Undefined references",
                "ok" if manuscript.compile_status == "ok" else "skip",
                "None." if manuscript.compile_status == "ok" else "No compile yet.",
            )
        )
    return rows


def _loc(diag) -> dict | None:
    if diag.get("file") and diag.get("line"):
        return {"kind": "line", "path": diag["file"], "line": diag["line"]}
    return None


def check_citations(manuscript, source) -> list[dict]:
    from .services import check_citations as cite_check

    result = cite_check(manuscript, source)
    rows = []
    missing = result["missing_from_bib"]
    if missing:
        rows.append(
            _check(
                "cite_missing",
                "Cited but not in the bibliography",
                "fail",
                f"{len(missing)} key{'s' if len(missing) != 1 else ''}: "
                + ", ".join(missing[:6])
                + (" …" if len(missing) > 6 else ""),
                {"kind": "tab", "tab": "bib"},
            )
        )
    else:
        rows.append(
            _check(
                "cite_missing",
                "Cited but not in the bibliography",
                "ok" if result["cited"] else "skip",
                "Every \\cite key resolves." if result["cited"] else "Nothing is cited yet.",
            )
        )
    uncited = result["uncited_in_bib"]
    if uncited:
        rows.append(
            _check(
                "cite_unused",
                "In the bibliography but never cited",
                "warn",
                f"{len(uncited)} entr{'ies' if len(uncited) != 1 else 'y'} would print unused: "
                + ", ".join(uncited[:6])
                + (" …" if len(uncited) > 6 else ""),
                {"kind": "tab", "tab": "bib"},
            )
        )
    else:
        rows.append(
            _check(
                "cite_unused", "In the bibliography but never cited", "ok", "Every entry is cited."
            )
        )
    return rows


def check_bibliography(manuscript, network: bool) -> list[dict]:
    from .services import manuscript_bib_report

    if not manuscript.manuscriptreference_set.exists():
        return [_check("bib_hygiene", "Bibliography hygiene", "skip", "No references linked.")]
    report = manuscript_bib_report(manuscript, include_network_checks=network)
    rows = []
    missing = report["missing_fields"]
    dups = report["duplicates"]
    problems = []
    if missing:
        problems.append(
            f"{len(missing)} entr{'ies' if len(missing) != 1 else 'y'} missing required fields"
        )
    if dups:
        problems.append(f"{len(dups)} possible duplicate{'s' if len(dups) != 1 else ''}")
    rows.append(
        _check(
            "bib_hygiene",
            "Bibliography hygiene",
            "warn" if problems else "ok",
            "; ".join(problems) + "." if problems else "Required fields present, no duplicates.",
            {"kind": "tab", "tab": "bib"} if problems else None,
        )
    )
    if network:
        bad_doi = report["doi_resolution"]
        rows.append(
            _check(
                "doi",
                "DOIs resolve",
                "warn" if bad_doi else "ok",
                f"{len(bad_doi)} DOI{'s' if len(bad_doi) != 1 else ''} did not resolve."
                if bad_doi
                else "Every DOI resolves.",
                {"kind": "tab", "tab": "bib"} if bad_doi else None,
            )
        )
    # #527: the retraction watch's stored verdicts are always consulted (no network needed);
    # a network pre-flight also asks Crossref about the papers it has not flagged yet.
    stored = sorted(
        {
            link.reference.bibtex_key
            for link in manuscript.manuscriptreference_set.select_related("reference")
            if link.reference.retraction_kind
        }
    )
    live = sorted(
        {
            r.bibtex_key
            for f in (report["retractions"] if network else [])
            if f.get("level") == "error"
            for r in f.get("references", [])
        }
    )
    retracted = sorted(set(stored) | set(live))
    rows.append(
        _check(
            "retractions",
            "Retractions",
            "fail" if retracted else "ok",
            (
                f"{len(retracted)} cited work{'s' if len(retracted) != 1 else ''} retracted: "
                + ", ".join(retracted)
                + "."
            )
            if retracted
            else ("None flagged." if network else "None flagged by the retraction watch."),
            {"kind": "tab", "tab": "bib"} if retracted else None,
        )
    )
    return rows


def check_budget(manuscript) -> list[dict]:
    from .budget import budget

    out = budget(manuscript)
    if not out["limits"]:
        return [
            _check(
                "budget",
                "Venue limits",
                "skip",
                "No venue limits set — nothing to measure against.",
                {"kind": "settings"},
            )
        ]
    near = [i["label"].lower() for i in out["items"] if i["state"] == "near"]
    if out["over"]:
        return [
            _check(
                "budget",
                "Venue limits",
                "fail",
                "Over the limit on " + ", ".join(out["over"]) + ".",
                {"kind": "budget"},
            )
        ]
    if near:
        return [
            _check(
                "budget",
                "Venue limits",
                "warn",
                "Within every limit; close on " + ", ".join(near) + ".",
                {"kind": "budget"},
            )
        ]
    return [_check("budget", "Venue limits", "ok", out["summary"].capitalize() + ".")]


def check_figures(manuscript, files) -> list[dict]:
    assets = {f.path for f in manuscript.files.filter(kind="asset")}
    stems = {p.rsplit(".", 1)[0] for p in assets}
    used, missing = [], []
    for f in files:
        for match in INCLUDEGRAPHICS.finditer(f.content):
            raw = match.group(1).strip().lstrip("./")
            used.append(raw)
            if raw in assets or raw in stems:
                continue
            if any(raw.endswith(ext) and raw in assets for ext in IMAGE_EXTENSIONS):
                continue
            missing.append((raw, f.path, f.content[: match.start()].count("\n") + 1))
    if not used:
        return [_check("figures", "Figure files", "skip", "No \\includegraphics in the sources.")]
    if missing:
        raw, path, line = missing[0]
        return [
            _check(
                "figures",
                "Figure files",
                "fail",
                f"{len(missing)} of {len(used)} figure path{'s' if len(used) != 1 else ''} match no file in the tree — first: {raw} ({path}:{line}).",
                {"kind": "line", "path": path, "line": line},
            )
        ]
    return [
        _check(
            "figures",
            "Figure files",
            "ok",
            f"All {len(used)} figure path{'s' if len(used) != 1 else ''} resolve to files in the tree.",
        )
    ]


def check_figure_quality(manuscript, files) -> list[dict]:
    """#473: will every raster figure print sharp? Vector formats pass; rasters are measured."""
    from writing.figures import audit_figures

    if not any(INCLUDEGRAPHICS.search(f.content) for f in files):
        return []  # the "Figure files" row already says there are none
    out = audit_figures(manuscript)
    bad = [r for r in out["figures"] if r["state"] in ("fail", "warn")]
    if not bad:
        return [_check("figure_quality", "Figure quality", "ok", out["summary"])]
    first = sorted(bad, key=lambda r: (r["state"] != "fail", r["tex"], r["line"]))[0]
    state = "fail" if out["fails"] else "warn"
    return [
        _check(
            "figure_quality",
            "Figure quality",
            state,
            f"{out['summary']} {first['path']}: {first['detail']}",
            {"kind": "line", "path": first["tex"], "line": first["line"]},
        )
    ]


def check_leftovers(files, source) -> list[dict]:
    hits = []
    if files:
        for f in files:
            for n, line in enumerate(f.content.splitlines(), 1):
                if LEFTOVER.search(line):
                    hits.append((f.path, n, line.strip()[:80]))
    else:
        for n, line in enumerate(source.splitlines(), 1):
            if LEFTOVER.search(line):
                hits.append(("main.tex", n, line.strip()[:80]))
    if not hits:
        return [
            _check(
                "leftovers",
                "Leftover markers",
                "ok",
                "No TODO / FIXME / \\todo / ?? in the sources.",
            )
        ]
    path, line, text = hits[0]
    return [
        _check(
            "leftovers",
            "Leftover markers",
            "warn",
            f"{len(hits)} marker{'s' if len(hits) != 1 else ''} still in the text — first at {path}:{line}: {text}",
            {"kind": "line", "path": path, "line": line},
        )
    ]


def check_lint(files, source) -> list[dict]:
    """#470: the style lint — never blocks (heuristics), but the first finding is one click away."""
    from writing.lint import lint_files

    pairs = [(f.path, f.content) for f in files] if files else [("main.tex", source)]
    out = lint_files(pairs)
    if not out["count"]:
        return [_check("lint", "Style lint", "ok", "No lint findings in the sources.")]
    first = out["findings"][0]
    n, e = out["count"], out["errors"]
    detail = (
        f"{n} finding{'s' if n != 1 else ''}"
        + (f" ({e} serious)" if e else "")
        + f" — first at {first['file']}:{first['line']}: {first['message']}"
    )
    return [
        _check(
            "lint",
            "Style lint",
            "warn",
            detail,
            {"kind": "line", "path": first["file"], "line": first["line"]},
        )
    ]


def check_bbl(manuscript) -> list[dict]:
    if not manuscript.manuscriptreference_set.exists():
        return [_check("bbl", "Bibliography file for arXiv", "skip", "No references linked.")]
    if manuscript.compiled_bbl:
        return [
            _check(
                "bbl",
                "Bibliography file for arXiv",
                "ok",
                "main.bbl was kept from the last compile; the submission zip ships it.",
            )
        ]
    return [
        _check(
            "bbl",
            "Bibliography file for arXiv",
            "warn",
            "No .bbl kept yet — compile once more so the submission zip carries it.",
            {"kind": "compile"},
        )
    ]


def preflight(manuscript, *, network: bool = False) -> dict:
    files = _tex_files(manuscript)
    source = _source(manuscript, files)
    checks = [
        *check_compile(manuscript),
        *check_diagnostics(manuscript),
        *check_citations(manuscript, source),
        *check_bibliography(manuscript, network),
        *check_budget(manuscript),
        *check_figures(manuscript, files),
        *check_figure_quality(manuscript, files),
        *check_leftovers(files, source),
        *check_lint(files, source),
        *check_bbl(manuscript),
        *check_metadata(manuscript),
    ]
    fails = sum(1 for c in checks if c["state"] == "fail")
    warns = sum(1 for c in checks if c["state"] == "warn")
    if fails:
        summary = (
            f"Not ready — {fails} blocking issue{'s' if fails != 1 else ''}"
            + (f", {warns} to look at" if warns else "")
            + "."
        )
    elif warns:
        summary = f"Ready with {warns} thing{'s' if warns != 1 else ''} to look at."
    else:
        summary = "Ready to submit."
    return {
        "ready": fails == 0,
        "fails": fails,
        "warns": warns,
        "summary": summary,
        "network": network,
        "checked_at": timezone.now().isoformat(),
        "checks": checks,
    }
