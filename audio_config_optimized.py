#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频录制服务优化配置 - 提升识别准确率
=====================================

针对中文语音识别准确率优化的配置文件
"""

import os
from dataclasses import dataclass
from typing import Optional, Literal, List, Dict

@dataclass
class OptimizedAudioConfig:
    """优化的音频录制配置 - 专注准确率提升"""

    # 📊 高质量录制参数
    chunk_duration: int = 6  # 稍微增加到6秒，给更多上下文
    sample_rate: int = 16000  # Whisper最佳采样率
    channels: int = 1         # 单声道，降噪效果更好

    # 🎯 设备设置
    use_system_audio: bool = True
    device_index: Optional[int] = None

    # 🧠 Whisper 模型设置 - 准确率优化
    whisper_backend: Literal["openai-whisper", "faster-whisper"] = "faster-whisper"
    whisper_model_size: str = "small"  # 升级到small模型，准确率更高
    whisper_language: str = "zh"
    use_simplified_chinese: bool = True

    # 📝 中文优化的初始提示 - 引导模型更好识别中文
    whisper_initial_prompt: str = "以下是一段中文普通话录音。请准确转录，包括标点符号。"

    # ⚡ faster-whisper 准确率优化设置
    compute_type: str = "float16"
    beam_size: int = 3  # 提升束搜索，平衡速度和准确率
    best_of: int = 3    # 增加候选数，提高准确率
    temperature: float = 0.1  # 轻微随机性，避免过于死板
    condition_on_previous_text: bool = True  # 启用上下文，提高连贯性

    # 🎚️ 质量阈值 - 更严格的质量控制
    no_speech_threshold: float = 0.6  # 降低阈值，减少漏检
    compression_ratio_threshold: float = 2.0  # 更严格的压缩比
    log_prob_threshold: float = -0.8  # 更宽松的概率阈值

    # 🔧 VAD优化设置
    vad_aggressiveness: int = 2  # VAD激进程度 (0-3)
    min_speech_duration: float = 0.3  # 最小语音时长
    max_silence_duration: float = 1.0  # 最大静音间隔
    max_segment_duration: float = 12.0  # 增加最大段落时长

    # 🎵 音频预处理设置
    enable_audio_enhancement: bool = True  # 启用音频增强
    noise_reduction_strength: float = 0.5  # 降噪强度 (0-1)
    volume_normalization: bool = True  # 音量标准化

    # 📚 词典和语言模型增强
    custom_vocabulary: List[str] = None  # 自定义词汇表
    enable_punctuation_model: bool = True  # 启用标点符号模型

    # 🎯 后处理优化
    enable_text_correction: bool = True  # 文本后处理校正
    enable_confidence_filtering: bool = True  # 置信度过滤
    min_confidence_threshold: float = 0.7  # 最小置信度阈值

    # 💾 存储和调试
    save_audio_files: bool = False
    audio_save_dir: str = "audio_recordings_optimized"
    log_level: str = "INFO"

    def __post_init__(self):
        """初始化后处理"""
        if self.custom_vocabulary is None:
            # 常用中文专业词汇
            self.custom_vocabulary = [
                "人工智能", "机器学习", "深度学习", "神经网络",
                "算法", "数据", "模型", "训练", "测试",
                "编程", "代码", "软件", "硬件", "系统",
                "应用", "功能", "界面", "用户", "体验"
            ]


# 🚀 预设配置方案
class OptimizedPresets:
    """优化预设配置"""

    @staticmethod
    def high_accuracy_config() -> OptimizedAudioConfig:
        """高准确率配置 - 最佳质量，稍慢"""
        return OptimizedAudioConfig(
            whisper_model_size="medium",  # 更大模型
            beam_size=5,  # 更大束搜索
            best_of=5,    # 更多候选
            temperature=0.0,  # 确定性解码
            chunk_duration=8,  # 更长上下文
            max_segment_duration=15.0,
            vad_aggressiveness=1,  # 更保守的VAD
            min_confidence_threshold=0.3  # 进一步降低阈值，接受更多转录
        )

    @staticmethod
    def balanced_config() -> OptimizedAudioConfig:
        """平衡配置 - 速度和准确率平衡"""
        return OptimizedAudioConfig(
            whisper_model_size="small",
            beam_size=3,
            best_of=3,
            temperature=0.1,
            chunk_duration=6,
            max_segment_duration=12.0,
            vad_aggressiveness=2,
            min_confidence_threshold=0.3  # 统一调整为0.3
        )

    @staticmethod
    def fast_config() -> OptimizedAudioConfig:
        """快速配置 - 优先速度"""
        return OptimizedAudioConfig(
            whisper_model_size="base",
            beam_size=1,
            best_of=1,
            temperature=0.2,
            chunk_duration=5,
            max_segment_duration=10.0,
            vad_aggressiveness=3,
            min_confidence_threshold=0.3
        )

    @staticmethod
    def noise_resistant_config() -> OptimizedAudioConfig:
        """抗噪音配置 - 适合嘈杂环境"""
        return OptimizedAudioConfig(
            whisper_model_size="small",
            beam_size=4,
            best_of=4,
            temperature=0.0,
            enable_audio_enhancement=True,
            noise_reduction_strength=0.8,
            volume_normalization=True,
            no_speech_threshold=0.7,
            vad_aggressiveness=1,  # 保守VAD，避免噪音误触
            min_confidence_threshold=0.3
        )


# 默认使用平衡配置
DEFAULT_OPTIMIZED_CONFIG = OptimizedPresets.balanced_config()

# 🎯 配置选择指南
CONFIG_GUIDE = {
    "high_accuracy": "最高准确率，适合重要会议、采访等",
    "balanced": "平衡方案，日常使用推荐",
    "fast": "快速响应，适合实时交互",
    "noise_resistant": "抗噪音，适合嘈杂环境"
}

def get_config_by_scenario(scenario: str) -> OptimizedAudioConfig:
    """根据使用场景获取配置"""
    configs = {
        "meeting": OptimizedPresets.high_accuracy_config(),
        "interview": OptimizedPresets.high_accuracy_config(),
        "daily": OptimizedPresets.balanced_config(),
        "chat": OptimizedPresets.fast_config(),
        "noisy": OptimizedPresets.noise_resistant_config(),
        "office": OptimizedPresets.noise_resistant_config()
    }
    return configs.get(scenario, DEFAULT_OPTIMIZED_CONFIG)

if __name__ == "__main__":
    print("🎯 音频识别配置优化方案")
    print("=" * 50)

    for name, desc in CONFIG_GUIDE.items():
        print(f"📋 {name}: {desc}")

    print("\n🔧 平衡配置详情:")
    config = DEFAULT_OPTIMIZED_CONFIG
    print(f"  模型大小: {config.whisper_model_size}")
    print(f"  束搜索: {config.beam_size}")
    print(f"  候选数: {config.best_of}")
    print(f"  段落长度: {config.chunk_duration}秒")
    print(f"  置信度阈值: {config.min_confidence_threshold}")