from __future__ import annotations

from typing import Any

EMOTION_KEYS: tuple[str, ...] = (
    "joy",
    "trust",
    "fear",
    "surprise",
    "sadness",
    "disgust",
    "anger",
    "anticipation",
)

DEFAULT_EMOTION_VALUE = 50
EMOTION_MIN = 0
EMOTION_MAX = 99


def default_emotion_state() -> dict[str, int]:
    return {k: DEFAULT_EMOTION_VALUE for k in EMOTION_KEYS}


def normalize_emotion_state(raw: Any) -> dict[str, int]:
    base = default_emotion_state()
    if not isinstance(raw, dict):
        return base
    for k in EMOTION_KEYS:
        v = raw.get(k)
        if isinstance(v, (int, float)):
            base[k] = max(EMOTION_MIN, min(EMOTION_MAX, int(v)))
    return base
