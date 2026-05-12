from __future__ import annotations

from pathlib import Path
from typing import Iterable

import srt

from .models import SubtitleEntry


def format_timestamp(seconds: float) -> tuple[int, int, int, int]:
    millis = int(seconds * 1000)
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return hours, minutes, secs, millis


def write_srt(entries: Iterable[SubtitleEntry], output_path: Path) -> None:
    subtitles = [
        srt.Subtitle(
            index=entry.seq,
            start=srt.timedelta(seconds=entry.start),
            end=srt.timedelta(seconds=entry.end),
            content=entry.text,
        )
        for entry in entries
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(srt.compose(subtitles), encoding="utf-8")

