"""SyncTeX for the studio (2026-09-07, #378): the map between a PDF position and a source line.

Tectonic writes ``<main>.synctex.gz`` when compiled with ``--synctex``. The format is a text
file: ``Input:<n>:<path>`` lines name the source files, then per page (``{n`` … ``}n``) a
stream of records — boxes ``(``/``[`` and points ``h``/``v``/``x``/``k``/``g``/``$`` — each
tagged ``<input>,<line>:<x>,<y>[:<w>,<h>,<d>]`` in scaled points (1/65536 pt), y measured
from the top of the page. We fold that into one rectangle per (page, file, line), which is
all the studio needs: double-click in the PDF → nearest line; cursor line → page and height.
"""

from __future__ import annotations

import gzip
import re
from pathlib import Path

SP = 65536.0
RECORD = re.compile(r"^([(\[hvxkg$])(\d+),(\d+):(-?\d+),(-?\d+)(?::(-?\d+),(-?\d+),(-?\d+))?")


def parse_synctex(text: str, workdir: str | Path) -> dict:
    """{"files": [rel paths], "pages": {"1": [[file_index, line, x, y, w, h], …]}} in PDF points."""
    workdir = Path(workdir).resolve()
    inputs: dict[str, int] = {}
    files: list[str] = []
    unit = 1.0
    x_off = y_off = 0.0
    rects: dict[tuple[int, int, int], list[float]] = {}
    page = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Input:"):
            _, num, path = line.split(":", 2)
            if not path:
                continue
            try:
                rel = Path(path).resolve().relative_to(workdir).as_posix()
            except ValueError:
                rel = Path(path).name
            if rel not in files:
                files.append(rel)
            inputs[num] = files.index(rel)
            continue
        if line.startswith("Unit:"):
            unit = float(line[5:] or 1)
            continue
        if line.startswith("X Offset:"):
            x_off = float(line[9:] or 0)
            continue
        if line.startswith("Y Offset:"):
            y_off = float(line[9:] or 0)
            continue
        if line[0] == "{":
            page = int(line[1:] or 0)
            continue
        if line[0] == "}":
            page = 0
            continue
        if not page:
            continue
        m = RECORD.match(line)
        if not m:
            continue
        kind, inp, ln, x, y, w, h, d = m.groups()
        if inp not in inputs or int(ln) <= 0:
            continue
        fi = inputs[inp]
        px = (float(x) + x_off) * unit / SP
        py = (float(y) + y_off) * unit / SP
        if w is not None:
            pw = float(w) * unit / SP
            ph = (float(h) + float(d)) * unit / SP
            top = py - float(h) * unit / SP
            if ph > 300:
                # the page's own vbox is tagged with whatever line was current at shipout —
                # it would claim the whole page for that one line
                continue
        else:
            pw, ph, top = 2.0, 10.0, py - 8.0  # a point record: a small box around it
        key = (page, fi, int(ln))
        rect = rects.get(key)
        if rect is None:
            rects[key] = [px, top, px + pw, top + ph]
        else:
            rect[0] = min(rect[0], px)
            rect[1] = min(rect[1], top)
            rect[2] = max(rect[2], px + pw)
            rect[3] = max(rect[3], top + ph)
    pages: dict[str, list] = {}
    for (pg, fi, ln), (x0, y0, x1, y1) in sorted(rects.items()):
        pages.setdefault(str(pg), []).append(
            [fi, ln, round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)]
        )
    return {"files": files, "pages": pages}


def read_synctex(path: str | Path, workdir: str | Path) -> dict:
    path = Path(path)
    data = path.read_bytes()
    if path.suffix == ".gz" or data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return parse_synctex(data.decode("utf-8", errors="replace"), workdir)


def forward(mapping: dict, file: str, line: int) -> dict | None:
    """Source (file, line) → the PDF spot: the same line, else the nearest one after it."""
    if not mapping or file not in mapping.get("files", []):
        return None
    fi = mapping["files"].index(file)
    best = None
    for page, rows in mapping.get("pages", {}).items():
        for f, ln, x, y, w, h in rows:
            if f != fi or ln < line:
                continue
            # a \section line also leaves a tiny mark in the running header of another page;
            # the real heading is the wider box, so prefer width before page order
            in_header = y < 60  # the running-header band at the top of a page
            cand = (ln - line, in_header, -w, int(page), y)
            if best is None or cand < best[0]:
                best = (cand, {"page": int(page), "x": x, "y": y, "w": w, "h": h, "line": ln})
    return best[1] if best else None


def inverse(mapping: dict, page: int, x: float, y: float) -> dict | None:
    """PDF (page, x, y in points from the top-left) → the closest source line."""
    rows = mapping.get("pages", {}).get(str(page)) if mapping else None
    if not rows:
        return None
    best = None
    for f, ln, rx, ry, rw, rh in rows:
        inside = rx <= x <= rx + rw and ry <= y <= ry + rh
        dy = 0.0 if ry <= y <= ry + rh else min(abs(y - ry), abs(y - (ry + rh)))
        dx = 0.0 if rx <= x <= rx + rw else min(abs(x - rx), abs(x - (rx + rw)))
        # inside a box: the smallest one wins (page and paragraph boxes contain everything)
        score = (0, rw * rh) if inside else (1, dy * 3 + dx)
        if best is None or score < best[0]:
            best = (score, {"file": mapping["files"][f], "line": ln})
    return best[1] if best else None
