"""Ids from the wire (Audit #31).

Postgres binds a Python int past int8 as `numeric` and the comparison simply misses; SQLite —
the desktop's database — refuses to bind anything past 2**63 - 1 with an OverflowError, and
Django's `__in` lookup (unlike `exact` / `gte` / `lte`) does not range-check its values. So
every id list that reaches a `pk__in` is parsed here: junk dropped (or refused when strict),
anything outside the 32-bit AutoField dropped, duplicates kept once in order, at most `limit`.
"""

MAX_PK = 2**31 - 1  # AutoField on Postgres; wider than any real Atlas table will ever get


def parse_ids(values, limit: int = 500, strict: bool = False) -> list[int]:
    """Integer ids from strings or ints. Non-integers are dropped, or raise ValueError when
    `strict`; out-of-range ids are always dropped (they cannot exist)."""
    out: list[int] = []
    seen: set[int] = set()
    for value in values or ():
        if isinstance(value, bool) or isinstance(value, float):
            if strict:
                raise ValueError("Ids must be integers.")
            continue
        try:
            pk = int(str(value).strip())
        except (TypeError, ValueError):
            if strict:
                raise ValueError("Ids must be integers.") from None
            continue
        if not 0 < pk <= MAX_PK or pk in seen:
            continue
        seen.add(pk)
        out.append(pk)
        if len(out) >= limit:
            break
    return out
