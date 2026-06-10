"""Local text-to-speech via Piper (Owner idea #3). Free, offline, no cloud."""

import io
import wave
from functools import lru_cache
from pathlib import Path

from django.conf import settings

VOICE_NAME = "en_US-amy-medium"
VOICE_DIR = Path(settings.BASE_DIR) / "tts_voices"
VOICE_PATH = VOICE_DIR / f"{VOICE_NAME}.onnx"
MAX_TTS_CHARS = 5000

VOICE_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium"


class TTSUnavailable(Exception):
    """Raised when the voice model is missing or Piper cannot load."""


def voice_available() -> bool:
    return VOICE_PATH.exists()


@lru_cache(maxsize=1)
def _load_voice():
    if not voice_available():
        raise TTSUnavailable(
            "Voice model not downloaded — run `manage.py download_tts_voice` first."
        )
    try:
        from piper import PiperVoice
    except ImportError as exc:  # pragma: no cover
        raise TTSUnavailable(f"piper-tts not installed ({exc})") from exc
    return PiperVoice.load(str(VOICE_PATH))


def synthesize_wav(text: str) -> bytes:
    """Render text to WAV bytes with the local Piper voice."""
    text = " ".join(text.split())[:MAX_TTS_CHARS]
    if not text:
        raise ValueError("Nothing to read.")
    voice = _load_voice()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    return buffer.getvalue()
