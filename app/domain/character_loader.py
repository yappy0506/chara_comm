from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml

# v1.01 仕様の3ファイル（profile / speech_style / episodes）を読み込む

@dataclass(frozen=True)
class CharacterBundle:
    profile: dict[str, Any]
    speech_style: dict[str, Any]
    episodes: dict[str, Any]

def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be mapping: {path}")
    return data

def load_character(characters_dir: str, character_id: str) -> CharacterBundle:
    base = Path(characters_dir) / character_id
    profile_p = base / "profile.yaml"
    style_p = base / "speech_style.yaml"
    episodes_p = base / "episodes.yaml"

    for p in (profile_p, style_p, episodes_p):
        if not p.exists():
            raise FileNotFoundError(p)

    profile = _read_yaml(profile_p)
    speech_style = _read_yaml(style_p)
    episodes = _read_yaml(episodes_p)

    return CharacterBundle(profile=profile, speech_style=speech_style, episodes=episodes)
