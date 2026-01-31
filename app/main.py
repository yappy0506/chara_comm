from __future__ import annotations

import logging
import argparse
from pathlib import Path

from app.config.settings import load_settings, save_settings_to_yaml, sync_llm_tts_limits
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


def _list_character_ids(characters_dir: str) -> list[str]:
    base = Path(characters_dir)
    if not base.exists():
        return []
    return sorted([p.name for p in base.iterdir() if p.is_dir()])


def _resolve_character_name(characters_dir: str, character_id: str) -> str:
    try:
        bundle = load_character(characters_dir, character_id)
        name = bundle.profile.get("name")
        if isinstance(bundle.profile.get("character"), dict):
            name = name or bundle.profile["character"].get("name")
        return name or character_id
    except Exception:
        return character_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Character conversation app")
    parser.add_argument("--character-id", help="起動時に使用するキャラクターID")
    args = parser.parse_args()

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
    character_ids = _list_character_ids("characters")
    if args.character_id:
        if args.character_id not in character_ids:
            print(f"[ERROR] character_id が見つかりません: {args.character_id}")
            if character_ids:
                print("[INFO] 利用可能なキャラクター: " + ", ".join(character_ids))
            session = session_service.resume_or_create()
        else:
            session = session_service.create_new(args.character_id)
            repo.enforce_max_sessions(st.max_session_count)
    else:
        session = session_service.resume_or_create()

    char_name = _resolve_character_name("characters", session.character_id)

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
            temperature=st.llm_temperature,
            top_p=st.llm_top_p,
            max_tokens=st.llm_max_tokens,
            presence_penalty=st.llm_presence_penalty,
            frequency_penalty=st.llm_frequency_penalty,
        )
    )

    conv = ConversationService("characters", prompt_builder, memory, llm, repo, st)
    try:
        conv.ensure_short_memory_loaded(session)
    except Exception as e:
        log.warning("restore short memory failed: %s", e)

    # TTS server enable (best-effort) + client setup
    tts_client = None

    def refresh_tts_client() -> None:
        nonlocal tts_client
        tts_client = None
        if not conv.settings.tts_base_url:
            return
        hs = ensure_tts_server(
            conv.settings.tts_base_url,
            conv.settings.tts_server_start_cmd,
            conv.settings.tts_server_cwd,
        )
        if not hs.ok:
            print("[INFO] TTSサーバへ接続できません。音声出力は無効のまま続行します。")
            print("[INFO] config.yaml の tts.base_url / tts.server_start_cmd を確認してください。")
            return
        try:
            effective_limit = conv.settings.tts_text_limit
            if conv.settings.tts_server_limit and (
                effective_limit <= 0 or effective_limit > conv.settings.tts_server_limit
            ):
                effective_limit = conv.settings.tts_server_limit
            tts_client = TtsClient(
                TtsConfig(
                    base_url=conv.settings.tts_base_url,
                    model_name=conv.settings.tts_model_name,
                    speaker=conv.settings.tts_speaker,
                    style=conv.settings.tts_style,
                    output_dir=conv.settings.tts_output_dir,
                    timeout_sec=conv.settings.tts_timeout_sec,
                    retry_max=conv.settings.tts_retry_max,
                    text_limit=effective_limit,
                )
            )
        except Exception:
            tts_client = None

    refresh_tts_client()

    controller = CUIController(conv, session_service, memory)
    controller.info(f"session: {session.id} (character_id={session.character_id})")
    controller.info("commands: /help /exit /new /reset /save /mode /config /character")

    def on_voice(text: str) -> None:
        if conv.settings.output_mode == "text":
            return
        if not tts_client:
            return
        try:
            wavs = tts_client.synthesize_to_wavs(text)
            if conv.settings.tts_autoplay:
                for wav in wavs:
                    play_wav_best_effort(wav)
        except Exception as e:
            controller.error(f"tts: {type(e).__name__}: {e}")

    def on_command(cmd: str, args: list[str], current_session, current_char_name):
        nonlocal session, tts_client

        if cmd == "help":
            controller.info("/mode [text_voice|text|voice]  : 出力モード変更")
            controller.info("/config show                 : 現在の設定を表示")
            controller.info("/config set KEY VALUE        : 設定を変更（config.yamlへ保存）")
            controller.info("   keys: default_character_id, output_mode, lmstudio_model, lmstudio_base_url, llm_temperature, llm_top_p, llm_max_tokens, llm_presence_penalty, llm_frequency_penalty, llm_repeat_retry_max")
            controller.info("         short_memory_turns, short_memory_max_chars, short_memory_max_tokens")
            controller.info("         max_session_count, tts_base_url, tts_speaker, tts_style, tts_output_dir, tts_autoplay, tts_timeout_sec, tts_retry_max, tts_text_limit")
            controller.info("         tts_model_name, tts_server_start_cmd, tts_server_cwd")
            controller.info("         db_path, log_path")
            controller.info("/character show              : 現在のキャラクターを表示")
            controller.info("/character list              : キャラクター一覧を表示")
            controller.info("/character set <ID>          : キャラクターを切り替え")
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
                controller.info(f"default_character_id={conv.settings.default_character_id}")
                controller.info(f"output_mode={conv.settings.output_mode}")
                controller.info(f"lmstudio_base_url={conv.settings.lmstudio_base_url}")
                controller.info(f"lmstudio_model={conv.settings.lmstudio_model}")
                controller.info(f"llm_temperature={conv.settings.llm_temperature}")
                controller.info(f"llm_top_p={conv.settings.llm_top_p}")
                controller.info(f"llm_max_tokens={conv.settings.llm_max_tokens}")
                controller.info(f"llm_presence_penalty={conv.settings.llm_presence_penalty}")
                controller.info(f"llm_frequency_penalty={conv.settings.llm_frequency_penalty}")
                controller.info(f"llm_repeat_retry_max={conv.settings.llm_repeat_retry_max}")
                controller.info(f"short_memory_turns={conv.settings.short_memory_turns}")
                controller.info(f"short_memory_max_chars={conv.settings.short_memory_max_chars}")
                controller.info(f"short_memory_max_tokens={conv.settings.short_memory_max_tokens}")
                controller.info(f"max_session_count={conv.settings.max_session_count}")
                controller.info(f"tts_base_url={conv.settings.tts_base_url}")
                controller.info(f"tts_model_name={conv.settings.tts_model_name}")
                controller.info(f"tts_speaker={conv.settings.tts_speaker}")
                controller.info(f"tts_style={conv.settings.tts_style}")
                controller.info(f"tts_output_dir={conv.settings.tts_output_dir}")
                controller.info(f"tts_autoplay={conv.settings.tts_autoplay}")
                controller.info(f"tts_timeout_sec={conv.settings.tts_timeout_sec}")
                controller.info(f"tts_retry_max={conv.settings.tts_retry_max}")
                controller.info(f"tts_text_limit={conv.settings.tts_text_limit}")
                controller.info(f"tts_server_limit={conv.settings.tts_server_limit}")
                controller.info(f"tts_server_start_cmd={conv.settings.tts_server_start_cmd}")
                controller.info(f"tts_server_cwd={conv.settings.tts_server_cwd}")
                controller.info(f"rag_top_k_episodes={conv.settings.rag_top_k_episodes}")
                controller.info(f"rag_top_k_log_messages={conv.settings.rag_top_k_log_messages}")
                controller.info(f"db_path={conv.settings.db_path}")
                controller.info(f"log_path={conv.settings.log_path}")
            elif sub == "set" and len(args) >= 3:
                key = args[1]
                val = " ".join(args[2:])
                prev_tts_limit = conv.settings.tts_text_limit
                tts_keys = {
                    "tts_base_url",
                    "tts_model_name",
                    "tts_speaker",
                    "tts_style",
                    "tts_output_dir",
                    "tts_autoplay",
                    "tts_timeout_sec",
                    "tts_retry_max",
                    "tts_text_limit",
                    "tts_server_start_cmd",
                    "tts_server_cwd",
                }

                if key in ("output_mode", "lmstudio_base_url", "lmstudio_model", "default_character_id"):
                    setattr(conv.settings, key, val)
                elif key in ("short_memory_turns", "short_memory_max_chars", "short_memory_max_tokens", "max_session_count", "rag_top_k_episodes", "rag_top_k_log_messages", "tts_speaker", "tts_retry_max", "tts_text_limit", "llm_max_tokens", "llm_repeat_retry_max"):
                    try:
                        setattr(conv.settings, key, int(val))
                    except ValueError:
                        controller.error("value must be int")
                        return current_session, current_char_name
                    if key == "max_session_count":
                        repo.enforce_max_sessions(conv.settings.max_session_count)
                elif key in ("llm_temperature", "llm_top_p", "llm_presence_penalty", "llm_frequency_penalty"):
                    try:
                        setattr(conv.settings, key, float(val))
                    except ValueError:
                        controller.error("value must be float")
                        return current_session, current_char_name
                elif key in ("tts_base_url", "tts_output_dir", "tts_style", "tts_model_name"):
                    setattr(conv.settings, key, val)
                elif key in ("tts_timeout_sec",):
                    try:
                        setattr(conv.settings, key, float(val))
                    except ValueError:
                        controller.error("value must be float")
                        return current_session, current_char_name
                elif key in ("db_path", "log_path"):
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

                if key == "tts_text_limit":
                    sync_llm_tts_limits(conv.settings, source="tts")
                elif key == "llm_max_tokens":
                    sync_llm_tts_limits(conv.settings, source="llm")

                save_settings_to_yaml(conv.settings)
                if key in tts_keys or conv.settings.tts_text_limit != prev_tts_limit:
                    refresh_tts_client()
                controller.info("config saved")
            else:
                controller.error("usage: /config show | /config set KEY VALUE")
            return current_session, current_char_name

        if cmd == "character":
            sub = args[0] if args else ""
            if sub in ("", "show"):
                controller.info(f"current_character_id={current_session.character_id}")
                controller.info(f"current_character_name={current_char_name}")
                return current_session, current_char_name
            if sub == "list":
                if character_ids:
                    controller.info("characters: " + ", ".join(character_ids))
                else:
                    controller.error("キャラクターが見つかりません")
                return current_session, current_char_name

            if sub in ("set", "switch") and len(args) >= 2:
                target_id = args[1]
            else:
                target_id = sub

            if target_id not in character_ids:
                controller.error(f"character_id が見つかりません: {target_id}")
                if character_ids:
                    controller.info("利用可能なキャラクター: " + ", ".join(character_ids))
                return current_session, current_char_name

            session = session_service.create_new(target_id)
            repo.enforce_max_sessions(conv.settings.max_session_count)
            current_char_name = _resolve_character_name("characters", session.character_id)
            controller.info(f"character switched: {session.character_id}")
            return session, current_char_name

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
