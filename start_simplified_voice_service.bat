@echo off
echo 启动简化版本的语音RAG服务...
echo.
echo 服务特性:
echo - 使用intelligent_agent统一意图识别
echo - 移除重复的意图分类逻辑
echo - 专注于语音交互网关功能
echo.
python voice_rag_service_fixed.py
pause