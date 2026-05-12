from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SlideAsset:
    """表示一页 PPT 的所有素材。"""

    index: int
    image_path: Path
    note_text: str
    audio_path: Path | None = None
    duration: float | None = None
    note_font: str | None = None  # 备注字体名称
    note_fontsize: int | None = None  # 备注字号


@dataclass(slots=True)
class SubtitleEntry:
    """字幕行。"""

    seq: int
    start: float
    end: float
    text: str

