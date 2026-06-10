import httpx
from django.core.management.base import BaseCommand

from core import tts


class Command(BaseCommand):
    help = f"Download the Piper voice model ({tts.VOICE_NAME}, ~60 MB) for Read aloud."

    def handle(self, *args, **options):
        tts.VOICE_DIR.mkdir(exist_ok=True)
        for suffix in (".onnx", ".onnx.json"):
            target = tts.VOICE_DIR / f"{tts.VOICE_NAME}{suffix}"
            if target.exists():
                self.stdout.write(f"already present: {target.name}")
                continue
            url = f"{tts.VOICE_BASE_URL}/{tts.VOICE_NAME}{suffix}"
            self.stdout.write(f"downloading {url} …")
            with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(120.0)) as client:
                response = client.get(url)
                response.raise_for_status()
                target.write_bytes(response.content)
            self.stdout.write(
                self.style.SUCCESS(f"saved {target.name} ({target.stat().st_size // 1024} KB)")
            )
        self.stdout.write(self.style.SUCCESS("Read aloud is ready."))
