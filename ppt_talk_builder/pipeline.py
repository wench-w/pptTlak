from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import audio_utils, ppt_reader, subtitles, video_builder
from .models import SlideAsset, SubtitleEntry
from .tts_engine import EdgeTTSEngine, TTSConfig


@dataclass(slots=True)
class PipelineConfig:
    ppt: Path
    workdir: Path
    libreoffice: str | None = None
    voice: str = "zh-CN-XiaoyiNeural"
    rate: str = "+0%"
    volume: str = "+0%"
    burn_subtitles: bool = False
    slides_dir: Path | None = None
    overwrite: bool = False
    subtitle_font: str = "Arial"
    subtitle_fontsize: int = 42


ProgressCallback = Callable[[str], None] | None


def run_pipeline(config: PipelineConfig, progress: ProgressCallback = None) -> dict[str, str]:
    ppt = config.ppt.expanduser().resolve()
    workdir = config.workdir.expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    slides_output = config.slides_dir or workdir / "slides"
    audio_output = workdir / "audio"
    subtitles_output = workdir / "subtitles"
    video_output = workdir / "talk.mp4"

    if video_output.exists() and not config.overwrite:
        raise FileExistsError(f"{video_output} 已存在，如需覆盖请设置 overwrite=True。")

    # 1. 幻灯片 -> PNG
    if config.slides_dir is None:
        _notify(progress, "正在导出幻灯片为 PNG ...")
        converter = config.libreoffice or shutil.which("libreoffice")
        if not converter:
            raise RuntimeError("找不到 LibreOffice，可安装后重试或提前准备 PNG 幻灯片。")
        images = ppt_reader.convert_ppt_to_images(ppt, slides_output, converter)
    else:
        images = ppt_reader.sorted_pngs(slides_output)

    if not images:
        raise RuntimeError("未找到幻灯片 PNG，流程终止。")

    notes, font_info = ppt_reader.extract_slide_notes(ppt)
    assets = ppt_reader.build_slide_assets(images, notes, font_info)

    # 2. 备注 -> TTS
    audio_output.mkdir(exist_ok=True)
    tts = EdgeTTSEngine(TTSConfig(voice=config.voice, rate=config.rate, volume=config.volume))

    _notify(progress, f"正在生成语音（共 {len(assets)} 页）...")
    for idx, asset in enumerate(assets, 1):
        text = asset.note_text or f"幻灯片 {asset.index}"
        _notify(progress, f"正在生成第 {idx}/{len(assets)} 页语音...")
        audio_path = audio_output / f"slide_{asset.index:03d}.mp3"
        tts.synthesize(text, audio_path)
        asset.audio_path = audio_path
        asset.duration = audio_utils.audio_duration_seconds(audio_path)
        _notify(progress, f"第 {idx} 页语音生成完成（时长: {asset.duration:.2f}秒）")

    # 3. 字幕
    _notify(progress, "正在生成字幕...")
    # 检查备注内容
    notes_with_content = [a for a in assets if a.note_text and a.note_text.strip()]
    _notify(progress, f"共 {len(assets)} 页，其中 {len(notes_with_content)} 页有备注内容")
    if notes_with_content:
        _notify(progress, f"第一页备注预览: {notes_with_content[0].note_text[:100]}...")
    
    subtitle_entries = build_subtitle_entries(assets)
    _notify(progress, f"已生成 {len(subtitle_entries)} 条字幕条目")
    if subtitle_entries:
        # 显示前3条字幕内容作为预览
        preview_count = min(3, len(subtitle_entries))
        for i, entry in enumerate(subtitle_entries[:preview_count], 1):
            preview_text = entry.text[:50] + "..." if len(entry.text) > 50 else entry.text
            _notify(progress, f"  字幕 {i}: {preview_text} (时间: {entry.start:.2f}s - {entry.end:.2f}s)")
    else:
        _notify(progress, "警告: 没有生成任何字幕条目！")
    srt_path = subtitles_output / "talk.srt"
    subtitles.write_srt(subtitle_entries, srt_path)
    _notify(progress, f"字幕文件已保存: {srt_path}")

    # 4. 合成视频
    _notify(progress, f"正在合成视频（共 {len(assets)} 页幻灯片）...")
    _notify(progress, "这可能需要几分钟，请耐心等待...")
    video_builder.build_video(assets, video_output)
    _notify(progress, "视频合成完成！")

    burned_video = None
    if config.burn_subtitles:
        _notify(progress, "正在烧录字幕到视频...")
        _notify(progress, "字幕烧录可能需要较长时间，请耐心等待...")
        burned_video = workdir / "talk_with_subtitles.mp4"
        
        # 尝试从第一页备注中获取字体信息，如果没有则使用配置的字体
        default_font = config.subtitle_font
        default_fontsize = config.subtitle_fontsize
        if assets and assets[0].note_font:
            default_font = assets[0].note_font
            _notify(progress, f"使用PPT备注字体: {default_font}")
        if assets and assets[0].note_fontsize:
            default_fontsize = assets[0].note_fontsize
            _notify(progress, f"使用PPT备注字号: {default_fontsize}")
        
        video_builder.burn_subtitles(
            video_output, 
            subtitle_entries, 
            burned_video,
            font=default_font,
            fontsize=default_fontsize,
        )
        _notify(progress, "字幕烧录完成！")

    manifest = {
        "slides": [str(s.image_path) for s in assets],
        "audio": [str(s.audio_path) for s in assets],
        "video": str(video_output),
        "subtitle": str(srt_path),
    }
    if burned_video:
        manifest["video_with_subtitles"] = str(burned_video)

    manifest_path = workdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest"] = str(manifest_path)
    _notify(progress, "完成！")
    return manifest


