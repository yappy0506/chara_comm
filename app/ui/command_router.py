from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal

Command = Literal["exit","new","reset","save"]

@dataclass(frozen=True)
class RoutedInput:
    is_command: bool
    command: Optional[Command] = None
    text: str = ""

def route(line: str) -> RoutedInput:
    raw = (line or "").strip()
    if not raw:
        return RoutedInput(is_command=False, text="")
    if raw.startswith("/"):
        cmd = raw[1:].split()[0] if len(raw) > 1 else ""
        if cmd in ("exit","new","reset","save"):
            return RoutedInput(is_command=True, command=cmd, text="")
    return RoutedInput(is_command=False, text=raw)
