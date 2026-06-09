#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版音频录制服务启动脚本
========================

提供多种配置选项以最大化识别准确率
"""

import sys
import logging
from enhanced_audio_recorder import EnhancedAudioRecorder, main
from audio_config_optimized import OptimizedPresets, CONFIG_GUIDE

def show_config_options():
    """显示配置选项"""
    print("🎯 增强版音频录制服务")
    print("=" * 60)
    print("📋 可用配置方案:")
    print()

    configs = {
        "1": ("high_accuracy", "最高准确率 - 适合重要会议"),
        "2": ("balanced", "平衡配置 - 日常使用推荐"),
        "3": ("fast", "快速响应 - 实时交互优先"),
        "4": ("noise_resistant", "抗噪音 - 嘈杂环境使用")
    }

    for key, (name, desc) in configs.items():
        print(f"  {key}. {desc}")

    print()
    print("🔧 技术特性:")
    print("  ✅ VAD智能分割 - 自然语音断句")
    print("  ✅ 音频增强 - 降噪和音量标准化")
    print("  ✅ 多级质量过滤 - 确保高质量转录")
    print("  ✅ 上下文优化 - 提升识别准确率")
    print("  ✅ 繁简转换 - 简体中文输出")
    print("  ✅ 自定义词汇 - 专业术语支持")
    print("=" * 60)

    return configs

def start_enhanced_service():
    """启动增强服务"""
    # 显示选项
    configs = show_config_options()

    try:
        choice = input("请选择配置方案 (1-4, 默认2): ").strip()
        if not choice:
            choice = "2"

        scenario_map = {
            "1": "meeting",
            "2": "daily",
            "3": "fast",
            "4": "noisy"
        }

        scenario = scenario_map.get(choice, "daily")
        config_name = ["", "high_accuracy", "balanced", "fast", "noise_resistant"][int(choice)] if choice in "1234" else "balanced"

        print(f"\n🚀 启动 {config_name} 配置...")
        print("=" * 40)

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # 创建录制器
        if scenario == "meeting":
            config = OptimizedPresets.high_accuracy_config()
        elif scenario == "noisy":
            config = OptimizedPresets.noise_resistant_config()
        elif scenario == "fast":
            config = OptimizedPresets.fast_config()
        else:
            config = OptimizedPresets.balanced_config()

        recorder = EnhancedAudioRecorder(config=config, scenario=scenario)

        # 显示配置详情
        print(f"📊 配置详情:")
        print(f"  🧠 模型大小: {config.whisper_model_size}")
        print(f"  ⚡ 束搜索: {config.beam_size}")
        print(f"  🎯 候选数: {config.best_of}")
        print(f"  ⏱️ 段落长度: {config.chunk_duration}秒")
        print(f"  🔊 音频增强: {'启用' if config.enable_audio_enhancement else '禁用'}")
        print(f"  📈 置信度阈值: {config.min_confidence_threshold}")
        print(f"  🎚️ VAD激进程度: {config.vad_aggressiveness}")
        print("=" * 40)

        # 开始录制
        if recorder.start_recording():
            print("✅ 增强版音频录制服务已启动")
            print("📊 实时统计信息将在停止时显示")
            print("🔄 转录结果将自动保存到数据库")
            print("按 Ctrl+C 停止服务")

            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n⏹️ 正在停止服务...")
            finally:
                recorder.cleanup()
        else:
            print("❌ 启动服务失败")

    except (ValueError, KeyboardInterrupt):
        print("\n👋 已取消启动")

if __name__ == "__main__":
    start_enhanced_service()