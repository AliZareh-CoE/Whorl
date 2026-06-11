#!/usr/bin/env bash
# Security probe sweep for the every-10-cycles audit (Backlog #79/#101).
# Runs the curl checks the audits had been doing by hand. Requires the dev server
# on :8000 and ATLAS_API_KEY in .env. Read-only — makes no changes.
set -uo pipefail

BASE="${ATLAS_BASE:-http://127.0.0.1:8000}"
KEY="$(grep -E '^ATLAS_API_KEY=' .env | cut -d= -f2)"
fail=0
pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=1; }

code() { curl -s -o /dev/null -w '%{http_code}' "$BASE$1"; }
code_key() { curl -s -o /dev/null -w '%{http_code}' -H "X-API-Key: $KEY" "$BASE$1"; }

echo "== Anonymous access (API must 401, pages 302 to login) =="
for p in /api/v1/projects/ /api/v1/weekly-review/ /api/v1/comments/reference/1/ /api/v1/bots/ /api/v1/pet/; do
  c=$(code "$p"); [ "$c" = 401 ] && pass "$p → 401" || bad "$p → $c (want 401)"
done
for p in / /library /projects/x/plan /classic/; do
  c=$(code "$p"); [ "$c" = 302 ] && pass "$p → 302" || bad "$p → $c (want 302)"
done

echo "== API key auth works =="
c=$(code_key /api/v1/projects/); [ "$c" = 200 ] && pass "keyed GET → 200" || bad "keyed GET → $c"

echo "== Route catch-all (#77) =="
c=$(code_key /api/v1/nonsense); [ "$c" = 404 ] && pass "/api/v1/nonsense → 404" || bad "/api/v1/nonsense → $c (want 404)"
ct=$(curl -s -o /dev/null -w '%{content_type}' "$BASE/static/js/spa.js")
[[ "$ct" == text/javascript* ]] && pass "static MIME ok" || bad "static MIME = $ct"

echo "== Open-redirect (/app/* must never leave our origin) =="
# Anonymous → redirects to /login/ (on-origin); authenticated → /evil.com/x (on-origin).
# Either is safe; the only failure is a redirect that leaves $BASE (off-site or //protocol-relative).
loc=$(curl -s -o /dev/null -w '%{redirect_url}' "$BASE/app//evil.com/x")
if [[ "$loc" == "$BASE"/* ]] && [[ "$loc" != //* ]]; then
  pass "/app//evil.com → on-origin ($loc)"
else
  bad "/app//evil.com → LEFT ORIGIN: $loc"
fi

echo "== Dependencies =="
if command -v uvx >/dev/null 2>&1; then
  uv pip freeze > /tmp/atlas-audit-req.txt 2>/dev/null
  if uvx pip-audit -r /tmp/atlas-audit-req.txt --no-deps --progress-spinner off 2>&1 | grep -q "No known vulnerabilities"; then
    pass "pip-audit: no known vulnerabilities"
  else bad "pip-audit found something — run it directly"; fi
else echo "  (uvx not available — skip pip-audit)"; fi
if [ -d frontend/node_modules ]; then
  (cd frontend && npm audit 2>&1 | grep -q "found 0 vulnerabilities") && pass "npm audit: 0 vulnerabilities" || bad "npm audit found something"
else echo "  (frontend deps not installed — skip npm audit)"; fi

echo
[ "$fail" = 0 ] && echo -e "\033[32mAudit sweep clean.\033[0m" || echo -e "\033[31mAudit sweep found issues — investigate above.\033[0m"
exit "$fail"
