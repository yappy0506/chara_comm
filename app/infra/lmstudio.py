from __future__ import annotations
from dataclasses import dataclass
import subprocess, requests

@dataclass(frozen=True)
class HealthStatus:
    ok: bool
    detail: str

def health_check(base_url: str, timeout_s: float = 2.5) -> HealthStatus:
    url = base_url.rstrip("/") + "/models"
    try:
        r = requests.get(url, timeout=timeout_s)
        return HealthStatus(r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        return HealthStatus(False, f"{type(e).__name__}: {e}")

def try_start_lm_studio(exe_path: str) -> bool:
    try:
        subprocess.Popen([exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def guidance_message(base_url: str) -> str:
    return (
        "LM Studio に接続できません。\n"
        f"- URL: {base_url}\n"
        "- LM Studio を起動し、Local Server(OpenAI互換API)を有効化してください\n"
        "- モデルをロードしてから再度お試しください"
    )
