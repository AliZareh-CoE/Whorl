"""LaTeX engine warm-up: cache detection and the background prefetch."""

import os
import stat
import threading

import pytest
from django.core.cache import cache

from writing import warmup

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.delete(warmup.CACHE_KEY)
    yield
    cache.delete(warmup.CACHE_KEY)


def _fake_engine(tmp_path, ok=True):
    script = tmp_path / "tectonic"
    body = "#!/bin/sh\n" + (
        'printf "%%PDF-1.4 warm" > warmup.pdf\necho done\n'
        if ok
        else 'echo "! LaTeX Error" >&2\nexit 1\n'
    )
    script.write_text(body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_cache_dir_honours_env_and_platform(monkeypatch, tmp_path):
    monkeypatch.setenv("TECTONIC_CACHE_DIR", str(tmp_path / "custom"))
    assert warmup.cache_dir() == tmp_path / "custom"
    monkeypatch.delenv("TECTONIC_CACHE_DIR")
    monkeypatch.setattr(warmup.platform, "system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "la"))
    assert warmup.cache_dir() == tmp_path / "la" / "TectonicProject" / "Tectonic" / "cache"
    monkeypatch.setattr(warmup.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert warmup.cache_dir() == tmp_path / "xdg" / "Tectonic"


def test_cache_state_cold_then_warm(monkeypatch, tmp_path):
    monkeypatch.setenv("TECTONIC_CACHE_DIR", str(tmp_path / "tc"))
    assert warmup.cache_state()["warm"] is False
    (tmp_path / "tc" / "files").mkdir(parents=True)
    (tmp_path / "tc" / "files" / "abc").write_bytes(b"x" * 2_097_152)
    state = warmup.cache_state()
    assert state["warm"] is True and state["size_mb"] == 2


@pytest.mark.skipif(os.name == "nt", reason="shell script engine")
def test_run_warm_up_records_success(monkeypatch, tmp_path):
    from writing import compile as compile_mod

    monkeypatch.setattr(compile_mod, "tectonic_path", lambda: _fake_engine(tmp_path))
    monkeypatch.setenv("TECTONIC_CACHE_DIR", str(tmp_path / "tc"))
    out = warmup.run_warm_up()
    assert out["state"] == "ok" and out["seconds"] is not None
    assert "done" in out["log"]


@pytest.mark.skipif(os.name == "nt", reason="shell script engine")
def test_run_warm_up_records_failure_and_missing_engine(monkeypatch, tmp_path):
    from writing import compile as compile_mod

    monkeypatch.setattr(compile_mod, "tectonic_path", lambda: _fake_engine(tmp_path, ok=False))
    assert warmup.run_warm_up()["state"] == "failed"
    monkeypatch.setattr(compile_mod, "tectonic_path", lambda: None)
    out = warmup.run_warm_up()
    assert out["state"] == "failed" and "Tectonic" in out["log"]


def test_start_warm_up_runs_once_on_a_thread(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow():
        started.set()
        release.wait(5)
        cache.set(warmup.CACHE_KEY, {"state": "ok", "log": "", "seconds": 0.1}, None)
        return warmup.status()

    monkeypatch.setattr(warmup, "run_warm_up", slow)
    assert warmup.start_warm_up()["state"] == "running"
    assert started.wait(5)
    assert warmup.start_warm_up()["state"] == "running"  # a second click does not start another
    release.set()
    for _ in range(50):
        if warmup.status()["state"] == "ok":
            break
        threading.Event().wait(0.05)
    assert warmup.status()["state"] == "ok"


def test_api_status_and_start(client_logged_in, monkeypatch):
    monkeypatch.setattr(
        warmup,
        "start_warm_up",
        lambda: {
            "state": "running",
            "warm": False,
            "dir": "/x",
            "size_mb": 0,
            "log": "",
            "seconds": None,
        },
    )
    assert client_logged_in.get("/api/v1/diagnostics/warm-latex/").json()["state"] == "idle"
    response = client_logged_in.post("/api/v1/diagnostics/warm-latex/")
    assert response.status_code == 202 and response.json()["state"] == "running"
    report = client_logged_in.get("/api/v1/diagnostics/").json()
    assert "latex" in report and "TeX bundle cache" in report["text"]
