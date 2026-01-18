from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
import requests


@dataclass(frozen=True)
class TtsConfig:
    base_url: str
    speaker: int = 0
    output_dir: str = "outputs"
    timeout_sec: float = 30.0


class TtsClient:
    """Best-effort Bert-VITS2 JP-Extra client.

    Assumption: TTS server exposes POST /tts with JSON {text, speaker} and returns audio bytes (wav).
    If your server differs, adjust here.
    """

    def __init__(self, cfg: TtsConfig):
        self.cfg = cfg

    def synthesize_to_wav(self, text: str) -> Path:
        out_dir = Path(self.cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        out_path = out_dir / f"tts_{ts}.wav"

        url = self.cfg.base_url.rstrip("/") + "/tts"
        r = requests.post(url, json={"text": text, "speaker": self.cfg.speaker}, timeout=self.cfg.timeout_sec)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        return out_path
