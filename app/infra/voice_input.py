from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import queue
import subprocess
import tempfile
import time
import wave


@dataclass(frozen=True)
class VoiceInputConfig:
    sample_rate: int = 16000
    channels: int = 1
    vad_mode: int = 2
    vad_silence_ms: int = 1000
    max_record_ms: int = 15000
    whisper_cpp_path: str | None = None
    whisper_model_path: str | None = None
    whisper_language: str = "ja"
    save_audio: bool = False
    save_log: bool = False
    audio_output_dir: str = "inputs"
    log_output_dir: str = "logs/asr"


def _normalize_text(text: str) -> str:
    cleaned = " ".join((text or "").strip().split())
    cleaned = cleaned.replace(" ,", ",").replace(" .", ".")
    cleaned = cleaned.replace(" 、", "、").replace(" 。", "。")
    if cleaned and not cleaned.endswith(("。", "!", "！", "?", "？")):
        cleaned += "。"
    return cleaned


def _write_wav(path: Path, pcm_bytes: bytes, sample_rate: int, channels: int) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def _run_whisper_cpp(cfg: VoiceInputConfig, wav_path: Path) -> str:
    if not cfg.whisper_cpp_path or not cfg.whisper_model_path:
        raise RuntimeError("whisper.cpp のパスが未設定です（whisper_cpp_path / whisper_model_path）")
    out_txt = wav_path.with_suffix(".txt")
    cmd = [
        cfg.whisper_cpp_path,
        "-m",
        cfg.whisper_model_path,
        "-l",
        cfg.whisper_language,
        "-f",
        str(wav_path),
        "-otxt",
        "-of",
        str(out_txt.with_suffix("")),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return out_txt.read_text(encoding="utf-8").strip()


def capture_and_transcribe(cfg: VoiceInputConfig) -> str:
    missing: list[str] = []
    for module_name in ("sounddevice", "webrtcvad"):
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing.append(module_name)
        except Exception as exc:
            raise RuntimeError(
                f"音声入力の初期化に失敗しました: {module_name} ({type(exc).__name__}: {exc})"
            ) from exc
    if missing:
        missing_str = ", ".join(missing)
        raise RuntimeError(
            "音声入力の依存関係が不足しています: "
            f"{missing_str}. "
            "セットアップを再実行するか、次を実行してください: "
            ".venv\\Scripts\\python -m pip install -r requirements.txt"
        )

    import sounddevice as sd
    import webrtcvad

    vad = webrtcvad.Vad(cfg.vad_mode)
    frame_ms = 30
    frame_size = int(cfg.sample_rate * frame_ms / 1000)
    frame_bytes = frame_size * 2 * cfg.channels
    silence_frames = max(1, int(cfg.vad_silence_ms / frame_ms))
    max_frames = max(1, int(cfg.max_record_ms / frame_ms))

    q: queue.Queue[bytes] = queue.Queue()

    def _callback(indata, frames, time_info, status):
        if status:
            return
        q.put(bytes(indata))

    pcm_chunks: list[bytes] = []
    started = False
    silent_count = 0

    with sd.RawInputStream(
        samplerate=cfg.sample_rate,
        channels=cfg.channels,
        dtype="int16",
        blocksize=frame_size,
        callback=_callback,
    ):
        start_at = time.time()
        while True:
            try:
                data = q.get(timeout=1.0)
            except queue.Empty:
                if time.time() - start_at > cfg.max_record_ms / 1000:
                    break
                continue
            if len(data) < frame_bytes:
                continue
            speech = vad.is_speech(data, cfg.sample_rate)
            if speech:
                started = True
                silent_count = 0
                pcm_chunks.append(data)
            elif started:
                silent_count += 1
                pcm_chunks.append(data)
                if silent_count >= silence_frames:
                    break

            if len(pcm_chunks) >= max_frames:
                break

    if not pcm_chunks:
        return ""

    pcm_bytes = b"".join(pcm_chunks)
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "input.wav"
        _write_wav(wav_path, pcm_bytes, cfg.sample_rate, cfg.channels)
        text = _run_whisper_cpp(cfg, wav_path)

    normalized = _normalize_text(text)

    if cfg.save_audio:
        out_dir = Path(cfg.audio_output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        _write_wav(out_dir / f"input_{ts}.wav", pcm_bytes, cfg.sample_rate, cfg.channels)

    if cfg.save_log:
        log_dir = Path(cfg.log_output_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        log_dir.joinpath(f"asr_{ts}.txt").write_text(normalized, encoding="utf-8")

    return normalized
