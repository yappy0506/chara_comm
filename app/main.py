from __future__ import annotations

import argparse
import logging
import sys
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
from app.domain.models import StructuredReply
from app.avatar_control.factory import build_avatar_motion_service


def _setup_logging(log_path: str) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _resolve_char_name(character_id: str) -> str:
    try:
        bundle = load_character("characters", character_id)
        return bundle.profile.get("character", {}).get("name") or bundle.profile.get("name") or character_id
    except Exception:
        return character_id


def _list_character_ids(characters_dir: str) -> list[str]:
    base = Path(characters_dir)
    if not base.exists():
        return []
    return sorted([p.name for p in base.iterdir() if p.is_dir()])


def _parse_character_arg(argv: list[str]) -> str | None:
    for i, arg in enumerate(argv):
        if arg in ("-c", "--character") and i + 1 < len(argv):
            return argv[i + 1]
    return None


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
    arg_character_id = _parse_character_arg(sys.argv[1:])
    if arg_character_id:
        try:
            load_character("characters", arg_character_id)
            session = session_service.create_new(arg_character_id)
        except Exception as e:
            print(f"[WARN] character '{arg_character_id}' を読み込めません: {type(e).__name__}")
            session = session_service.resume_or_create()
    else:
        session = session_service.resume_or_create()

    char_name = _resolve_char_name(session.character_id)

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
    avatar_motion = build_avatar_motion_service(st)
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
        nonlocal session, tts_client, avatar_motion

        if cmd == "help":
            controller.info("/mode [text_voice|text|voice]  : 出力モード変更")
            controller.info("/config show                 : 現在の設定を表示")
            controller.info("/config set KEY VALUE        : 設定を変更（config.yamlへ保存）")
            controller.info("/character list              : 利用可能なキャラクター一覧")
            controller.info("/character set ID            : キャラクター変更（新規セッション）")
            controller.info("/character show              : 現在のキャラクターIDを表示")
            controller.info("   keys: output_mode, lmstudio_model, lmstudio_base_url, llm_temperature, llm_top_p, llm_max_tokens, llm_presence_penalty, llm_frequency_penalty, llm_repeat_retry_max")
            controller.info("         short_memory_turns, short_memory_max_chars, short_memory_max_tokens")
            controller.info("         max_session_count, tts_base_url, tts_speaker, tts_style, tts_output_dir, tts_autoplay, tts_timeout_sec, tts_retry_max, tts_text_limit")
            controller.info("         tts_model_name, tts_server_start_cmd, tts_server_cwd")
            controller.info("         avatar_enabled, avatar_backend")
            controller.info("         vtube_studio_ws_url, vtube_studio_plugin_name, vtube_studio_plugin_developer, vtube_studio_auth_token_path, vtube_studio_timeout_sec")
            controller.info("         db_path, log_path")
            controller.info("/character show              : 現在のキャラクターを表示")
            controller.info("/character list              : キャラクター一覧を表示")
            controller.info("/character set <ID>          : キャラクターを切り替え")
            return current_session, current_char_name

        if cmd == "new":
            session = session_service.create_new()
            repo.enforce_max_sessions(conv.settings.max_session_count)
            memory.clear(session.id)
            current_char_name = _resolve_char_name(session.character_id)
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
                controller.info(f"avatar_enabled={conv.settings.avatar_enabled}")
                controller.info(f"avatar_backend={conv.settings.avatar_backend}")
                controller.info(f"vtube_studio_ws_url={conv.settings.vtube_studio_ws_url}")
                controller.info(f"vtube_studio_plugin_name={conv.settings.vtube_studio_plugin_name}")
                controller.info(f"vtube_studio_plugin_developer={conv.settings.vtube_studio_plugin_developer}")
                controller.info(f"vtube_studio_auth_token_path={conv.settings.vtube_studio_auth_token_path}")
                controller.info(f"vtube_studio_timeout_sec={conv.settings.vtube_studio_timeout_sec}")
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

                avatar_keys = {
                    "avatar_enabled",
                    "avatar_backend",
                    "vtube_studio_ws_url",
                    "vtube_studio_plugin_name",
                    "vtube_studio_plugin_developer",
                    "vtube_studio_auth_token_path",
                    "vtube_studio_timeout_sec",
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
                elif key in ("tts_timeout_sec", "vtube_studio_timeout_sec"):
                    try:
                        setattr(conv.settings, key, float(val))
                    except ValueError:
                        controller.error("value must be float")
                        return current_session, current_char_name
                elif key in ("avatar_backend", "vtube_studio_ws_url", "vtube_studio_plugin_name", "vtube_studio_plugin_developer", "vtube_studio_auth_token_path"):
                    setattr(conv.settings, key, val)
                elif key in ("db_path", "log_path"):
                    setattr(conv.settings, key, val)
                elif key in ("tts_server_cwd",):
                    setattr(conv.settings, key, val)
                elif key in ("tts_server_start_cmd",):
                    # value is a command line; split by spaces (no shell). For paths with spaces, set in config.yaml directly.
                    cmd_list = args[2:]
                    conv.settings.tts_server_start_cmd = cmd_list
                elif key in ("tts_autoplay", "avatar_enabled"):
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
                if key in avatar_keys:
                    avatar_motion = build_avatar_motion_service(conv.settings)
                controller.info("config saved")
            else:
                controller.error("usage: /config show | /config set KEY VALUE")
            return current_session, current_char_name

        if cmd == "character":
            sub = args[0] if args else "show"
            if sub == "list":
                ids = _list_character_ids("characters")
                if ids:
                    controller.info("available: " + ", ".join(ids))
                else:
                    controller.info("available: (none)")
            elif sub == "set" and len(args) >= 2:
                target = args[1]
                try:
                    load_character("characters", target)
                except Exception as e:
                    controller.error(f"character not found: {target} ({type(e).__name__})")
                    return current_session, current_char_name
                session = session_service.create_new(target)
                repo.enforce_max_sessions(conv.settings.max_session_count)
                memory.clear(session.id)
                current_char_name = _resolve_char_name(target)
                controller.info(f"character -> {target}")
                controller.info(f"new session: {session.id}")
                return session, current_char_name
            elif sub == "show":
                controller.info(f"character_id={current_session.character_id}")
            else:
                controller.error("usage: /character list | /character set ID | /character show")
            return current_session, current_char_name

        return current_session, current_char_name

    def on_reply(reply: StructuredReply) -> None:
        avatar_motion.drive(reply.actions, reply.emotion)

    try:
        controller.run(session, char_name, on_command, on_voice, on_reply=on_reply)
    except Exception as e:
        log.exception("fatal: %s", e)
        print(f"[ERROR] fatal: {type(e).__name__}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
