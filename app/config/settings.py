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
    short_memory_max_tokens: int
    max_session_count: int

    # lmstudio
    lmstudio_base_url: str
    lmstudio_model: str
    llm_timeout_sec: float
    retry_max: int
    lmstudio_exe_path: str | None
    llm_temperature: float
    llm_top_p: float
    llm_max_tokens: int
    llm_presence_penalty: float
    llm_frequency_penalty: float
    llm_repeat_retry_max: int

    # output
    output_mode: str  # text_voice / text / voice

    # tts
    tts_base_url: str | None
    tts_model_name: str | None
    tts_speaker: int
    tts_style: str | None
    tts_output_dir: str
    tts_autoplay: bool
    tts_timeout_sec: float
    tts_retry_max: int
    tts_text_limit: int
    tts_server_limit: int | None

    # tts server (best-effort)
    tts_server_start_cmd: list[str]
    tts_server_cwd: str | None

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


def _cfg_get(cfg: dict[str, Any], keys: list[str], default: Any) -> Any:
    cur: Any = cfg
    for k in keys:
        if not isinstance(cur, dict):
            return default
        if k not in cur:
            return default
        cur = cur[k]
    return cur


def _load_tts_server_limit(repo_root: Path) -> int | None:
    path = repo_root / "Style-Bert-VITS2-2.7.0" / "config.yml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    for keys in (["server", "limit"], ["server_config", "limit"]):
        raw = _cfg_get(data, keys, None)
        if isinstance(raw, int):
            return raw if raw > 0 else None
        if isinstance(raw, str):
            try:
                val = int(raw)
                return val if val > 0 else None
            except ValueError:
                continue
    return None


def _derive_llm_max_tokens(text_limit: int) -> int:
    # Use 1 char/token to avoid premature truncation; rely on prompt limit.
    return max(1, int(text_limit))


def _derive_tts_text_limit(max_tokens: int) -> int:
    return max(1, int(max_tokens))


def sync_llm_tts_limits(settings: "Settings", source: str = "auto") -> None:
    # source: "tts" / "llm" / "auto"
    if source == "llm":
        if settings.llm_max_tokens > 0:
            settings.tts_text_limit = _derive_tts_text_limit(settings.llm_max_tokens)
        if settings.tts_server_limit and (
            settings.tts_text_limit <= 0 or settings.tts_text_limit > settings.tts_server_limit
        ):
            settings.tts_text_limit = settings.tts_server_limit
            if settings.tts_text_limit > 0:
                settings.llm_max_tokens = _derive_llm_max_tokens(settings.tts_text_limit)
        return

    # source == "tts" or "auto"
    if settings.tts_server_limit and (
        settings.tts_text_limit <= 0 or settings.tts_text_limit > settings.tts_server_limit
    ):
        settings.tts_text_limit = settings.tts_server_limit
    if settings.tts_text_limit > 0:
        settings.llm_max_tokens = _derive_llm_max_tokens(settings.tts_text_limit)
        return

    if source == "tts":
        settings.llm_max_tokens = 0
        return

    # auto: fall back to llm -> tts
    if settings.llm_max_tokens > 0:
        settings.tts_text_limit = _derive_tts_text_limit(settings.llm_max_tokens)
        if settings.tts_server_limit and settings.tts_text_limit > settings.tts_server_limit:
            settings.tts_text_limit = settings.tts_server_limit
            if settings.tts_text_limit > 0:
                settings.llm_max_tokens = _derive_llm_max_tokens(settings.tts_text_limit)


