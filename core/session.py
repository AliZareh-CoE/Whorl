"""Session-remembered UI choices (Backlog #191).

A few list pages let you pick a sort/order and remember it across visits (the library
sort #176, the per-project literature order #190). They all want the same little dance:
read the choice from the querystring if present (and remember it), otherwise restore the
last-used value from the session — always validated against an allow-list so a missing,
stale, or tampered value can never reach the ORM (defense-in-depth for AUDIT #192).
"""


def remembered_choice(request, param, session_key, allowed, default):
    """Return a validated UI choice, persisting an explicit one and restoring it later.

    - If ``request.GET[param]`` is present, it becomes the choice and is stored in the
      session under ``session_key`` (only when valid — we never persist junk, #192).
    - Otherwise the choice is restored from the session, falling back to ``default``.
    - The returned value is always a member of ``allowed`` (else ``default``).
    """
    raw = request.GET.get(param)
    if raw is None:
        raw = request.session.get(session_key, default)
    elif raw in allowed:
        request.session[session_key] = raw
    return raw if raw in allowed else default
