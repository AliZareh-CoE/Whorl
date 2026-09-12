"""Compiles never run inside the HTTP request in immediate (desktop) mode."""

import threading

import pytest
from django.test import override_settings

from writing import tasks

pytestmark = pytest.mark.django_db


def test_immediate_mode_compiles_on_a_background_thread(monkeypatch):
    seen = {}
    done = threading.Event()

    def fake_compile(manuscript_id, generation=None):
        seen["thread"] = threading.current_thread().name
        seen["args"] = (manuscript_id, generation)
        done.set()

    monkeypatch.setattr(tasks.compile_manuscript_task, "call_local", fake_compile)
    with override_settings(HUEY={"huey_class": "huey.MemoryHuey", "name": "t", "immediate": True}):
        assert tasks.enqueue_compile(7, 3) == "thread"
    assert done.wait(5)
    assert seen["thread"] == "compile-7"
    assert seen["args"] == (7, 3)


def test_worker_mode_queues_the_task(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tasks, "compile_manuscript_task", lambda mid, gen=None: calls.append((mid, gen))
    )
    with override_settings(HUEY={"huey_class": "huey.MemoryHuey", "name": "t", "immediate": False}):
        assert tasks.enqueue_compile(1, 2) == "queue"
    assert calls == [(1, 2)]
