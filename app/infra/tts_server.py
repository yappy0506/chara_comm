from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


@dataclass(frozen=True)
class TtsServerStatus:
    ok: bool
    detail: str = ""


def tts_health_check(base_url: str, timeout_sec: float = 2.0) -> TtsServerStatus:
    """Best-effort health check.

    Style-Bert-VITS2 JP-Extra / Bert-VITS2系のサーバは環境によりエンドポイントが揺れるため、
    代表的なパスを順に試す。
    """
    base = (base_url or "").rstrip("/")
    if not base:
        return TtsServerStatus(ok=False, detail="base_url is empty")

    candidates = ["/health", "/docs", "/openapi.json"]
    for p in candidates:
        try:
            r = requests.get(base + p, timeout=timeout_sec)
            if 200 <= r.status_code < 500:  # 404でも生存は分かる
                return TtsServerStatus(ok=True, detail=f"reachable: {p} ({r.status_code})")
        except Exception:
            continue
    return TtsServerStatus(ok=False, detail="unreachable")


def try_start_tts_server(start_cmd: list[str], cwd: Optional[str] = None) -> bool:
    """Best-effort server startup.

    - start_cmd が空の場合は何もしない
    - 起動に失敗しても例外は投げない（仕様: ベストエフォート）
    """
    if not start_cmd:
        return False

    try:
        workdir = Path(cwd).expanduser() if cwd else None
        subprocess.Popen(
            start_cmd,
            cwd=str(workdir) if workdir else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
        return True
    except Exception:
        return False


def ensure_tts_server(base_url: str, start_cmd: list[str], cwd: Optional[str] = None, wait_sec: float = 5.0) -> TtsServerStatus:
    """起動済みならOK、未起動なら起動を試みて再チェックする。"""
    hs = tts_health_check(base_url)
    if hs.ok:
        return hs

    if try_start_tts_server(start_cmd=start_cmd, cwd=cwd):
        # wait for boot
        deadline = time.time() + max(0.0, wait_sec)
        while time.time() < deadline:
            time.sleep(0.5)
            hs2 = tts_health_check(base_url)
            if hs2.ok:
                return hs2
        return TtsServerStatus(ok=False, detail="started but still unreachable")

    return hs
