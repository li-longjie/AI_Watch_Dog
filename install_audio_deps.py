#!/usr/bin/env python3
# install_audio_deps.py

"""
音频服务依赖安装脚本
"""

import subprocess
import sys
import platform
import os

def run_command(command, description):
    """运行命令并显示结果"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description}成功")
            return True
        else:
            print(f"❌ {description}失败:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ {description}出错: {e}")
        return False

def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    print(f"🐍 Python 版本: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ 需要 Python 3.8 或更高版本")
        return False

    print("✅ Python 版本满足要求")
    return True

def install_pyaudio():
    """安装 PyAudio"""
    system = platform.system().lower()

    if system == "windows":
        # Windows 上安装 PyAudio
        print("🪟 检测到 Windows 系统")
        success = run_command("pip install pyaudio", "安装 PyAudio")

        if not success:
            print("⚠️  如果安装失败，请尝试以下方法:")
            print("1. 使用预编译的 wheel:")
            print("   pip install pipwin")
            print("   pipwin install pyaudio")
            print("2. 或从 https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio 下载对应版本")

        return success

    elif system == "darwin":  # macOS
        print("🍎 检测到 macOS 系统")
        # 先尝试安装 portaudio
        print("📦 安装 PortAudio...")
        if run_command("brew install portaudio", "安装 PortAudio (使用 Homebrew)"):
            return run_command("pip install pyaudio", "安装 PyAudio")
        else:
            print("⚠️  请先安装 Homebrew，然后运行:")
            print("   brew install portaudio")
            print("   pip install pyaudio")
            return False

    elif system == "linux":
        print("🐧 检测到 Linux 系统")
        # Linux 上需要先安装系统依赖
        print("📦 安装系统依赖...")

        # 检测发行版
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = f.read().lower()

            if 'ubuntu' in os_info or 'debian' in os_info:
                if run_command("sudo apt-get update", "更新包列表"):
                    if run_command("sudo apt-get install -y portaudio19-dev python3-pyaudio", "安装 PortAudio 和依赖"):
                        return run_command("pip install pyaudio", "安装 PyAudio")

            elif 'centos' in os_info or 'rhel' in os_info or 'fedora' in os_info:
                if run_command("sudo yum install -y portaudio-devel", "安装 PortAudio 开发包"):
                    return run_command("pip install pyaudio", "安装 PyAudio")

            else:
                print("⚠️  未识别的 Linux 发行版，请手动安装 PortAudio 开发包")
                return run_command("pip install pyaudio", "安装 PyAudio")

        except Exception as e:
            print(f"⚠️  检测 Linux 发行版时出错: {e}")
            return run_command("pip install pyaudio", "安装 PyAudio")

    else:
        print(f"⚠️  未知操作系统: {system}")
        return run_command("pip install pyaudio", "安装 PyAudio")

def install_whisper():
    """安装 Whisper"""
    print("🎤 安装 OpenAI Whisper...")

    # 先尝试安装 torch (Whisper 的依赖)
    if run_command("pip install torch torchvision torchaudio", "安装 PyTorch"):
        return run_command("pip install openai-whisper", "安装 Whisper")
    else:
        print("⚠️  PyTorch 安装失败，尝试仅安装 Whisper...")
        return run_command("pip install openai-whisper", "安装 Whisper")

def install_other_deps():
    """安装其他依赖"""
    deps = [
        "numpy",
        "scipy",
        "librosa",  # 音频处理
        "soundfile",  # 音频文件读写
    ]

    success_count = 0
    for dep in deps:
        if run_command(f"pip install {dep}", f"安装 {dep}"):
            success_count += 1

    print(f"📦 其他依赖安装完成: {success_count}/{len(deps)}")
    return success_count == len(deps)

def test_installation():
    """测试安装结果"""
    print("\n🧪 测试安装结果...")

    # 测试 PyAudio
    try:
        import pyaudio
        print("✅ PyAudio 导入成功")

        # 测试创建 PyAudio 实例
        audio = pyaudio.PyAudio()
        device_count = audio.get_device_count()
        print(f"✅ 检测到 {device_count} 个音频设备")
        audio.terminate()

    except ImportError:
        print("❌ PyAudio 导入失败")
        return False
    except Exception as e:
        print(f"❌ PyAudio 测试失败: {e}")
        return False

    # 测试 Whisper
    try:
        import whisper
        print("✅ Whisper 导入成功")

        # 测试加载模型
        print("🔄 测试加载 Whisper 模型...")
        model = whisper.load_model("tiny")
        print("✅ Whisper 模型加载成功")

    except ImportError:
        print("❌ Whisper 导入失败")
        return False
    except Exception as e:
        print(f"❌ Whisper 测试失败: {e}")
        return False

    return True

def main():
    print("🎵 音频服务依赖安装器")
    print("=" * 40)

    # 检查 Python 版本
    if not check_python_version():
        sys.exit(1)

    print("\n📋 将要安装的组件:")
    print("- PyAudio (音频录制)")
    print("- OpenAI Whisper (语音转文字)")
    print("- 相关依赖包")

    try:
        confirm = input("\n是否继续安装? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ 安装已取消")
            sys.exit(0)
    except KeyboardInterrupt:
        print("\n❌ 安装已取消")
        sys.exit(0)

    print("\n🚀 开始安装...")

    # 升级 pip
    run_command("python -m pip install --upgrade pip", "升级 pip")

    # 安装组件
    success_count = 0
    total_count = 3

    if install_pyaudio():
        success_count += 1

    if install_whisper():
        success_count += 1

    if install_other_deps():
        success_count += 1

    print(f"\n📊 安装完成: {success_count}/{total_count}")

    if success_count == total_count:
        print("✅ 所有组件安装成功!")

        # 测试安装
        if test_installation():
            print("\n🎉 安装测试通过!")
            print("\n📝 后续步骤:")
            print("1. 运行测试脚本: python test_audio_simple.py")
            print("2. 启动音频服务: python start_audio_service.py")
        else:
            print("\n⚠️  安装测试失败，可能需要手动检查")
    else:
        print("\n⚠️  部分组件安装失败")
        print("请检查错误信息并手动安装失败的组件")

if __name__ == "__main__":
    main()