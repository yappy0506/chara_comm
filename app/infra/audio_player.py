from __future__ import annotations

from pathlib import Path
from typing import Union


WavInput = Union[str, Path, bytes]


def play_wav_best_effort(source: WavInput) -> bool:
    """Play wav on Windows using winsound. Returns True if attempted."""
    try:
        import winsound
        if isinstance(source, (str, Path)):
            winsound.PlaySound(str(source), winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            winsound.PlaySound(source, winsound.SND_MEMORY | winsound.SND_ASYNC)
        return True
    except Exception:
        return False
