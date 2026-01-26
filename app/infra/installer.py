from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class StyleBertVits2InstallConfig:
    enabled: bool = True
    repo_url: str = "https://github.com/litagin02/Style-Bert-VITS2.git"
    repo_ref: str = "main"
    install_dir: str = "third_party/Style-Bert-VITS2"
    requirements_file: str = "requirements.txt"
    marker_file: str = "data/.style_bert_vits2_installed"
    models_marker_file: str = "data/.style_bert_vits2_models_ready"
    download_models: bool = True

def _run(cmd: list[str], cwd: Optional[str] = None) -> int:
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=False)
    if p.stdout:
        for _ in range(300):
            line = p.stdout.readline()
            if not line:
                break
            print("[INFO] " + line.rstrip())
    return p.wait()

def _ensure_git_installed() -> bool:
    """Best-effort git installer (Windows via winget)."""
    try:
        subprocess.check_output(["git", "--version"], stderr=subprocess.STDOUT, text=True)
        return True
    except Exception:
        pass

    # Windows: try winget
    if os.name == "nt":
        try:
            print("[INFO] git が見つかりません。winget でインストールを試みます...")
            rc = _run(["winget", "install", "--id", "Git.Git", "-e", "--source", "winget"])
            if rc == 0:
                subprocess.check_output(["git", "--version"], stderr=subprocess.STDOUT, text=True)
                print("[INFO] git のインストールに成功しました。")
                return True
        except Exception:
            pass

    print("[ERROR] git を自動インストールできませんでした。手動で git をインストールしてください。")
    return False

def _has_git() -> bool:

    try:
        subprocess.check_output(["git", "--version"], stderr=subprocess.STDOUT, text=True)
        return True
    except Exception:
        return False

def ensure_style_bert_vits2_installed(cfg: StyleBertVits2InstallConfig) -> None:
    """First-run bootstrapper for Style-Bert-VITS2 (best-effort)."""
    if not cfg.enabled:
        return
    marker = Path(cfg.marker_file)
    if marker.exists():
        return

    marker.parent.mkdir(parents=True, exist_ok=True)
    install_dir = Path(cfg.install_dir)

    print("[INFO] 初回起動: Style-Bert-VITS2JP-Extra をセットアップします（ベストエフォート）")
    print("[INFO] ※ 依存関係のダウンロードが発生します。ネットワークが必要です。")

    if not _ensure_git_installed():
        print("[ERROR] git が見つかりません。git をインストールしてから再起動してください。")
        return

    if not install_dir.exists():
        install_dir.parent.mkdir(parents=True, exist_ok=True)
        rc = _run(["git", "clone", "--depth", "1", "--branch", cfg.repo_ref, cfg.repo_url, str(install_dir)])
        if rc != 0:
            print("[ERROR] git clone に失敗しました。手動でセットアップしてください。")
            return
    else:
        _run(["git", "fetch", "--all"], cwd=str(install_dir))
        _run(["git", "checkout", cfg.repo_ref], cwd=str(install_dir))
        _run(["git", "pull"], cwd=str(install_dir))

    req = install_dir / cfg.requirements_file
    if not req.exists():
        print(f"[ERROR] requirements が見つかりません: {req}")
        return

    print("[INFO] pip で依存関係をインストールします...")
    rc = _run([sys.executable, "-m", "pip", "install", "-r", str(req)])
    if rc != 0:
        print("[ERROR] pip install に失敗しました。手動でセットアップしてください。")
        return

    # Download model assets (JP-Extraなど)
    if getattr(cfg, "download_models", True):
        models_marker = Path(getattr(cfg, "models_marker_file", "data/.style_bert_vits2_models_ready"))
        if not models_marker.exists():
            print("[INFO] 事前学習モデル（JP-Extra含む）をダウンロードします...（時間がかかる場合があります）")
            # Style-Bert-VITS2側の公式スクリプトに委譲（必要なモデルとデフォルトTTSモデルを取得）
            rc = _run([sys.executable, "initialize.py"], cwd=str(install_dir))
            if rc != 0:
                print("[ERROR] モデルダウンロード（initialize.py）に失敗しました。ネットワーク環境を確認し、手動で initialize.py を実行してください。")
            else:
                models_marker.parent.mkdir(parents=True, exist_ok=True)
                models_marker.write_text("ready\n", encoding="utf-8")
                print("[INFO] モデルデータのダウンロードが完了しました。")
        else:
            print("[INFO] モデルデータは既にセットアップ済みです。")
    else:
        print("[INFO] config によりモデルの自動取得をスキップしました。")

    marker.write_text("installed\n", encoding="utf-8")

    print("[INFO] Style-Bert-VITS2 のセットアップが完了しました。")
