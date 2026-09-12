import logging
import threading

from django.conf import settings
from huey.contrib.djhuey import db_task

log = logging.getLogger(__name__)


@db_task()
def compile_manuscript_task(manuscript_id: int, generation: int | None = None):
    from .compile import compile_manuscript
    from .models import Manuscript

    return compile_manuscript(Manuscript.objects.get(pk=manuscript_id), generation=generation)


def _compile_in_thread(manuscript_id: int, generation: int | None) -> None:
    from django.db import connection

    try:
        task = compile_manuscript_task
        # tests may monkeypatch the task with a plain function
        getattr(task, "call_local", task)(manuscript_id, generation)
    except Exception:  # pragma: no cover - logged, the status row records the failure
        log.exception("background compile failed for manuscript %s", manuscript_id)
    finally:
        connection.close()


def enqueue_compile(manuscript_id: int, generation: int | None = None) -> str:
    """Start a compile without blocking the request.

    With a huey worker (server installs) the task is queued as usual. In *immediate* mode
    (the desktop and Redis-less dev) huey would run the task inline inside the HTTP request —
    a first Tectonic run downloads its bundle for minutes, so the request that clicked
    "Compile" would hang and, on the desktop, the webview with it. The compile runs on a
    daemon thread instead; the studio polls compile-status either way.
    Returns "thread" or "queue" for tests and diagnostics.
    """
    if settings.HUEY.get("immediate"):
        threading.Thread(
            target=_compile_in_thread,
            args=(manuscript_id, generation),
            name=f"compile-{manuscript_id}",
            daemon=True,
        ).start()
        return "thread"
    compile_manuscript_task(manuscript_id, generation)
    return "queue"
