"""Editor smoke test (Backlog #141): a trimmed 6-check Playwright battery for CI.

Drives the real LaTeX editor page headless — the distilled core of the 26-check
cutover battery from cycle 126 — so editor regressions surface on PRs, not audits.

Checks: mount without page errors (and zero CDN editor requests), autosave,
multi-file create/switch/preserve, line comment -> gutter dot, cite autocomplete,
and the compile wiring (a real compile if bin/tectonic exists, else the graceful
missing-binary failure).

Env: ATLAS_BASE (default http://127.0.0.1:8000), SMOKE_USER/SMOKE_PASS (the login),
ATLAS_API_KEY (to find/seed the manuscript). Exit code 0 = all pass.
"""

import json
import os
import sys
import time
import urllib.request

BASE = os.environ.get("ATLAS_BASE", "http://127.0.0.1:8000")
USER = os.environ.get("SMOKE_USER", "owner")
PASSWORD = os.environ.get("SMOKE_PASS", "atlas-owner-pass")
API_KEY = os.environ.get("ATLAS_API_KEY", "change-me-api-key")

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("  ✓" if cond else "  ✗ FAIL"), name, flush=True)
    if not cond:
        FAILURES.append(name)


def api(path: str, payload: dict | None = None) -> dict | list:
    req = urllib.request.Request(
        f"{BASE}/api/v1{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def find_or_seed_manuscript() -> tuple[str, int]:
    """Return (project_slug, manuscript_id), creating both if the DB is empty (CI)."""
    listing = api("/manuscripts/")
    rows = listing["results"] if isinstance(listing, dict) else listing
    if rows:
        m = rows[0]
        detail = api(f"/manuscripts/{m['id']}/")
        return detail["project"], m["id"]
    projects = api("/projects/")
    prows = projects["results"] if isinstance(projects, dict) else projects
    if prows:
        slug = prows[0]["slug"]
    else:
        slug = api("/projects/", {"name": "Smoke", "slug": "smoke"})["slug"]
    m = api(
        "/manuscripts/",
        {
            "project": slug,
            "title": "CI smoke manuscript",
            "status": "drafting",
            "latex_source": "\\documentclass{article}\n\\begin{document}\nSmoke.\n\\end{document}\n",
        },
    )
    return slug, m["id"]


def main() -> int:
    from playwright.sync_api import sync_playwright

    slug, mid = find_or_seed_manuscript()
    editor_url = f"{BASE}/projects/{slug}/writing/{mid}/editor/"
    print(f"editor smoke → {editor_url}", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--ignore-certificate-errors"])
        page = browser.new_page(viewport={"width": 1500, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(f"{BASE}/login/")
        page.fill("input[name=username]", USER)
        page.fill("input[name=password]", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        page.goto(editor_url)
        page.wait_for_selector(".cm-editor", timeout=15000)
        page.wait_for_timeout(1200)

        # 1. mount: CM6 up, no page errors, no CDN editor assets
        cdn = page.evaluate(
            "performance.getEntriesByType('resource')"
            ".filter(r => r.name.includes('cdnjs') && r.name.includes('codemirror')).length"
        )
        check("editor mounts (no errors, no CDN editor assets)", not errors and cdn == 0)

        # 2. autosave: type -> Saved
        page.click(".cm-content")
        page.keyboard.press("Control+End")
        page.keyboard.type(" smoke", delay=15)
        try:
            page.wait_for_selector("text=/Saved \\d/", timeout=10000)
            check("autosave", True)
        except Exception:
            check("autosave", False)

        # 3. multi-file: create, type, switch back, content preserved
        stamp = str(int(time.time()))
        page.click("#new-file-btn")
        page.fill("#new-file-path", f"sections/smoke{stamp}.tex")
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        page.click(".cm-content")
        page.keyboard.type("smoke section", delay=10)
        page.wait_for_timeout(2400)
        page.click("#file-tree li:has-text('main.tex')")
        page.wait_for_timeout(500)
        main_ok = "smoke section" not in page.evaluate("editor.getValue()")
        page.click(f"#file-tree li:has-text('smoke{stamp}')")
        page.wait_for_timeout(500)
        sect_ok = "smoke section" in page.evaluate("editor.getValue()")
        check("multi-file switch preserves buffers", main_ok and sect_ok)
        page.click("#file-tree li:has-text('main.tex')")
        page.wait_for_timeout(400)

        # 4. line comment -> thread posts and the gutter dot renders
        page.evaluate(
            "() => { for (const el of document.querySelectorAll('.cm-lineNumbers .cm-gutterElement'))"
            " { if (el.textContent.trim() === '2') { el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true})); break; } } }"
        )
        try:
            page.wait_for_selector("#comment-modal:not(.hidden)", timeout=5000)
            page.fill("#comment-input", f"smoke {stamp}")
            page.click("#comment-post")
            page.wait_for_timeout(900)
            posted = f"smoke {stamp}" in page.inner_text("#comment-thread")
            page.click("#comment-modal-close")
            page.wait_for_timeout(300)
            dot = page.locator(".cm-comment-gutter >> text=💬").count() >= 1
            check("line comment + gutter dot", posted and dot)
        except Exception:
            check("line comment + gutter dot", False)

        # 5. cite autocomplete offers something for \cite{
        page.click(".cm-content")
        page.keyboard.press("Control+End")
        page.keyboard.type("\\cite{", delay=30)
        page.wait_for_timeout(800)
        has_ac = page.locator(".cm-tooltip-autocomplete li").count() >= 1
        page.keyboard.press("Escape")
        check("cite autocomplete", has_ac)

        # 6. compile wiring: Recompile -> compiled OR a surfaced failure (no tectonic in CI)
        page.click("#compile-btn")
        try:
            page.wait_for_selector("text=/✓ compiled|compile failed/", timeout=90000)
            check("compile wiring (result surfaced)", True)
        except Exception:
            check("compile wiring (result surfaced)", False)

        browser.close()

    print(("ALL PASS" if not FAILURES else f"FAILED: {FAILURES}"), flush=True)
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
