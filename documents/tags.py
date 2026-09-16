"""Tag management for the file explorer (backlog 354): rename, recolour, merge and delete a
project's file tags, and the AND filter shared by the documents list and the tree.

Merge goes through the M2M manager (never the through table or `.update()`): the
`m2m_changed` signal is what bumps `updated_at` / the data version, so every client's ETag
moves with it.
"""

from __future__ import annotations

import re

from django.db import transaction
from django.db.models import QuerySet

from .models import Tag

MAX_FILTER_TAGS = 10
NAME_MAX = 60
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class TagError(Exception):
    pass


def find_tag(project, name: str, *, exclude_pk: int | None = None) -> Tag | None:
    """The project's tag with this name, any case (the explorer treats `Key-Paper` and
    `key-paper` as one tag when it creates them)."""
    queryset = project.tags.filter(name__iexact=(name or "").strip())
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.first()


def clean_name(project, name: str, *, exclude_pk: int | None = None) -> str:
    wanted = " ".join((name or "").split())
    if not wanted:
        raise TagError("Name the tag.")
    if len(wanted) > NAME_MAX:
        raise TagError(f"A tag name has at most {NAME_MAX} characters.")
    existing = find_tag(project, wanted, exclude_pk=exclude_pk)
    if existing is not None:
        raise TagError(f"A tag named “{existing.name}” already exists.")
    return wanted


def clean_color(color: str) -> str:
    color = (color or "").strip()
    if color and not COLOR_RE.match(color):
        raise TagError("A colour is #rrggbb.")
    return color.lower()


def rename_tag(tag: Tag, name: str) -> Tag:
    tag.name = clean_name(tag.project, name, exclude_pk=tag.pk)
    tag.save(update_fields=["name", "updated_at"])
    return tag


def recolour_tag(tag: Tag, color: str) -> Tag:
    tag.color = clean_color(color)
    tag.save(update_fields=["color", "updated_at"])
    return tag


@transaction.atomic
def merge_tags(source: Tag, target: Tag) -> int:
    """Every file carrying `source` carries `target` instead; `source` is gone. Returns how
    many files moved (a file already carrying both counts — it loses one chip, keeps one)."""
    if source.pk == target.pk:
        raise TagError("Pick a different tag to merge into.")
    if source.project_id != target.project_id:
        raise TagError("Tags merge within one project.")
    documents = list(source.documents.all())
    if documents:
        target.documents.add(*documents)
    source.delete()
    return len(documents)


def delete_tag(tag: Tag) -> int:
    """Remove the tag from the project; returns how many files it was on (they keep their
    other tags)."""
    count = tag.documents.count()
    tag.delete()
    return count


def tag_names(values) -> list[str]:
    """Distinct, non-empty, capped tag names from repeated `?tag=` query parameters."""
    out: list[str] = []
    for raw in values or []:
        name = (raw or "").strip()[:NAME_MAX]
        if name and name not in out:
            out.append(name)
    return out[:MAX_FILTER_TAGS]


def filter_by_tags(queryset: QuerySet, names: list[str]) -> QuerySet:
    """Documents carrying every one of `names` (one join per tag = AND). `distinct` guards
    against two same-named legacy tags from different projects joining a row twice."""
    for name in names:
        queryset = queryset.filter(tags__name=name)
    return queryset.distinct() if names else queryset
