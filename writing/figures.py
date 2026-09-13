"""Figure audit (#473): will every figure print well?

For each ``\\includegraphics`` in the manuscript's .tex files: the asset it resolves to, its
format, pixel size (PNG / JPEG / GIF headers parsed directly — no image library), the width
it will print at (from the options: ``width=0.8\\textwidth``, ``\\columnwidth``,
``\\linewidth``, or an absolute length), the effective resolution in dots per inch, and the
file size. Vector formats (PDF, EPS, SVG) are resolution-independent and pass on sight.
Thresholds follow what journals ask for: 300 dpi for a raster figure, 150 as the floor
below which it will visibly pixelate; 10 MB is the usual per-file ceiling.
"""

from __future__ import annotations

import re
import struct

INCLUDEGRAPHICS = re.compile(r"\\includegraphics(?:\[([^\]]*)\])?\{([^}]+)\}")
IMAGE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg", ".tif", ".tiff", ".gif")
VECTOR = (".pdf", ".eps", ".svg")
TEXT_WIDTH_IN = 6.5  # article, 1in margins: what \textwidth / \linewidth resolve to
GOOD_DPI = 300
FLOOR_DPI = 150
MAX_BYTES = 10 * 1024 * 1024
LENGTH = re.compile(r"width\s*=\s*([0-9.]*)\s*\\?(textwidth|linewidth|columnwidth|in|cm|mm|pt)")


def printed_width_in(options: str | None) -> float | None:
    """The width an \\includegraphics will print at, in inches, or None when the options
    leave it to the image's own size (then the pixel size decides at 72 dpi)."""
    if not options:
        return None
    m = LENGTH.search(options.replace(" ", ""))
    if not m:
        return None
    factor = float(m.group(1)) if m.group(1) else 1.0
    unit = m.group(2)
    if unit in ("textwidth", "linewidth"):
        return round(factor * TEXT_WIDTH_IN, 2)
    if unit == "columnwidth":
        return round(factor * TEXT_WIDTH_IN / 2, 2)
    per_in = {"in": 1.0, "cm": 2.54, "mm": 25.4, "pt": 72.27}[unit]
    return round(factor / per_in, 2)


def image_size(head: bytes) -> tuple[str, int, int] | None:
    """(format, width, height) from the first bytes of a PNG, JPEG or GIF; None otherwise."""
    if head[:8] == b"\x89PNG\r\n\x1a\n" and len(head) >= 24:
        w, h = struct.unpack(">II", head[16:24])
        return "png", w, h
    if head[:6] in (b"GIF87a", b"GIF89a") and len(head) >= 10:
        w, h = struct.unpack("<HH", head[6:10])
        return "gif", w, h
    if head[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(head):
            if head[i] != 0xFF:
                i += 1
                continue
            marker = head[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = struct.unpack(">H", head[i + 2 : i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
                h, w = struct.unpack(">HH", head[i + 5 : i + 9])
                return "jpeg", w, h
            i += 2 + length
    return None


def _resolve(raw: str, assets: dict[str, object]):
    raw = raw.strip().lstrip("./")
    if raw in assets:
        return raw, assets[raw]
    for ext in IMAGE_EXTENSIONS:
        if raw + ext in assets:
            return raw + ext, assets[raw + ext]
    return raw, None


def audit_figures(manuscript) -> dict:
    assets = {f.path: f for f in manuscript.files.filter(kind="asset")}
    used: set[str] = set()
    rows: list[dict] = []
    for tex in manuscript.files.filter(kind="tex").order_by("path"):
        for m in INCLUDEGRAPHICS.finditer(tex.content):
            line = tex.content[: m.start()].count("\n") + 1
            path, asset = _resolve(m.group(2), assets)
            width_in = printed_width_in(m.group(1))
            row: dict = {
                "tex": tex.path,
                "line": line,
                "path": path,
                "width_in": width_in,
                "format": None,
                "pixels": None,
                "dpi": None,
                "bytes": None,
                "state": "ok",
                "detail": "",
            }
            if asset is None:
                row.update(state="fail", detail="No file in the tree matches this path.")
                rows.append(row)
                continue
            used.add(path)
            ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
            try:
                size = asset.asset.size if asset.asset else None
            except (OSError, ValueError):
                size = None
            row["bytes"] = size
            if ext in VECTOR:
                row["format"] = ext.lstrip(".")
                row["detail"] = "Vector — prints sharp at any size."
            else:
                head = b""
                try:
                    if asset.asset:
                        with asset.asset.open("rb") as fh:
                            head = fh.read(65536)
                except (OSError, ValueError):
                    head = b""
                info = image_size(head)
                if info is None:
                    row.update(
                        format=ext.lstrip(".") or None,
                        state="warn",
                        detail="Could not read the image size — is this a real image file?",
                    )
                else:
                    fmt, w, h = info
                    row["format"] = fmt
                    row["pixels"] = [w, h]
                    inches = width_in if width_in else w / 72.0
                    dpi = int(round(w / inches)) if inches else None
                    row["dpi"] = dpi
                    if width_in is None:
                        row["width_in"] = round(w / 72.0, 2)
                    if dpi is not None and dpi < FLOOR_DPI:
                        row.update(
                            state="fail",
                            detail=f"{w}×{h} px printed {row['width_in']} in wide is {dpi} dpi — it will pixelate. Export at ≥ {GOOD_DPI} dpi (≈ {int(row['width_in'] * GOOD_DPI)} px wide).",
                        )
                    elif dpi is not None and dpi < GOOD_DPI:
                        row.update(
                            state="warn",
                            detail=f"{w}×{h} px at {row['width_in']} in is {dpi} dpi — journals ask for {GOOD_DPI} (≈ {int(row['width_in'] * GOOD_DPI)} px wide).",
                        )
                    else:
                        row["detail"] = f"{w}×{h} px at {row['width_in']} in — {dpi} dpi."
            if size is not None and size > MAX_BYTES:
                row["state"] = "fail" if row["state"] == "fail" else "warn"
                row["detail"] = (
                    f"{size / 1024 / 1024:.1f} MB — most venues cap a figure at 10 MB. "
                    + row["detail"]
                )
            rows.append(row)
    unused = sorted(
        p
        for p in assets
        if p not in used
        and ("." + p.rsplit(".", 1)[-1].lower() if "." in p else "") in IMAGE_EXTENSIONS
    )
    fails = sum(1 for r in rows if r["state"] == "fail")
    warns = sum(1 for r in rows if r["state"] == "warn")
    if not rows:
        summary = "No figures in the sources."
    elif fails:
        summary = (
            f"{fails} of {len(rows)} figure{'s' if len(rows) != 1 else ''} will not print well."
        )
    elif warns:
        summary = (
            f"{len(rows)} figure{'s' if len(rows) != 1 else ''}, {warns} below {GOOD_DPI} dpi."
        )
    elif len(rows) == 1:
        summary = "The figure prints sharp."
    else:
        summary = f"All {len(rows)} figures print sharp."
    return {
        "manuscript": manuscript.id,
        "count": len(rows),
        "fails": fails,
        "warns": warns,
        "summary": summary,
        "text_width_in": TEXT_WIDTH_IN,
        "figures": rows,
        "unused": unused,
    }
