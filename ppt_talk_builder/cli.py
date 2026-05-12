from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .pipeline import PipelineConfig, run_pipeline

app = typer.Typer(help="将 PPT 备注转换为带字幕的演讲视频。")


@app.command()
def build(
    ppt: Path = typer.Option(..., help="PPT/PPTX 文件路径"),
    workdir: Path = typer.Option(Path("./build"), help="输出目录"),
    libreoffice: Optional[str] = typer.Option(None, help="LibreOffice 可执行文件路径"),
    voice: str = typer.Option("zh-CN-XiaoyiNeural", help="Edge TTS 发音人"),
    rate: str = typer.Option("+0%", help="Edge TTS 语速"),
    volume: str = typer.Option("+0%", help="Edge TTS 音量"),
    burn_subtitles: bool = typer.Option(False, help="是否将字幕烧录进视频（依赖 ImageMagick）"),
    slides_dir: Optional[Path] = typer.Option(None, help="已存在的幻灯片 PNG 目录，跳过转换"),
    overwrite: bool = typer.Option(False, help="若目标文件存在，是否覆盖"),
):
    """
    主流程：幻灯片转换 -> 备注转语音 -> 合成视频 -> 生成字幕。
    """

    config = PipelineConfig(
        ppt=ppt,
        workdir=workdir,
        libreoffice=libreoffice,
        voice=voice,
        rate=rate,
        volume=volume,
        burn_subtitles=burn_subtitles,
        slides_dir=slides_dir,
        overwrite=overwrite,
    )

    def notify(message: str) -> None:
        typer.echo(message)

    try:
        manifest = run_pipeline(config, progress=notify)
    except FileExistsError as exc:
        typer.echo(f"[WARN] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"[ERROR] {exc}")
        raise typer.Exit(code=1) from exc

    typer.echo("完成！生成结果：")
    typer.echo(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()

