from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable, List

# 在导入 MoviePy 之前配置 ImageMagick 路径
_IMAGEMAGICK_PATHS = [
    "/opt/homebrew/bin/convert",  # Homebrew on Apple Silicon
    "/usr/local/bin/convert",  # Homebrew on Intel
    shutil.which("convert"),  # 系统 PATH 中的 convert
]

_IMAGEMAGICK_BINARY = None
for path in _IMAGEMAGICK_PATHS:
    if path and os.path.exists(path):
        _IMAGEMAGICK_BINARY = path
        os.environ["IMAGEMAGICK_BINARY"] = path
        break

from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.tools.subtitles import SubtitlesClip

from .models import SlideAsset, SubtitleEntry


def build_video(
    slides: Iterable[SlideAsset],
    output_path: Path,
    fps: int = 30,
) -> Path:
    clips = []
    # 统一视频尺寸（1920x1080），避免字体变化
    target_size = (1920, 1080)
    
    for slide in slides:
        if slide.audio_path is None or slide.duration is None:
            raise ValueError(f"缺少音频或时长: {slide.index}")
        
        # 创建图片剪辑，统一尺寸和时长
        image_clip = ImageClip(str(slide.image_path))
        # 调整尺寸，保持宽高比，居中显示
        image_clip = image_clip.resize(height=target_size[1])  # 按高度缩放
        if image_clip.w > target_size[0]:
            image_clip = image_clip.resize(width=target_size[0])  # 如果宽度超了，按宽度缩放
        
        # 居中显示
        image_clip = image_clip.set_position("center")
        image_clip = image_clip.set_duration(slide.duration)
        image_clip = image_clip.set_fps(fps)
        
        # 创建与目标尺寸匹配的合成剪辑
        final_image_clip = CompositeVideoClip(
            [image_clip.set_position("center")],
            size=target_size
        ).set_duration(slide.duration).set_fps(fps)
        
        # 添加音频
        audio_clip = AudioFileClip(str(slide.audio_path))
        clips.append(final_image_clip.set_audio(audio_clip))
    
    final_clip = concatenate_videoclips(clips, method="compose")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_clip.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(output_path.with_suffix(".temp-audio.m4a")),
        remove_temp=True,
        bitrate="8000k",  # 提高比特率，确保字体清晰
        preset="medium",  # 编码预设
    )
    final_clip.close()
    for clip in clips:
        clip.close()
    return output_path


def burn_subtitles(
    video_path: Path,
    subtitles: List[SubtitleEntry],
    output_path: Path,
    font: str = "Arial",
    fontsize: int = 42,
    color: str = "white",
) -> Path:
    # 确保 ImageMagick 路径已设置
    if _IMAGEMAGICK_BINARY:
        os.environ["IMAGEMAGICK_BINARY"] = _IMAGEMAGICK_BINARY
    
    if not _IMAGEMAGICK_BINARY:
        raise RuntimeError(
            "找不到 ImageMagick。请安装 ImageMagick：\n"
            "  macOS: brew install imagemagick\n"
            "  或使用 Conda: conda install -c conda-forge imagemagick"
        )
    
    def generator(txt):
        # 每次创建 TextClip 前确保环境变量已设置
        if _IMAGEMAGICK_BINARY:
            os.environ["IMAGEMAGICK_BINARY"] = _IMAGEMAGICK_BINARY
        return TextClip(
            txt,
            font=font,
            fontsize=fontsize,
            color=color,
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(1280, None),
        )

    subs_data = [
        (
            (entry.start, entry.end),
            entry.text,
        )
        for entry in subtitles
    ]

    video = VideoFileClip(str(video_path))
    subtitles_clip = SubtitlesClip(subs_data, generator).set_position(("center", "bottom"))
    composite = CompositeVideoClip([video, subtitles_clip])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composite.write_videofile(
        str(output_path), 
        codec="libx264", 
        audio_codec="aac",
        bitrate="8000k",  # 提高比特率，确保字体清晰
        preset="medium",  # 编码预设
    )
    composite.close()
    video.close()
    subtitles_clip.close()
    return output_path

