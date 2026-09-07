"""UI audit sweep (DECISIONS #346): screenshot every SPA route and flag horizontal overflow,
sub-10 px text, empty bodies, console errors and unexpected redirects.

    uv run python scripts/ui_audit.py <out_dir> <dark|light> <viewport width> [desktop]

Needs a dev server on 127.0.0.1:8000 seeded with `seed_demo` (login atlas/atlas) and the
Playwright Chromium at CHROME (override with the CHROME env var).
"""

import asyncio
import os
import sys

from playwright.async_api import async_playwright

OUT, THEME, WIDTH = sys.argv[1], sys.argv[2], int(sys.argv[3])
# 4th arg "desktop": pretend to be the Tauri webview (window.__TAURI__ present, IPC refusing)
# so desktop-only code paths run — the 2026-09-07 blank-dashboard bug only showed up there.
DESKTOP = len(sys.argv) > 4 and sys.argv[4] == "desktop"
TAURI_STUB = (
    "window.__TAURI__ = { core: { invoke: () => Promise.reject(new Error('no ipc')) } };"
    "window.__TAURI_INTERNALS__ = { invoke: () => Promise.reject(new Error('no ipc')), transformCallback: () => 0 };"
)
P = "attention-and-memory"
PAGES = [
    "/",
    "/projects",
    "/projects/new",
    f"/projects/{P}",
    f"/projects/{P}/plan",
    f"/projects/{P}/timeline",
    f"/projects/{P}/documents",
    f"/projects/{P}/figures",
    f"/projects/{P}/files",
    f"/projects/{P}/literature",
    f"/projects/{P}/queue",
    f"/projects/{P}/read",
    f"/projects/{P}/notes",
    f"/projects/{P}/research",
    f"/projects/{P}/review",
    f"/projects/{P}/matrix",
    "/review",
    f"/projects/{P}/decisions",
    f"/projects/{P}/graph",
    "/automations",
    "/library",
    "/references/{ref}",
    "/writing",
    "/manuscripts/{ms}",
    "/manuscripts/{ms}/editor",
    "/achievements",
    "/connect",
    "/diagnostics",
    "/inbox",
    "/today",
    "/prompts",
    "/search?q=attention",
    "/pet",
]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(
            executable_path=os.environ.get(
                "CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
            ),
            args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"],
        )
        ctx = await b.new_context(viewport={"width": WIDTH, "height": 900})
        await ctx.add_init_script(f"try{{localStorage.setItem('theme','{THEME}')}}catch(e){{}}")
        if DESKTOP:
            await ctx.add_init_script(TAURI_STUB)
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)[:160]))
        page.on(
            "console",
            lambda m: (
                errors.append(m.text[:160])
                if m.type == "error" and "ERR_CONNECTION" not in m.text
                else None
            ),
        )
        await page.goto("http://127.0.0.1:8000/login/")
        await page.fill("input[name=username]", "atlas")
        await page.fill("input[name=password]", "atlas")
        await page.click("button[type=submit]")
        # real ids: the demo is re-seeded now and then, so ids drift
        ids = await page.evaluate(
            """async () => ({
              ref: (await (await fetch('/api/v1/references/?page_size=1&ordering=id')).json()).results[0]?.id ?? 1,
              ms: (await (await fetch('/api/v1/manuscripts/?page_size=1')).json()).results[0]?.id ?? 1,
            })"""
        )
        report = []
        for path in [p.format(**ids) for p in PAGES]:
            errors.clear()
            try:
                await page.goto("http://127.0.0.1:8000" + path, timeout=20000)
                await page.wait_for_timeout(1800)
            except Exception as e:
                report.append({"path": path, "error": str(e)[:100]})
                continue
            info = await page.evaluate("""() => {
              const de = document.documentElement; const vw = de.clientWidth;
              const over = [...document.querySelectorAll('body *')].filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && (r.right > vw + 2) && getComputedStyle(el).position !== 'fixed'; }).slice(0,4).map(el => el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').slice(0,3).join('.') : ''));
              const tiny = [...document.querySelectorAll('body *')].filter(el => { const cs = getComputedStyle(el); return el.childNodes.length && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(cs.fontSize) < 10; }).length;
              const empty = document.body.innerText.trim().length < 40;
              return {hscroll: de.scrollWidth > vw + 2, over, tiny, empty, title: document.title, h1: (document.querySelector('h1')||{}).innerText || ''};
            }""")
            name = path.strip("/").replace("/", "_").replace("?", "_") or "dashboard"
            await page.screenshot(path=f"{OUT}/{name}-{THEME}-{WIDTH}.png", full_page=False)
            report.append(
                {
                    "path": path,
                    "url": page.url.replace("http://127.0.0.1:8000", ""),
                    **info,
                    "errors": errors[:3],
                }
            )
        for r in report:
            flags = []
            if r.get("error"):
                flags.append("NAV-ERROR " + r["error"])
            if r.get("hscroll"):
                flags.append("HSCROLL " + ",".join(r.get("over", [])))
            if r.get("tiny", 0) > 8:
                flags.append(f"tiny-text x{r['tiny']}")
            if r.get("empty"):
                flags.append("EMPTY")
            if r.get("errors"):
                flags.append("JS " + " | ".join(r["errors"]))
            if r.get("url") and r["url"] != r["path"]:
                flags.append("REDIRECT→" + r["url"])
            print(f"{r['path']:45s} {' ; '.join(flags) or 'ok'}")
        await b.close()


asyncio.run(main())
