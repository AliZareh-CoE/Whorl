from huey.contrib.djhuey import db_task


@db_task()
def compile_manuscript_task(manuscript_id: int, generation: int | None = None):
    from .compile import compile_manuscript
    from .models import Manuscript

    return compile_manuscript(Manuscript.objects.get(pk=manuscript_id), generation=generation)
