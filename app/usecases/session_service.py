from __future__ import annotations
from dataclasses import dataclass
from app.domain.models import Session, new_session
from app.infra.repositories import LogRepository

@dataclass
class SessionService:
    repo: LogRepository
    default_character_id: str

    def resume_or_create(self) -> Session:
        s = self.repo.get_latest_session()
        if s:
            return s
        s = new_session(self.default_character_id)
        self.repo.upsert_session(s)
        return s

    def create_new(self, character_id: str | None = None) -> Session:
        s = new_session(character_id or self.default_character_id)
        self.repo.upsert_session(s)
        return s
