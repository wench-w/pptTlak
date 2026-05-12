from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

# 在导入任何模块之前配置 ImageMagick 路径
_IMAGEMAGICK_PATHS = [
    "/opt/homebrew/bin/convert",  # Homebrew on Apple Silicon
    "/usr/local/bin/convert",  # Homebrew on Intel
    shutil.which("convert"),  # 系统 PATH 中的 convert
]

for path in _IMAGEMAGICK_PATHS:
    if path and os.path.exists(path):
        os.environ["IMAGEMAGICK_BINARY"] = path
        break

import streamlit as st

from ppt_talk_builder.pipeline import PipelineConfig, run_pipeline

VOICE_OPTIONS = [
    "zh-CN-XiaoyiNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-XiaochenNeural",
]


def main() -> None:
    st.set_page_config(page_title="PPT Talk Builder", layout="centered")
    if "slides_cleared" not in st.session_state:
        st.session_state["slides_cleared"] = False
    if "manifest" not in st.session_state:
        st.session_state["manifest"] = None
    st.title("PPT Talk Builder")
    st.caption("上传 PPT 备注，自动生成带字幕的演讲视频")

    with st.sidebar:
        st.header("语音配置")
        voice = st.selectbox("发音人", VOICE_OPTIONS, index=0)
        rate = st.slider("语速 (百分比)", -50, 50, 0, step=5)
        volume = st.slider("音量 (百分比)", -50, 50, 0, step=5)
        burn_subtitles = st.checkbox("烧录字幕到视频", value=False)
        
        st.header("字幕配置")
        # 常见中文字体选项
        font_options = [
            "Arial",
            "SimHei",  # 黑体
            "SimSun",  # 宋体
            "Microsoft YaHei",  # 微软雅黑
            "PingFang SC",  # 苹方（macOS）
            "STHeiti",  # 华文黑体（macOS）
            "STSong",  # 华文宋体（macOS）
            "Helvetica",
            "Times New Roman",
        ]
        subtitle_font = st.selectbox("字幕字体", font_options, index=4)  # 默认使用 PingFang SC
        subtitle_fontsize = st.slider("字幕字号", 24, 72, 42, step=2)
        
        st.header("系统配置")
        libreoffice = st.text_input(
            "LibreOffice 可执行路径（可留空）",
            value="/Applications/LibreOffice.app/Contents/MacOS/soffice",
        )

    uploaded_file = st.file_uploader("上传 PPT/PPTX 文件", type=["pptx", "ppt"])
    default_workdir = Path.cwd() / "gui_output"
    workdir_input = st.text_input("输出目录", value=str(default_workdir))
    
    # 初始化 workdir，确保下载按钮可以访问
    if "workdir" not in st.session_state:
        st.session_state["workdir"] = str(default_workdir)
    if workdir_input:
        st.session_state["workdir"] = workdir_input

    start = st.button("开始生成", type="primary", use_container_width=True)

    if start:
        if not uploaded_file:
            st.error("请先上传 PPT 文件。")
            return

        workdir = Path(workdir_input).expanduser()
        workdir.mkdir(parents=True, exist_ok=True)
        
        # 清理上次生成的文件
        def cleanup_previous_files():
            """清理上次生成的所有文件"""
            try:
                # 清理视频文件
                for video_file in workdir.glob("*.mp4"):
                    video_file.unlink(missing_ok=True)
                
                # 清理音频目录
                audio_dir = workdir / "audio"
                if audio_dir.exists():
                    shutil.rmtree(audio_dir)
                
                # 清理字幕目录
                subtitles_dir = workdir / "subtitles"
                if subtitles_dir.exists():
                    shutil.rmtree(subtitles_dir)
                
                # 清理 slides 目录
                slides_dir = workdir / "slides"
                if slides_dir.exists():
                    shutil.rmtree(slides_dir)
                
                # 清理清单文件
                manifest_file = workdir / "manifest.json"
                if manifest_file.exists():
                    manifest_file.unlink(missing_ok=True)
                
                st.info("已清理上次生成的文件，准备生成新的视频。")
            except Exception as e:
                st.warning(f"清理文件时出错: {e}")
        
        cleanup_previous_files()
        st.session_state["slides_cleared"] = False

        upload_dir = workdir / "uploads"
        upload_dir.mkdir(exist_ok=True)
        timestamp = int(time.time())
        suffix = Path(uploaded_file.name).suffix or ".pptx"
        ppt_path = upload_dir / f"uploaded_{timestamp}{suffix}"
        ppt_path.write_bytes(uploaded_file.getbuffer())

        config = PipelineConfig(
            ppt=ppt_path,
            workdir=workdir,
            libreoffice=libreoffice or None,
            voice=voice,
            rate=f"{rate:+d}%",
            volume=f"{volume:+d}%",
            burn_subtitles=burn_subtitles,
            overwrite=True,
            subtitle_font=subtitle_font,
            subtitle_fontsize=subtitle_fontsize,
        )

        status = st.status(label="处理中，请稍候 ...", state="running")

        def notify(message: str) -> None:
            status.write(message)

        try:
            manifest = run_pipeline(config, progress=notify)
        except Exception as exc:  # noqa: BLE001
            status.update(label="处理失败", state="error")
            st.error(f"生成失败：{exc}")
            return

        status.update(label="处理完成！", state="complete")
        st.success("已生成演讲视频与字幕")
        
        # 保存 manifest 到 session_state，确保下载按钮始终可用
        st.session_state["manifest"] = manifest
        st.json(manifest)

        video_path = manifest.get("video")
        burned_path = manifest.get("video_with_subtitles")
        subtitle_path = manifest.get("subtitle")

        # 将文件路径保存到 session_state，确保下载按钮始终可用
        if video_path:
            st.session_state["video_path"] = video_path
        if burned_path:
            st.session_state["burned_path"] = burned_path
        if subtitle_path:
            st.session_state["subtitle_path"] = subtitle_path

    # 显示下载按钮（即使不在生成流程中，只要文件存在就显示）
    # 从 session_state 读取路径，确保即使页面刷新也能显示
    video_path_to_use = st.session_state.get("video_path")
    burned_path_to_use = st.session_state.get("burned_path")
    subtitle_path_to_use = st.session_state.get("subtitle_path")
    
    # 如果 session_state 中没有，尝试从 manifest 中读取
    if not video_path_to_use and st.session_state.get("manifest"):
        video_path_to_use = st.session_state["manifest"].get("video")
    if not burned_path_to_use and st.session_state.get("manifest"):
        burned_path_to_use = st.session_state["manifest"].get("video_with_subtitles")
    if not subtitle_path_to_use and st.session_state.get("manifest"):
        subtitle_path_to_use = st.session_state["manifest"].get("subtitle")

    # 显示下载按钮区域
    if video_path_to_use or burned_path_to_use or subtitle_path_to_use:
        st.divider()
        st.subheader("下载生成的文件")
        
        def cleanup_slides_on_download():
            """下载时只清理 slides 目录，不删除视频文件"""
            workdir = Path(st.session_state.get("workdir", workdir_input)).expanduser()
            slides_dir = workdir / "slides"
            if slides_dir.exists() and not st.session_state.get("slides_cleared", False):
                try:
                    shutil.rmtree(slides_dir)
                    st.session_state["slides_cleared"] = True
                    st.info("已清理 slides 目录，释放存储空间。")
                except Exception as e:
                    st.warning(f"清理 slides 目录时出错: {e}")

        if video_path_to_use and Path(video_path_to_use).exists():
            video_file = Path(video_path_to_use)
            try:
                data = video_file.read_bytes()
                st.download_button(
                    "下载 talk.mp4",
                    data=data,
                    file_name=video_file.name,
                    mime="video/mp4",
                    key="download_video",
                    on_click=cleanup_slides_on_download,
                )
            except Exception as e:
                st.warning(f"读取视频文件失败: {e}")

        if burned_path_to_use and Path(burned_path_to_use).exists():
            burned_file = Path(burned_path_to_use)
            try:
                data = burned_file.read_bytes()
                st.download_button(
                    "下载带字幕视频",
                    data=data,
                    file_name=burned_file.name,
                    mime="video/mp4",
                    key="download_video_sub",
                    on_click=cleanup_slides_on_download,
                )
            except Exception as e:
                st.warning(f"读取带字幕视频文件失败: {e}")

        if subtitle_path_to_use and Path(subtitle_path_to_use).exists():
            subtitle_file = Path(subtitle_path_to_use)
            try:
                data = subtitle_file.read_bytes()
                st.download_button(
                    "下载字幕文件",
                    data=data,
                    file_name=subtitle_file.name,
                    mime="application/x-subrip",
                    key="download_subtitle",
                )
            except Exception as e:
                st.warning(f"读取字幕文件失败: {e}")


if __name__ == "__main__":
    main()

