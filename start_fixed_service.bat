@echo off
echo 正在停止旧的语音RAG服务...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq voice_rag_service*" 2>nul

echo.
echo 🎤 启动修复版本的语音RAG服务...
echo ================================================
echo 如果出现错误，请确保：
echo 1. 已激活 Awd 环境：conda activate Awd
echo 2. 已安装所需依赖：pip install whisper
echo 3. FFmpeg 可用（已检查通过）
echo ================================================
echo.

python voice_rag_service_fixed.py

pause