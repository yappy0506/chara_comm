from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AvatarCommand:
    """アバター制御バックエンドへ渡す標準コマンド。"""

    command_type: str
    payload: dict[str, Any] = field(default_factory=dict)


class AvatarBackend(Protocol):
    """VTSなど具体実装を差し替えるための抽象IF。"""

    def dispatch(self, commands: list[AvatarCommand]) -> None:
        ...
