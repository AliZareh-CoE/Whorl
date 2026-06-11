"""Owner idea #5 remainder: local extractive summarization."""

import pytest
from django.urls import reverse

from core.summarize import split_sentences, summarize

pytestmark = pytest.mark.django_db

LONG_TEXT = (
    "Working memory load changes how attention is allocated across tasks. "
    "The weather in the lab was unremarkable on Tuesday. "
    "We measured attention lapses under high and low working memory load. "
    "Participants drank coffee before some sessions. "
    "Results show load reliably increased attention lapses in every condition. "
    "The coffee machine is next to the scanner."
)


class TestSummarize:
    def test_picks_salient_sentences_in_order(self):
        result = summarize(LONG_TEXT, max_sentences=3)
        assert len(result) == 3
        joined = " ".join(result)
        assert "attention" in joined and "load" in joined
        assert "coffee machine" not in joined
        # original order preserved
        indices = [LONG_TEXT.index(s) for s in result]
        assert indices == sorted(indices)

    def test_short_text_passes_through(self):
        assert summarize("One sentence only.") == ["One sentence only."]

    def test_empty(self):
        assert summarize("") == []
        assert split_sentences("   ") == []

    def test_opening_sentence_favored(self):
        text = (
            "Strategic allocation explains the load effect. "
            "Stimuli were presented on a grey screen. "
            "Sessions took place in the morning. "
            "Trials lasted two seconds each. "
            "Breaks were provided between blocks."
        )
        result = summarize(text, max_sentences=2)
        assert "Strategic allocation explains the load effect." in result


class TestSummarizeEndpoint:
    def test_returns_tldr_panel(self, client_logged_in):
        response = client_logged_in.post(reverse("core:summarize"), {"text": LONG_TEXT})
        content = response.content.decode()
        assert "tl;dr" in content
        assert "attention" in content

    def test_requires_login(self, client, owner):
        assert client.post(reverse("core:summarize"), {"text": "x"}).status_code == 302

    def test_buttons_wired_on_note_and_reference(self, client_logged_in):
        from literature.tests.factories import ReferenceFactory
        from notes.tests.factories import NoteFactory

        note = NoteFactory()
        assert b"tl;dr" in client_logged_in.get(note.get_absolute_url()).content
        ref = ReferenceFactory(abstract="An abstract that exists.")
        assert b"tl;dr" in client_logged_in.get(ref.get_absolute_url()).content
