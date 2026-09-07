"""Render the Atlas app icon (owner, 2026-09-07: "the app doesn't have a proper desktop icon").

Pure Python, no image libraries: a 1024×1024 RGBA PNG drawn from signed-distance fields —
the Observatory look. A deep navy rounded square, an aurora glow, a tilted orbit ring and a
bright star: "where is what, and how is it going" as a picture. Feed the result to
`tauri icon` to regenerate every platform size:

    uv run python scripts/make_icon.py desktop/icons/source.png
    npx tauri icon desktop/icons/source.png -o desktop/icons
"""

import math
import struct
import sys
import zlib

SIZE = 1024


def smooth(edge0: float, edge1: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def rounded_rect(x, y, half, radius):
    qx, qy = abs(x) - half + radius, abs(y) - half + radius
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    return outside + min(max(qx, qy), 0.0) - radius


def render():
    px = 1.0 / SIZE
    rows = []
    # palette
    navy_top = (13, 16, 38)
    navy_bottom = (24, 28, 64)
    indigo = (124, 108, 255)
    violet = (168, 85, 247)
    teal = (56, 189, 248)
    white = (255, 255, 255)
    # orbit geometry (unit coordinates, centre 0)
    tilt = math.radians(-28)
    ct, st = math.cos(tilt), math.sin(tilt)
    ring_rx, ring_ry = 0.36, 0.145
    star = (0.235, -0.225)  # sits on the upper-right of the ring
    for j in range(SIZE):
        row = bytearray()
        y = (j + 0.5) / SIZE - 0.5
        for i in range(SIZE):
            x = (i + 0.5) / SIZE - 0.5
            d = rounded_rect(x, y, 0.47, 0.115)
            alpha = 1.0 - smooth(-px, px, d)
            if alpha <= 0.0:
                row += b"\x00\x00\x00\x00"
                continue
            # background: vertical gradient + aurora glows
            t = y + 0.5
            col = lerp(navy_top, navy_bottom, t)
            g1 = math.exp(-((x + 0.22) ** 2 + (y + 0.28) ** 2) / 0.05)
            g2 = math.exp(-((x - 0.3) ** 2 + (y - 0.32) ** 2) / 0.06)
            col = lerp(col, violet, 0.32 * g1)
            col = lerp(col, teal, 0.22 * g2)
            # star grain: a few fixed small stars
            for sx, sy, r in (
                (-0.33, 0.3, 0.007),
                (0.37, -0.36, 0.006),
                (-0.12, -0.4, 0.005),
                (0.02, 0.4, 0.005),
                (0.41, 0.05, 0.004),
            ):
                dd = math.hypot(x - sx, y - sy)
                col = lerp(col, white, 0.8 * (1.0 - smooth(0.0, r, dd)))
            # orbit ring: rotate into the ellipse frame
            rx = ct * x + st * y
            ry = -st * x + ct * y
            e = math.hypot(rx / ring_rx, ry / ring_ry)
            ring_d = abs(e - 1.0) * min(ring_rx, ring_ry)
            ring = 1.0 - smooth(0.006, 0.012, ring_d)
            # the ring fades where it passes "behind" the star's glow and brightens near it
            ring_col = lerp(indigo, white, 0.35)
            col = lerp(col, ring_col, 0.9 * ring)
            # star: glow + 4-point sparkle + core
            dxs, dys = x - star[0], y - star[1]
            glow = math.exp(-(dxs * dxs + dys * dys) / 0.006)
            col = lerp(col, indigo, 0.75 * glow)
            spark = (abs(dxs) ** 0.5 + abs(dys) ** 0.5) ** 2  # astroid-like
            spark_mask = 1.0 - smooth(0.05, 0.065, spark)
            core = 1.0 - smooth(0.028, 0.036, math.hypot(dxs, dys))
            col = lerp(col, white, max(0.95 * spark_mask, core))
            r, g, b = (max(0, min(255, int(round(c)))) for c in col)
            row += bytes((r, g, b, int(round(alpha * 255))))
        rows.append(bytes(row))
    return rows


def write_png(path: str, rows) -> None:
    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (
            struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "desktop/icons/source.png"
    write_png(out, render())
    print(f"wrote {out} ({SIZE}×{SIZE})")
