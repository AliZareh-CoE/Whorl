"""Tests for the session-remembered choice helper (Backlog #191/#192)."""

from django.contrib.sessions.backends.cache import SessionStore
from django.test import RequestFactory

from core.session import remembered_choice

ALLOWED = {"title", "year", "cited"}


def _request(query=""):
    request = RequestFactory().get(f"/?{query}" if query else "/")
    request.session = SessionStore()
    return request


def test_explicit_choice_is_returned_and_remembered():
    request = _request("sort=year")
    assert remembered_choice(request, "sort", "k", ALLOWED, "title") == "year"
    # a later bare request restores it
    later = _request()
    later.session = request.session
    assert remembered_choice(later, "sort", "k", ALLOWED, "title") == "year"


def test_missing_param_falls_back_to_default():
    request = _request()
    assert remembered_choice(request, "sort", "k", ALLOWED, "title") == "title"


def test_invalid_param_falls_back_and_is_not_stored():
    # #192: a hostile value must not reach the ORM AND must not be persisted to the session.
    request = _request("sort='; DROP TABLE")
    assert remembered_choice(request, "sort", "k", ALLOWED, "title") == "title"
    assert "k" not in request.session


def test_tampered_session_value_is_validated_on_read():
    request = _request()
    request.session["k"] = "<script>"
    assert remembered_choice(request, "sort", "k", ALLOWED, "title") == "title"
