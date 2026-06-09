#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
准实时音频录制服务启动脚本
===========================

启动配置为5秒转录间隔的音频录制服务，实现准实时转录。
"""

import sys
import logging
from audio_recorder import AudioRecorder, main
from audio_config import AudioConfig

def start_realtime_audio_service():
    """启动准实时音频录制服务"""

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🎤 准实时音频录制服务")
    print("=" * 50)
    print("📊 配置信息:")
    print(f"  转录间隔: 5秒（准实时）")
    print(f"  Whisper后端: Faster-Whisper")
    print(f"  模型大小: base")
    print(f"  计算类型: float16/int8")
    print(f"  优化模式: 贪心解码（最快）")
    print("=" * 50)
    print("🚀 启动服务...")

    # 直接调用主函数，它会使用更新后的配置
    main()

if __name__ == "__main__":
    start_realtime_audio_service()