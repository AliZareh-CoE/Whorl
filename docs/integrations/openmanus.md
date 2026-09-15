# Atlas as a tab inside OpenManus

[OpenManus](https://github.com/muhammed-aksoy/OpenManus) is a conversation-first agent runtime:
a React + Vite front end on port 3000 with a fixed left sidebar, a FastAPI back end on port 8000.
This guide puts the whole of Atlas into that sidebar as one more tab, without changing how either
app runs. Atlas keeps its own process, database and login; OpenManus shows it in a frame.

Two halves. The Atlas half is built in and tested. The OpenManus half is a patch of three
insertions against its `main` branch (read at the time of writing) — apply it in your own
checkout or fork; it has not been run from here.

## 1. The Atlas half

Atlas refuses to be framed by default (`X-Frame-Options: DENY`). Name the origins that may:

```
ATLAS_FRAME_ANCESTORS=http://localhost:3000
```

With that set, every Atlas page answers with `Content-Security-Policy: frame-ancestors 'self'
http://localhost:3000` instead of the `DENY` header — the OpenManus tab may show Atlas, any other
site still may not. Several origins are separated by spaces or commas; only whole origins count
(`scheme://host[:port]`, no path, no wildcard); anything else is dropped. The `Diagnostics` page
("Embeddable from"), `GET /api/v1/diagnostics/` (`frame_ancestors`) and the `get_diagnostics`
MCP tool all say what is in effect.

OpenManus already owns port 8000, so Atlas must run on another one — and it must be *pinned*,
because the desktop app steps aside to a random free port when 8000 is taken, which would break
the tab's address:

| How you run Atlas | Where to set it |
|---|---|
| Docker / `runserver` | in `.env`: `ATLAS_FRAME_ANCESTORS=http://localhost:3000`, then `manage.py runserver 127.0.0.1:8001` |
| `make standalone` / from source in desktop mode | `ATLAS_PORT=8001 ATLAS_FRAME_ANCESTORS=http://localhost:3000 make standalone` |
| the desktop app (installed) | user environment variables `ATLAS_PORT=8001` and `ATLAS_FRAME_ANCESTORS=http://localhost:3000` (Windows: *Edit environment variables for your account*; macOS/Linux: `launchctl setenv` / your session's environment — a GUI launch does not read your shell profile), then restart the app |

Use the **same hostname** in the OpenManus address bar and in the Atlas address the tab loads
(`localhost` on both sides, or `127.0.0.1` on both). Browsers treat `localhost:3000` and
`localhost:8001` as the same site, so the Atlas session cookie is sent inside the frame and you log
in once; `localhost` on one side and `127.0.0.1` on the other breaks that.

Beyond one machine — OpenManus served from another host — Atlas must be served over HTTPS with
`SESSION_COOKIE_SAMESITE=None` (browsers refuse cross-site cookies otherwise). Not covered here.

## 2. The OpenManus half

Three insertions in `frontend/` and one line in `docker-compose.yml`.

**a. A page** — `frontend/src/pages/AtlasPage.tsx` (new file):

```tsx
const ATLAS_URL = (import.meta.env.VITE_ATLAS_URL as string | undefined) ?? 'http://localhost:8001';

export default function AtlasPage() {
  return (
    <div className="flex h-full min-h-screen w-full flex-col">
      <iframe
        title="Atlas"
        src={ATLAS_URL}
        className="h-full min-h-screen w-full flex-1 border-0"
        allow="clipboard-read; clipboard-write; fullscreen"
        referrerPolicy="same-origin"
      />
    </div>
  );
}
```

No `sandbox` attribute: Atlas needs scripts, forms, its own origin (for the session cookie) and
downloads (backups, `.bib` exports, PDFs), and `sandbox` removes them.

**b. The route** — in `frontend/src/app.tsx`, import the page next to the other pages:

```tsx
import AtlasPage from '@/pages/AtlasPage';
```

and add one line inside the `<Routes>` block, before `</Routes>`:

```tsx
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/atlas" element={<AtlasPage />} />
          </Routes>
```

**c. The tab** — in the same file the sidebar header has a "Home" button; add "Atlas" right after
it (the `Button` component and `navigate` are already in scope; the icon is one more name in the
existing `lucide-react` import):

```tsx
            <Button
              size="sm"
              variant="outline"
              className="mt-2 w-full"
              onClick={() => navigate('/atlas')}
            >
              <BookOpen className="size-4" />
              Atlas
            </Button>
```

**d. The address** — in `docker-compose.yml`, under the `frontend` service:

```yaml
  frontend:
    build:
      context: ./frontend
    environment:
      - VITE_ATLAS_URL=http://localhost:8001
```

Then `docker compose up --build frontend` (the front-end image copies the source at build time,
and the Vite dev server it runs reads `VITE_*` from the environment). Open
`http://localhost:3000`, click **Atlas** in the sidebar: the Atlas login appears inside the tab,
and after that the dashboard.

## 3. If the tab stays blank

- Blank with a browser-console line about `frame-ancestors` or `X-Frame-Options`: Atlas is not
  allowing the origin. Check `Diagnostics › Embeddable from` in Atlas, and that the origin in
  `ATLAS_FRAME_ANCESTORS` is exactly the one in the OpenManus address bar (scheme, host, port).
- "Connection refused": Atlas is not on 8001 — `ATLAS_PORT` unset, or the desktop app started
  before the variable existed.
- Login loops or every click asks for the password again: hostname mismatch (`localhost` vs
  `127.0.0.1`) between the two addresses; the cookie is not reaching the frame.

## 4. The other directions

- **OpenManus as a tab inside Atlas.** The OpenManus dev server sends no framing header, so an
  Atlas page with an `<iframe src="http://localhost:3000">` renders it as is, including inside
  the desktop app's web view. Not built; ask for it if the tab should live on the Atlas side.
- **The agent, not the UI.** Everything in Atlas is on its REST API (`/api/docs/`) and in the
  bundled MCP server (`atlas-mcp`, see the README's *Claude integration* section). An agent
  runtime that can call an MCP server or an HTTP API can read the library, tick milestones and
  file captures without any embedding. Whether OpenManus can be pointed at an MCP server is a
  question for its documentation.
