#!/usr/bin/env python3
# start_audio_service.py

"""
音频录制服务启动脚本
"""

import argparse
import logging
import sys
import os
from pathlib import Path

# 添加当前目录到 Python 路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from audio_recorder import AudioRecorder
from audio_config import get_config_by_name, print_config_info, DEFAULT_CONFIG

def setup_logging(log_level: str):
    """设置日志"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')

    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('audio_service.log')
        ]
    )

def check_dependencies():
    """检查依赖是否安装"""
    missing_deps = []

    try:
        import pyaudio
    except ImportError:
        missing_deps.append("pyaudio")

    try:
        import whisper
    except ImportError:
        missing_deps.append("openai-whisper")

    if missing_deps:
        print("❌ 缺少以下依赖:")
        for dep in missing_deps:
            print(f"   - {dep}")
        print("\n安装命令:")
        if "pyaudio" in missing_deps:
            print("   pip install pyaudio")
        if "openai-whisper" in missing_deps:
            print("   pip install openai-whisper")
        return False

    print("✅ 所有依赖已安装")
    return True

def list_audio_devices():
    """列出可用的音频设备"""
    try:
        import pyaudio
        audio = pyaudio.PyAudio()

        print("\n可用的音频设备:")
        print("-" * 60)

        for i in range(audio.get_device_count()):
            device_info = audio.get_device_info_by_index(i)
            device_type = []

            if device_info['maxInputChannels'] > 0:
                device_type.append("输入")
            if device_info['maxOutputChannels'] > 0:
                device_type.append("输出")

            print(f"设备 {i:2d}: {device_info['name']}")
            print(f"         类型: {', '.join(device_type)}")
            print(f"         输入通道: {device_info['maxInputChannels']}")
            print(f"         输出通道: {device_info['maxOutputChannels']}")
            print(f"         默认采样率: {int(device_info['defaultSampleRate'])} Hz")
            print("-" * 60)

        # 显示默认设备
        try:
            default_input = audio.get_default_input_device_info()
            print(f"默认输入设备: {default_input['name']} (索引: {default_input['index']})")
        except:
            print("无默认输入设备")

        try:
            default_output = audio.get_default_output_device_info()
            print(f"默认输出设备: {default_output['name']} (索引: {default_output['index']})")
        except:
            print("无默认输出设备")

        audio.terminate()

    except ImportError:
        print("❌ PyAudio 未安装，无法列出音频设备")
    except Exception as e:
        print(f"❌ 列出音频设备时出错: {e}")

def test_whisper():
    """测试 Whisper 模型"""
    try:
        import whisper
        print("正在测试 Whisper 模型...")

        # 加载最小的模型进行测试
        model = whisper.load_model("tiny")
        print("✅ Whisper 模型加载成功")

        return True
    except ImportError:
        print("❌ Whisper 未安装")
        return False
    except Exception as e:
        print(f"❌ Whisper 测试失败: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="音频录制和语音转文字服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python start_audio_service.py                    # 使用默认配置启动
  python start_audio_service.py -c high_quality    # 使用高质量配置
  python start_audio_service.py -d 5              # 指定音频设备 5
  python start_audio_service.py --list-devices     # 列出所有音频设备
  python start_audio_service.py --test            # 测试依赖和配置
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
            whisper_ok = test_whisper()
            if whisper_ok:
                print("✅ 所有测试通过，系统准备就绪")
            else:
                print("❌ Whisper 测试失败")
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

    # 应用命令行参数覆盖
    if args.device is not None:
        config.device_index = args.device
        config.use_system_audio = False  # 如果指定了设备，不自动查找系统音频

    if args.chunk_duration:
        config.chunk_duration = args.chunk_duration

    if args.model_size:
        config.whisper_model_size = args.model_size

    if args.log_level:
        config.log_level = args.log_level

    print("🎤 启动音频录制服务 (OpenAI Whisper)")
    print(f"配置: {args.config}")
    print(f"后端: openai-whisper")
    print(f"模型: {config.whisper_model_size}")
    print(f"采样率: {config.sample_rate} Hz")
    print(f"处理间隔: {config.chunk_duration} 秒")
    if config.device_index is not None:
        print(f"音频设备: {config.device_index}")
    else:
        print("音频设备: 自动检测")

    # 强制使用openai-whisper后端（兼容原版）
    config.whisper_backend = "openai-whisper"

    # 创建并启动录制器
    try:
        recorder = AudioRecorder(config=config)

        if recorder.start_recording(use_system_audio=config.use_system_audio):
            print("✅ 音频录制服务已启动")
            print("📝 转录的文本将自动保存到活动记录数据库")
            print("🔍 您可以通过活动查询界面搜索音频内容")
            print("⏹️  按 Ctrl+C 停止服务")

            try:
                # 保持服务运行
                import time
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