# audio_config.py

"""
音频录制服务配置文件
"""

import os
from dataclasses import dataclass
from typing import Optional, Literal

@dataclass
class AudioConfig:
    """音频录制配置"""

    # 录制参数
    chunk_duration: int = 5  # 每次处理的音频时长（秒）- 改为5秒实现准实时转录
    sample_rate: int = 16000  # 采样率 (Hz)
    channels: int = 1         # 声道数 (1=单声道, 2=立体声)

    # 设备设置
    use_system_audio: bool = True  # 是否尝试使用系统音频设备
    device_index: Optional[int] = None  # 指定音频设备索引，None为自动选择

    # Whisper 模型设置
    whisper_backend: Literal["openai-whisper", "faster-whisper"] = "faster-whisper"  # 后端选择
    whisper_model_size: str = "base"  # 模型大小: tiny, base, small, medium, large
    whisper_language: str = "zh"      # 识别语言
    use_simplified_chinese: bool = True  # 是否转换为简体中文
    whisper_initial_prompt: str = ""  # 移除初始提示，避免静音时的幻觉输出

    # faster-whisper 专用设置（为5秒转录优化）
    compute_type: str = "float16"     # 计算类型: float16, int8, int8_float16
    beam_size: int = 1                # 束搜索大小，1=贪心解码（最快）
    best_of: int = 1                  # 采样候选数，1为最快
    temperature: float = 0.0          # 采样温度，0为贪心解码
    condition_on_previous_text: bool = False  # 关闭前文条件生成，避免连续幻觉
    no_speech_threshold: float = 0.8  # 提高无语音阈值，更严格地过滤静音
    compression_ratio_threshold: float = 2.4  # 压缩比阈值
    log_prob_threshold: float = -0.5  # 提高对数概率阈值，过滤低质量转录

    # 处理设置
    min_silence_duration: float = 2.0  # 最小静音时长（秒），用于分段
    energy_threshold: float = 300      # 音频能量阈值，低于此值视为静音

    # 存储设置
    save_audio_files: bool = False     # 是否保存音频文件（调试用）
    audio_save_dir: str = "audio_recordings"  # 音频文件保存目录

    # 日志设置
    log_level: str = "INFO"  # 日志级别: DEBUG, INFO, WARNING, ERROR

    # 性能设置
    max_buffer_size: int = 10  # 最大缓冲区大小（音频块数量）
    processing_threads: int = 1  # 处理线程数

    def __post_init__(self):
        """配置验证和初始化"""
        # 验证模型大小
        valid_models = ["tiny", "base", "small", "medium", "large"]
        if self.whisper_model_size not in valid_models:
            raise ValueError(f"无效的 Whisper 模型大小: {self.whisper_model_size}. "
                           f"有效选项: {valid_models}")

        # 创建音频保存目录
        if self.save_audio_files:
            os.makedirs(self.audio_save_dir, exist_ok=True)

        # 验证采样率
        if self.sample_rate not in [8000, 16000, 22050, 44100, 48000]:
            raise ValueError(f"不推荐的采样率: {self.sample_rate}. "
                           f"推荐使用: 16000 (语音识别) 或 44100 (高质量音频)")

        # 验证声道数
        if self.channels not in [1, 2]:
            raise ValueError(f"无效的声道数: {self.channels}. 支持 1 (单声道) 或 2 (立体声)")

# 默认配置实例
DEFAULT_CONFIG = AudioConfig()

# 高质量配置（更好的转录效果，但需要更多资源）
HIGH_QUALITY_CONFIG = AudioConfig(
    chunk_duration=20,
    sample_rate=16000,
    whisper_backend="faster-whisper",
    whisper_model_size="small",  # 使用更大的模型
    compute_type="float16",      # 高质量计算
    beam_size=5,                 # 标准束搜索
    min_silence_duration=1.5,
    energy_threshold=200
)

# 低资源配置（适合性能较低的机器）
LOW_RESOURCE_CONFIG = AudioConfig(
    chunk_duration=45,
    sample_rate=16000,
    whisper_backend="faster-whisper",
    whisper_model_size="tiny",   # 使用最小的模型
    compute_type="int8",         # 量化计算节省资源
    beam_size=1,                 # 贪心解码，最快速度
    min_silence_duration=3.0,
    energy_threshold=400,
    processing_threads=1
)

# 调试配置（保存音频文件用于调试）
DEBUG_CONFIG = AudioConfig(
    chunk_duration=15,
    sample_rate=16000,
    whisper_backend="faster-whisper",
    whisper_model_size="base",
    compute_type="float16",
    beam_size=1,                 # 快速调试
    save_audio_files=True,
    log_level="DEBUG"
)

def get_config_by_name(config_name: str) -> AudioConfig:
    """根据名称获取配置"""
    configs = {
        "default": DEFAULT_CONFIG,
        "high_quality": HIGH_QUALITY_CONFIG,
        "low_resource": LOW_RESOURCE_CONFIG,
        "debug": DEBUG_CONFIG
    }

    if config_name not in configs:
        raise ValueError(f"未知的配置名称: {config_name}. "
                        f"可用配置: {list(configs.keys())}")

    return configs[config_name]

def print_config_info():
    """打印所有可用配置的信息"""
    configs = {
        "default": ("默认配置", "平衡性能和质量"),
        "high_quality": ("高质量配置", "更好的转录效果，需要更多资源"),
        "low_resource": ("低资源配置", "适合性能较低的机器"),
        "debug": ("调试配置", "保存音频文件用于调试")
    }

    print("可用的音频录制配置:")
    for name, (title, desc) in configs.items():
        print(f"  {name}: {title} - {desc}")