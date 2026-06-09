#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能音频录制服务启动脚本
========================

启动集成VAD语音活动检测的智能音频录制服务，
自动在语音停顿处分割，确保句子完整性。
"""

import sys
import logging
from smart_audio_recorder import SmartAudioRecorder, main

def start_smart_audio_service():
    """启动智能音频录制服务"""

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🧠 智能音频录制服务 (VAD语音活动检测)")
    print("=" * 60)
    print("📊 技术特性:")
    print("  🎯 VAD智能分割: 在语音停顿处自然分段")
    print("  📝 句子完整性: 避免固定时间分割导致的句子截断")
    print("  ⚡ 实时响应: 0.5-8秒弹性段落，更自然")
    print("  🔄 繁简转换: 自动转换为简体中文")
    print("  🚫 幻觉过滤: 智能过滤低质量转录")
    print("=" * 60)
    print("🔧 VAD配置:")
    print("  激进程度: 2 (中等)")
    print("  最小语音时长: 0.5秒")
    print("  最大静音间隔: 1.5秒")
    print("  最大段落时长: 8秒")
    print("=" * 60)
    print("🚀 启动服务...")

    # 直接调用主函数
    main()

if __name__ == "__main__":
    start_smart_audio_service()