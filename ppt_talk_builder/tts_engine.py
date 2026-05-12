from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import edge_tts


@dataclass(slots=True)
class TTSConfig:
    voice: str = "zh-CN-XiaoyiNeural"
    rate: str = "+0%"
    volume: str = "+0%"


class EdgeTTSEngine:
    def __init__(self, config: TTSConfig | None = None):
        self.config = config or TTSConfig()

    async def synthesize_async(self, text: str, output_path: Path) -> None:
        communicator = edge_tts.Communicate(
            text=text,
            voice=self.config.voice,
            rate=self.config.rate,
            volume=self.config.volume,
        )
        await communicator.save(str(output_path))

    def synthesize(self, text: str, output_path: Path) -> None:
        asyncio.run(self.synthesize_async(text, output_path))

