from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.avatar_control.contracts import AvatarBackend
from app.avatar_control.mapper import AvatarActionMapper


@dataclass
class AvatarMotionService:
    enabled: bool
    mapper: AvatarActionMapper
    backend: AvatarBackend

    def drive(self, actions: list[Any], emotion: dict[str, Any]) -> None:
        if not self.enabled:
            return
        commands = self.mapper.map_actions(actions, emotion)
        if not commands:
            return
        try:
            self.backend.dispatch(commands)
        except Exception as e:
            logging.getLogger("app.avatar").warning("avatar dispatch failed: %s", e)
