# 音频录制和语音转文字服务

这个服务为现有的桌面行为记录系统增加了音频录制和语音转文字功能，可以记录系统播放的音频（如视频、音乐、会议等）并将其转换为文字，存储到向量数据库中以便后续检索。

## 功能特点

- 🎤 **系统音频录制**: 录制系统播放的音频（立体声混音）
- 🎙️ **麦克风录制**: 支持麦克风输入录制
- 🔤 **语音转文字**: 使用 OpenAI Whisper 进行高质量语音识别
- 💾 **数据集成**: 转录文本自动存储到现有的活动记录数据库
- 🔍 **向量索引**: 支持语义搜索，可以通过自然语言查询音频内容
- ⚙️ **灵活配置**: 支持多种配置模式（默认、高质量、低资源等）

## 安装依赖

### 方法一：自动安装（推荐）
```bash
python install_audio_deps.py
```

### 方法二：手动安装
```bash
# 安装 PyAudio（音频录制）
pip install pyaudio

# 安装 Whisper（语音转文字）
pip install openai-whisper

# 安装其他依赖
pip install numpy scipy librosa soundfile
```

### 系统依赖

**Windows:**
- 通常不需要额外系统依赖

**macOS:**
```bash
brew install portaudio
```

**Ubuntu/Debian:**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
```

**CentOS/RHEL/Fedora:**
```bash
sudo yum install portaudio-devel
```

## 快速开始

### 1. 测试系统环境
```bash
python test_audio_simple.py
```
这个脚本会：
- 检查依赖是否正确安装
- 列出可用的音频设备
- 测试 Whisper 模型加载
- 进行简单的录制和转录测试

### 2. 启动音频服务
```bash
# 使用默认配置
python start_audio_service.py

# 使用高质量配置
python start_audio_service.py -c high_quality

# 指定音频设备
python start_audio_service.py -d 5

# 查看帮助
python start_audio_service.py --help
```

## 配置选项

### 预定义配置

| 配置名称 | 描述 | 适用场景 |
|---------|------|----------|
| `default` | 默认配置，平衡性能和质量 | 一般使用 |
| `high_quality` | 高质量配置，更好的转录效果 | 重要会议、内容创作 |
| `low_resource` | 低资源配置，适合性能较低的机器 | 老旧设备 |
| `debug` | 调试配置，保存音频文件 | 开发调试 |

### 命令行参数

```bash
python start_audio_service.py [选项]

选项:
  -c, --config CONF         配置名称 (default, high_quality, low_resource, debug)
  -d, --device INDEX        指定音频设备索引
  --chunk-duration SECONDS  音频处理块时长（秒）
  --model-size SIZE         Whisper 模型大小 (tiny, base, small, medium, large)
  --list-devices            列出所有可用的音频设备
  --list-configs            列出所有可用的配置
  --test                    测试依赖和配置
  --log-level LEVEL         日志级别 (DEBUG, INFO, WARNING, ERROR)
```

## 使用场景

### 1. 录制视频音频
```bash
# 启动服务，播放视频，音频内容会自动转录并存储
python start_audio_service.py -c high_quality
```

### 2. 会议录制
```bash
# 使用高质量配置录制在线会议
python start_audio_service.py -c high_quality --model-size small
```

### 3. 音乐/播客转录
```bash
# 录制播客或有声内容的文字版本
python start_audio_service.py -c default
```

## 音频设备设置

### Windows 启用立体声混音
1. 右键点击系统托盘中的音量图标
2. 选择"录音设备"
3. 在空白处右键，选择"显示已禁用的设备"
4. 找到"立体声混音"，右键启用
5. 设为默认录制设备

### macOS 系统音频录制
macOS 需要使用第三方工具如 SoundFlower 或 BlackHole 来录制系统音频。

### Linux 系统音频录制
```bash
# 安装 PulseAudio 音量控制
sudo apt-get install pavucontrol

# 在 pavucontrol 中配置监听器
pavucontrol
```

## 数据查询

音频转录的文本会自动存储到现有的活动记录数据库中，可以通过以下方式查询：

### 1. 通过 Web 界面
访问现有的活动查询界面，可以搜索音频转录的内容。

### 2. 自然语言查询示例
- "昨天开会讨论了什么？"
- "刚才看的视频讲了什么内容？"
- "上午的音乐播放列表"
- "会议中提到的项目名称"

## 技术细节

### 音频处理流程
1. **音频捕获**: 使用 PyAudio 录制系统音频或麦克风输入
2. **分块处理**: 将音频分成固定时长的块（默认30秒）
3. **语音转文字**: 使用 Whisper 模型进行转录
4. **数据存储**: 将转录文本保存到 SQLite 数据库
5. **向量索引**: 使用现有的向量数据库进行语义索引

### 存储格式
转录的音频数据会以以下格式存储：
```json
{
  "record_type": "audio_transcription",
  "app_name": "System Audio",
  "ocr_text": "转录的文本内容",
  "parser_type": "whisper",
  "timestamp": "2024-01-01T12:00:00"
}
```

### 性能优化
- 使用多线程处理音频录制和转录
- 支持不同大小的 Whisper 模型以平衡速度和质量
- 缓冲区管理避免内存溢出
- 可配置的处理间隔和质量设置

## 故障排除

### 常见问题

**1. PyAudio 安装失败**
```bash
# Windows: 尝试使用预编译包
pip install pipwin
pipwin install pyaudio

# 或从官网下载对应版本的 wheel 文件
```

**2. 找不到音频设备**
```bash
# 列出所有设备
python start_audio_service.py --list-devices
```

**3. Whisper 模型下载慢**
```bash
# 预先下载模型
python -c "import whisper; whisper.load_model('base')"
```

**4. 转录质量差**
- 使用更大的 Whisper 模型 (`--model-size small` 或 `medium`)
- 检查音频设备设置和音量
- 确保环境安静，减少背景噪音

**5. 系统音频录制不到**
- 检查立体声混音是否启用
- 尝试不同的音频设备索引
- 确认系统音频输出正常

### 日志查看
```bash
# 查看详细日志
python start_audio_service.py --log-level DEBUG

# 日志文件位置
tail -f audio_service.log
```

## 集成说明

这个音频服务完全集成到现有的桌面行为记录系统中：

1. **数据库共享**: 使用相同的 SQLite 数据库
2. **向量索引**: 自动索引到现有的 ChromaDB
3. **查询接口**: 通过现有的查询 API 可以搜索音频内容
4. **Web 界面**: 在现有的 Web 界面中可以查看音频转录记录

## 隐私和安全

- 所有音频处理都在本地进行，不会上传到外部服务
- 可选择是否保存原始音频文件
- 转录文本存储在本地数据库中
- 支持配置数据保留策略

## 开发和贡献

### 项目结构
```
audio_recorder.py          # 核心音频录制和转录类
audio_config.py           # 配置管理
start_audio_service.py    # 服务启动脚本
test_audio_simple.py      # 简单测试脚本
install_audio_deps.py     # 依赖安装脚本
```

### 扩展功能
- 支持更多音频格式
- 实时语音识别
- 说话人识别
- 情感分析
- 多语言支持

---

如有问题或建议，请在项目中提交 issue。