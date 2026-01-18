from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _tokenize(text: str) -> list[str]:
    """Very small tokenizer (best-effort, no external deps)."""
    text = (text or "").lower().replace("\n", " ")
    parts: list[str] = []

    # whitespace tokens (English/romaji)
    for p in text.split():
        p = p.strip()
        if p:
            parts.append(p)

    # 2-gram tokens for Japanese/CJK characters (rough but dependency-free)
    cjk = ''.join(ch for ch in text if ('぀' <= ch <= 'ヿ') or ('一' <= ch <= '鿿'))
    for i in range(max(0, len(cjk) - 1)):
        parts.append(cjk[i:i+2])

    return parts


def _score(query: str, doc: str) -> int:
    q = set(_tokenize(query))
    if not q:
        return 0
    d = set(_tokenize(doc))
    return len(q & d)


@dataclass(frozen=True)
class RagHit:
    title: str
    snippet: str


def retrieve_episodes(query: str, episodes_yaml: dict[str, Any], top_k: int) -> list[RagHit]:
    eps = episodes_yaml.get('episodes') if isinstance(episodes_yaml.get('episodes'), list) else []
    scored = []
    for ep in eps:
        if not isinstance(ep, dict):
            continue
        tell = ep.get('tellable') if isinstance(ep.get('tellable'), dict) else {}
        if tell.get('allow', True) is False:
            continue
        title = str(ep.get('title', '')).strip()
        summary = str(ep.get('summary', '')).strip()
        key_lines = tell.get('key_lines') if isinstance(tell.get('key_lines'), list) else []
        doc = ' '.join([title, summary] + [str(x) for x in key_lines])
        scored.append((_score(query, doc), title, summary, key_lines))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[RagHit] = []
    for s, title, summary, key_lines in scored[: max(0, top_k)]:
        if s <= 0:
            continue
        snippet = summary
        if key_lines:
            snippet += ' / ' + ' / '.join([str(x) for x in key_lines[:2]])
        out.append(RagHit(title=title, snippet=snippet))
    return out


def retrieve_logs(query: str, role_contents: list[tuple[str, str]], top_k: int) -> list[RagHit]:
    scored = []
    for role, content in role_contents:
        doc = str(content or '')
        scored.append((_score(query, doc), role, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[RagHit] = []
    for s, role, doc in scored[: max(0, top_k)]:
        if s <= 0:
            continue
        snippet = doc.replace('\n', ' ')
        if len(snippet) > 180:
            snippet = snippet[:180] + '…'
        out.append(RagHit(title=f'log:{role}', snippet=snippet))
    return out