def build_subtitle_entries(slides: list[SlideAsset]) -> list[SubtitleEntry]:
    """将备注文本按句子分割，创建细粒度的字幕条目，与语音同步。"""
    import re
    
    entries: list[SubtitleEntry] = []
    cursor = 0.0
    seq = 1
    
    for asset in slides:
        duration = asset.duration or 0.0
        # 获取备注文本，保留原始内容
        text = asset.note_text if asset.note_text else ""
        text = text.strip()
        
        # 如果没有备注或时长为0
        if not text or duration <= 0:
            # 创建一个占位条目
            placeholder_text = f"幻灯片 {asset.index}" if not text else text
            entries.append(SubtitleEntry(
                seq=seq,
                start=cursor,
                end=cursor + max(duration, 1.0),
                text=placeholder_text,
            ))
            cursor += max(duration, 1.0)
            seq += 1
            continue
        
        # 按句子分割：支持中文和英文标点
        # 匹配：。！？；\n 以及英文的 .!?; 后面可能有空格
        # 使用正向先行断言，保留分隔符在结果中
        split_pattern = r'([。！？；\n]|[.!?;])\s*'
        parts = re.split(split_pattern, text)
        
        # 重新组合句子和标点
        sentences = []
        current = ""
        for i, part in enumerate(parts):
            if not part:
                continue
            # 检查是否是标点符号
            if re.match(r'^[。！？；\n.!?;]$', part):
                # 是标点，添加到当前句子并结束
                current += part
                if current.strip():
                    sentences.append(current.strip())
                    current = ""
            else:
                # 是文本内容
                current += part
        
        # 添加最后一个句子（如果有）
        if current.strip():
            sentences.append(current.strip())
        
        # 如果没有分割出句子，使用整段文本
        if not sentences:
            sentences = [text]
        
        # 过滤空句子
        sentences = [s for s in sentences if s.strip()]
        if not sentences:
            sentences = [text]
        
        # 根据句子长度按比例分配时间
        total_chars = sum(len(s) for s in sentences)
        if total_chars == 0:
            total_chars = len(text) if text else 1
        
        # 计算每个句子的时长
        sentence_durations = []
        for sentence in sentences:
            if not sentence.strip():
                continue
            # 按字符数比例分配时间
            char_ratio = len(sentence) / total_chars if total_chars > 0 else 1.0 / len(sentences)
            sentence_duration = char_ratio * duration
            # 确保最小显示时间为0.5秒，最大不超过总时长
            sentence_duration = max(0.5, min(sentence_duration, duration))
            sentence_durations.append((sentence.strip(), sentence_duration))
        
        # 如果分配的总时长超过原始时长，按比例缩放
        total_allocated = sum(d for _, d in sentence_durations)
        if total_allocated > duration and total_allocated > 0:
            scale = duration / total_allocated
            sentence_durations = [(s, d * scale) for s, d in sentence_durations]
        
        # 如果分配的总时长小于原始时长，将剩余时间分配给最后一个句子
        total_allocated = sum(d for _, d in sentence_durations)
        if total_allocated < duration and sentence_durations:
            remaining = duration - total_allocated
            last_sentence, last_duration = sentence_durations[-1]
            sentence_durations[-1] = (last_sentence, last_duration + remaining)
        
        # 创建字幕条目
        for sentence, sentence_duration in sentence_durations:
            entries.append(SubtitleEntry(
                seq=seq,
                start=cursor,
                end=cursor + sentence_duration,
                text=sentence,  # 保留原始文本，包括所有标点符号
            ))
            cursor += sentence_duration
            seq += 1
    
    return entries


def _notify(callback: ProgressCallback, message: str) -> None:
    if callback:
        callback(message)

