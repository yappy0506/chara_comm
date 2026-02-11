from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.avatar_control.contracts import AvatarCommand


@dataclass(frozen=True)
class AvatarActionMapper:
    """LLM actions/emotion をバックエンド非依存コマンドへ変換する。"""

    action_to_hotkey: dict[str, str]
    emotion_to_hotkey: dict[str, str]

    def map_actions(self, actions: list[Any], emotion: dict[str, Any]) -> list[AvatarCommand]:
        commands: list[AvatarCommand] = []

        for action in actions:
            if not isinstance(action, dict):
                continue

            # action例: {"type":"hotkey","name":"smile"}
            action_name = str(action.get("name") or action.get("value") or "").strip().lower()
            if not action_name:
                continue

            hotkey = self.action_to_hotkey.get(action_name)
            if hotkey:
                commands.append(AvatarCommand(command_type="trigger_hotkey", payload={"hotkey": hotkey}))

        if commands:
            return commands

        # actionsが無い場合は emotion から1つだけ補完（任意）
        dominant = self._dominant_emotion(emotion)
        if dominant:
            hotkey = self.emotion_to_hotkey.get(dominant)
            if hotkey:
                commands.append(AvatarCommand(command_type="trigger_hotkey", payload={"hotkey": hotkey}))
        return commands

    @staticmethod
    def _dominant_emotion(emotion: dict[str, Any]) -> str | None:
        if not isinstance(emotion, dict) or not emotion:
            return None
        winner: tuple[str, float] | None = None
        for k, v in emotion.items():
            try:
                score = float(v)
            except (TypeError, ValueError):
                continue
            if winner is None or score > winner[1]:
                winner = (str(k).lower(), score)
        if not winner:
            return None
        return winner[0]
