"""Demo GIF (DECISIONS #430): a scripted tour of the seeded demo, one keyframe per screen with
a caption, cross-faded into `docs/demo.gif` for the README.

    uv run --with pillow python scripts/demo_gif.py [out.gif]

Needs a dev server on 127.0.0.1:8000 seeded with `seed_demo` (login atlas/atlas) and the
Playwright Chromium at CHROME (override with the CHROME env var). Pillow is only needed by
this script, so it is pulled in ad hoc with `--with` rather than pinned in pyproject.
"""

import asyncio
import io
import os
import sys

from playwright.async_api import async_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else "docs/demo.gif"
BASE = "http://127.0.0.1:8000"
P = "attention-and-memory"
WIDTH, HEIGHT, GIF_WIDTH = 1280, 800, 960
HOLD_MS, FADE_MS = 2200, 80

# (path, caption, settle ms). `{ms}`/`{note}` are filled from the API so re-seeds don't matter.
SCENES = [
    ("/", "Every project at a glance — one calm dashboard.", 1500),
    (f"/projects/{P}", "A project overview: current phase, next milestones, deadlines.", 1500),
    (f"/projects/{P}/plan", "Plans, not backlogs — milestones roll up into phases.", 1500),
    ("/library", "A library that reads your PDFs: add by DOI, drop a folder, dedupe.", 2000),
    (f"/projects/{P}/read", "Read in the app; highlights become notes.", 2500),
    (
        f"/projects/{P}/notes/{{note}}",
        "Notes cite papers with @key and link with [[wiki-links]].",
        1800,
    ),
    (f"/projects/{P}/graph", "The knowledge graph — citations, notes and links in 3D.", 4500),
    ("/manuscripts/{ms}/editor", "A LaTeX studio that compiles and checks every \\cite{}.", 5000),
    (f"/projects/{P}/matrix", "Literature review matrix: papers × themes, gaps called out.", 1500),
    ("/connect", "Claude Code built in — 96 MCP tools over the same API the UI uses.", 1500),
]

CAPTION_JS = """(text) => {
  let el = document.getElementById('demo-caption');
  if (!el) { el = document.createElement('div'); el.id = 'demo-caption'; document.body.appendChild(el); }
  el.textContent = text;
  el.style.cssText = 'position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;' +
    'max-width:86%;padding:12px 20px;border-radius:14px;background:rgba(12,10,24,.92);color:#f5f3ff;' +
    'font:600 20px/1.3 system-ui,sans-serif;letter-spacing:.01em;box-shadow:0 10px 40px rgba(0,0,0,.5);' +
    'border:1px solid rgba(129,140,248,.45);pointer-events:none';
}"""


async def shoot():
    frames = []
    async with async_playwright() as p:
        b = await p.chromium.launch(
            executable_path=os.environ.get(
                "CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
            ),
            args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"],
        )
        ctx = await b.new_context(viewport={"width": WIDTH, "height": HEIGHT})
        await ctx.add_init_script("try{localStorage.setItem('theme','dark')}catch(e){}")
        # the achievement toast fires on the demo data at every visit — keep it out of the frames
        await ctx.add_init_script(
            "document.addEventListener('DOMContentLoaded', () => { const s = document.createElement('style');"
            " s.textContent = 'a[href=\"/achievements\"].fixed{display:none!important}'; document.head.appendChild(s); });"
        )
        page = await ctx.new_page()
        await page.goto(f"{BASE}/login/")
        await page.fill("input[name=username]", "atlas")
        await page.fill("input[name=password]", "atlas")
        await page.click("button[type=submit]")
        await page.wait_for_url(lambda u: not u.rstrip("/").endswith("/login"), timeout=60000)
        ids = await page.evaluate(
            """async () => ({
              ms: (await (await fetch('/api/v1/manuscripts/?page_size=1')).json()).results[0]?.id ?? 1,
              note: (await (await fetch('/api/v1/notes/?page_size=1&ordering=id')).json()).results[0]?.id ?? 1,
            })"""
        )
        compiled = await page.evaluate(
            """async (ms) => {
              const r = await fetch(`/api/v1/manuscripts/${ms}/compile/`, {method: 'POST', headers: {'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''}});
              if (!r.ok) return 'no engine (' + r.status + ')';
              for (let i = 0; i < 60; i++) {
                await new Promise((res) => setTimeout(res, 2000));
                const st = await (await fetch(`/api/v1/manuscripts/${ms}/compile-status/`)).json();
                if (st.status !== 'running') return st.status;
              }
              return 'timeout';
            }""",
            ids["ms"],
        )
        print("compile:", compiled, file=sys.stderr)
        for path, caption, settle in SCENES:
            await page.goto(BASE + path.format(**ids), timeout=30000)
            await page.wait_for_timeout(settle)
            await page.evaluate(CAPTION_JS, caption)
            await page.wait_for_timeout(150)
            frames.append(await page.screenshot(type="png"))
            print("shot", path, file=sys.stderr)
        # the palette: the last scene, typed live
        await page.goto(BASE + "/")
        await page.wait_for_timeout(1200)
        await page.keyboard.press("Control+k")
        await page.wait_for_timeout(500)
        await page.keyboard.type("add paper", delay=40)
        await page.wait_for_timeout(700)
        await page.evaluate(
            CAPTION_JS, "⌘K — ask Atlas anything: jump, capture, add a paper by DOI."
        )
        await page.wait_for_timeout(150)
        frames.append(await page.screenshot(type="png"))
        await b.close()
    return frames


def assemble(pngs: list[bytes]) -> None:
    from PIL import Image

    imgs = []
    for raw in pngs:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        imgs.append(im.resize((GIF_WIDTH, round(im.height * GIF_WIDTH / im.width)), Image.LANCZOS))
    out, durations = [], []

    def push(im, ms):
        out.append(
            im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        )
        durations.append(ms)

    for i, im in enumerate(imgs):
        push(im, HOLD_MS)
        push(Image.blend(im, imgs[(i + 1) % len(imgs)], 0.5), FADE_MS)  # a soft cut
    out[0].save(
        OUT,
        save_all=True,
        append_images=out[1:],
        duration=durations,
        loop=0,
        optimize=False,
        disposal=1,
    )
    print(f"wrote {OUT}: {len(out)} frames, {os.path.getsize(OUT) / 1e6:.1f} MB", file=sys.stderr)


def main() -> None:
    # DEMO_FRAMES=<dir> keeps the raw screenshots so encoding can be re-tuned without re-shooting
    cache = os.environ.get("DEMO_FRAMES")
    if cache and os.path.isdir(cache) and sorted(os.listdir(cache)):
        pngs = [open(os.path.join(cache, n), "rb").read() for n in sorted(os.listdir(cache))]
    else:
        pngs = asyncio.run(shoot())
        if cache:
            os.makedirs(cache, exist_ok=True)
            for i, raw in enumerate(pngs):
                with open(os.path.join(cache, f"{i:02d}.png"), "wb") as fh:
                    fh.write(raw)
    assemble(pngs)


if __name__ == "__main__":
    main()
