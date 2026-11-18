# Selma VOX Lab v0.1: Offline Evidence-Preserving Acoustic Review

Portable Python module for Android-Termux, Chromebook Linux, and desktop environments. **No uploaded recordings or generated/stock images.** Media remain local; original bytes are never edited.

## Install and run

Requires Python 3.10+, NumPy and local FFmpeg/FFprobe on PATH. Offline use once installed. For Termux, use `pkg install python ffmpeg` then follow its NumPy package instructions. For Linux desktop:

```bash
python3 -m pip install numpy
python3 -m voxlab analyze /path/to/security_video.mp4 --out ./vox-results --sensitivity 1.0
python3 -m unittest discover -s tests -v
```

The output folder is keyed by original SHA-256 and contains:
- `review.json` source properties, integrity digest, acoustic transient timestamps, and evidence warnings.
- `speech_band_listening_copy.wav` a **derived** FFmpeg bandpass/FFT denoise WAV (not a source recording).

A score or energy burst is **not** evidence of speech, a specific speaker, intent, or a particular location. Upsampling 8kHz to 16kHz for analysis does not restore >4kHz signal.

## Optional local, offline ASR

```bash
pip install faster-whisper
python3 -m voxlab analyze clip.mp4 --out ./vox-results --asr-model /absolute/path/to/existing/local-faster-whisper-model
```

An already downloaded CTranslate2 model folder must exist. The script deliberately rejects model names that would trigger automatic online downloads. Whisper output is *tentative* and runs separately on original and processed audio; no hallucination is promoted into verified evidence.

## Cooperative listening/corrections

Find the original's SHA-256 in `review.json`. Then, for a timestamped listener note:

```bash
python3 -m voxlab correct --db local-reviews.sqlite3 --sha <64-char-sha> \
    --start 12.0 --end 14.5 --text 'Possible word or sound noted' --status listener_reported
python3 -m voxlab export-corrections --db local-reviews.sqlite3 --out review-only.jsonl
```

Correction statuses are `hypothesis`, `listener_reported`, or `rejected`. Export records are explicitly `training_approved=false`. Independent verification and deliberate, held-out evaluation are required before a future model-training pipeline can consume any labels. The pipeline never updates weights automatically.

## Security and scope

- Offline, local-only default; no arbitrary remote model fetching or uploads.
- SHA-256 of original, read-only analysis, no source replacement. Ensure adequate output storage before running.
- 15-minute single-file guard; split long material into individually hashed originals if longer sessions are needed.
- No facial recognition, sound-source geolocation, speaker identification, or automatic evidence claims.
- Source separation is **not yet implemented**. Pretrained speech enhancement integration requires an existing, explicitly selected offline model and independent test examples.
- Original evidence should be retained separately with a record of collection and custody.

This is v0.1 standalone module for integration into Selma.0, not a production forensic certification or a deployed APK.