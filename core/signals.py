"""Keep ETags honest (#384): any write to an Atlas model moves the data version, and an M2M
change stamps `updated_at` on the rows involved (Django's M2M writes never touch it)."""

from __future__ import annotations

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.utils import timezone

from .versioning import bump_data_version

ATLAS_APPS = frozenset(
    {
        "core",
        "projects",
        "plans",
        "documents",
        "literature",
        "notes",
        "writing",
        "research",
        "prompts",
        "bots",
    }
)


def _is_atlas_model(sender) -> bool:
    meta = getattr(sender, "_meta", None)
    return bool(meta) and meta.app_label in ATLAS_APPS


def _touch(model, pks) -> None:
    if pks and any(f.name == "updated_at" for f in model._meta.fields):
        model.objects.filter(pk__in=list(pks)).update(updated_at=timezone.now())  # etag: ok


def on_write(sender, **kwargs):
    if _is_atlas_model(sender):
        bump_data_version()


def on_m2m(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if not (_is_atlas_model(type(instance)) or _is_atlas_model(model)):
        return
    _touch(type(instance), [instance.pk])
    if pk_set:
        _touch(model, pk_set)
    bump_data_version()


def connect() -> None:
    post_save.connect(on_write, dispatch_uid="atlas-version-save")
    post_delete.connect(on_write, dispatch_uid="atlas-version-delete")
    m2m_changed.connect(on_m2m, dispatch_uid="atlas-version-m2m")
