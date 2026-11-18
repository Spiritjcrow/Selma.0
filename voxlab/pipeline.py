"""Analyze media without changing original files or asserting ambiguous speech.

Requires ffmpeg/ffprobe and numpy. A local Faster-Whisper model is optional.
No network access is initiated by this module.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
from typing import Any

import numpy as np

ANALYSIS_RATE = 16000
MAX_SECONDS = 900  # memory-bounded 15-minute clips; split larger sources explicitly


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(args: list[str], *, timeout: int = 240) -> bytes:
    try:
        process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required local executable not installed: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Timed out while running {args[0]}") from exc
    if process.returncode != 0:
        raise RuntimeError(f"{args[0]} failed: {process.stderr.decode('utf-8', 'replace')[:350]}")
    return process.stdout


def probe_media(path: Path) -> dict[str, Any]:
    payload = _run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
    info = json.loads(payload)
    streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not streams:
        raise ValueError("No audio stream is present in this media")
    audio = streams[0]
    duration = float(audio.get("duration") or info.get("format", {}).get("duration") or 0)
    if not math.isfinite(duration) or duration < 0:
        raise ValueError("Invalid media duration")
    if duration > MAX_SECONDS:
        raise ValueError(f"Clip is {duration:.1f}s, exceeds {MAX_SECONDS}s limit; split or process a shorter range")
    return {
        "container": info.get("format", {}).get("format_name"),
        "duration_seconds": duration,
        "original_codec": audio.get("codec_name"),
        "original_sample_rate_hz": int(audio.get("sample_rate") or 0),
        "original_channels": int(audio.get("channels") or 0),
        "original_audio_bit_rate": audio.get("bit_rate"),
        "original_nyquist_hz": int(audio.get("sample_rate") or 0) / 2,
    }


def decode_pcm(path: Path) -> np.ndarray:
    raw = _run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-i", str(path),
                "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(ANALYSIS_RATE), "-f", "s16le", "-"])
    if not raw:
        raise ValueError("Decoded audio is empty")
    return np.frombuffer(raw[: len(raw) - len(raw) % 2], dtype="<i2").astype(np.float32) / 32768.0


def find_acoustic_events(samples: np.ndarray, sr: int = ANALYSIS_RATE,
                         sensitivity: float = 0.9) -> list[dict[str, Any]]:
    """Energy transients only; NOT speech recognition or voice identification.

    Higher sensitivity lowers relative energy cutoff, increasing false positives.
    The score is an energy contrast in dB, never a probability of speech.
    """
    if not 0.0 <= sensitivity <= 1.0:
        raise ValueError("sensitivity must be in [0,1]")
    frame = max(32, int(sr * .030))
    hop = max(16, int(sr * .010))
    if len(samples) < frame or np.max(np.abs(samples)) < 1e-7:
        return []
    # Frames are viewed rather than copied. RMS is not conditioned on phrases.
    windows = np.lib.stride_tricks.sliding_window_view(samples, frame)[::hop]
    rms = np.sqrt(np.mean(windows.astype(np.float64) ** 2, axis=1) + 1e-14)
    db = 20 * np.log10(np.maximum(rms, 1e-7))
    noise_floor = float(np.percentile(db, 40))
    spread = float(np.percentile(db, 75) - np.percentile(db, 25))
    cutoff = noise_floor + max(2.5, (8.0 - 5.0 * sensitivity), spread * (1.0 - .45 * sensitivity))
    active = (db > cutoff) & (db > -83)
    # Suppress lone 10 ms transients and merge gaps under 180 ms.
    groups = []
    starts = np.flatnonzero(np.diff(np.r_[False, active, False].astype(np.int8)) == 1)
    ends = np.flatnonzero(np.diff(np.r_[False, active, False].astype(np.int8)) == -1)
    for start, end in zip(starts, ends):
        if groups and (start - groups[-1][1]) * hop / sr <= .18:
            groups[-1][1] = int(end)
        else:
            groups.append([int(start), int(end)])
    events = []
    for start, end in groups:
        start_s = start * hop / sr
        end_s = min(len(samples) / sr, ((end - 1) * hop + frame) / sr)
        if end_s - start_s < .10:
            continue
        peak = float(np.max(db[start:end]))
        events.append({
            "start_seconds": round(start_s, 3),
            "end_seconds": round(end_s, 3),
            "type": "acoustic_candidate_unclassified",
            "peak_rms_dbfs": round(peak, 2),
            "contrast_above_noise_floor_db": round(peak - noise_floor, 2),
            "speech_confirmed": False,
        })
    return events


def make_enhanced_copy(path: Path, out: Path, input_rate: int) -> None:
    # Never overwrite input. This file is solely for listening; not original evidence.
    if out.resolve() == path.resolve():
        raise ValueError("Output cannot overwrite the original")
    lowpass = min(3400, max(400, int(input_rate * .43))) if input_rate else 3400
    _run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y", "-i", str(path),
          "-map", "0:a:0", "-vn", "-af", f"highpass=f=110,lowpass=f={lowpass},afftdn=nr=10",
          "-ac", "1", "-ar", str(ANALYSIS_RATE), "-c:a", "pcm_s16le", str(out)])


def _transcribe_local(audio_file: Path, model_path: Path, language: str | None) -> list[dict[str, Any]]:
    if not model_path.is_dir():
        raise ValueError("--asr-model must point to an existing LOCAL Faster-Whisper model folder")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Optional ASR requires: pip install faster-whisper") from exc
    model = WhisperModel(str(model_path), device="cpu", compute_type="int8", local_files_only=True)
    segments, _ = model.transcribe(str(audio_file), beam_size=5, vad_filter=True,
                                    condition_on_previous_text=False, language=language)
    return [{"start_seconds": round(s.start, 3), "end_seconds": round(s.end, 3),
             "tentative_text": s.text.strip(), "model_avg_logprob": getattr(s, "avg_logprob", None),
             "verified": False} for s in segments]


def analyze_file(input_path: str | Path, output_dir: str | Path, sensitivity: float = .9,
                 asr_model: str | Path | None = None, language: str | None = None,
                 enhance: bool = True) -> dict[str, Any]:
    source = Path(input_path).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("Source must be a file")
    evidence_hash = sha256_file(source)
    metadata = probe_media(source)
    audio = decode_pcm(source)
    root = Path(output_dir).expanduser().resolve()
    work = root / evidence_hash[:16]
    work.mkdir(parents=True, exist_ok=True)
    # Derived files are deterministically addressed by hash, not by mutable titles.
    listening_path = work / "speech_band_listening_copy.wav"
    if enhance:
        make_enhanced_copy(source, listening_path, metadata["original_sample_rate_hz"])
    report = {
        "schema": "selma.vox.review.v1",
        "original": {"name": source.name, "size_bytes": source.stat().st_size,
                     "sha256": evidence_hash, "metadata": metadata},
        "analysis": {"analysis_rate_hz": ANALYSIS_RATE, "sensitivity": sensitivity,
                     "analysis_is_not_speech_identification": True,
                     "source_frequency_limit_hz": metadata["original_nyquist_hz"],
                     "events": find_acoustic_events(audio, sensitivity=sensitivity)},
        "derivatives": {"speech_band_listening_copy": listening_path.name if enhance else None},
        "asr": {"status": "not_run_no_local_model", "original": [], "enhanced": []},
        "interpretation": "Acoustic candidates and ASR hypotheses must not be presented as verified voices or words.",
    }
    if asr_model is not None:
        model_path = Path(asr_model).expanduser().resolve()
        report["asr"] = {
            "status": "tentative_not_verified",
            "model_path": str(model_path),
            "original": _transcribe_local(source, model_path, language),
            "enhanced": _transcribe_local(listening_path, model_path, language) if enhance else [],
        }
    destination = work / "review.json"
    temp = work / "review.json.tmp"
    temp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, destination)
    report["report_path"] = str(destination)
    return report