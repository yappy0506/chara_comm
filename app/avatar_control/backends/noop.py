from __future__ import annotations

from app.avatar_control.contracts import AvatarBackend, AvatarCommand


class NoopAvatarBackend(AvatarBackend):
    def dispatch(self, commands: list[AvatarCommand]) -> None:
        _ = commands
