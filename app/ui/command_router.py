from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RoutedInput:
    is_command: bool
    command: str | None = None
    args: list[str] | None = None
    text: str = ""


def route(line: str) -> RoutedInput:
    raw = (line or "").strip()
    if not raw:
        return RoutedInput(is_command=False, text="")

    if raw.startswith("/"):
        parts = raw[1:].split()
        cmd = parts[0] if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        # known commands
        if cmd in ("exit", "new", "reset", "save", "mode", "config", "help"):
            return RoutedInput(is_command=True, command=cmd, args=args, text="")

    return RoutedInput(is_command=False, text=raw)