def load_settings() -> Settings:
    load_dotenv()

    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    cfg = _load_yaml(config_path)
    repo_root = Path(__file__).resolve().parents[2]
    tts_server_limit = _load_tts_server_limit(repo_root)

    # v1.03: grouped config (keep backward compatibility with flat keys)
    session_cfg = cfg.get("session") if isinstance(cfg.get("session"), dict) else {}
    lm_cfg = cfg.get("lmstudio") if isinstance(cfg.get("lmstudio"), dict) else {}
    tts_cfg = cfg.get("tts") if isinstance(cfg.get("tts"), dict) else {}
    rag_cfg = cfg.get("rag") if isinstance(cfg.get("rag"), dict) else {}
    paths_cfg = cfg.get("paths") if isinstance(cfg.get("paths"), dict) else {}

    # Some older configs had conversation.output_mode or top-level output_mode
    output_mode_cfg = (
        _cfg_get(cfg, ["conversation", "output_mode"], None)
        or session_cfg.get("output_mode")
        or cfg.get("output_mode")
        or "text_voice"
    )

    tts_start_cmd = tts_cfg.get("server_start_cmd")
    if not isinstance(tts_start_cmd, list):
        tts_start_cmd = []

    tts_text_limit_raw = _get_int("TTS_TEXT_LIMIT", int(tts_cfg.get("text_limit", 100)))
    llm_max_tokens_raw = _get_int(
        "LLM_MAX_TOKENS",
        int(lm_cfg.get("max_tokens", cfg.get("llm_max_tokens", 256))),
    )

    return Settings(
        default_character_id=os.getenv(
            "DEFAULT_CHARACTER_ID",
            str(session_cfg.get("default_character_id", cfg.get("default_character_id", "shimogamo_tokina"))),
        ),
        short_memory_turns=_get_int(
            "SHORT_MEMORY_TURNS",
            int(session_cfg.get("short_memory_turns", cfg.get("short_memory_turns", 100))),
        ),
        short_memory_max_chars=_get_int(
            "SHORT_MEMORY_MAX_CHARS",
            int(session_cfg.get("short_memory_max_chars", cfg.get("short_memory_max_chars", 12000))),
        ),
        short_memory_max_tokens=_get_int(
            "SHORT_MEMORY_MAX_TOKENS",
            int(session_cfg.get("short_memory_max_tokens", cfg.get("short_memory_max_tokens", 4096))),
        ),
        max_session_count=_get_int(
            "MAX_SESSION_COUNT",
            int(session_cfg.get("max_session_count", cfg.get("max_session_count", 200))),
        ),

        lmstudio_base_url=os.getenv(
            "LMSTUDIO_BASE_URL",
            str(lm_cfg.get("base_url", cfg.get("lmstudio_base_url", "http://127.0.0.1:1234/v1"))),
        ).rstrip("/"),
        lmstudio_model=os.getenv(
            "LMSTUDIO_MODEL",
            str(lm_cfg.get("model", cfg.get("lmstudio_model", "mistral-nemo-12b-arliai-rpmax-v1.2"))),
        ),
        llm_timeout_sec=_get_float(
            "LLM_TIMEOUT_SEC",
            float(lm_cfg.get("timeout_sec", cfg.get("llm_timeout_sec", 60.0))),
        ),
        retry_max=_get_int(
            "RETRY_MAX",
            int(lm_cfg.get("retry_max", cfg.get("retry_max", 2))),
        ),
        lmstudio_exe_path=os.getenv("LMSTUDIO_EXE_PATH") or (
            str(lm_cfg.get("exe_path", cfg.get("lmstudio_exe_path")))
            if (lm_cfg.get("exe_path") or cfg.get("lmstudio_exe_path"))
            else None
        ),
        llm_temperature=_get_float(
            "LLM_TEMPERATURE",
            float(lm_cfg.get("temperature", cfg.get("llm_temperature", 0.7))),
        ),
        llm_top_p=_get_float(
            "LLM_TOP_P",
            float(lm_cfg.get("top_p", cfg.get("llm_top_p", 0.9))),
        ),
        llm_max_tokens=llm_max_tokens_raw,
        llm_presence_penalty=_get_float(
            "LLM_PRESENCE_PENALTY",
            float(lm_cfg.get("presence_penalty", cfg.get("llm_presence_penalty", 0.0))),
        ),
        llm_frequency_penalty=_get_float(
            "LLM_FREQUENCY_PENALTY",
            float(lm_cfg.get("frequency_penalty", cfg.get("llm_frequency_penalty", 0.0))),
        ),
        llm_repeat_retry_max=_get_int(
            "LLM_REPEAT_RETRY_MAX",
            int(lm_cfg.get("repeat_retry_max", cfg.get("llm_repeat_retry_max", 1))),
        ),

        output_mode=os.getenv("OUTPUT_MODE", str(output_mode_cfg)),

        tts_base_url=os.getenv("TTS_BASE_URL", str(tts_cfg.get("base_url", ""))) or None,
        tts_model_name=os.getenv("TTS_MODEL_NAME", str(tts_cfg.get("model_name", ""))) or None,
        tts_speaker=_get_int("TTS_SPEAKER", int(tts_cfg.get("speaker", 0))),
        tts_style=os.getenv("TTS_STYLE", str(tts_cfg.get("style", ""))) or None,
        tts_output_dir=os.getenv("TTS_OUTPUT_DIR", str(tts_cfg.get("output_dir", "outputs"))),
        tts_autoplay=_get_bool("TTS_AUTOPLAY", bool(tts_cfg.get("autoplay", True))),
        tts_timeout_sec=_get_float("TTS_TIMEOUT_SEC", float(tts_cfg.get("timeout_sec", 30.0))),
        tts_retry_max=_get_int("TTS_RETRY_MAX", int(tts_cfg.get("retry_max", 2))),
        tts_text_limit=tts_text_limit_raw,
        tts_server_limit=tts_server_limit,

        tts_server_start_cmd=tts_start_cmd,
        tts_server_cwd=str(tts_cfg.get("server_cwd")) if tts_cfg.get("server_cwd") else None,

        rag_top_k_episodes=_get_int("RAG_TOP_K_EPISODES", int(rag_cfg.get("top_k_episodes", 3))),
        rag_top_k_log_messages=_get_int("RAG_TOP_K_LOG_MESSAGES", int(rag_cfg.get("top_k_log_messages", 6))),

        db_path=os.getenv(
            "DB_PATH",
            str(paths_cfg.get("db_path", cfg.get("db_path", os.path.join("data", "app.db")))),
        ),
        log_path=os.getenv(
            "LOG_PATH",
            str(paths_cfg.get("log_path", cfg.get("log_path", os.path.join("logs", "app.log")))),
        ),
        config_path=config_path,
    )

    sync_llm_tts_limits(settings, source="auto")
    return settings


