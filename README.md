# PPT Talk Builder

使用 Python 将 PPT 幻灯片与备注转换成带字幕的演讲视频。流程：

1. 利用 LibreOffice 将 PPT 转成 PDF，再通过 PyMuPDF 渲染为一页一张的 PNG。
2. 读取每页备注，调用 `edge-tts` 将文字转成语音。
3. 根据音频时长拼接幻灯片，合成视频。
4. 输出 `.srt` 字幕文件（包含备注文本），播放器可直接加载，或使用 `--burn-subtitles` 生成内嵌字幕版本。

## 环境准备（Conda）

```bash
conda env create -f environment.yml
conda activate ppt-talk-builder
```

若 Conda 安装包不可用，可退回 `pip install -r requirements.txt`（已由 `pyproject` 描述）。

## 依赖组件

- LibreOffice：负责将 PPT/PPTX 转成 PNG（也可自行提供图片目录）。
- FFmpeg：`moviepy` 依赖，用于写入 H.264 + AAC。
- Edge TTS：微软 Edge 在线语音服务，默认使用 `zh-CN-XiaoyiNeural`。
- PyMuPDF：将 LibreOffice 生成的 PDF 渲染成逐页 PNG。

## 使用步骤

### 步骤一：安装依赖
1. 安装 Miniconda/Anaconda，并确保终端可以执行 `conda`.
2. 在项目根目录运行：
   ```bash
   conda env create -f environment.yml
   conda activate ppt-talk-builder
   ```
3. 安装 LibreOffice，并记下其可执行路径（macOS 默认为 `/Applications/LibreOffice.app/Contents/MacOS/soffice`）。

### 步骤二：命令行模式
```bash
ppt-talk-builder build \
  --ppt /绝对路径/你的.pptx \
  --workdir /绝对路径/output \
  --libreoffice /Applications/LibreOffice.app/Contents/MacOS/soffice \
  --voice zh-CN-XiaoyiNeural \
  --burn-subtitles
```

常用参数：

| 参数 | 描述 |
| --- | --- |
| `--ppt` | PPT/PPTX 文件路径 |
| `--workdir` | 中间结果与最终结果输出位置 |
| `--libreoffice` | `soffice` 可执行文件路径 |
| `--voice` | TTS 发音人 |
| `--rate` | 语速（如 `+15%`） |
| `--burn-subtitles` | 是否将字幕烧录进视频 |

生成完成后，`workdir` 下会包含：
- `slides/`：自动渲染的 PNG 幻灯片（下载成片后 GUI 会清理）。
- `audio/`：每页备注的语音文件。
- `subtitles/talk.srt`：字幕。
- `talk.mp4`（以及 `talk_with_subtitles.mp4`，若启用烧录）。
- `manifest.json`：记录本次构建的所有文件路径。

### 步骤三：图形界面（可选）

```bash
conda activate ppt-talk-builder
streamlit run streamlit_app.py
```

界面操作：
1. 左侧选择发音人、语速/音量，勾选是否烧录字幕；LibreOffice 路径默认已填好（可按需修改）。
2. 主区域上传 PPT/PPTX，填写输出目录，点击“开始生成”。
3. 处理完成后可查看 manifest 信息，并下载生成的视频与字幕；下载任一视频后，`slides/` 会自动清空释放空间。

### 常见问题
- 只生成单页：确认已安装新版（使用 PDF+PyMuPDF 流程）并重新创建环境；或检查 PPT 是否为只含一页。
- 没有 LibreOffice：安装并在 CLI/GUI 中指定 `--libreoffice` 路径，或手动提前导出 PNG 幻灯片并配合 `--slides-dir`。
- TTS 网络异常：确保可访问 Edge TTS 服务，必要时更换网络环境或改用其他 TTS 引擎。

## 图形界面（Streamlit）

如果希望通过界面上传 PPT、配置输出目录与语音信息，可运行：

```bash
conda activate ppt-talk-builder
streamlit run streamlit_app.py
```

界面说明：

- 左侧边栏配置发音人、语速/音量、是否烧录字幕以及 LibreOffice 路径。
- 主区域上传 PPT/PPTX 文件，填写输出目录，点击“开始生成”即可。
- 生成完成后可直接看到 manifest 信息并下载 `talk.mp4`、`talk_with_subtitles.mp4`（若勾选烧录）以及 `talk.srt`。

## 项目结构

```
ppt_talk_builder/
  cli.py           # Typer CLI
  models.py        # 数据模型
  ppt_reader.py    # PPT -> notes + slides
  tts_engine.py    # Edge TTS 封装
  audio_utils.py   # 音频工具
  subtitles.py     # 字幕写入
  video_builder.py # 利用 moviepy 合成视频
```

## 未来改进

- 支持本地 TTS 引擎（如 VITS/Bark）。
- 增加批量任务与并行处理。
- 提供 GUI。

# pptTlak
