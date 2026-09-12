"""Conditional file responses (#434, backlog #54 + #251): every uploaded file Atlas serves —
document downloads, inline previews, the workspace raw view — carries `Last-Modified` and an
`ETag`, answers `If-None-Match` / `If-Modified-Since` with 304, and shares one cache policy.
Uploaded files are immutable (edits create new files), so a day of private caching plus a
free revalidation afterwards is the right shape: the PDF reader and the studio never
re-download a file they already hold.
"""

from __future__ import annotations

from django.http import FileResponse, HttpResponseNotModified
from django.utils.http import http_date
from django.views.static import was_modified_since

CACHE_CONTROL = "private, max-age=86400"


def _validators(field_file) -> tuple[float | None, int | None]:
    storage, name = field_file.storage, field_file.name
    try:
        mtime = storage.get_modified_time(name).timestamp()
    except (NotImplementedError, OSError, ValueError):
        mtime = None
    try:
        size = storage.size(name)
    except (NotImplementedError, OSError):
        size = None
    return mtime, size


def etag_for(field_file) -> str | None:
    mtime, size = _validators(field_file)
    if mtime is None or size is None:
        return None
    return f'"{int(mtime)}-{size}"'


def file_response(
    request,
    field_file,
    *,
    handle=None,
    as_attachment: bool = False,
    content_type: str | None = None,
    inline: bool = False,
):
    """A FileResponse for ``field_file`` (or the already-opened ``handle``) with validators —
    or a 304 when the request's `If-None-Match` / `If-Modified-Since` still hold."""
    mtime, size = _validators(field_file)
    etag = f'"{int(mtime)}-{size}"' if mtime is not None and size is not None else None
    if_none_match = request.headers.get("If-None-Match")
    if_modified_since = request.headers.get("If-Modified-Since")
    fresh = False
    if etag and if_none_match:
        fresh = etag in [t.strip() for t in if_none_match.split(",")] or if_none_match == "*"
    elif mtime is not None and if_modified_since:
        fresh = not was_modified_since(if_modified_since, mtime)
    if fresh:
        if handle is not None:
            handle.close()
        response = HttpResponseNotModified()
    else:
        response = FileResponse(
            handle if handle is not None else field_file.open("rb"),
            as_attachment=as_attachment,
            content_type=content_type,
        )
        if inline:
            response["Content-Disposition"] = "inline"
        response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = CACHE_CONTROL
    if etag:
        response["ETag"] = etag
    if mtime is not None:
        response["Last-Modified"] = http_date(mtime)
    return response
