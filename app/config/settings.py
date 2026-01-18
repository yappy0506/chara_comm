from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class Settings:
    # character/session
    default_character_id: str
    short_memory_turns: int
    short_memory_max_chars: int
    max_session_count: int

    # lmstudio
    lmstudio_base_url: str
    lmstudio_model: str
    llm_timeout_sec: float
    retry_max: int
    lmstudio_exe_path: str | None

    # output
    output_mode: str  # text_voice / text / voice

    # tts
    tts_base_url: str | None
    tts_speaker: int
    tts_output_dir: str
    tts_autoplay: bool

    # rag
    rag_top_k_episodes: int
    rag_top_k_log_messages: int

    # paths
    db_path: str
    log_path: str
    config_path: str


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1","true","yes","y","on")


def _load_yaml(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_settings() -> Settings:
    load_dotenv()

    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    cfg = _load_yaml(config_path)

    # nested config convenience
    tts_cfg = cfg.get("tts") if isinstance(cfg.get("tts"), dict) else {}
    rag_cfg = cfg.get("rag") if isinstance(cfg.get("rag"), dict) else {}

    return Settings(
        default_character_id=os.getenv("DEFAULT_CHARACTER_ID", "shimogamo_tokina"),
        short_memory_turns=_get_int("SHORT_MEMORY_TURNS", int(cfg.get("short_memory_turns", 100))),
        short_memory_max_chars=_get_int("SHORT_MEMORY_MAX_CHARS", int(cfg.get("short_memory_max_chars", 12000))),
        max_session_count=_get_int("MAX_SESSION_COUNT", int(cfg.get("max_session_count", 200))),

        lmstudio_base_url=os.getenv("LMSTUDIO_BASE_URL", str(cfg.get("lmstudio_base_url", "http://127.0.0.1:1234/v1"))).rstrip("/"),
        lmstudio_model=os.getenv("LMSTUDIO_MODEL", str(cfg.get("lmstudio_model", "mistral-nemo-12b-arliai-rpmax-v1.2"))),
        llm_timeout_sec=_get_float("LLM_TIMEOUT_SEC", float(cfg.get("llm_timeout_sec", 60.0))),
        retry_max=_get_int("RETRY_MAX", int(cfg.get("retry_max", 2))),
        lmstudio_exe_path=os.getenv("LMSTUDIO_EXE_PATH") or (str(cfg.get("lmstudio_exe_path")) if cfg.get("lmstudio_exe_path") else None),

        output_mode=os.getenv("OUTPUT_MODE", str(cfg.get("output_mode", "text_voice"))),

        tts_base_url=os.getenv("TTS_BASE_URL", str(tts_cfg.get("base_url", ""))) or None,
        tts_speaker=_get_int("TTS_SPEAKER", int(tts_cfg.get("speaker", 0))),
        tts_output_dir=os.getenv("TTS_OUTPUT_DIR", str(tts_cfg.get("output_dir", "outputs"))),
        tts_autoplay=_get_bool("TTS_AUTOPLAY", bool(tts_cfg.get("autoplay", True))),

        rag_top_k_episodes=_get_int("RAG_TOP_K_EPISODES", int(rag_cfg.get("top_k_episodes", 3))),
        rag_top_k_log_messages=_get_int("RAG_TOP_K_LOG_MESSAGES", int(rag_cfg.get("top_k_log_messages", 6))),

        db_path=os.getenv("DB_PATH", str(cfg.get("db_path", os.path.join("data", "app.db")))),
        log_path=os.getenv("LOG_PATH", str(cfg.get("log_path", os.path.join("logs", "app.log")))),
        config_path=config_path,
    )


def save_settings_to_yaml(settings: Settings) -> None:
    # persist a minimal subset (non-secret)
    cfg = {
        "output_mode": settings.output_mode,
        "short_memory_turns": settings.short_memory_turns,
        "short_memory_max_chars": settings.short_memory_max_chars,
        "max_session_count": settings.max_session_count,
        "lmstudio_base_url": settings.lmstudio_base_url,
        "lmstudio_model": settings.lmstudio_model,
        "llm_timeout_sec": settings.llm_timeout_sec,
        "retry_max": settings.retry_max,
        "db_path": settings.db_path,
        "log_path": settings.log_path,
        "tts": {
            "base_url": settings.tts_base_url or "",
            "speaker": settings.tts_speaker,
            "output_dir": settings.tts_output_dir,
            "autoplay": settings.tts_autoplay,
        },
        "rag": {
            "top_k_episodes": settings.rag_top_k_episodes,
            "top_k_log_messages": settings.rag_top_k_log_messages,
        },
    }
    Path(settings.config_path).write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
