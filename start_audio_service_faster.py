#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
音频录制和语音转文字服务启动脚本 (Faster-Whisper版本)
支持使用配置文件和命令行参数
"""

import argparse
import logging
import sys
import signal
import time
from audio_config import get_config_by_name, print_config_info, AudioConfig
from audio_recorder import AudioRecorder

def setup_logging(level):
    """设置日志"""
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )

def check_dependencies():
    """检查依赖项"""
    missing_deps = []

    try:
        import pyaudio
        print("✅ PyAudio 已安装")
    except ImportError:
        missing_deps.append("pyaudio")
        print("❌ PyAudio 未安装")

    try:
        from faster_whisper import WhisperModel
        print("✅ Faster-Whisper 已安装")
    except ImportError:
        missing_deps.append("faster-whisper")
        print("❌ Faster-Whisper 未安装")

    try:
        from activity_retriever import create_db_connection
        print("✅ 数据库模块可用")
    except ImportError:
        print("⚠️  数据库模块未找到，转录结果将无法保存")

    if missing_deps:
        print("\n缺少必要依赖，请安装:")
        for dep in missing_deps:
            if dep == "pyaudio":
                print(f"  pip install {dep}")
            elif dep == "faster-whisper":
                print(f"  pip install {dep}")
        return False

    return True

def test_faster_whisper():
    """测试Faster-Whisper模型加载"""
    try:
        print("🔄 测试Faster-Whisper模型加载...")
        from faster_whisper import WhisperModel

        # 尝试加载最小模型
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("✅ Faster-Whisper模型加载成功")

        # 清理模型
        del model
        return True

    except Exception as e:
        print(f"❌ Faster-Whisper模型加载失败: {e}")
        return False

def list_audio_devices():
    """列出音频设备"""
    try:
        import pyaudio
        audio = pyaudio.PyAudio()

        print("🎤 可用的音频设备:")
        print("-" * 60)

        for i in range(audio.get_device_count()):
            device_info = audio.get_device_info_by_index(i)
            print(f"设备 {i:2d}: {device_info['name']}")
            print(f"         输入通道: {device_info['maxInputChannels']}")
            print(f"         输出通道: {device_info['maxOutputChannels']}")
            print(f"         采样率: {device_info['defaultSampleRate']}")
            print("-" * 60)

        # 显示默认设备
        try:
            default_input = audio.get_default_input_device_info()
            print(f"\n🎯 默认输入设备: {default_input['name']} (索引: {default_input['index']})")
        except:
            print("\n⚠️  无法获取默认输入设备")

        audio.terminate()

    except Exception as e:
        print(f"❌ 列出音频设备失败: {e}")

def signal_handler(signum, frame):
    """信号处理器"""
    print("\n🛑 收到停止信号，正在关闭服务...")
    if 'recorder' in globals() and recorder:
        recorder.cleanup()
    sys.exit(0)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="音频录制和语音转文字服务 (Faster-Whisper版本)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python start_audio_service_faster.py                    # 使用默认配置启动
  python start_audio_service_faster.py -c high_quality    # 使用高质量配置
  python start_audio_service_faster.py -d 5              # 指定音频设备 5
  python start_audio_service_faster.py --list-devices     # 列出所有音频设备
  python start_audio_service_faster.py --test            # 测试依赖和配置
  python start_audio_service_faster.py --compute-type int8 # 使用int8量化
        """
    )

    parser.add_argument(
        '-c', '--config',
        default='default',
        help='配置名称 (default, high_quality, low_resource, debug)'
    )

    parser.add_argument(
        '-d', '--device',
        type=int,
        help='指定音频设备索引'
    )

    parser.add_argument(
        '--chunk-duration',
        type=int,
        help='音频处理块时长（秒）'
    )

    parser.add_argument(
        '--model-size',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        help='Whisper 模型大小'
    )

    parser.add_argument(
        '--compute-type',
        choices=['float16', 'int8', 'int8_float16'],
        help='Faster-Whisper 计算类型'
    )

    parser.add_argument(
        '--beam-size',
        type=int,
        help='束搜索大小 (1-10)'
    )

    parser.add_argument(
        '--list-devices',
        action='store_true',
        help='列出所有可用的音频设备'
    )

    parser.add_argument(
        '--list-configs',
        action='store_true',
        help='列出所有可用的配置'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='测试依赖和配置'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别'
    )

    args = parser.parse_args()

    # 设置日志
    setup_logging(args.log_level)

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 处理特殊命令
    if args.list_devices:
        list_audio_devices()
        return

    if args.list_configs:
        print_config_info()
        return

    if args.test:
        print("🔍 正在检查系统环境...")
        deps_ok = check_dependencies()
        if deps_ok:
            whisper_ok = test_faster_whisper()
            if whisper_ok:
                print("✅ 所有测试通过，系统准备就绪")
            else:
                print("❌ Faster-Whisper 测试失败")
        return

    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    # 获取配置
    try:
        config = get_config_by_name(args.config)
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        print_config_info()
        sys.exit(1)

    # 强制使用faster-whisper后端
    config.whisper_backend = "faster-whisper"

    # 应用命令行参数覆盖
    if args.device is not None:
        config.device_index = args.device
        config.use_system_audio = False  # 如果指定了设备，不自动查找系统音频

    if args.chunk_duration:
        config.chunk_duration = args.chunk_duration

    if args.model_size:
        config.whisper_model_size = args.model_size

    if args.compute_type:
        config.compute_type = args.compute_type

    if args.beam_size:
        config.beam_size = args.beam_size

    if args.log_level:
        config.log_level = args.log_level

    print("🎤 启动音频录制服务 (Faster-Whisper)")
    print(f"配置: {args.config}")
    print(f"后端: {config.whisper_backend}")
    print(f"模型: {config.whisper_model_size}")
    print(f"计算类型: {config.compute_type}")
    print(f"束搜索: {config.beam_size}")
    print(f"采样率: {config.sample_rate} Hz")
    print(f"处理间隔: {config.chunk_duration} 秒")
    if config.device_index is not None:
        print(f"音频设备: 索引 {config.device_index}")
    else:
        print("音频设备: 自动检测")

    # 创建并启动录制器
    try:
        global recorder
        recorder = AudioRecorder(config=config)

        if recorder.start_recording(use_system_audio=config.use_system_audio):
            print("✅ 音频录制服务已启动")
            print("📝 转录的文本将自动保存到活动记录数据库")
            print("🔍 您可以通过活动查询界面搜索音频内容")
            print("⚡ 使用Faster-Whisper，享受更快的转录速度")
            print("⏹️  按 Ctrl+C 停止服务")

            try:
                # 保持服务运行
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 收到停止信号")
            finally:
                recorder.cleanup()
                print("✅ 服务已安全停止")
        else:
            print("❌ 启动音频录制服务失败")
            sys.exit(1)

    except Exception as e:
        logging.error(f"服务运行时出错: {e}", exc_info=True)
        print(f"❌ 服务出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()