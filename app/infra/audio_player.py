from __future__ import annotations

from pathlib import Path


def play_wav_best_effort(path: str | Path) -> bool:
    """Play wav on Windows using winsound. Returns True if attempted."""
    try:
        import winsound
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        return True
    except Exception:
        return False
