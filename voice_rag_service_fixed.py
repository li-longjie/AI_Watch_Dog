#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音RAG服务 - 修复版本
=====================

修复了音频格式处理问题：
- 支持WebM/OGG音频格式
- 添加音频格式转换
- 改进错误处理
- 添加详细调试日志

版本：1.1.0
"""

import asyncio
import json
import logging
import os
import time
import threading
import tempfile
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import subprocess

# 第三方库
import torch
import whisper
import pyaudio
import numpy as np
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import httpx
import edge_tts
import pygame

# ==================== 配置部分 ====================

class VoiceRAGConfig:
    """语音RAG服务配置"""

    # 服务配置
    HOST = "0.0.0.0"
    PORT = 8087

    # 音频配置
    SAMPLE_RATE = 16000
    CHANNELS = 1
    CHUNK_SIZE = 1024
    AUDIO_FORMAT = pyaudio.paInt16

    # Whisper配置
    WHISPER_MODEL = "base"  # 平衡速度和准确性
    WHISPER_LANGUAGE = "zh"
    WHISPER_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    # RAG服务配置
    RAG_SERVER_URL = "http://localhost:8085"
    ACTIVITY_SERVER_URL = "http://localhost:5001"

    # TTS配置
    TTS_VOICE = "zh-CN-XiaoyiNeural"

    # 性能优化配置
    MAX_AUDIO_DURATION = 30  # 最大音频时长（秒）
    RESPONSE_TIMEOUT = 30    # 响应超时时间（秒）- 增加到30秒以适应活动查询
    CACHE_SIZE = 100         # 缓存大小

    # FFmpeg配置（用于音频格式转换）
    FFMPEG_PATH = "ffmpeg"  # 如果ffmpeg在PATH中

    # 语音RAG服务现在作为语音交互网关，不再需要重复的意图识别关键词
    # 所有意图识别将由intelligent_agent.py统一处理

# ==================== 数据模型 ====================

class VoiceRequest(BaseModel):
    """语音请求模型"""
    audio_data: str  # Base64编码的音频数据
    format: str = "wav"
    mode: str = "rag"  # 模式：'rag'(AI问答) 或 'activity'(活动检索)

class VoiceResponse(BaseModel):
    """语音响应模型"""
    success: bool
    transcription: str = ""
    response_text: str = ""
    audio_url: str = ""
    processing_time: float = 0.0
    error: str = ""

class QueryResult(BaseModel):
    """查询结果模型"""
    success: bool
    answer: str
    query_type: str = "unknown"
    processing_time: float = 0.0

# ==================== 工具函数 ====================

def check_ffmpeg():
    """检查FFmpeg是否可用"""
    try:
        result = subprocess.run(['ffmpeg', '-version'],
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

# ==================== 核心服务类 ====================

class PerformanceOptimizer:
    """性能优化器"""

    def __init__(self):
        self.response_cache = {}
        self.model_cache = {}
        self.last_cleanup = time.time()

    def get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        return f"query_{hash(text.lower().strip())}"

    def get_cached_response(self, text: str) -> Optional[str]:
        """获取缓存响应"""
        key = self.get_cache_key(text)
        if key in self.response_cache:
            cached_item = self.response_cache[key]
            if time.time() - cached_item['timestamp'] < 300:  # 5分钟缓存
                return cached_item['response']
        return None

    def cache_response(self, text: str, response: str):
        """缓存响应"""
        key = self.get_cache_key(text)
        self.response_cache[key] = {
            'response': response,
            'timestamp': time.time()
        }

        # 定期清理缓存
        if time.time() - self.last_cleanup > 600:  # 10分钟清理一次
            self.cleanup_cache()

    def cleanup_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, item in self.response_cache.items()
            if current_time - item['timestamp'] > 300
        ]
        for key in expired_keys:
            del self.response_cache[key]
        self.last_cleanup = current_time

# 移除IntentClassifier类 - 意图识别现在由intelligent_agent.py统一处理

class AudioProcessor:
    """音频处理器 - 修复版本"""

    def __init__(self, config: VoiceRAGConfig):
        self.config = config
        self.whisper_model = None
        self.model_lock = threading.Lock()
        self.temp_dir = Path("./voice_rag_temp")
        self.temp_dir.mkdir(exist_ok=True)

        # 检查FFmpeg
        self.ffmpeg_available = check_ffmpeg()
        if not self.ffmpeg_available:
            logging.warning("FFmpeg不可用，将尝试直接处理音频文件")

        self._load_model()

    def _load_model(self):
        """预加载Whisper模型"""
        try:
            logging.info(f"正在加载Whisper模型: {self.config.WHISPER_MODEL}")
            self.whisper_model = whisper.load_model(
                self.config.WHISPER_MODEL,
                device=self.config.WHISPER_DEVICE
            )
            logging.info("Whisper模型加载完成")
        except Exception as e:
            logging.error(f"Whisper模型加载失败: {e}")
            raise

    def convert_audio_format(self, input_path: str, output_path: str) -> bool:
        """转换音频格式为WAV"""
        try:
            if self.ffmpeg_available:
                # 使用FFmpeg转换
                command = [
                    'ffmpeg',
                    '-i', input_path,
                    '-ar', str(self.config.SAMPLE_RATE),  # 采样率
                    '-ac', str(self.config.CHANNELS),     # 声道数
                    '-acodec', 'pcm_s16le',               # 编码格式
                    '-y',  # 覆盖输出文件
                    output_path
                ]

                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    logging.info(f"音频格式转换成功: {input_path} -> {output_path}")
                    return True
                else:
                    logging.error(f"FFmpeg转换失败: {result.stderr}")
                    return False
            else:
                # 如果没有FFmpeg，尝试直接复制（适用于已经是正确格式的文件）
                import shutil
                shutil.copy2(input_path, output_path)
                logging.info(f"音频文件复制完成: {input_path} -> {output_path}")
                return True

        except Exception as e:
            logging.error(f"音频格式转换失败: {e}")
            return False

    def save_audio_from_base64(self, base64_data: str, format_hint: str = "webm") -> Optional[str]:
        """从Base64数据保存音频文件"""
        try:
            # 解析Base64数据
            if ',' in base64_data:
                header, data = base64_data.split(',', 1)
                # 从header中提取格式信息
                if 'audio/webm' in header:
                    extension = 'webm'
                elif 'audio/wav' in header:
                    extension = 'wav'
                elif 'audio/ogg' in header:
                    extension = 'ogg'
                else:
                    extension = format_hint
            else:
                data = base64_data
                extension = format_hint

            # 解码Base64数据
            audio_bytes = base64.b64decode(data)

            if len(audio_bytes) == 0:
                logging.error("音频数据为空")
                return None

            # 保存到临时文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            temp_file = self.temp_dir / f"input_{timestamp}.{extension}"

            with open(temp_file, 'wb') as f:
                f.write(audio_bytes)

            logging.info(f"音频文件保存完成: {temp_file} ({len(audio_bytes)} bytes)")
            return str(temp_file)

        except Exception as e:
            logging.error(f"保存音频文件失败: {e}")
            return None

    async def transcribe_audio(self, audio_data: str, format_hint: str = "webm") -> Tuple[str, float]:
        """转录音频为文本 - 修复版本"""
        start_time = time.time()

        try:
            # 1. 保存Base64音频数据到临时文件
            input_file = self.save_audio_from_base64(audio_data, format_hint)
            if not input_file:
                return "", time.time() - start_time

            # 2. 转换音频格式为WAV
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            wav_file = self.temp_dir / f"converted_{timestamp}.wav"

            if not self.convert_audio_format(input_file, str(wav_file)):
                logging.error("音频格式转换失败")
                # 清理临时文件
                if os.path.exists(input_file):
                    os.remove(input_file)
                return "", time.time() - start_time

            # 3. 使用Whisper转录
            loop = asyncio.get_event_loop()

            def transcribe():
                with self.model_lock:
                    try:
                        result = self.whisper_model.transcribe(
                            str(wav_file),
                            language=self.config.WHISPER_LANGUAGE,
                            initial_prompt="以下是普通话的句子。",
                            word_timestamps=False
                        )
                        return result["text"].strip()
                    except Exception as e:
                        logging.error(f"Whisper转录异常: {e}")
                        return ""

            # 在线程池中执行转录
            transcription = await loop.run_in_executor(None, transcribe)

            # 4. 清理临时文件
            try:
                if os.path.exists(input_file):
                    os.remove(input_file)
                if os.path.exists(wav_file):
                    os.remove(wav_file)
            except Exception as e:
                logging.warning(f"清理临时文件失败: {e}")

            processing_time = time.time() - start_time

            if transcription:
                logging.info(f"语音转录完成: '{transcription}' (耗时: {processing_time:.2f}s)")
            else:
                logging.warning(f"语音转录结果为空 (耗时: {processing_time:.2f}s)")

            return transcription, processing_time

        except Exception as e:
            logging.error(f"语音转录失败: {e}")
            return "", time.time() - start_time

class IntelligentQueryClient:
    """智能查询客户端 - 直接调用intelligent_agent"""

    def __init__(self, config: VoiceRAGConfig):
        self.config = config
        # 导入智能代理
        try:
            from intelligent_agent import IntelligentAgent
            self.intelligent_agent = IntelligentAgent()
            logging.info("智能代理初始化成功")
        except ImportError as e:
            logging.error(f"无法导入智能代理: {e}")
            self.intelligent_agent = None

    async def process_query(self, text: str, mode: str = "rag") -> QueryResult:
        """使用智能代理处理查询。

        关键改动：当智能代理返回“重定向”方法（video_activity_redirect/activity_redirect）时，
        直接执行对应的数据源查询并返回最终结果，而不是把提示语"请稍候..." 原样返回给前端。
        """
        start_time = time.time()

        try:
            if not self.intelligent_agent:
                # 如果智能代理不可用，回退到RAG服务
                return await self._fallback_to_rag(text, start_time, mode)

            # 使用智能代理处理请求，传递模式信息
            result = await self.intelligent_agent.process_user_request(text, mode=mode)

            if result.get("status") == "success":
                method = result.get("method", "")
                # 当检测到重定向指示时，直接走后端查询拿最终答案
                if method in ("video_activity_redirect", "activity_redirect"):
                    logging.info(f"检测到{method}，改为直接查询对应数据源")
                    return await self._fallback_to_rag(text, start_time, mode)

                answer = result.get("answer", "抱歉，无法处理您的请求")
                query_type = method or "intelligent_agent"

                return QueryResult(
                    success=True,
                    answer=answer,
                    query_type=query_type,
                    processing_time=time.time() - start_time
                )
            else:
                # 智能代理处理失败，回退到RAG服务
                logging.warning(f"智能代理处理失败: {result}")
                return await self._fallback_to_rag(text, start_time, mode)

        except Exception as e:
            logging.error(f"智能代理查询失败: {e}")
            # 出现异常时回退到RAG服务
            return await self._fallback_to_rag(text, start_time, mode)

    async def _fallback_to_rag(self, text: str, start_time: float, mode: str = "rag") -> QueryResult:
        """回退到RAG服务"""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.config.RESPONSE_TIMEOUT) as client:
                if mode == "activity":
                    # 活动检索模式 - 调用活动服务
                    response = await client.post(
                        f"{self.config.ACTIVITY_SERVER_URL}/api/query",
                        json={"message": text},
                        headers={"Content-Type": "application/json"}
                    )

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("result"):
                            return QueryResult(
                                success=True,
                                answer=data.get("result", "无法获取活动信息"),
                                query_type="activity_fallback",
                                processing_time=time.time() - start_time
                            )
                else:
                    # AI问答模式 - 调用RAG服务
                    response = await client.post(
                        f"{self.config.RAG_SERVER_URL}/detect_intent/",
                        json={"query": text, "mode": mode},
                        headers={"Content-Type": "application/json"}
                    )

                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "success":
                            return QueryResult(
                                success=True,
                                answer=data.get("answer", "无法获取回答"),
                                query_type="rag_fallback",
                                processing_time=time.time() - start_time
                            )

                return QueryResult(
                    success=False,
                    answer="抱歉，服务暂时不可用，请稍后重试",
                    processing_time=time.time() - start_time
                )

        except Exception as e:
            logging.error(f"回退服务失败: {e}")
            return QueryResult(
                success=False,
                answer="网络连接错误，请检查服务状态",
                processing_time=time.time() - start_time
            )

class TTSProcessor:
    """语音合成处理器"""

    def __init__(self, config: VoiceRAGConfig):
        self.config = config
        self.output_dir = Path("./voice_rag_output")
        self.output_dir.mkdir(exist_ok=True)

    async def generate_speech(self, text: str) -> str:
        """生成语音文件"""
        try:
            # 生成唯一文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"tts_{timestamp}.mp3"
            filepath = self.output_dir / filename

            # 使用Edge-TTS生成语音
            communicate = edge_tts.Communicate(text, self.config.TTS_VOICE)
            await communicate.save(str(filepath))

            logging.info(f"语音合成完成: {filename}")
            return str(filepath)

        except Exception as e:
            logging.error(f"语音合成失败: {e}")
            return ""

# ==================== 主服务类 ====================

class VoiceRAGService:
    """语音RAG集成服务 - 简化版本，专注于语音交互"""

    def __init__(self):
        self.config = VoiceRAGConfig()
        self.performance_optimizer = PerformanceOptimizer()
        self.audio_processor = AudioProcessor(self.config)
        self.query_client = IntelligentQueryClient(self.config)  # 使用智能查询客户端
        self.tts_processor = TTSProcessor(self.config)

        # 初始化pygame用于音频播放
        pygame.mixer.init()

        logging.info("语音RAG服务初始化完成")

    async def process_voice_request(self, audio_data: str, format_hint: str = "webm", mode: str = "rag") -> VoiceResponse:
        """处理语音请求的主入口 - 修复版本"""
        start_time = time.time()

        try:
            logging.info(f"开始处理语音请求，格式提示: {format_hint}")

            # 1. 语音转文本
            transcription, transcribe_time = await self.audio_processor.transcribe_audio(
                audio_data, format_hint
            )

            if not transcription:
                return VoiceResponse(
                    success=False,
                    error="无法识别语音内容，请确保说话清晰且环境安静",
                    processing_time=time.time() - start_time
                )

            logging.info(f"语音识别成功: '{transcription}'")

            # 2. 检查缓存
            cached_response = self.performance_optimizer.get_cached_response(transcription)
            if cached_response:
                logging.info(f"使用缓存响应: {transcription}")
                return VoiceResponse(
                    success=True,
                    transcription=transcription,
                    response_text=cached_response,
                    processing_time=time.time() - start_time
                )

            # 3. 直接使用智能代理处理查询（跳过重复的意图分类）
            query_result = await self.query_client.process_query(transcription, mode)
            logging.info(f"智能代理处理结果: {query_result.query_type}, 模式: {mode}")

            if not query_result.success:
                return VoiceResponse(
                    success=False,
                    transcription=transcription,
                    error=query_result.answer,
                    processing_time=time.time() - start_time
                )

            # 5. 生成语音回复
            audio_path = await self.tts_processor.generate_speech(query_result.answer)

            # 6. 缓存响应
            self.performance_optimizer.cache_response(transcription, query_result.answer)

            # 7. 返回结果
            return VoiceResponse(
                success=True,
                transcription=transcription,
                response_text=query_result.answer,
                audio_url=audio_path,
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logging.error(f"处理语音请求失败: {e}")
            return VoiceResponse(
                success=False,
                transcription=transcription if 'transcription' in locals() else "",
                error=f"处理请求时发生错误: {str(e)}",
                processing_time=time.time() - start_time
            )

    async def cleanup(self):
        """清理资源"""
        # 智能查询客户端不需要特殊的清理操作
        pygame.mixer.quit()
        logging.info("语音RAG服务资源清理完成")

# ==================== FastAPI应用 ====================

# 创建FastAPI应用
app = FastAPI(
    title="语音RAG集成服务 - 简化版本",
    description="专注于语音交互的智能网关，集成intelligent_agent进行统一意图识别",
    version="2.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局服务实例
voice_rag_service = None

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global voice_rag_service

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 初始化服务
    voice_rag_service = VoiceRAGService()
    logging.info("语音RAG服务启动完成")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    global voice_rag_service
    if voice_rag_service:
        await voice_rag_service.cleanup()
    logging.info("语音RAG服务已关闭")

@app.post("/api/voice/transcribe")
async def transcribe_voice(request: VoiceRequest):
    """仅进行语音转录的API端点"""
    try:
        logging.info(f"收到语音转录请求，格式: {request.format}")

        # 只进行语音转录，不进行RAG处理
        transcription, transcribe_time = await voice_rag_service.audio_processor.transcribe_audio(
            request.audio_data,
            request.format
        )

        result = {
            "success": bool(transcription),
            "transcription": transcription,
            "transcribe_time": transcribe_time
        }

        if not transcription:
            result["error"] = "无法识别语音内容，请确保说话清晰且环境安静"

        logging.info(f"语音转录完成，成功: {result['success']}, 转录耗时: {transcribe_time:.2f}s")
        return result

    except Exception as e:
        logging.error(f"转录API处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice/process", response_model=VoiceResponse)
async def process_voice(request: VoiceRequest):
    """处理语音请求的API端点 - 简化版本，使用intelligent_agent统一处理"""
    try:
        logging.info(f"收到语音处理请求，格式: {request.format}, 模式: {request.mode}")

        # 处理语音请求
        result = await voice_rag_service.process_voice_request(
            request.audio_data,
            request.format,
            request.mode
        )

        logging.info(f"语音处理完成，成功: {result.success}")
        return result

    except Exception as e:
        logging.error(f"API处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "Voice RAG Service - Simplified",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "intelligent_agent_available": voice_rag_service.query_client.intelligent_agent is not None,
        "ffmpeg_available": check_ffmpeg()
    }

@app.get("/api/status")
async def get_status():
    """获取服务状态"""
    return {
        "whisper_model": voice_rag_service.config.WHISPER_MODEL,
        "device": voice_rag_service.config.WHISPER_DEVICE,
        "cache_size": len(voice_rag_service.performance_optimizer.response_cache),
        "intelligent_agent_available": voice_rag_service.query_client.intelligent_agent is not None,
        "rag_server": voice_rag_service.config.RAG_SERVER_URL,
        "ffmpeg_available": voice_rag_service.audio_processor.ffmpeg_available
    }

# ==================== 主程序入口 ====================

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🎤 语音RAG集成服务 - 修复版本")
    print("=" * 50)
    print(f"🌐 服务地址: http://{VoiceRAGConfig.HOST}:{VoiceRAGConfig.PORT}")
    print(f"🤖 Whisper模型: {VoiceRAGConfig.WHISPER_MODEL}")
    print(f"💻 运行设备: {VoiceRAGConfig.WHISPER_DEVICE}")
    print(f"📊 RAG服务: {VoiceRAGConfig.RAG_SERVER_URL}")
    print(f"📱 活动服务: {VoiceRAGConfig.ACTIVITY_SERVER_URL}")
    print(f"🔧 FFmpeg可用: {check_ffmpeg()}")
    print("=" * 50)
    print("✨ 功能特点:")
    print("  • 高精度语音识别 (Whisper)")
    print("  • 音频格式自动转换")
    print("  • 智能意图识别")
    print("  • RAG数据库查询")
    print("  • 快速响应缓存")
    print("  • 语音合成回复")
    print("=" * 50)

    # 启动服务
    uvicorn.run(
        app,
        host=VoiceRAGConfig.HOST,
        port=VoiceRAGConfig.PORT,
        log_level="info"
    )