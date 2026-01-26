from __future__ import annotations
import sqlite3, json
from datetime import datetime, timezone
from typing import Optional
from app.domain.models import Session, Message

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class LogRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert_session(self, session: Session) -> None:
        self.conn.execute(
            """INSERT INTO sessions(session_id, character_id, title, created_at, updated_at)
                 VALUES (?, ?, ?, ?, ?)
                 ON CONFLICT(session_id) DO UPDATE SET
                   character_id=excluded.character_id,
                   title=COALESCE(excluded.title, sessions.title),
                   updated_at=excluded.updated_at""",
            (session.id, session.character_id, session.title, _now_iso(), _now_iso())
        )
        self.conn.commit()

    def touch_session(self, session_id: str) -> None:
        self.conn.execute("UPDATE sessions SET updated_at=? WHERE session_id=?", (_now_iso(), session_id))
        self.conn.commit()

    def get_latest_session(self) -> Optional[Session]:
        row = self.conn.execute(
            "SELECT session_id, character_id, title FROM sessions ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return Session(id=row["session_id"], character_id=row["character_id"], title=row["title"], created_at=0.0, updated_at=0.0)

    def count_sessions(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"])

    def list_sessions_oldest_first(self) -> list[str]:
        rows = self.conn.execute("SELECT session_id FROM sessions ORDER BY created_at ASC").fetchall()
        return [r["session_id"] for r in rows]

    def delete_session(self, session_id: str) -> None:
        self.conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
        self.conn.commit()

    def enforce_max_sessions(self, max_count: int) -> None:
        if max_count <= 0:
            return
        while self.count_sessions() > max_count:
            oldest = self.list_sessions_oldest_first()
            if not oldest:
                break
            self.delete_session(oldest[0])

    def add_message(self, msg: Message) -> None:
        self.conn.execute(
            """INSERT INTO messages(message_id, session_id, role, content, meta_json, created_at)
                 VALUES (?, ?, ?, ?, ?, ?)""",
            (msg.id, msg.session_id, msg.role, msg.content, json.dumps(msg.meta, ensure_ascii=False), _now_iso())
        )
        self.touch_session(msg.session_id)
        self.conn.commit()

    def fetch_recent_messages(self, session_id: str, limit: int) -> list[Message]:
        rows = self.conn.execute(
            """SELECT message_id, role, content, meta_json
                 FROM messages WHERE session_id=?
                 ORDER BY created_at DESC LIMIT ?""",
            (session_id, max(0, limit))
        ).fetchall()
        rows = list(reversed(rows))
        out: list[Message] = []
        for r in rows:
            try:
                meta = json.loads(r["meta_json"] or "{}")
            except Exception:
                meta = {}
            out.append(Message(
                id=r["message_id"],
                session_id=session_id,
                role=r["role"],
                content=r["content"],
                created_at=0.0,
                meta=meta if isinstance(meta, dict) else {},
            ))
        return out


def fetch_recent_message_texts(self, session_id: str, limit: int) -> list[tuple[str, str]]:
    """Return (role, content) pairs for recent messages (newest first)."""
    rows = self.conn.execute(
        "SELECT role, content FROM messages WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
        (session_id, max(0, limit))
    ).fetchall()
    return [(r["role"], r["content"]) for r in rows]
