from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

from app.domain.models import Message

ChatRole = Literal["user", "assistant"]


@dataclass
class MemoryManager:
    short_memory_turns: int
    short_memory_max_chars: int
    _by_session: dict[str, list[Message]] = field(default_factory=dict)

    def get_pairs(self, session_id: str) -> list[tuple[ChatRole, str]]:
        pairs: list[tuple[ChatRole, str]] = []
        for m in self._by_session.get(session_id, []):
            if m.role == "user":
                pairs.append(("user", m.content))
            elif m.role == "assistant":
                pairs.append(("assistant", m.content))

        # trim by char budget (best-effort)
        if self.short_memory_max_chars > 0:
            total = 0
            kept: list[tuple[ChatRole, str]] = []
            for role, content in reversed(pairs):
                total += len(content)
                kept.append((role, content))
                if total >= self.short_memory_max_chars:
                    break
            pairs = list(reversed(kept))

        return pairs

    def load(self, session_id: str, history: list[Message]) -> None:
        self._by_session[session_id] = list(history)
        self._trim(session_id)

    def add(self, msg: Message) -> None:
        self._by_session.setdefault(msg.session_id, []).append(msg)
        self._trim(msg.session_id)

    def clear(self, session_id: str) -> None:
        self._by_session[session_id] = []

    def _trim(self, session_id: str) -> None:
        max_msgs = max(0, self.short_memory_turns) * 2
        if max_msgs <= 0:
            return
        msgs = self._by_session.get(session_id, [])
        if len(msgs) > max_msgs:
            del msgs[: len(msgs) - max_msgs]
