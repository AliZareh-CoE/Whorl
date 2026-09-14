"""mcp_server.client is Django-free; test it with a mock transport."""

import json

import httpx
import pytest

from mcp_server import client


def calls_url_has(calls, fragment):
    return fragment in calls["url"]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ATLAS_API_URL", "http://testserver")
    monkeypatch.setenv("ATLAS_API_KEY", "k")


@pytest.fixture
def capture(monkeypatch, env):
    calls = {}

    def fake_client():
        def handler(request):
            calls["method"] = request.method
            calls["url"] = str(request.url)
            calls["body"] = request.content.decode() if request.content else ""
            return httpx.Response(200, json={"ok": True})

        return httpx.Client(
            base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(client, "_client", fake_client)
    return calls


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("ATLAS_API_KEY", raising=False)
    with pytest.raises(client.AtlasClientError, match="ATLAS_API_KEY"):
        client.list_projects()


def test_complete_milestone_patches_timestamp(capture):
    client.complete_milestone(7)
    assert capture["method"] == "PATCH"
    assert capture["url"].endswith("/milestones/7/")
    assert "completed_at" in capture["body"]


def test_add_reference_by_doi_includes_project(capture):
    client.add_reference_by_doi("10.1/x", "my-project")
    assert capture["url"].endswith("/references/by-doi/")
    assert "my-project" in capture["body"]


def test_error_response_raises_with_detail(monkeypatch, env):
    def fake_client():
        return httpx.Client(
            base_url="http://testserver/api/v1",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(404, json={"detail": "nope"})
            ),
        )

    monkeypatch.setattr(client, "_client", fake_client)
    with pytest.raises(client.AtlasClientError, match="404"):
        client.get_plan("missing")


