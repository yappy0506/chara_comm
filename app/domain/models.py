from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Any
import time, uuid

Role = Literal["user","assistant","system"]

@dataclass(frozen=True)
class Session:
    id: str
    character_id: str
    created_at: float
    updated_at: float
    title: str | None = None

@dataclass(frozen=True)
class Message:
    id: str
    session_id: str
    role: Role
    content: str
    created_at: float
    meta: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class StructuredReply:
    utterance: str
    emotion: dict[str, Any] = field(default_factory=dict)
    actions: list[Any] = field(default_factory=list)

def new_session(character_id: str) -> Session:
    now = time.time()
    return Session(id=str(uuid.uuid4()), character_id=character_id, created_at=now, updated_at=now)

def new_message(session_id: str, role: Role, content: str, meta: dict[str, Any] | None = None) -> Message:
    return Message(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role=role,
        content=content,
        created_at=time.time(),
        meta=meta or {},
    )
