"""Audit #34 (backlog 356): a deleted document or version takes its storage file with it.
Django never removes a FileField's bytes on delete; every delete path — single, bulk, a
folder, a project — cascades through these rows, so one post_delete hook covers them all.
The unlink waits for the transaction to commit (a rolled-back delete keeps its bytes)."""

from django.db import transaction
from django.db.models.signals import post_delete


def _drop_file(sender, instance, **kwargs):
    name = instance.file.name if instance.file else ""
    if not name:
        return
    storage = instance.file.storage

    def unlink():
        try:
            storage.delete(name)
        except OSError:
            pass  # the bytes may already be gone (a restore, an earlier sweep)

    transaction.on_commit(unlink)


def connect():
    from .models import Document, DocumentVersion

    post_delete.connect(_drop_file, sender=Document, dispatch_uid="documents.drop_file")
    post_delete.connect(
        _drop_file, sender=DocumentVersion, dispatch_uid="documents.drop_version_file"
    )
