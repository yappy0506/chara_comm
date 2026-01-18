from __future__ import annotations

import logging
from pathlib import Path

from app.config.settings import load_settings, save_settings_to_yaml
from app.infra.db import connect
from app.infra.repositories import LogRepository
from app.infra.lmstudio import health_check, try_start_lm_studio, guidance_message
from app.infra.installer import ensure_style_bert_vits2_installed, StyleBertVits2InstallConfig
from app.infra.llm_client import LlmClient, LlmClientConfig
from app.infra.tts_client import TtsClient, TtsConfig
from app.infra.audio_player import play_wav_best_effort
from app.infra.tts_server import ensure_tts_server

from app.domain.prompt_builder import PromptBuilder
from app.domain.memory_manager import MemoryManager
from app.domain.character_loader import load_character

from app.usecases.session_service import SessionService
from app.usecases.conversation_service import ConversationService
from app.ui.cui_controller import CUIController


def _setup_logging(log_path: str) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    st = load_settings()
    _setup_logging(st.log_path)
    log = logging.getLogger("app")

    conn = connect(st.db_path)
    repo = LogRepository(conn)
    repo.enforce_max_sessions(st.max_session_count)

    # LM Studio health check (non-fatal)
    hs = health_check(st.lmstudio_base_url)
    if not hs.ok:
        if st.lmstudio_exe_path:
            if try_start_lm_studio(st.lmstudio_exe_path):
                print("[INFO] LM Studio の起動を試みました。サーバ有効化/モデルロード後に再試行してください。")
            else:
                print("[INFO] LM Studio の自動起動に失敗しました。手動で起動してください。")
        print("[INFO] " + guidance_message(st.lmstudio_base_url))

    session_service = SessionService(repo=repo, default_character_id=st.default_character_id)
    session = session_service.resume_or_create()

    # resolve character name
    try:
        bundle = load_character("characters", session.character_id)
        char_name = (bundle.profile.get("character", {}).get("name") or session.character_id)
    except Exception:
        char_name = session.character_id

    memory = MemoryManager(
        short_memory_turns=st.short_memory_turns,
        short_memory_max_chars=st.short_memory_max_chars,
        short_memory_max_tokens=st.short_memory_max_tokens,
    )
    prompt_builder = PromptBuilder()

    llm = LlmClient(
        LlmClientConfig(
            base_url=st.lmstudio_base_url,
            model=st.lmstudio_model,
            timeout_sec=st.llm_timeout_sec,
            retry_max=st.retry_max,
        )
    )

    conv = ConversationService("characters", prompt_builder, memory, llm, repo, st)
    try:
        conv.ensure_short_memory_loaded(session)
    except Exception as e:
        log.warning("restore short memory failed: %s", e)

    # TTS server enable (best-effort) + client setup
    tts_client = None
    if st.tts_base_url:
        hs = ensure_tts_server(st.tts_base_url, st.tts_server_start_cmd, st.tts_server_cwd)
        if not hs.ok:
            print("[INFO] TTSサーバへ接続できません。音声出力は無効のまま続行します。")
            print("[INFO] config.yaml の tts.base_url / tts.server_start_cmd を確認してください。")
        try:
            tts_client = TtsClient(TtsConfig(base_url=st.tts_base_url, speaker=st.tts_speaker, output_dir=st.tts_output_dir))
        except Exception:
            tts_client = None

    controller = CUIController(conv, session_service, memory)
    controller.info(f"session: {session.id} (character_id={session.character_id})")
    controller.info("commands: /help /exit /new /reset /save /mode /config")

    def on_voice(text: str) -> None:
        if conv.settings.output_mode == "text":
            return
        if not tts_client:
            return
        try:
            wav = tts_client.synthesize_to_wav(text)
            if conv.settings.tts_autoplay:
                play_wav_best_effort(wav)
        except Exception as e:
            controller.error(f"tts: {type(e).__name__}: {e}")

    def on_command(cmd: str, args: list[str], current_session, current_char_name):
        nonlocal session

        if cmd == "help":
            controller.info("/mode [text_voice|text|voice]  : 出力モード変更")
            controller.info("/config show                 : 現在の設定を表示")
            controller.info("/config set KEY VALUE        : 設定を変更（config.yamlへ保存）")
            controller.info("   keys: output_mode, lmstudio_model, lmstudio_base_url, short_memory_turns, short_memory_max_chars, short_memory_max_tokens")
            controller.info("         tts_base_url, tts_speaker, tts_output_dir, tts_autoplay, tts_server_start_cmd, tts_server_cwd")
            return current_session, current_char_name

        if cmd == "new":
            session = session_service.create_new()
            repo.enforce_max_sessions(conv.settings.max_session_count)
            memory.clear(session.id)
            try:
                b = load_character("characters", session.character_id)
                current_char_name = (b.profile.get("character", {}).get("name") or session.character_id)
            except Exception:
                current_char_name = session.character_id
            controller.info(f"new session: {session.id}")
            return session, current_char_name

        if cmd == "reset":
            memory.clear(current_session.id)
            controller.info("short memory cleared")
            return current_session, current_char_name

        if cmd == "save":
            controller.info("saved (autosave enabled)")
            return current_session, current_char_name

        if cmd == "mode":
            if args:
                m = args[0].strip()
                if m in ("text_voice", "text", "voice"):
                    conv.settings.output_mode = m
                    controller.info(f"output_mode -> {m}")
                    save_settings_to_yaml(conv.settings)
                else:
                    controller.error("mode must be text_voice/text/voice")
            else:
                controller.info(f"output_mode = {conv.settings.output_mode}")
            return current_session, current_char_name

        if cmd == "config":
            sub = args[0] if args else ""
            if sub == "show" or sub == "":
                controller.info(f"output_mode={conv.settings.output_mode}")
                controller.info(f"lmstudio_base_url={conv.settings.lmstudio_base_url}")
                controller.info(f"lmstudio_model={conv.settings.lmstudio_model}")
                controller.info(f"short_memory_turns={conv.settings.short_memory_turns}")
                controller.info(f"short_memory_max_chars={conv.settings.short_memory_max_chars}")
                controller.info(f"short_memory_max_tokens={conv.settings.short_memory_max_tokens}")
                controller.info(f"tts_base_url={conv.settings.tts_base_url}")
                controller.info(f"tts_server_start_cmd={conv.settings.tts_server_start_cmd}")
                controller.info(f"tts_server_cwd={conv.settings.tts_server_cwd}")
                controller.info(f"rag_top_k_episodes={conv.settings.rag_top_k_episodes}")
                controller.info(f"rag_top_k_log_messages={conv.settings.rag_top_k_log_messages}")
            elif sub == "set" and len(args) >= 3:
                key = args[1]
                val = " ".join(args[2:])
                if key in ("output_mode", "lmstudio_base_url", "lmstudio_model"):
                    setattr(conv.settings, key, val)
                elif key in ("short_memory_turns", "short_memory_max_chars", "short_memory_max_tokens", "max_session_count", "rag_top_k_episodes", "rag_top_k_log_messages", "tts_speaker"):
                    try:
                        setattr(conv.settings, key, int(val))
                    except ValueError:
                        controller.error("value must be int")
                elif key in ("tts_base_url", "tts_output_dir"):
                    setattr(conv.settings, key, val)
                elif key in ("tts_server_cwd",):
                    setattr(conv.settings, key, val)
                elif key in ("tts_server_start_cmd",):
                    # value is a command line; split by spaces (no shell). For paths with spaces, set in config.yaml directly.
                    cmd_list = args[2:]
                    conv.settings.tts_server_start_cmd = cmd_list
                elif key in ("tts_autoplay",):
                    setattr(conv.settings, key, val.strip().lower() in ("1","true","yes","y","on"))
                else:
                    controller.error("unknown key")
                    return current_session, current_char_name

                save_settings_to_yaml(conv.settings)
                controller.info("config saved")
            else:
                controller.error("usage: /config show | /config set KEY VALUE")
            return current_session, current_char_name

        return current_session, current_char_name

    try:
        controller.run(session, char_name, on_command, on_voice)
    except Exception as e:
        log.exception("fatal: %s", e)
        print(f"[ERROR] fatal: {type(e).__name__}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
