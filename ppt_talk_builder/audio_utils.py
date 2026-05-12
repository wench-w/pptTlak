from __future__ import annotations

from pathlib import Path

from mutagen import File


def audio_duration_seconds(path: Path) -> float:
    audio = File(str(path))
    if audio is None or not getattr(audio.info, "length", None):
        raise ValueError(f"无法读取音频长度: {path}")
    return float(audio.info.length)

