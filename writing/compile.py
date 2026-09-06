"""Server-side LaTeX compilation via the vendored Tectonic binary (Owner idea #9/#24)."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import Manuscript, ManuscriptFile
from .services import export_manuscript_bib

TECTONIC = Path(settings.BASE_DIR) / "bin" / "tectonic"
COMPILE_TIMEOUT = 180
MISSING_ENGINE = (
    "The LaTeX engine (Tectonic) was not found. Desktop builds bundle it; in a source "
    "checkout run `make tectonic`, or point ATLAS_TECTONIC at a tectonic binary."
)

RESULT_FIELDS = [
    "compile_status",
    "compile_log",
    "compile_diagnostics",
    "compiled_pdf",
    "compiled_at",
    "updated_at",
]


def tectonic_path() -> Path | None:
    """Where the engine lives: ATLAS_TECTONIC, then the bundled bin/ (desktop builds ship
    `tectonic` / `tectonic.exe` there), then PATH. Owner report 2026-09-06: the desktop
    installer had no engine at all, so Recompile always failed."""
    env = os.environ.get("ATLAS_TECTONIC")
    if env and Path(env).exists():
        return Path(env)
    for name in ("tectonic", "tectonic.exe"):
        candidate = TECTONIC.with_name(name)
        if candidate.exists():
            return candidate
    found = shutil.which("tectonic")
    return Path(found) if found else None


def tectonic_available() -> bool:
    return tectonic_path() is not None


def _stale(manuscript: Manuscript, generation: int | None) -> bool:
    """A newer compile was queued after this one — drop our results (epic slice 2)."""
    if generation is None:
        return False
    current = Manuscript.objects.values_list("compile_generation", flat=True).get(pk=manuscript.pk)
    return generation < current


def _fail(manuscript: Manuscript, log: str) -> str:
    from .log_parser import parse_compile_log

    manuscript.compile_status = Manuscript.CompileStatus.FAILED
    manuscript.compile_log = log
    manuscript.compile_diagnostics = parse_compile_log(log)
    # explicit update_fields everywhere: a full save would push a stale latex_source
    # over main-file edits made while we ran (alias hook, slice 6)
    manuscript.save(update_fields=RESULT_FIELDS)
    return manuscript.compile_log


def _write_tree(work: Path, files: list[ManuscriptFile]) -> str | None:
    """Write the manuscript tree into the build dir; an error string on refusal."""
    work_resolved = work.resolve()
    for f in files:
        dest = work / f.path
        if not dest.resolve().is_relative_to(work_resolved):
            # model validation forbids traversal; rows injected past it must fail LOUDLY
            return f"Refusing to write {f.path!r} outside the build directory."
        dest.parent.mkdir(parents=True, exist_ok=True)
        if f.kind == ManuscriptFile.Kind.ASSET and f.asset:
            with f.asset.open("rb") as src:
                dest.write_bytes(src.read())
        else:
            dest.write_text(f.content)
    return None


def compile_manuscript(manuscript: Manuscript, generation: int | None = None) -> str:
    """Compile the manuscript's file tree (or legacy latex_source) to PDF."""
    if _stale(manuscript, generation):
        return "skipped: a newer compile was queued"

    files = list(manuscript.files.all())
    main = next((f for f in files if f.is_main), None)
    if not files:
        main_path, source = "main.tex", manuscript.latex_source  # legacy, no rows yet
    elif main is None:
        return _fail(manuscript, "error: No main file is set — mark one file as main.")
    else:
        main_path, source = main.path, main.content

    if not source.strip():
        return _fail(manuscript, "Nothing to compile — the LaTeX source is empty.")
    if not tectonic_available():
        return _fail(manuscript, MISSING_ENGINE)

    manuscript.compile_status = Manuscript.CompileStatus.RUNNING
    manuscript.save(update_fields=["compile_status", "updated_at"])

    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        if files:
            refusal = _write_tree(work, files)
            if refusal:
                return _fail(manuscript, f"error: {refusal}")
        else:
            (work / main_path).write_text(source)
        # generated bib must not clobber a user-created references.bib
        bib = export_manuscript_bib(manuscript)
        if bib and not (work / "references.bib").exists():
            (work / "references.bib").write_text(bib)
        try:
            proc = subprocess.run(
                [str(tectonic_path()), "--untrusted", "--chatter", "minimal", main_path],
                cwd=work,
                capture_output=True,
                text=True,
                timeout=COMPILE_TIMEOUT,
            )
            log = (proc.stdout + proc.stderr).strip()
            pdf_path = (work / main_path).with_suffix(".pdf")
            if proc.returncode == 0 and pdf_path.exists():
                manuscript.compiled_pdf.save(
                    f"manuscript-{manuscript.pk}.pdf",
                    ContentFile(pdf_path.read_bytes()),
                    save=False,
                )
                manuscript.compile_status = Manuscript.CompileStatus.OK
                manuscript.compiled_at = timezone.now()
            else:
                manuscript.compile_status = Manuscript.CompileStatus.FAILED
        except subprocess.TimeoutExpired:
            log = f"Compile timed out after {COMPILE_TIMEOUT}s."
            manuscript.compile_status = Manuscript.CompileStatus.FAILED
    if _stale(manuscript, generation):
        return "skipped: a newer compile superseded this one"
    manuscript.compile_log = log[-10000:]
    from .log_parser import parse_compile_log

    manuscript.compile_diagnostics = parse_compile_log(manuscript.compile_log)
    manuscript.save(update_fields=RESULT_FIELDS)
    if manuscript.compile_status == Manuscript.CompileStatus.OK:
        from .models import snapshot_manuscript

        snapshot_manuscript(manuscript)  # version history (slice 9)
    return manuscript.compile_log