def test_no_django_imports():
    """The MCP client must stay a pure HTTP client — the API is the single contract."""
    import ast

    import mcp_server.client as module

    tree = ast.parse(open(module.__file__).read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "django" not in imported
    assert imported <= {"os", "datetime", "httpx", "mimetypes"}  # stdlib only, plus httpx


class TestETagCache:
    @pytest.fixture(autouse=True)
    def fresh_cache(self):
        client._etag_cache.clear()
        yield
        client._etag_cache.clear()

    def _transport(self, monkeypatch, statuses):
        """Server stub: first response 200+ETag, then 304 when If-None-Match matches."""

        def fake_client():
            def handler(request):
                statuses.append((request.method, request.headers.get("If-None-Match", "")))
                if request.headers.get("If-None-Match") == 'W/"abc"':
                    return httpx.Response(304)
                return httpx.Response(200, json={"projects": [1, 2]}, headers={"ETag": 'W/"abc"'})

            return httpx.Client(
                base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
            )

        monkeypatch.setattr(client, "_client", fake_client)

    def test_repeat_get_serves_cached_body_on_304(self, monkeypatch, env):
        seen = []
        self._transport(monkeypatch, seen)
        first = client.list_projects()
        second = client.list_projects()
        assert first == second == {"projects": [1, 2]}
        assert seen == [("GET", ""), ("GET", 'W/"abc"')]

    def test_params_split_the_cache(self, monkeypatch, env):
        seen = []
        self._transport(monkeypatch, seen)
        client.search("alpha")
        client.search("beta")  # different params — must not send alpha's ETag
        assert seen == [("GET", ""), ("GET", "")]

    def test_posts_never_touch_the_cache(self, monkeypatch, env):
        seen = []
        self._transport(monkeypatch, seen)
        client.quick_capture("hello")
        assert seen == [("POST", "")]
        assert client._etag_cache == {}


def test_get_weekly_review_builds_request(capture):
    from mcp_server import client

    client.get_weekly_review("attention-and-memory", weeks_back=2)
    assert calls_url_has(capture, "/weekly-review/")
    assert "project=attention-and-memory" in capture["url"]
    assert "weeks_back=2" in capture["url"]


def test_get_weekly_review_global(capture):
    from mcp_server import client

    client.get_weekly_review()
    assert "project=" not in capture["url"]


def test_get_synthesis_scaffold_builds_request(capture):
    from mcp_server import client

    client.get_synthesis_scaffold("attention-and-memory")
    assert "/projects/attention-and-memory/synthesis/" in capture["url"]


# --- B4: manuscript workbench + compile tools ---


def test_list_manuscripts_scopes_by_project(capture):
    client.list_manuscripts("attn")
    assert "/manuscripts/" in capture["url"] and "project=attn" in capture["url"]


def test_set_main_file_patches_is_main(capture):
    client.set_main_file(9)
    assert capture["method"] == "PATCH"
    assert "/manuscript-files/9/" in capture["url"]
    assert '"is_main":true' in capture["body"]


def test_compile_manuscript_posts(capture):
    client.compile_manuscript(42)
    assert capture["method"] == "POST" and "/manuscripts/42/compile/" in capture["url"]


def test_latex_word_count_hits_action(capture):
    client.latex_word_count(42)
    assert "/manuscripts/42/word-count/" in capture["url"]


def test_write_manuscript_file_creates_when_path_new(monkeypatch, env):
    seen = []

    def fake_client():
        def handler(request):
            seen.append(
                (
                    request.method,
                    str(request.url),
                    request.content.decode() if request.content else "",
                )
            )
            if request.method == "GET":
                return httpx.Response(200, json=[])  # no existing files
            return httpx.Response(201, json={"id": 5, "path": "new.tex"})

        return httpx.Client(
            base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(client, "_client", fake_client)
    client.write_manuscript_file(42, "new.tex", "hi")
    methods = [m for m, _, _ in seen]
    assert "GET" in methods and "POST" in methods
    post = next(s for s in seen if s[0] == "POST")
    assert "/manuscript-files/" in post[1] and '"path":"new.tex"' in post[2]


def test_write_manuscript_file_updates_when_path_exists(monkeypatch, env):
    seen = []

    def fake_client():
        def handler(request):
            seen.append((request.method, str(request.url)))
            if request.method == "GET":
                return httpx.Response(200, json=[{"id": 10, "path": "main.tex"}])
            return httpx.Response(200, json={"id": 10})

        return httpx.Client(
            base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(client, "_client", fake_client)
    client.write_manuscript_file(42, "main.tex", "updated")
    assert ("PATCH", "http://testserver/api/v1/manuscript-files/10/") in seen


def test_compile_and_wait_polls_until_done(monkeypatch, env):
    states = iter(
        [{"status": "running"}, {"status": "running"}, {"status": "ok", "pdf_url": "/p.pdf"}]
    )

    def fake_client():
        def handler(request):
            if request.method == "POST":
                return httpx.Response(202, json={"status": "running"})
            return httpx.Response(200, json=next(states))

        return httpx.Client(
            base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(client, "_client", fake_client)
    result = client.compile_and_wait(42, timeout_seconds=30)
    assert result["status"] == "ok" and result["pdf_url"] == "/p.pdf"


def test_compile_and_wait_respects_timeout(monkeypatch, env):
    def fake_client():
        def handler(request):
            if request.method == "POST":
                return httpx.Response(202, json={"status": "running"})
            return httpx.Response(200, json={"status": "running"})

        return httpx.Client(
            base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(client, "_client", fake_client)
    result = client.compile_and_wait(42, timeout_seconds=0)  # immediate deadline
    assert result["status"] == "running"  # returns, doesn't loop forever


def test_list_protocols_scopes_to_project(capture):
    client.list_protocols("my-project")
    assert capture["method"] == "GET"
    assert capture["url"].endswith("/protocols/?project=my-project")


def test_add_protocol_posts_fields(capture):
    client.add_protocol("my-project", "Cell prep", "step 1")
    assert capture["method"] == "POST"
    assert capture["url"].endswith("/protocols/")
    assert "my-project" in capture["body"] and "Cell prep" in capture["body"]


def test_new_protocol_version_omits_unset_fields(capture):
    client.new_protocol_version(5, body="step 2")
    assert capture["method"] == "POST"
    assert capture["url"].endswith("/protocols/5/new-version/")
    assert "step 2" in capture["body"]
    assert "title" not in capture["body"]  # carried over, not sent


def test_connection_refused_explains_that_atlas_is_not_running(monkeypatch, env):
    def fake_client():
        def handler(request):
            raise httpx.ConnectError("All connection attempts failed", request=request)

        return httpx.Client(
            base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(client, "_client", fake_client)
    with pytest.raises(client.AtlasClientError, match="is the Atlas app running"):
        client.list_projects()


def test_import_references_posts_text_and_project(capture):
    client.import_references("@article{k, title={T}}", "bibtex", "proj")
    assert capture["method"] == "POST" and calls_url_has(capture, "/references/import/")
    assert '"format":"bibtex"' in capture["body"] and '"project":"proj"' in capture["body"]


def test_import_from_zotero_posts(capture):
    client.import_from_zotero()
    assert capture["method"] == "POST" and calls_url_has(capture, "/references/import-zotero/")
    assert capture["body"] == "{}"


def test_discover_related_builds_request(capture):
    client.discover_related(7, "cited_by", 5)
    assert calls_url_has(capture, "/references/7/discover/") and "kind=cited_by" in capture["url"]


def test_export_bibtex_returns_text(monkeypatch, env):
    def fake_client():
        def handler(request):
            assert "ids=1%2C2" in str(request.url) or "ids=1,2" in str(request.url)
            return httpx.Response(200, text="@article{k, title={T}}")

        return httpx.Client(
            base_url="http://testserver/api/v1", transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(client, "_client", fake_client)
    assert client.export_bibtex([1, 2]).startswith("@article")


def test_format_citations_builds_request(capture):
    client.format_citations([3, 1], "chicago")
    assert (
        calls_url_has(capture, "/references/cite/")
        and "ids=3%2C1" in capture["url"]
        and "style=chicago" in capture["url"]
    )


def test_todo_client_calls(capture):
    client.list_todos()
    assert calls_url_has(capture, "/todos/") and "done=false" in capture["url"]
    client.add_todo("Book scanner", "proj")
    assert capture["method"] == "POST" and '"project":"proj"' in capture["body"]
    client.complete_todo(4)
    assert (
        capture["method"] == "PATCH"
        and calls_url_has(capture, "/todos/4/")
        and '"done":true' in capture["body"]
    )


def test_tag_client_calls(capture):
    client.list_library_tags()
    assert calls_url_has(capture, "/library-tags/")
    client.tag_references([1, 2], "pilot", remove=True)
    assert (
        capture["method"] == "POST"
        and '"action":"untag"' in capture["body"]
        and '"value":"pilot"' in capture["body"]
    )


def test_duplicate_client_calls(capture):
    client.find_duplicates()
    assert calls_url_has(capture, "/references/duplicates/")
    client.merge_references(1, [2, 3])
    assert (
        capture["method"] == "POST"
        and calls_url_has(capture, "/references/merge/")
        and '"merge":[2,3]' in capture["body"]
    )


def test_reading_client_calls(capture):
    client.list_highlights(7)
    assert calls_url_has(capture, "/highlights/") and "reference=7" in capture["url"]
    client.add_highlight(7, "a passage", page=3, project="deep", comment="why")
    assert (
        capture["method"] == "POST"
        and calls_url_has(capture, "/highlights/")
        and '"page":3' in capture["body"]
        and '"project":"deep"' in capture["body"]
    )
    client.add_highlight(7, "global")
    assert '"project"' not in capture["body"] and '"page"' not in capture["body"]
    client.get_highlights_markdown(7)
    assert calls_url_has(capture, "/references/7/highlights-markdown/")
    client.get_reading_notes(7)
    assert calls_url_has(capture, "/references/7/reading-notes/")
    client.set_reading_notes(4, "notes")
    assert capture["method"] == "PATCH" and calls_url_has(capture, "/project-references/4/")
    client.fetch_pdf(7)
    assert capture["method"] == "POST" and calls_url_has(capture, "/references/7/fetch-pdf/")


def test_pdf_text_search_client_calls(capture):
    client.search_pdf_text("perceptual load", project="deep", limit=5)
    assert calls_url_has(capture, "/references/text-search/") and "project=deep" in capture["url"]
    client.search_in_pdf(7, "load")
    assert calls_url_has(capture, "/references/7/text-search/") and "q=load" in capture["url"]


def test_plan_outline_client_calls(capture):
    client.get_plan_outline("deep")
    assert calls_url_has(capture, "/projects/deep/outline/")
    client.set_plan_outline("deep", "# A", dry_run=True)
    assert capture["method"] == "POST" and '"dry_run":true' in capture["body"]


def test_roadmap_client_calls(capture):
    client.get_roadmap("deep")
    assert calls_url_has(capture, "/projects/deep/roadmap/")
    client.set_phase_dates(3, start="2026-09-01")
    assert capture["method"] == "PATCH" and calls_url_has(capture, "/phases/3/")
    assert '"target_start":"2026-09-01"' in capture["body"] and "target_end" not in capture["body"]


def test_week_focus_client_call(capture):
    client.get_week_focus("deep")
    assert calls_url_has(capture, "/projects/deep/focus/")


def test_notes_client_calls(capture):
    client.list_notes("deep", q="load")
    assert calls_url_has(capture, "/notes/") and "q=load" in capture["url"]
    client.get_note(4)
    assert calls_url_has(capture, "/notes/4/")
    client.update_note(4, body="new body")
    assert (
        capture["method"] == "PATCH"
        and '"body":"new body"' in capture["body"]
        and "title" not in capture["body"]
    )
    client.get_note_links(4)
    assert calls_url_has(capture, "/notes/4/links/")


def test_note_template_and_export_client_calls(capture):
    client.create_note_from_template("deep", "literature", reference_id=9)
    assert (
        capture["method"] == "POST"
        and '"reference":9' in capture["body"]
        and '"kind":"literature"' in capture["body"]
    )
    client.create_note_from_template("deep", "daily")
    assert "reference" not in capture["body"]
    client.export_note(4, style="ieee")
    assert calls_url_has(capture, "/notes/4/export/") and "style=ieee" in capture["url"]


def test_manuscript_bibliography_client_calls(capture):
    client.get_manuscript_bibliography(3)
    assert calls_url_has(capture, "/manuscripts/3/bibliography/")
    client.add_manuscript_reference(3, 9, cite_key_override="lavie10")
    assert (
        capture["method"] == "POST"
        and '"reference":9' in capture["body"]
        and "lavie10" in capture["body"]
    )
    client.remove_manuscript_reference(3, 9)
    assert capture["method"] == "DELETE" and calls_url_has(
        capture, "/manuscripts/3/bibliography/9/"
    )
    client.manuscript_cite_check(3)
    assert calls_url_has(capture, "/manuscripts/3/cite-check/")
    client.add_submission_event(3, "submitted", "2026-09-06", "to NeurIPS")
    assert capture["method"] == "POST" and '"kind":"submitted"' in capture["body"]


def test_reviews_client_calls(capture):
    client.log_reviews(3, "Reviewer 1\n1. small n", date="2026-09-06")
    assert (
        capture["method"] == "POST"
        and calls_url_has(capture, "/manuscripts/3/reviews/")
        and '"date":"2026-09-06"' in capture["body"]
    )
    try:
        client.get_response_progress(3)
    except (KeyError, TypeError):
        pass  # the capture transport returns an empty body; the URL is what we check
    assert calls_url_has(capture, "/manuscripts/3/response-progress/")


def test_budget_client_calls(capture):
    client.get_manuscript_budget(3)
    assert calls_url_has(capture, "/manuscripts/3/budget/")
    client.set_venue_limits(3, {"words": 8000})
    assert capture["method"] == "PATCH" and '"venue_limits":{"words":8000}' in capture["body"]


def test_dashboard_client_call(capture):
    client.get_dashboard()
    assert calls_url_has(capture, "/dashboard/")


def test_inbox_client_calls(capture):
    client.list_inbox()
    assert calls_url_has(capture, "/quick-capture/") and "processed=false" in capture["url"]
    assert "snoozed=false" in capture["url"]
    client.list_inbox(snoozed=True)
    assert "snoozed=true" in capture["url"]
    client.enrich_capture(9, force=True)
    assert capture["method"] == "POST" and calls_url_has(capture, "/quick-capture/9/enrich/")
    assert "force=1" in capture["url"]
    client.triage_captures([1, 2], "file", project="deep")
    assert (
        capture["method"] == "POST"
        and calls_url_has(capture, "/quick-capture/bulk/")
        and '"ids":[1,2]' in capture["body"]
        and '"project":"deep"' in capture["body"]
    )
    client.get_inbox_history(12)
    assert calls_url_has(capture, "/quick-capture/history/") and "limit=12" in capture["url"]
    client.snooze_capture(5, "monday")
    assert (
        capture["method"] == "POST"
        and calls_url_has(capture, "/quick-capture/5/snooze/")
        and '"until":"monday"' in capture["body"]
    )
    client.convert_capture(5, "milestone", project="deep", phase_id=3, due="2026-10-01")
    assert (
        capture["method"] == "POST"
        and calls_url_has(capture, "/quick-capture/5/convert/")
        and '"phase":3' in capture["body"]
        and '"tz":"' in capture["body"]  # #500: the machine's offset unless given
    )
    client.convert_capture(5, "todo", tz="Europe/Berlin")
    assert '"tz":"Europe/Berlin"' in capture["body"]


def test_review_matrix_client_calls(capture):
    client.set_review_mark("deep", "lavie2010attention", "Sample size", note="n=12")
    assert (
        capture["method"] == "POST"
        and calls_url_has(capture, "/projects/deep/review-matrix/mark/")
        and '"note":"n=12"' in capture["body"]
    )
    client.add_review_theme("deep", "Load type")
    assert calls_url_has(capture, "/projects/deep/review-matrix/themes/")


def test_research_client_calls(capture):
    client.add_hypothesis("deep", "Load is strategic")
    assert (
        capture["method"] == "POST"
        and calls_url_has(capture, "/hypotheses/")
        and '"statement":"Load is strategic"' in capture["body"]
    )
    client.set_hypothesis_status(4, "testing")
    assert capture["method"] == "PATCH" and calls_url_has(capture, "/hypotheses/4/")
    client.add_evidence(4, "supports", "n=12 pilot", reference_id=9)
    assert (
        calls_url_has(capture, "/evidence/")
        and '"reference":9' in capture["body"]
        and "note" not in capture["body"]
    )
    client.log_experiment("deep", "Pilot run", hypothesis_ids=[4], date="2026-09-06")
    assert calls_url_has(capture, "/experiments/") and '"hypotheses":[4]' in capture["body"]


def test_theme_suggestions_and_diagnostics_client_calls(capture):
    client.suggest_review_themes("attention")
    assert calls_url_has(capture, "/projects/attention/review-matrix/suggest/")
    client.get_diagnostics(network=True)
    assert calls_url_has(capture, "/diagnostics/?network=1")


def test_get_achievements(capture):
    client.get_achievements()
    assert capture["url"].endswith("/achievements/")


def test_take_snapshot_client_calls(capture):
    """#464: list_only reads the status; the default writes a snapshot (POST)."""
    client.take_snapshot(list_only=True)
    assert capture["url"].endswith("/snapshots/") and capture["method"] == "GET"
    client.take_snapshot()
    assert capture["url"].endswith("/snapshots/") and capture["method"] == "POST"


def test_preflight_client_call(capture):
    """#466: the readiness checks, with the network flag only when asked."""
    client.preflight_manuscript(4)
    assert capture["url"].endswith("/manuscripts/4/preflight/")
    client.preflight_manuscript(4, network=True)
    assert capture["url"].endswith("/manuscripts/4/preflight/?network=1")


def test_submit_manuscript_client_call(capture):
    """#469: submit through the pre-flight; the date rides only when given."""
    client.submit_manuscript(4, force=True, notes="n")
    assert capture["url"].endswith("/manuscripts/4/submit/") and capture["method"] == "POST"
    assert json.loads(capture["body"]) == {"force": True, "notes": "n"}
    client.submit_manuscript(4, date="2026-09-10")
    assert json.loads(capture["body"])["date"] == "2026-09-10"


def test_fix_lint_client_call(capture):
    """#472: apply the lint's mechanical fixes; `only` rides only when given."""
    client.fix_lint(4)
    assert capture["url"].endswith("/manuscripts/4/lint/fix/") and capture["method"] == "POST"
    assert json.loads(capture["body"]) == {}
    client.fix_lint(4, only=[{"file": "main.tex", "line": 2, "rule": "unit-space", "col": 4}])
    assert json.loads(capture["body"])["only"][0]["rule"] == "unit-space"


def test_get_venue_turnaround_client_call(capture):
    """#474: the venue's turnaround; `exclude` rides only when given."""
    client.get_venue_turnaround("JEP:G")
    assert "/manuscripts/venue-turnaround/" in capture["url"] and "venue=JEP" in capture["url"]
    assert "exclude=" not in capture["url"]
    client.get_venue_turnaround("JEP:G", exclude=4)
    assert "exclude=4" in capture["url"]


def test_search_and_replace_client_calls(capture):
    """#476: find in project and replace across files."""
    client.search_manuscript(4, "load", regex=True)
    assert capture["url"].endswith("/manuscripts/4/search/?q=load&regex=1")
    client.replace_in_manuscript(4, "load", "demand", files=["main.tex"])
    assert capture["method"] == "POST" and capture["url"].endswith("/manuscripts/4/replace/")
    assert json.loads(capture["body"]) == {
        "q": "load",
        "replacement": "demand",
        "regex": False,
        "case": False,
        "files": ["main.tex"],
    }


def test_get_status_update_builds_request(capture):
    """#482"""
    from mcp_server import client

    client.get_status_update("attention-and-memory", days=14)
    assert capture["method"] == "GET"
    assert calls_url_has(capture, "/projects/attention-and-memory/status-update/")
    assert "days=14" in capture["url"]


def test_get_daily_brief_builds_request(capture):
    """#491"""
    from mcp_server import client

    client.get_daily_brief()
    assert capture["method"] == "GET" and calls_url_has(capture, "/dashboard/brief/")


def test_get_day_activity_builds_request(capture):
    """#492"""
    from mcp_server import client

    client.get_day_activity("2026-09-08")
    assert calls_url_has(capture, "/dashboard/day/") and "date=2026-09-08" in capture["url"]
    client.get_day_activity()
    assert "date=" not in capture["url"]
