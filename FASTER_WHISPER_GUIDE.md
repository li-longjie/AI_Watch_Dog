# Faster-Whisper 音频转录服务

## 概述

本项目已升级支持 **Faster-Whisper**，相比原版 OpenAI Whisper 提供：
- 🚀 **2-4倍更快的转录速度**
- 💾 **减少3倍内存使用**
- 🎯 **相同的转录准确度**
- ⚡ **更好的GPU利用率**

## 安装依赖

### 1. 基础安装
```bash
pip install faster-whisper pyaudio
```

### 2. GPU支持 (推荐)
如果有NVIDIA GPU，安装CUDA支持：
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install faster-whisper[cuda]
```

### 3. 完整安装
```bash
pip install -r requirements_faster_whisper.txt
```

## 快速开始

### 1. 基本启动
```bash
python start_audio_service_faster.py
```

### 2. 高质量模式
```bash
python start_audio_service_faster.py -c high_quality
```

### 3. 低资源模式
```bash
python start_audio_service_faster.py -c low_resource
```

## 配置选项

### 预设配置
- `default`: 平衡性能和质量
- `high_quality`: 最佳转录质量
- `low_resource`: 最小资源占用
- `debug`: 调试模式，保存音频文件

### 命令行参数
```bash
# 指定模型大小
python start_audio_service_faster.py --model-size small

# 设置计算类型（量化）
python start_audio_service_faster.py --compute-type int8

# 调整束搜索大小
python start_audio_service_faster.py --beam-size 1

# 指定音频设备
python start_audio_service_faster.py -d 5

# 列出所有音频设备
python start_audio_service_faster.py --list-devices
```

## 性能对比

| 配置 | 模型 | 计算类型 | 速度 | 内存 | 准确度 |
|------|------|----------|------|------|--------|
| 默认 | base | float16 | 4x | 1GB | 高 |
| 高质量 | small | float16 | 2x | 2GB | 很高 |
| 低资源 | tiny | int8 | 8x | 500MB | 中等 |

## 配置详解

### Faster-Whisper 专用参数

```python
# 计算类型（影响速度和质量）
compute_type: str = "float16"  # float16, int8, int8_float16

# 束搜索大小（影响准确度和速度）
beam_size: int = 5  # 1=贪心（最快），5=标准，10=最准确

# 采样参数
best_of: int = 5
temperature: float = 0.0  # 0=确定性输出

# 检测阈值
no_speech_threshold: float = 0.6
compression_ratio_threshold: float = 2.4
log_prob_threshold: float = -1.0
```

### 计算类型说明

| 类型 | 速度 | 质量 | 内存 | 适用场景 |
|------|------|------|------|----------|
| `float16` | 快 | 最佳 | 中等 | GPU推荐 |
| `int8` | 最快 | 良好 | 最少 | CPU/低资源 |
| `int8_float16` | 很快 | 很好 | 少 | 平衡选择 |

## 使用示例

### 1. 系统音频转录
```bash
# 自动检测系统音频设备（立体声混音）
python start_audio_service_faster.py

# 手动指定设备
python start_audio_service_faster.py -d 2
```

### 2. 高性能配置
```bash
# 最快速度（牺牲一些质量）
python start_audio_service_faster.py \
  --model-size tiny \
  --compute-type int8 \
  --beam-size 1

# 最高质量（需要更多资源）
python start_audio_service_faster.py \
  --model-size small \
  --compute-type float16 \
  --beam-size 5
```

### 3. 调试模式
```bash
# 保存音频文件用于调试
python start_audio_service_faster.py -c debug
```

## 故障排除

### 1. 检查系统环境
```bash
python start_audio_service_faster.py --test
```

### 2. 列出音频设备
```bash
python start_audio_service_faster.py --list-devices
```

### 3. 常见问题

**Q: 找不到系统音频设备？**
A: 确保启用了"立体声混音"或类似的系统音频设备。

**Q: GPU不被识别？**
A: 检查CUDA安装和torch版本兼容性。

**Q: 转录速度慢？**
A: 尝试使用int8量化或更小的模型。

**Q: 内存不足？**
A: 使用low_resource配置或int8计算类型。

## 与原版对比

| 特性 | OpenAI Whisper | Faster-Whisper |
|------|----------------|----------------|
| 速度 | 1x | 2-4x |
| 内存 | 基准 | -67% |
| 准确度 | 基准 | 相同 |
| GPU优化 | 基础 | 优秀 |
| 量化支持 | 无 | 支持 |
| 实时性 | 较差 | 良好 |

## 更新日志

### v2.0.0
- ✅ 集成Faster-Whisper支持
- ✅ 添加计算类型配置
- ✅ 优化GPU内存使用
- ✅ 向后兼容原版Whisper
- ✅ 新增性能监控

### 迁移指南

从原版迁移只需要：
1. 安装faster-whisper: `pip install faster-whisper`
2. 使用新启动脚本: `python start_audio_service_faster.py`
3. 配置文件自动兼容，无需修改

## 技术支持

如遇问题，请检查：
1. 依赖安装是否完整
2. 音频设备是否正常
3. GPU驱动是否最新
4. 系统权限是否足够