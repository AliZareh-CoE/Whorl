"""Boot check (#390): does the app actually draw? Used by CI against the frozen server on
every platform we build, and usable locally against any running Atlas.

    uv run --with playwright python scripts/boot_check.py http://127.0.0.1:8765 [out_dir]

Logs in (ATLAS_ADMIN_USER / ATLAS_ADMIN_PASSWORD, default atlas/atlas), pretends to be the
Tauri web view (window.__TAURI__ stub, so desktop-only code paths run), loads the dashboard,
projects and diagnostics pages, and fails on: an empty #root, a missing sidebar, a page
error, a console error, the boot-failure panel, or any HTTP 4xx/5xx the page triggered.
Screenshots land in out_dir (default: the working directory) so a failure can be looked at.
"""

import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else ".")
USER = os.environ.get("ATLAS_ADMIN_USER", "atlas")
PASSWORD = os.environ.get("ATLAS_ADMIN_PASSWORD", "atlas")
PAGES = ["/", "/projects", "/library", "/diagnostics"]
STUB = (
    "window.__TAURI__ = { core: { invoke: () => Promise.reject(new Error('no ipc')) } };"
    "window.__TAURI_INTERNALS__ = { invoke: () => Promise.reject(new Error('no ipc')), "
    "transformCallback: () => 0 };"
)


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    async with async_playwright() as p:
        launch = {}
        if os.environ.get("CHROME"):
            launch["executable_path"] = os.environ["CHROME"]
        browser = await p.chromium.launch(**launch)
        ctx = await browser.new_context(viewport={"width": 1400, "height": 900})
        await ctx.add_init_script(STUB)
        page = await ctx.new_page()
        problems: list[str] = []
        page.on("pageerror", lambda e: problems.append(f"page error: {str(e)[:300]}"))
        page.on(
            "console",
            lambda m: (
                problems.append(f"console error: {m.text[:300]}") if m.type == "error" else None
            ),
        )
        page.on(
            "response",
            lambda r: (
                problems.append(f"HTTP {r.status} {r.url}")
                if r.status >= 400 and "/api/v1/client-errors/" not in r.url
                else None
            ),
        )
        await page.goto(f"{BASE}/login/", timeout=60000)
        await page.fill("input[name=username]", USER)
        await page.fill("input[name=password]", PASSWORD)
        await page.click("button[type=submit]")
        await page.wait_for_timeout(500)
        for path in PAGES:
            problems.clear()
            name = (path.strip("/") or "dashboard").replace("/", "_")
            try:
                await page.goto(BASE + path, timeout=60000)
                await page.wait_for_timeout(2500)
                info = await page.evaluate(
                    "() => ({kids: document.getElementById('root')?.children.length ?? -1,"
                    " sidebar: !!document.querySelector('aside'),"
                    " panel: !!document.querySelector('[data-testid=boot-failure]'),"
                    " crashed: !!document.querySelector('[data-testid=render-failure]'),"
                    " text: document.body.innerText.trim().slice(0, 60)})"
                )
            except Exception as exc:  # noqa: BLE001 - reported below
                info = {"kids": -1, "sidebar": False, "panel": False, "crashed": False, "text": ""}
                problems.append(f"navigation: {str(exc)[:200]}")
            await page.screenshot(path=str(OUT / f"boot-check-{name}.png"))
            bad = []
            if info["kids"] <= 0:
                bad.append("nothing mounted in #root")
            if not info["sidebar"]:
                bad.append("no sidebar")
            if info["panel"]:
                bad.append("boot-failure panel shown")
            if info["crashed"]:
                bad.append("render-failure panel shown")
            bad += problems
            status = "ok" if not bad else "FAIL"
            print(
                f"{path:14s} {status}  {info['text']!r}"
                + ("" if not bad else "\n    " + "\n    ".join(bad))
            )
            if bad:
                failures.append(path)
        await browser.close()
    if failures:
        print(f"boot check FAILED on {', '.join(failures)} — screenshots in {OUT.resolve()}")
        return 1
    print("boot check passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
