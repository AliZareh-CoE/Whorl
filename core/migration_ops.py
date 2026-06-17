"""Backend-adaptive migration operations (#266 — desktop goes SQLite).

The web/server deployment runs on Postgres; the self-contained desktop app runs on SQLite
(a single file — no server, no initdb, instant startup). The trigram search indexes
(GinIndex + gin_trgm_ops) and the pg_trgm extension are Postgres-only. TrigramExtension already
no-ops on non-Postgres; PostgresAddIndex does the same for the indexes — it creates them on
Postgres exactly as before and skips the DDL on SQLite — so one set of migrations applies
cleanly to both backends. Search already falls back to icontains off Postgres (core/search.py).
"""

from django.db.migrations.operations import AddIndex


class PostgresAddIndex(AddIndex):
    """An AddIndex that only touches the database on PostgreSQL.

    The index still enters Django's migration *state* on every backend (so makemigrations stays
    quiet and the model's Meta.indexes match), but the actual CREATE INDEX runs only on Postgres
    — SQLite, which has no GIN/gin_trgm_ops, is skipped instead of erroring.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != "postgresql":
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != "postgresql":
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)
