from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from websocket import create_connection

from app.avatar_control.contracts import AvatarBackend, AvatarCommand


@dataclass
class VtubeStudioBackendConfig:
    ws_url: str
    plugin_name: str
    plugin_developer: str
    auth_token_path: str
    timeout_sec: float


class VtubeStudioBackend(AvatarBackend):
    def __init__(self, cfg: VtubeStudioBackendConfig):
        self.cfg = cfg

    def dispatch(self, commands: list[AvatarCommand]) -> None:
        if not commands:
            return

        ws = create_connection(self.cfg.ws_url, timeout=self.cfg.timeout_sec)
        try:
            self._authenticate(ws)
            hotkey_id_map = self._fetch_hotkeys(ws)
            for cmd in commands:
                if cmd.command_type != "trigger_hotkey":
                    continue
                raw_hotkey = str(cmd.payload.get("hotkey") or "").strip()
                if not raw_hotkey:
                    continue
                hotkey_id = hotkey_id_map.get(raw_hotkey.lower(), raw_hotkey)
                self._send(
                    ws,
                    "HotkeyTriggerRequest",
                    {
                        "hotkeyID": hotkey_id,
                    },
                )
        finally:
            ws.close()

    def _authenticate(self, ws) -> None:
        token_path = Path(self.cfg.auth_token_path)
        token = token_path.read_text(encoding="utf-8").strip() if token_path.exists() else ""

        if not token:
            r = self._send(
                ws,
                "AuthenticationTokenRequest",
                {
                    "pluginName": self.cfg.plugin_name,
                    "pluginDeveloper": self.cfg.plugin_developer,
                },
            )
            token = str(r.get("data", {}).get("authenticationToken") or "").strip()
            if token:
                token_path.parent.mkdir(parents=True, exist_ok=True)
                token_path.write_text(token, encoding="utf-8")

        self._send(
            ws,
            "AuthenticationRequest",
            {
                "pluginName": self.cfg.plugin_name,
                "pluginDeveloper": self.cfg.plugin_developer,
                "authenticationToken": token,
            },
        )

    def _fetch_hotkeys(self, ws) -> dict[str, str]:
        resp = self._send(ws, "HotkeysInCurrentModelRequest", {})
        items = resp.get("data", {}).get("availableHotkeys", [])
        out: dict[str, str] = {}
        if not isinstance(items, list):
            return out
        for item in items:
            if not isinstance(item, dict):
                continue
            hotkey_id = str(item.get("hotkeyID") or "").strip()
            name = str(item.get("name") or item.get("hotkeyName") or "").strip()
            if hotkey_id:
                out[hotkey_id.lower()] = hotkey_id
            if name and hotkey_id:
                out[name.lower()] = hotkey_id
        return out

    def _send(self, ws, message_type: str, data: dict[str, object]) -> dict[str, object]:
        payload = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": str(uuid.uuid4()),
            "messageType": message_type,
            "data": data,
        }
        ws.send(json.dumps(payload, ensure_ascii=False))
        raw = ws.recv()
        if not isinstance(raw, str):
            raise RuntimeError("VTube Studio response is not text")
        res = json.loads(raw)
        if not isinstance(res, dict):
            raise RuntimeError("VTube Studio response is invalid")
        if res.get("messageType") == "APIError":
            raise RuntimeError(f"VTube Studio API error: {res}")
        return res
