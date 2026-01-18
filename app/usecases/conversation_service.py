from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import Settings
from app.domain.models import Session, StructuredReply, new_message
from app.domain.memory_manager import MemoryManager
from app.domain.prompt_builder import PromptBuilder
from app.domain.character_loader import load_character
from app.domain.rag import retrieve_episodes, retrieve_logs
from app.infra.llm_client import LlmClient
from app.infra.repositories import LogRepository


@dataclass
class ConversationService:
    characters_dir: str
    prompt_builder: PromptBuilder
    memory: MemoryManager
    llm: LlmClient
    repo: LogRepository
    settings: Settings

    def ensure_short_memory_loaded(self, session: Session) -> None:
        msgs = self.repo.fetch_recent_messages(session.id, self.memory.short_memory_turns * 2)
        self.memory.load(session.id, msgs)

    def handle_turn(self, session: Session, user_text: str) -> StructuredReply:
        # save user message
        um = new_message(session.id, "user", user_text)
        self.repo.add_message(um)
        self.memory.add(um)

        bundle = load_character(self.characters_dir, session.character_id)

        # RAG (best-effort)
        rag_hits: list[tuple[str, str]] = []
        try:
            ep_hits = retrieve_episodes(user_text, bundle.episodes, top_k=self.settings.rag_top_k_episodes)
            rag_hits += [(h.title, h.snippet) for h in ep_hits]
        except Exception:
            pass

        try:
            # pull older logs for relevance search (beyond short memory)
            role_contents = self.repo.fetch_recent_message_texts(session.id, limit=200)
            log_hits = retrieve_logs(user_text, role_contents, top_k=self.settings.rag_top_k_log_messages)
            rag_hits += [(h.title, h.snippet) for h in log_hits]
        except Exception:
            pass

        system_prompt = self.prompt_builder.build_system_prompt(bundle, rag_hits=rag_hits, mode="default")
        raw = self.llm.chat(system_prompt, self.memory.get_pairs(session.id))

        reply = StructuredReply(utterance=raw, emotion={}, actions=[])

        am = new_message(session.id, "assistant", reply.utterance, meta={"emotion": reply.emotion, "actions": reply.actions})
        self.repo.add_message(am)
        self.memory.add(am)
        return reply
