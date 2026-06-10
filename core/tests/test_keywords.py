"""Owner idea #5: local keyword extraction + tag suggestions."""

import pytest
from django.urls import reverse

from core.keywords import extract_keywords
from documents.tests.factories import DocumentFactory, TagFactory

pytestmark = pytest.mark.django_db


class TestExtractKeywords:
    def test_salient_phrases_surface(self):
        text = (
            "Working memory load modulates sustained attention in dual-task settings. "
            "We manipulate working memory load and measure sustained attention lapses."
        )
        keywords = extract_keywords(text)
        joined = " ".join(keywords)
        assert "working memory load" in joined
        assert "sustained attention" in joined

    def test_stopwords_never_appear(self):
        keywords = extract_keywords("the of and for with this that是 attention")
        for keyword in keywords:
            assert keyword not in {"the", "of", "and", "for", "with", "this", "that"}

    def test_empty_and_junk_input(self):
        assert extract_keywords("") == []
        assert extract_keywords("!!! ??? 123") == []

    def test_max_keywords_respected(self):
        words = [
            "alphaone",
            "betatwo",
            "gammathree",
            "deltafour",
            "epsilonfive",
            "zetasix",
            "etaseven",
            "thetaeight",
            "iotanine",
            "kappaten",
        ]
        text = ". ".join(words)  # periods break phrases → 10 distinct candidates
        assert len(extract_keywords(text, max_keywords=5)) == 5

    def test_phrase_length_capped(self):
        keywords = extract_keywords(
            "alpha beta gamma delta epsilon zeta eta theta iota kappa", max_keywords=3
        )
        assert all(len(kw.split()) <= 4 for kw in keywords)


class TestSurfaces:
    def test_reference_detail_shows_keyword_chips(self, client_logged_in):
        from literature.tests.factories import ReferenceFactory

        ref = ReferenceFactory(
            title="Spatial attention and visual working memory interplay",
            abstract="Visual working memory guides spatial attention deployment.",
        )
        response = client_logged_in.get(ref.get_absolute_url())
        assert b"Keywords" in response.content
        assert b"working memory" in response.content

    def test_document_edit_suggests_and_attaches_tag(self, client_logged_in):
        doc = DocumentFactory(
            title="Pupillometry calibration protocol",
            description="Calibration steps for the pupillometry rig.",
        )
        edit = client_logged_in.get(
            reverse("documents:document_edit", args=[doc.project.slug, doc.pk])
        )
        assert b"Suggested tags" in edit.content
        assert b"pupillometry" in edit.content

        response = client_logged_in.post(
            reverse("documents:add_suggested_tag", args=[doc.project.slug, doc.pk]),
            {"name": "pupillometry calibration"},
        )
        assert response.status_code == 302
        assert doc.tags.filter(name="pupillometry calibration").exists()

    def test_suggestion_excludes_existing_tags(self, client_logged_in):
        doc = DocumentFactory(title="Eye tracking pipeline", description="")
        tag = TagFactory(project=doc.project, name="eye tracking pipeline")
        doc.tags.add(tag)
        response = client_logged_in.get(
            reverse("documents:document_edit", args=[doc.project.slug, doc.pk])
        )
        content = response.content.decode()
        assert 'value="eye tracking pipeline"' not in content

    def test_attach_is_idempotent_per_tag_name(self, client_logged_in):
        doc = DocumentFactory(title="Misc", description="")
        url = reverse("documents:add_suggested_tag", args=[doc.project.slug, doc.pk])
        client_logged_in.post(url, {"name": "replication"})
        client_logged_in.post(url, {"name": "replication"})
        assert doc.project.tags.filter(name="replication").count() == 1
        assert doc.tags.count() == 1
