"""One rule for archive member names (#453, backlog #133).

Every zip Atlas writes — the submission package, the Markdown vault, the backup — derives its
entry names from rows or paths that were validated on the way in. Defence in depth still wants
one place that says what may be written into an archive, so a row injected past validation or a
future export cannot emit a name that unzips outside its folder.
"""

from __future__ import annotations

import re

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_DRIVE = re.compile(r"^[A-Za-z]:")


def safe_archive_name(name: str) -> str | None:
    """A member name that is safe to write, or None when it must not be written.

    Backslashes become slashes, `./` segments and duplicate slashes collapse; absolute paths,
    drive letters, `..` segments, control characters and empty names are refused.
    """
    if not isinstance(name, str):
        return None
    text = name.replace("\\", "/")
    if _CONTROL.search(text) or _DRIVE.match(text) or text.startswith("/"):
        return None
    parts = [p for p in text.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)


def is_safe_archive_name(name: str) -> bool:
    return safe_archive_name(name) is not None
