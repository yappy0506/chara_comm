from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
import requests


@dataclass(frozen=True)
class TtsConfig:
    base_url: str
    model_name: str | None = None
    speaker: int = 0
    style: str | None = None
    output_dir: str = "outputs"
    timeout_sec: float = 30.0
    retry_max: int = 2
    text_limit: int | None = None


class TtsClient:
    """Best-effort Style-Bert-VITS2 client.

    Assumption: TTS server exposes POST /voice with query params and returns audio bytes (wav).
    """

    def __init__(self, cfg: TtsConfig):
        self.cfg = cfg
        self._seq = 0

    def _next_out_path(self, out_dir: Path) -> Path:
        ts = int(time.time() * 1000)
        self._seq = (self._seq + 1) % 1_000_000
        return out_dir / f"tts_{ts}_{self._seq}.wav"

    def _split_text(self, text: str) -> list[str]:
        if not text:
            return []
        limit = self.cfg.text_limit or 0
        if limit <= 0 or len(text) <= limit:
            trimmed = text.strip()
            return [trimmed] if trimmed else []

        seps = ["\n\n", "\n", "。", "！", "？", "!", "?", "、", "，", ",", " "]
        out: list[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(start + limit, n)
            if end < n:
                window = text[start:end]
                cut = -1
                for sep in seps:
                    idx = window.rfind(sep)
                    if idx > 0:
                        cand = idx + len(sep)
                        if cand > cut:
                            cut = cand
                if cut > 0:
                    end = start + cut
            chunk = text[start:end].strip()
            if chunk:
                out.append(chunk)
            start = end
        return out

    def synthesize_to_wav(self, text: str) -> Path:
        if self.cfg.text_limit and len(text) > self.cfg.text_limit:
            text = text[: self.cfg.text_limit]
        out_dir = Path(self.cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = self._next_out_path(out_dir)

        url = self.cfg.base_url.rstrip("/") + "/voice"
        params = {"text": text, "speaker_id": self.cfg.speaker}
        if self.cfg.model_name:
            params["model_name"] = self.cfg.model_name
        if self.cfg.style:
            params["style"] = self.cfg.style

        last_error: Exception | None = None
        for _ in range(max(self.cfg.retry_max, 1)):
            try:
                r = requests.post(url, params=params, timeout=self.cfg.timeout_sec)
                r.raise_for_status()
                out_path.write_bytes(r.content)
                return out_path
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error
        return out_path

    def synthesize_to_wavs(self, text: str) -> list[Path]:
        chunks = self._split_text(text)
        if not chunks:
            return []
        return [self.synthesize_to_wav(chunk) for chunk in chunks]
