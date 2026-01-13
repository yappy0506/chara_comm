from __future__ import annotations
from dataclasses import dataclass
import sys
from app.ui.command_router import route
from app.domain.models import Session
from app.usecases.conversation_service import ConversationService
from app.usecases.session_service import SessionService
from app.domain.memory_manager import MemoryManager

@dataclass
class CUIController:
    conversation: ConversationService
    sessions: SessionService
    memory: MemoryManager

    def info(self, msg: str) -> None:
        sys.stdout.write(f"[INFO] {msg}\n"); sys.stdout.flush()

    def error(self, msg: str) -> None:
        sys.stdout.write(f"[ERROR] {msg}\n"); sys.stdout.flush()

    def prompt(self, char_name: str) -> str:
        try:
            return input(f"{char_name} > ")
        except (EOFError, KeyboardInterrupt):
            return "/exit"

    def say(self, char_name: str, utterance: str) -> None:
        sys.stdout.write(f"{char_name}: {utterance}\n"); sys.stdout.flush()

    def run(self, session: Session, char_name: str, on_command) -> None:
        while True:
            line = self.prompt(char_name)
            ri = route(line)
            if ri.is_command:
                if ri.command == "exit":
                    self.info("bye")
                    return
                session, char_name = on_command(ri.command, session, char_name)
                continue

            text = ri.text.strip()
            if not text:
                continue

            try:
                reply = self.conversation.handle_turn(session, text)
                self.say(char_name, reply.utterance)
            except TimeoutError:
                self.error("generation timeout")
            except Exception as e:
                self.error(f"{type(e).__name__}: {e}")
