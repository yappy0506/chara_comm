from __future__ import annotations
from dataclasses import dataclass
import os
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    default_character_id: str
    short_memory_turns: int
    max_session_count: int
    lmstudio_base_url: str
    lmstudio_model: str
    llm_timeout_sec: float
    retry_max: int
    lmstudio_exe_path: str | None
    db_path: str
    log_path: str

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

def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        default_character_id=os.getenv("DEFAULT_CHARACTER_ID", "fushimi_eru"),
        short_memory_turns=_get_int("SHORT_MEMORY_TURNS", 100),
        max_session_count=_get_int("MAX_SESSION_COUNT", 200),
        lmstudio_base_url=os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/"),
        # lmstudio_model=os.getenv("LMSTUDIO_MODEL", "openai/gpt-oss-20b"),
        lmstudio_model=os.getenv("LMSTUDIO_MODEL", "mistral-nemo-12b-arliai-rpmax-v1.2"),
        llm_timeout_sec=_get_float("LLM_TIMEOUT_SEC", 60.0),
        retry_max=_get_int("RETRY_MAX", 2),
        lmstudio_exe_path=os.getenv("LMSTUDIO_EXE_PATH") or None,
        db_path=os.getenv("DB_PATH", os.path.join("data", "app.db")),
        log_path=os.getenv("LOG_PATH", os.path.join("logs", "app.log")),
    )
