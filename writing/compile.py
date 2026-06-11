"""Server-side LaTeX compilation via the vendored Tectonic binary (Owner idea #9)."""

import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import Manuscript
from .services import export_manuscript_bib

TECTONIC = Path(settings.BASE_DIR) / "bin" / "tectonic"
COMPILE_TIMEOUT = 180


def tectonic_available() -> bool:
    return TECTONIC.exists()


def _stale(manuscript: Manuscript, generation: int | None) -> bool:
    """A newer compile was queued after this one — drop our results (epic slice 2)."""
    if generation is None:
        return False
    current = Manuscript.objects.values_list("compile_generation", flat=True).get(pk=manuscript.pk)
    return generation < current


def compile_manuscript(manuscript: Manuscript, generation: int | None = None) -> str:
    """Compile latex_source to PDF; stores status, log, and the PDF on the manuscript."""
    if _stale(manuscript, generation):
        return "skipped: a newer compile was queued"
    if not manuscript.latex_source.strip():
        manuscript.compile_status = Manuscript.CompileStatus.FAILED
        manuscript.compile_log = "Nothing to compile — the LaTeX source is empty."
        manuscript.compile_diagnostics = []
        manuscript.save()
        return manuscript.compile_log
    if not tectonic_available():
        manuscript.compile_status = Manuscript.CompileStatus.FAILED
        manuscript.compile_log = "Tectonic binary missing — run `make tectonic` first."
        manuscript.compile_diagnostics = []
        manuscript.save()
        return manuscript.compile_log

    manuscript.compile_status = Manuscript.CompileStatus.RUNNING
    manuscript.save(update_fields=["compile_status", "updated_at"])

    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        (work / "main.tex").write_text(manuscript.latex_source)
        bib = export_manuscript_bib(manuscript)
        if bib:
            (work / "references.bib").write_text(bib)
        try:
            proc = subprocess.run(
                [str(TECTONIC), "--chatter", "minimal", "main.tex"],
                cwd=work,
                capture_output=True,
                text=True,
                timeout=COMPILE_TIMEOUT,
            )
            log = (proc.stdout + proc.stderr).strip()
            pdf_path = work / "main.pdf"
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
    manuscript.save()
    return manuscript.compile_log
