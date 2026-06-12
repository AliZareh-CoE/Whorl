"""Owner idea #3: Read aloud (Piper TTS). Synthesis is mocked; the real voice is optional."""

import pytest
from django.urls import reverse

from core import tts

pytestmark = pytest.mark.django_db


class TestReadAloudEndpoint:
    def test_returns_wav_when_available(self, client_logged_in, monkeypatch):
        monkeypatch.setattr("core.tts.synthesize_wav", lambda text, stage=None: b"RIFFfakewav")
        response = client_logged_in.post(reverse("core:tts"), {"text": "Hello researcher"})
        assert response.status_code == 200
        assert response["Content-Type"] == "audio/wav"
        assert response.content == b"RIFFfakewav"

    def test_view_passes_current_pet_stage(self, client_logged_in, monkeypatch):
        captured = {}

        def fake(text, stage=None):
            captured["stage"] = stage
            return b"RIFFfakewav"

        monkeypatch.setattr("core.tts.synthesize_wav", fake)
        monkeypatch.setattr("core.pet.pet_state", lambda: {"stage": "hatchling"})
        client_logged_in.post(reverse("core:tts"), {"text": "peep"})
        assert captured["stage"] == "hatchling"

    def test_missing_voice_gives_clear_503(self, client_logged_in, monkeypatch):
        def boom(text, stage=None):
            raise tts.TTSUnavailable("Voice model not downloaded")

        monkeypatch.setattr("core.tts.synthesize_wav", boom)
        response = client_logged_in.post(reverse("core:tts"), {"text": "Hello"})
        assert response.status_code == 503
        assert "Voice model" in response.json()["error"]

    def test_empty_text_rejected(self, client_logged_in):
        response = client_logged_in.post(reverse("core:tts"), {"text": "  "})
        assert response.status_code == 400

    def test_requires_login(self, client, owner):
        response = client.post(reverse("core:tts"), {"text": "hi"})
        assert response.status_code == 302

    def test_get_not_allowed(self, client_logged_in):
        assert client_logged_in.get(reverse("core:tts")).status_code == 405


class FakeVoice:
    def __init__(self, captured):
        self.captured = captured

    def synthesize_wav(self, text, wav_file, syn_config=None):
        self.captured["text"] = text
        self.captured["syn_config"] = syn_config
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00")


class TestSynthesis:
    def test_text_is_trimmed_and_capped(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(tts, "_load_voice", lambda: FakeVoice(captured))
        audio = tts.synthesize_wav("  hello\n\nworld  " + "x" * (tts.MAX_TTS_CHARS + 100))
        assert captured["text"].startswith("hello world")
        assert len(captured["text"]) <= tts.MAX_TTS_CHARS
        assert audio[:4] == b"RIFF"

    def test_stage_voices_cover_every_pet_stage(self):
        from core.pet import STAGES

        assert set(tts.STAGE_VOICES) == {name for _, name, _, _ in STAGES}

    def test_stage_shapes_delivery(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(tts, "_load_voice", lambda: FakeVoice(captured))
        tts.synthesize_wav("measured words", stage="sage")
        assert captured["syn_config"] is not None
        assert captured["syn_config"].length_scale == tts.STAGE_VOICES["sage"]["length_scale"]

    def test_scholar_and_unknown_stage_use_default_voice(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(tts, "_load_voice", lambda: FakeVoice(captured))
        tts.synthesize_wav("plain", stage="scholar")
        assert captured["syn_config"] is None
        tts.synthesize_wav("plain", stage="not-a-stage")
        assert captured["syn_config"] is None

    def test_unavailable_without_model(self, monkeypatch):
        monkeypatch.setattr(tts, "voice_available", lambda: False)
        tts._load_voice.cache_clear()
        with pytest.raises(tts.TTSUnavailable):
            tts.synthesize_wav("hello")

    @pytest.mark.skipif(not tts.voice_available(), reason="Piper voice not downloaded")
    def test_real_voice_synthesizes(self):
        tts._load_voice.cache_clear()
        audio = tts.synthesize_wav("Atlas reads this aloud.")
        assert audio[:4] == b"RIFF"
        assert len(audio) > 10000