def save_settings_to_yaml(settings: Settings) -> None:
    # v1.03 grouped config (non-secret)
    cfg = {
        "session": {
            "default_character_id": settings.default_character_id,
            "output_mode": settings.output_mode,
            "short_memory_turns": settings.short_memory_turns,
            "short_memory_max_chars": settings.short_memory_max_chars,
            "short_memory_max_tokens": settings.short_memory_max_tokens,
            "max_session_count": settings.max_session_count,
        },
        "lmstudio": {
            "base_url": settings.lmstudio_base_url,
            "model": settings.lmstudio_model,
            "timeout_sec": settings.llm_timeout_sec,
            "retry_max": settings.retry_max,
            "exe_path": settings.lmstudio_exe_path or "",
            "temperature": settings.llm_temperature,
            "top_p": settings.llm_top_p,
            "max_tokens": settings.llm_max_tokens,
            "presence_penalty": settings.llm_presence_penalty,
            "frequency_penalty": settings.llm_frequency_penalty,
            "repeat_retry_max": settings.llm_repeat_retry_max,
        },
        "tts": {
            "base_url": settings.tts_base_url or "",
            "model_name": settings.tts_model_name or "",
            "speaker": settings.tts_speaker,
            "style": settings.tts_style or "",
            "output_dir": settings.tts_output_dir,
            "autoplay": settings.tts_autoplay,
            "timeout_sec": settings.tts_timeout_sec,
            "retry_max": settings.tts_retry_max,
            "text_limit": settings.tts_text_limit,
            "server_start_cmd": settings.tts_server_start_cmd,
            "server_cwd": settings.tts_server_cwd or "",
        },
        "rag": {
            "top_k_episodes": settings.rag_top_k_episodes,
            "top_k_log_messages": settings.rag_top_k_log_messages,
        },
        "paths": {
            "db_path": settings.db_path,
            "log_path": settings.log_path,
        },
    }
    Path(settings.config_path).write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
