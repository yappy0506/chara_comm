from __future__ import annotations
import logging
from pathlib import Path

from app.config.settings import load_settings
from app.infra.db import connect
from app.infra.repositories import LogRepository
from app.infra.lmstudio import health_check, try_start_lm_studio, guidance_message
from app.infra.llm_client import LlmClient, LlmClientConfig

from app.domain.prompt_builder import PromptBuilder
from app.domain.memory_manager import MemoryManager
from app.domain.character_loader import load_character

from app.usecases.session_service import SessionService
from app.usecases.conversation_service import ConversationService
from app.ui.cui_controller import CUIController

def _setup_logging(log_path: str) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

def main() -> None:
    st = load_settings()
    _setup_logging(st.log_path)
    log = logging.getLogger("app")

    conn = connect(st.db_path)
    repo = LogRepository(conn)
    repo.enforce_max_sessions(st.max_session_count)

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

    try:
        bundle = load_character("characters", session.character_id)
        char_name = (bundle.profile.get('character', {}).get('name') or session.character_id)
    except Exception:
        char_name = session.character_id

    memory = MemoryManager(short_memory_turns=st.short_memory_turns)
    prompt_builder = PromptBuilder()
    llm = LlmClient(LlmClientConfig(
        base_url=st.lmstudio_base_url,
        model=st.lmstudio_model,
        timeout_sec=st.llm_timeout_sec,
        retry_max=st.retry_max
    ))
    conv = ConversationService("characters", prompt_builder, memory, llm, repo)
    try:
        conv.ensure_short_memory_loaded(session)
    except Exception as e:
        log.warning("restore short memory failed: %s", e)

    controller = CUIController(conv, session_service, memory)
    controller.info(f"session: {session.id} (character_id={session.character_id})")
    controller.info("commands: /exit /new /reset /save")

    def on_command(cmd: str, current_session, current_char_name):
        nonlocal session
        if cmd == "new":
            session = session_service.create_new()
            repo.enforce_max_sessions(st.max_session_count)
            memory.clear(session.id)
            try:
                b = load_character("characters", session.character_id)
                current_char_name = (b.profile.get('character', {}).get('name') or session.character_id)
            except Exception:
                current_char_name = session.character_id
            controller.info(f"new session: {session.id}")
            return session, current_char_name

        if cmd == "reset":
            memory.clear(current_session.id)
            controller.info("short memory cleared")
            return current_session, current_char_name

        if cmd == "save":
            controller.info("saved (noop; autosave enabled)")
            return current_session, current_char_name

        return current_session, current_char_name

    try:
        controller.run(session, char_name, on_command)
    except Exception as e:
        log.exception("fatal: %s", e)
        print(f"[ERROR] fatal: {type(e).__name__}: {e}")
    finally:
        try: conn.close()
        except Exception: pass
