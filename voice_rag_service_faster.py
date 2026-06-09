#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音RAG服务 - Faster-Whisper版本
===============================

升级到Faster-Whisper，显著提升性能：
- 2-4倍更快的转录速度
- 减少67%内存使用
- 支持int8量化加速
- GPU优化更好
- 保持相同的转录准确度

版本：2.0.0 (Faster-Whisper)
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
import pyaudio
import numpy as np
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import httpx
import edge_tts
import pygame

# Faster-Whisper (优先) 和 原版Whisper (备用)
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logging.warning("Faster-Whisper 未安装，将使用原版Whisper")

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logging.warning("原版Whisper 未安装")

if not FASTER_WHISPER_AVAILABLE and not WHISPER_AVAILABLE:
    raise ImportError("请安装 faster-whisper 或 openai-whisper: pip install faster-whisper")

# ==================== 配置部分 ====================

class VoiceRAGConfig:
    """语音RAG服务配置 - Faster-Whisper优化版本"""

    # 服务配置
    HOST = "0.0.0.0"
    PORT = 8087  # 与原版保持一致，实现无缝替换
    # PORT = 8088  # 如需测试，可临时修改为8088

    # 音频配置
    SAMPLE_RATE = 16000
    CHANNELS = 1
    CHUNK_SIZE = 1024
    AUDIO_FORMAT = pyaudio.paInt16

    # Whisper配置 - Faster-Whisper优化
    WHISPER_BACKEND = "faster-whisper"  # "faster-whisper" 或 "openai-whisper"
    WHISPER_MODEL = "base"  # 平衡速度和准确性
    WHISPER_LANGUAGE = "zh"
    WHISPER_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    # Faster-Whisper专用配置
    COMPUTE_TYPE = "float16"  # float16, int8, int8_float16
    BEAM_SIZE = 1             # 1=贪心解码(最快), 5=标准, 10=最准确
    BEST_OF = 1               # 采样候选数，1最快
    TEMPERATURE = 0.0         # 0=确定性输出
    CONDITION_ON_PREVIOUS_TEXT = True
    NO_SPEECH_THRESHOLD = 0.6
    COMPRESSION_RATIO_THRESHOLD = 2.4
    LOG_PROB_THRESHOLD = -1.0

    # RAG服务配置
    RAG_SERVER_URL = "http://localhost:8085"
    ACTIVITY_SERVER_URL = "http://localhost:5001"

    # TTS配置 - 升级为更灵动的语音选项
    # 主要语音：使用更自然、情感丰富的语音
    TTS_VOICE = "zh-CN-XiaoxiaoNeural"  # 晓晓 - 温暖自然，适合日常对话

    # 语音选择策略配置
    VOICE_SELECTION_MODE = "adaptive"  # "fixed", "adaptive", "random"

    # 多种语音选项 - 根据内容和情感自动选择
    VOICE_OPTIONS = {
        # 中文语音 - 按情感和场景分类
        "friendly": "zh-CN-XiaoxiaoNeural",      # 晓晓 - 友好温暖
        "lively": "zh-CN-XiaoyiNeural",          # 小艺 - 活泼生动
        "calm": "zh-CN-YunxiNeural",             # 云希 - 沉稳磁性
        "energetic": "zh-CN-YunyangNeural",      # 云扬 - 充满活力
        "gentle": "zh-CN-YunxiaNeural",          # 云夏 - 温柔甜美
        "storytelling": "zh-CN-YunjianNeural",   # 云健 - 适合讲故事

        # 多语言支持
        "english": "en-US-AvaMultilingualNeural",    # 自然流畅的英文
        "japanese": "ja-JP-NanamiNeural",            # 日语
        "french": "fr-FR-DeniseNeural",              # 法语
        "german": "de-DE-KatjaNeural",               # 德语
    }

    # 情感和风格控制
    EMOTION_STYLES = {
        "default": "",
        "cheerful": "cheerful",
        "excited": "excited",
        "friendly": "friendly",
        "hopeful": "hopeful",
        "sad": "sad",
        "angry": "angry",
        "fearful": "fearful",
        "disgruntled": "disgruntled",
        "serious": "serious",
        "affectionate": "affectionate",
        "gentle": "gentle",
        "lyrical": "lyrical"
    }

    # 性能优化配置
    MAX_AUDIO_DURATION = 30  # 最大音频时长（秒）
    RESPONSE_TIMEOUT = 30    # 响应超时时间（秒）
    CACHE_SIZE = 100         # 缓存大小

    # FFmpeg配置
    FFMPEG_PATH = "ffmpeg"

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
    transcribe_time: float = 0.0  # 新增：转录耗时
    backend_used: str = ""        # 新增：使用的后端
    voice_used: str = ""          # 新增：使用的语音类型
    auto_play: bool = True        # 新增：是否自动播放
    should_play_immediately: bool = True  # 新增：是否立即播放
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

def is_cuda_available():
    """检查CUDA是否可用"""
    try:
        return torch.cuda.is_available()
    except:
        return False

def clean_text_for_tts(text: str) -> str:
    """清理文本用于语音合成，移除Markdown格式符号"""
    if not text:
        return ""

    cleaned = text

    # 最简单的方法：直接替换所有可能的Markdown符号

    # 先移除三个连续的符号，再移除两个，最后移除单个
    markdown_patterns = [
        '***',  # 三个星号
        '___',  # 三个下划线
        '**',   # 两个星号
        '__',   # 两个下划线
        '~~',   # 删除线
        '```',  # 代码块
        '*',    # 单个星号
        '_',    # 单个下划线
        '`',    # 反引号
        '#',    # 井号
        '|',    # 竖线
        '[',    # 左方括号
        ']',    # 右方括号
        '(',    # 左圆括号（在链接中）
        ')',    # 右圆括号（在链接中）
        '{',    # 左花括号
        '}',    # 右花括号
        '<',    # 左尖括号
        '>',    # 右尖括号
        '-',    # 连字符（用于列表）
        '+',    # 加号（用于列表）
    ]

    for pattern in markdown_patterns:
        cleaned = cleaned.replace(pattern, ' ')

    # 清理数字列表标记（但保留小数）
    import re
    # 只删除数字列表标记（如"1. "），但保留小数（如"0.3"）
    cleaned = re.sub(r'(?<!\d)\d+\.\s+', '', cleaned)

    # 清理多余空白
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()

    return cleaned

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

class AudioProcessor:
    """音频处理器 - Faster-Whisper版本"""

    def __init__(self, config: VoiceRAGConfig):
        self.config = config
        self.faster_whisper_model = None
        self.whisper_model = None
        self.model_lock = threading.Lock()
        self.temp_dir = Path("./voice_rag_temp")
        self.temp_dir.mkdir(exist_ok=True)
        self.backend_used = "none"

        # 检查FFmpeg
        self.ffmpeg_available = check_ffmpeg()
        if not self.ffmpeg_available:
            logging.warning("FFmpeg不可用，将尝试直接处理音频文件")

        self._load_model()

    def _load_model(self):
        """加载Whisper模型 - 优先使用Faster-Whisper"""
        try:
            if self.config.WHISPER_BACKEND == "faster-whisper" and FASTER_WHISPER_AVAILABLE:
                self._load_faster_whisper()
            elif self.config.WHISPER_BACKEND == "openai-whisper" and WHISPER_AVAILABLE:
                self._load_openai_whisper()
            else:
                # 自动选择可用的后端
                if FASTER_WHISPER_AVAILABLE:
                    self._load_faster_whisper()
                elif WHISPER_AVAILABLE:
                    self._load_openai_whisper()
                else:
                    raise ImportError("没有可用的Whisper后端")

        except Exception as e:
            logging.error(f"模型加载失败: {e}")
            raise

    def _load_faster_whisper(self):
        """加载Faster-Whisper模型"""
        try:
            logging.info(f"正在加载 Faster-Whisper 模型: {self.config.WHISPER_MODEL}")

            device = "cuda" if is_cuda_available() else "cpu"
            compute_type = self.config.COMPUTE_TYPE

            # 如果是CPU，自动调整compute_type
            if device == "cpu" and compute_type == "float16":
                compute_type = "int8"
                logging.info("CPU环境下自动切换到int8计算类型")

            self.faster_whisper_model = WhisperModel(
                self.config.WHISPER_MODEL,
                device=device,
                compute_type=compute_type
            )

            self.backend_used = "faster-whisper"
            logging.info(f"Faster-Whisper 模型加载完成 (设备: {device}, 计算类型: {compute_type})")

        except Exception as e:
            logging.error(f"Faster-Whisper 模型加载失败: {e}")
            # 回退到原版Whisper
            if WHISPER_AVAILABLE:
                logging.info("回退到原版Whisper")
                self._load_openai_whisper()
            else:
                raise

    def _load_openai_whisper(self):
        """加载原版Whisper模型"""
        try:
            logging.info(f"正在加载 OpenAI-Whisper 模型: {self.config.WHISPER_MODEL}")
            self.whisper_model = whisper.load_model(
                self.config.WHISPER_MODEL,
                device=self.config.WHISPER_DEVICE
            )
            self.backend_used = "openai-whisper"
            logging.info("OpenAI-Whisper 模型加载完成")

        except Exception as e:
            logging.error(f"OpenAI-Whisper 模型加载失败: {e}")
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
                # 如果没有FFmpeg，尝试直接复制
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

    async def transcribe_audio(self, audio_data: str, format_hint: str = "webm") -> Tuple[str, float, str]:
        """转录音频为文本 - Faster-Whisper版本"""
        start_time = time.time()

        try:
            # 1. 保存Base64音频数据到临时文件
            input_file = self.save_audio_from_base64(audio_data, format_hint)
            if not input_file:
                return "", time.time() - start_time, self.backend_used

            # 2. 转换音频格式为WAV
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            wav_file = self.temp_dir / f"converted_{timestamp}.wav"

            if not self.convert_audio_format(input_file, str(wav_file)):
                logging.error("音频格式转换失败")
                # 清理临时文件
                if os.path.exists(input_file):
                    os.remove(input_file)
                return "", time.time() - start_time, self.backend_used

            # 3. 选择转录方法
            if self.faster_whisper_model:
                transcription = await self._transcribe_with_faster_whisper(wav_file)
            elif self.whisper_model:
                transcription = await self._transcribe_with_openai_whisper(wav_file)
            else:
                logging.error("没有可用的Whisper模型")
                transcription = ""

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
                logging.info(f"语音转录完成 ({self.backend_used}): '{transcription}' (耗时: {processing_time:.2f}s)")
            else:
                logging.warning(f"语音转录结果为空 ({self.backend_used}) (耗时: {processing_time:.2f}s)")

            return transcription, processing_time, self.backend_used

        except Exception as e:
            logging.error(f"语音转录失败: {e}")
            return "", time.time() - start_time, self.backend_used

    async def _transcribe_with_faster_whisper(self, wav_file: Path) -> str:
        """使用Faster-Whisper转录"""
        try:
            loop = asyncio.get_event_loop()

            def transcribe():
                with self.model_lock:
                    try:
                        segments, info = self.faster_whisper_model.transcribe(
                            str(wav_file),
                            language=self.config.WHISPER_LANGUAGE,
                            task='transcribe',
                            beam_size=self.config.BEAM_SIZE,
                            best_of=self.config.BEST_OF,
                            temperature=self.config.TEMPERATURE,
                            condition_on_previous_text=self.config.CONDITION_ON_PREVIOUS_TEXT,
                            no_speech_threshold=self.config.NO_SPEECH_THRESHOLD,
                            compression_ratio_threshold=self.config.COMPRESSION_RATIO_THRESHOLD,
                            log_prob_threshold=self.config.LOG_PROB_THRESHOLD,
                            initial_prompt="以下是普通话的句子。"
                        )

                        # 拼接所有段落的文本
                        text = "".join([segment.text for segment in segments]).strip()
                        return text

                    except Exception as e:
                        logging.error(f"Faster-Whisper转录异常: {e}")
                        return ""

            # 在线程池中执行转录
            return await loop.run_in_executor(None, transcribe)

        except Exception as e:
            logging.error(f"Faster-Whisper转录失败: {e}")
            return ""

    async def _transcribe_with_openai_whisper(self, wav_file: Path) -> str:
        """使用OpenAI-Whisper转录"""
        try:
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
                        logging.error(f"OpenAI-Whisper转录异常: {e}")
                        return ""

            # 在线程池中执行转录
            return await loop.run_in_executor(None, transcribe)

        except Exception as e:
            logging.error(f"OpenAI-Whisper转录失败: {e}")
            return ""

class IntelligentQueryClient:
    """智能查询客户端"""

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
        """使用智能代理处理查询"""
        start_time = time.time()

        try:
            if not self.intelligent_agent:
                # 如果智能代理不可用，回退到RAG服务
                return await self._fallback_to_rag(text, start_time, mode)

            # 使用智能代理处理请求
            result = await self.intelligent_agent.process_user_request(text, mode=mode)

            if result.get("status") == "success":
                method = result.get("method", "")
                # 当检测到重定向指示时，直接走后端查询
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
            async with httpx.AsyncClient(timeout=self.config.RESPONSE_TIMEOUT) as client:
                if mode == "activity":
                    # 活动检索模式
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
                    # AI问答模式
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
    """语音合成处理器 - 支持智能语音选择和情感控制"""

    def __init__(self, config: VoiceRAGConfig):
        self.config = config
        self.output_dir = Path("./voice_rag_output")
        self.output_dir.mkdir(exist_ok=True)

        # 导入语言检测库
        try:
            import langid
            self.langid = langid
            self.language_detection_available = True
        except ImportError:
            logging.warning("langid库未安装，将使用默认中文语音")
            self.language_detection_available = False

    def detect_emotion_and_content_type(self, text: str) -> tuple:
        """检测文本情感和内容类型"""
        text_lower = text.lower()

        # 情感检测关键词
        emotion_keywords = {
            "excited": ["太棒了", "amazing", "awesome", "excited", "wonderful", "fantastic", "激动", "兴奋", "棒极了"],
            "cheerful": ["开心", "高兴", "happy", "joy", "笑", "哈哈", "嘿嘿", "愉快"],
            "gentle": ["温柔", "轻柔", "soft", "gentle", "calm", "peaceful", "安静", "宁静"],
            "serious": ["严肃", "重要", "serious", "important", "critical", "注意", "警告"],
            "sad": ["难过", "伤心", "sad", "sorry", "抱歉", "遗憾", "可惜"],
            "friendly": ["朋友", "friend", "你好", "hello", "欢迎", "welcome", "谢谢", "thanks"]
        }

        # 内容类型检测
        content_keywords = {
            "storytelling": ["故事", "从前", "很久以前", "story", "once upon", "传说", "tale"],
            "energetic": ["加油", "冲", "go", "let's", "快", "hurry", "赶紧"],
            "calm": ["冥想", "放松", "meditation", "relax", "breathe", "平静", "安静"]
        }

        # 检测情感
        detected_emotion = "default"
        for emotion, keywords in emotion_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                detected_emotion = emotion
                break

        # 检测内容类型
        detected_content = "friendly"  # 默认友好
        for content_type, keywords in content_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                detected_content = content_type
                break

        return detected_emotion, detected_content

    def select_voice(self, text: str) -> str:
        """智能选择语音"""
        try:
            # 如果设置为固定模式，直接返回配置的语音
            if self.config.VOICE_SELECTION_MODE == "fixed":
                return self.config.TTS_VOICE

            # 语言检测
            if self.language_detection_available:
                language, confidence = self.langid.classify(text)
                if language != "zh" and confidence > 0.8:
                    # 非中文文本，选择对应语言的语音
                    if language in ["en"]:
                        return self.config.VOICE_OPTIONS.get("english", self.config.TTS_VOICE)
                    elif language in ["ja"]:
                        return self.config.VOICE_OPTIONS.get("japanese", self.config.TTS_VOICE)
                    elif language in ["fr"]:
                        return self.config.VOICE_OPTIONS.get("french", self.config.TTS_VOICE)
                    elif language in ["de"]:
                        return self.config.VOICE_OPTIONS.get("german", self.config.TTS_VOICE)

            # 中文文本的智能选择
            if self.config.VOICE_SELECTION_MODE == "adaptive":
                emotion, content_type = self.detect_emotion_and_content_type(text)

                # 优先根据内容类型选择
                if content_type in self.config.VOICE_OPTIONS:
                    selected_voice = self.config.VOICE_OPTIONS[content_type]
                    logging.info(f"根据内容类型选择语音: {content_type} -> {selected_voice}")
                    return selected_voice

                # 根据情感选择
                emotion_to_voice = {
                    "excited": "energetic",
                    "cheerful": "lively",
                    "gentle": "gentle",
                    "serious": "calm",
                    "sad": "gentle",
                    "friendly": "friendly"
                }

                voice_key = emotion_to_voice.get(emotion, "friendly")
                if voice_key in self.config.VOICE_OPTIONS:
                    selected_voice = self.config.VOICE_OPTIONS[voice_key]
                    logging.info(f"根据情感选择语音: {emotion} -> {voice_key} -> {selected_voice}")
                    return selected_voice

            # 随机模式
            elif self.config.VOICE_SELECTION_MODE == "random":
                import random
                chinese_voices = [v for k, v in self.config.VOICE_OPTIONS.items()
                                if k in ["friendly", "lively", "calm", "energetic", "gentle", "storytelling"]]
                selected_voice = random.choice(chinese_voices)
                logging.info(f"随机选择语音: {selected_voice}")
                return selected_voice

            # 默认返回配置的主语音
            return self.config.TTS_VOICE

        except Exception as e:
            logging.error(f"语音选择失败: {e}")
            return self.config.TTS_VOICE

    def create_ssml_with_emotion(self, text: str, voice: str) -> str:
        """创建带情感的SSML"""
        try:
            emotion, content_type = self.detect_emotion_and_content_type(text)

            # 检查语音是否支持情感样式
            emotion_supported_voices = [
                "zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural",
                "zh-CN-YunxiNeural", "zh-CN-YunyangNeural"
            ]

            if voice in emotion_supported_voices and emotion in self.config.EMOTION_STYLES:
                style = self.config.EMOTION_STYLES[emotion]
                if style:  # 如果有对应的情感样式
                    ssml = f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="zh-CN"><voice name="{voice}"><mstts:express-as style="{style}" styledegree="1.2">{text}</mstts:express-as></voice></speak>'
                    logging.info(f"使用SSML情感控制: {emotion} -> {style}")
                    return ssml

            # 不支持情感或无情感时，返回基本SSML
            ssml = f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN"><voice name="{voice}"><prosody rate="0.9" pitch="+2%">{text}</prosody></voice></speak>'
            return ssml

        except Exception as e:
            logging.error(f"创建SSML失败: {e}")
            return text  # 回退到纯文本

    async def generate_speech(self, text: str) -> str:
        """生成语音文件 - 支持智能语音选择和情感控制"""
        try:
            # 🧹 清理文本，移除Markdown格式符号
            cleaned_text = clean_text_for_tts(text)

            if not cleaned_text.strip():
                logging.warning("清理后文本为空，跳过语音生成")
                return ""

            # 生成唯一文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"tts_{timestamp}.mp3"
            filepath = self.output_dir / filename

            # 智能选择语音
            selected_voice = self.select_voice(cleaned_text)

            # 使用Edge-TTS生成语音 - 使用清理后的纯文本
            communicate = edge_tts.Communicate(cleaned_text, selected_voice)
            logging.info(f"🎵 使用清理后的纯文本生成语音: {selected_voice}")
            logging.info(f"📝 原始文本: {repr(text[:100])}")
            logging.info(f"🧹 清理后文本: {repr(cleaned_text[:100])}")

            await communicate.save(str(filepath))

            logging.info(f"语音合成完成: {filename} (语音: {selected_voice})")
            return str(filepath)

        except Exception as e:
            logging.error(f"语音合成失败: {e}")
            # 回退到基础语音合成
            try:
                # 同样清理文本
                cleaned_text = clean_text_for_tts(text)
                if not cleaned_text.strip():
                    logging.warning("回退时清理后文本为空")
                    return ""

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"tts_fallback_{timestamp}.mp3"
                filepath = self.output_dir / filename

                communicate = edge_tts.Communicate(cleaned_text, self.config.TTS_VOICE)
                await communicate.save(str(filepath))

                logging.info(f"回退语音合成完成: {filename}")
                return str(filepath)
            except Exception as fallback_error:
                logging.error(f"回退语音合成也失败: {fallback_error}")
                return ""

# ==================== 主服务类 ====================

class VoiceRAGService:
    """语音RAG集成服务 - Faster-Whisper版本"""

    def __init__(self):
        self.config = VoiceRAGConfig()
        self.performance_optimizer = PerformanceOptimizer()
        self.audio_processor = AudioProcessor(self.config)
        self.query_client = IntelligentQueryClient(self.config)
        self.tts_processor = TTSProcessor(self.config)

        # 初始化pygame用于音频播放
        pygame.mixer.init()

        logging.info(f"语音RAG服务初始化完成 (后端: {self.audio_processor.backend_used})")

    async def process_voice_request(self, audio_data: str, format_hint: str = "webm", mode: str = "rag") -> VoiceResponse:
        """处理语音请求 - Faster-Whisper优化版本"""
        start_time = time.time()

        try:
            logging.info(f"开始处理语音请求，格式提示: {format_hint}, 后端: {self.audio_processor.backend_used}")

            # 1. 语音转文本 - 使用Faster-Whisper
            transcription, transcribe_time, backend_used = await self.audio_processor.transcribe_audio(
                audio_data, format_hint
            )

            if not transcription:
                return VoiceResponse(
                    success=False,
                    error="无法识别语音内容，请确保说话清晰且环境安静",
                    processing_time=time.time() - start_time,
                    transcribe_time=transcribe_time,
                    backend_used=backend_used
                )

            logging.info(f"语音识别成功 ({backend_used}): '{transcription}' (转录耗时: {transcribe_time:.2f}s)")

            # 2. 检查缓存
            cached_response = self.performance_optimizer.get_cached_response(transcription)
            if cached_response:
                logging.info(f"使用缓存响应: {transcription}")
                # 即使是缓存响应也要生成新的语音
                selected_voice = self.tts_processor.select_voice(cached_response)
                audio_path = await self.tts_processor.generate_speech(cached_response)

                if audio_path:
                    audio_filename = os.path.basename(audio_path)
                    # 生成完整的音频URL，确保前端能正确访问
                    audio_url = f"http://{VoiceRAGConfig.HOST}:{VoiceRAGConfig.PORT}/api/audio/{audio_filename}"
                else:
                    audio_url = ""
                    selected_voice = "unknown"

                return VoiceResponse(
                    success=True,
                    transcription=transcription,
                    response_text=cached_response,
                    audio_url=audio_url,
                    processing_time=time.time() - start_time,
                    transcribe_time=transcribe_time,
                    backend_used=backend_used,
                    voice_used=selected_voice,
                    auto_play=True,
                    should_play_immediately=True
                )

            # 3. 智能代理处理查询
            query_result = await self.query_client.process_query(transcription, mode)
            logging.info(f"智能代理处理结果: {query_result.query_type}, 模式: {mode}")

            if not query_result.success:
                return VoiceResponse(
                    success=False,
                    transcription=transcription,
                    error=query_result.answer,
                    processing_time=time.time() - start_time,
                    transcribe_time=transcribe_time,
                    backend_used=backend_used
                )

            # 4. 智能语音选择和生成语音回复
            selected_voice = self.tts_processor.select_voice(query_result.answer)
            audio_path = await self.tts_processor.generate_speech(query_result.answer)

            # 转换为前端可访问的URL
            if audio_path:
                audio_filename = os.path.basename(audio_path)
                # 生成完整的音频URL，确保前端能正确访问
                # 使用localhost而不是0.0.0.0，避免浏览器访问问题
                host = "localhost" if VoiceRAGConfig.HOST == "0.0.0.0" else VoiceRAGConfig.HOST
                audio_url = f"http://{host}:{VoiceRAGConfig.PORT}/api/audio/{audio_filename}"
                logging.info(f"语音合成完成，文件: {audio_filename}, 语音: {selected_voice}")
            else:
                audio_url = ""
                selected_voice = "unknown"
                logging.warning("语音合成失败")

            # 5. 缓存响应
            self.performance_optimizer.cache_response(transcription, query_result.answer)

            total_time = time.time() - start_time

            # 6. 返回结果
            return VoiceResponse(
                success=True,
                transcription=transcription,
                response_text=query_result.answer,
                audio_url=audio_url,
                processing_time=total_time,
                transcribe_time=transcribe_time,
                backend_used=backend_used,
                voice_used=selected_voice,
                auto_play=True,
                should_play_immediately=True
            )

        except Exception as e:
            logging.error(f"处理语音请求失败: {e}")
            return VoiceResponse(
                success=False,
                transcription=transcription if 'transcription' in locals() else "",
                error=f"处理请求时发生错误: {str(e)}",
                processing_time=time.time() - start_time,
                transcribe_time=transcribe_time if 'transcribe_time' in locals() else 0.0,
                backend_used=self.audio_processor.backend_used
            )

    async def cleanup(self):
        """清理资源"""
        pygame.mixer.quit()
        logging.info("语音RAG服务资源清理完成")

# ==================== FastAPI应用 ====================

# 创建FastAPI应用
app = FastAPI(
    title="语音RAG集成服务 - Faster-Whisper版本",
    description="使用Faster-Whisper实现2-4倍速度提升的语音交互智能网关",
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

# 添加静态文件服务 - 提供音频文件访问
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

output_dir = Path("./voice_rag_output")
output_dir.mkdir(exist_ok=True)
app.mount("/api/audio", StaticFiles(directory=str(output_dir)), name="audio")

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
async def transcribe_voice_only(request: VoiceRequest):
    """仅转录语音，立即返回结果（用于快速显示用户输入）"""
    try:
        logging.info(f"收到语音转录请求，格式: {request.format}")

        # 仅进行语音转录，不处理AI回答
        transcription, transcribe_time, backend_used = await voice_rag_service.audio_processor.transcribe_audio(
            request.audio_data,
            request.format
        )

        if transcription:
            logging.info(f"语音转录完成 ({backend_used}): '{transcription}' (耗时: {transcribe_time:.2f}s)")
            return {
                "success": True,
                "transcription": transcription,
                "transcribe_time": transcribe_time,
                "backend_used": backend_used
            }
        else:
            logging.warning(f"语音转录结果为空 ({backend_used}) (耗时: {transcribe_time:.2f}s)")
            return {
                "success": False,
                "transcription": "",
                "transcribe_time": transcribe_time,
                "backend_used": backend_used,
                "error": "语音转录失败或结果为空"
            }

    except Exception as e:
        logging.error(f"语音转录API处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query/process")
async def process_text_query(request: dict):
    """处理文本查询，生成AI回答（用于分阶段显示）"""
    try:
        text = request.get("text", "")
        mode = request.get("mode", "rag")

        if not text:
            raise HTTPException(status_code=400, detail="文本内容不能为空")

        logging.info(f"收到文本查询请求: '{text}', 模式: {mode}")

        start_time = time.time()

        # 检查缓存
        cached_response = voice_rag_service.performance_optimizer.get_cached_response(text)
        if cached_response:
            logging.info(f"使用缓存响应: {text}")
            response_text = cached_response
        else:
            # 智能代理处理查询
            query_result = await voice_rag_service.query_client.process_query(text, mode)
            logging.info(f"智能代理处理结果: {query_result.query_type}, 模式: {mode}")

            if not query_result.success:
                return {
                    "success": False,
                    "error": query_result.answer,
                    "processing_time": time.time() - start_time
                }

            response_text = query_result.answer

        # 智能语音选择和生成语音回复
        selected_voice = voice_rag_service.tts_processor.select_voice(response_text)
        audio_path = await voice_rag_service.tts_processor.generate_speech(response_text)

        if audio_path:
            audio_filename = os.path.basename(audio_path)
            # 生成完整的音频URL，确保前端能正确访问
            if voice_rag_service.config.HOST == "0.0.0.0":
                audio_url = f"http://localhost:{voice_rag_service.config.PORT}/api/audio/{audio_filename}"
            else:
                audio_url = f"http://{voice_rag_service.config.HOST}:{voice_rag_service.config.PORT}/api/audio/{audio_filename}"
        else:
            audio_url = ""
            selected_voice = "unknown"

        processing_time = time.time() - start_time

        return {
            "success": True,
            "response_text": response_text,
            "audio_url": audio_url,
            "voice_used": selected_voice,
            "processing_time": processing_time,
            "auto_play": True,
            "should_play_immediately": True
        }

    except Exception as e:
        logging.error(f"文本查询API处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice/process", response_model=VoiceResponse)
async def process_voice(request: VoiceRequest):
    """处理语音请求的API端点"""
    try:
        logging.info(f"收到语音处理请求，格式: {request.format}, 模式: {request.mode}")

        # 处理语音请求
        result = await voice_rag_service.process_voice_request(
            request.audio_data,
            request.format,
            request.mode
        )

        logging.info(f"语音处理完成，成功: {result.success}, 后端: {result.backend_used}, 转录耗时: {result.transcribe_time:.2f}s")
        return result

    except Exception as e:
        logging.error(f"API处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "Voice RAG Service - Faster-Whisper",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "backend_used": voice_rag_service.audio_processor.backend_used,
        "faster_whisper_available": FASTER_WHISPER_AVAILABLE,
        "openai_whisper_available": WHISPER_AVAILABLE,
        "cuda_available": is_cuda_available(),
        "ffmpeg_available": check_ffmpeg()
    }

@app.get("/api/status")
async def get_status():
    """获取服务状态"""
    return {
        "whisper_backend": voice_rag_service.audio_processor.backend_used,
        "whisper_model": voice_rag_service.config.WHISPER_MODEL,
        "device": voice_rag_service.config.WHISPER_DEVICE,
        "compute_type": voice_rag_service.config.COMPUTE_TYPE,
        "beam_size": voice_rag_service.config.BEAM_SIZE,
        "cache_size": len(voice_rag_service.performance_optimizer.response_cache),
        "intelligent_agent_available": voice_rag_service.query_client.intelligent_agent is not None,
        "rag_server": voice_rag_service.config.RAG_SERVER_URL,
        "ffmpeg_available": voice_rag_service.audio_processor.ffmpeg_available,

        # 新增：TTS语音配置状态
        "tts_config": {
            "primary_voice": voice_rag_service.config.TTS_VOICE,
            "voice_selection_mode": voice_rag_service.config.VOICE_SELECTION_MODE,
            "available_voices": len(voice_rag_service.config.VOICE_OPTIONS),
            "emotion_styles": len(voice_rag_service.config.EMOTION_STYLES),
            "language_detection": voice_rag_service.tts_processor.language_detection_available
        }
    }

@app.get("/api/performance")
async def get_performance_info():
    """获取性能信息"""
    return {
        "backend": voice_rag_service.audio_processor.backend_used,
        "expected_speedup": "2-4x faster than OpenAI Whisper" if voice_rag_service.audio_processor.backend_used == "faster-whisper" else "baseline",
        "memory_usage": "~67% less than OpenAI Whisper" if voice_rag_service.audio_processor.backend_used == "faster-whisper" else "baseline",
        "compute_type": voice_rag_service.config.COMPUTE_TYPE,
        "beam_size": voice_rag_service.config.BEAM_SIZE,
        "optimizations": [
            "Faster-Whisper CTranslate2 optimization",
            "Weight quantization",
            "Layer fusion",
            "Batch reordering",
            "GPU memory optimization"
        ] if voice_rag_service.audio_processor.backend_used == "faster-whisper" else ["Standard OpenAI Whisper"]
    }

@app.get("/api/voices")
async def get_voice_config():
    """获取语音配置信息"""
    return {
        "current_config": {
            "primary_voice": voice_rag_service.config.TTS_VOICE,
            "selection_mode": voice_rag_service.config.VOICE_SELECTION_MODE,
            "language_detection_available": voice_rag_service.tts_processor.language_detection_available
        },
        "available_voices": voice_rag_service.config.VOICE_OPTIONS,
        "emotion_styles": voice_rag_service.config.EMOTION_STYLES,
        "voice_descriptions": {
            "zh-CN-XiaoxiaoNeural": "晓晓 - 温暖自然，适合日常对话",
            "zh-CN-XiaoyiNeural": "小艺 - 活泼生动，充满朝气",
            "zh-CN-YunxiNeural": "云希 - 沉稳磁性，适合正式场合",
            "zh-CN-YunyangNeural": "云扬 - 充满活力，适合激励性内容",
            "zh-CN-YunxiaNeural": "云夏 - 温柔甜美，适合温馨内容",
            "zh-CN-YunjianNeural": "云健 - 适合讲故事和叙述",
            "en-US-AvaMultilingualNeural": "Ava - 自然流畅的多语言英文",
            "ja-JP-NanamiNeural": "Nanami - 日语女声",
            "fr-FR-DeniseNeural": "Denise - 法语女声",
            "de-DE-KatjaNeural": "Katja - 德语女声"
        },
        "selection_modes": {
            "fixed": "固定使用主语音",
            "adaptive": "根据内容和情感智能选择",
            "random": "随机选择中文语音"
        }
    }

@app.post("/api/voices/test")
async def test_voice(request: dict):
    """测试语音效果"""
    try:
        text = request.get("text", "你好，这是语音测试")
        voice = request.get("voice", voice_rag_service.config.TTS_VOICE)

        # 生成测试语音
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"test_voice_{timestamp}.mp3"
        filepath = voice_rag_service.tts_processor.output_dir / filename

        # 清理文本并生成语音
        cleaned_text = clean_text_for_tts(text)
        if not cleaned_text.strip():
            cleaned_text = "测试文本为空"

        communicate = edge_tts.Communicate(cleaned_text, voice)
        await communicate.save(str(filepath))

        logging.info(f"测试语音生成 - 原始: {repr(text[:50])}, 清理后: {repr(cleaned_text[:50])}")

        return {
            "success": True,
            "message": f"测试语音生成成功",
            "voice_used": voice,
            "audio_file": str(filepath),
            "text": text
        }

    except Exception as e:
        logging.error(f"语音测试失败: {e}")
        raise HTTPException(status_code=500, detail=f"语音测试失败: {str(e)}")

@app.post("/api/voices/config")
async def update_voice_config(request: dict):
    """更新语音配置"""
    try:
        # 更新配置（注意：这只在当前会话中生效，重启后会恢复默认值）
        if "selection_mode" in request:
            mode = request["selection_mode"]
            if mode in ["fixed", "adaptive", "random"]:
                voice_rag_service.config.VOICE_SELECTION_MODE = mode
                logging.info(f"语音选择模式已更新为: {mode}")

        if "primary_voice" in request:
            voice = request["primary_voice"]
            if voice in voice_rag_service.config.VOICE_OPTIONS.values() or voice == voice_rag_service.config.TTS_VOICE:
                voice_rag_service.config.TTS_VOICE = voice
                logging.info(f"主语音已更新为: {voice}")

        return {
            "success": True,
            "message": "语音配置已更新",
            "current_config": {
                "primary_voice": voice_rag_service.config.TTS_VOICE,
                "selection_mode": voice_rag_service.config.VOICE_SELECTION_MODE
            }
        }

    except Exception as e:
        logging.error(f"更新语音配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置更新失败: {str(e)}")

@app.post("/api/tts/generate")
async def generate_tts(request: dict):
    """文本转语音API - 用于前端文字自动播报"""
    try:
        text = request.get("text", "")

        # 添加详细的调试输出
        print("=" * 80)
        print("🔍 TTS生成调试信息:")
        print(f"📝 接收到的文本类型: {type(text)}")
        print(f"📝 接收到的文本长度: {len(text) if text else 0}")
        print("📝 接收到的文本内容:")
        print(repr(text))  # 使用repr显示转义字符
        print("-" * 40)
        if text:
            print("📝 文本的前100个字符:")
            print(repr(text[:100]))
        print("=" * 80)

        if not text:
            raise HTTPException(status_code=400, detail="文本内容不能为空")

        # 智能选择语音
        selected_voice = voice_rag_service.tts_processor.select_voice(text)
        logging.info(f"TTS API智能语音选择: {selected_voice}")
        print(f"🎵 选择的语音: {selected_voice}")

        # 生成语音
        audio_path = await voice_rag_service.tts_processor.generate_speech(text)

        if not audio_path:
            raise HTTPException(status_code=500, detail="语音生成失败")

        # 返回相对URL路径，便于前端访问
        audio_filename = os.path.basename(audio_path)
        audio_url = f"/api/audio/{audio_filename}"

        return {
            "success": True,
            "text": text,
            "audio_url": audio_url,
            "voice_used": selected_voice,
            "auto_play": True,
            "message": "语音生成成功"
        }

    except Exception as e:
        logging.error(f"文本转语音失败: {e}")
        raise HTTPException(status_code=500, detail=f"语音生成失败: {str(e)}")

@app.post("/api/auto-play")
async def auto_play_text(request: dict):
    """自动播放文本 - 专为前端自动播报设计"""
    try:
        text = request.get("text", "")
        if not text:
            return {"success": False, "message": "文本内容为空"}

        # 智能选择语音
        selected_voice = voice_rag_service.tts_processor.select_voice(text)
        logging.info(f"自动播报智能语音选择: {selected_voice}")

        # 生成语音
        audio_path = await voice_rag_service.tts_processor.generate_speech(text)

        if audio_path:
            # 返回相对URL路径，便于前端访问
            audio_filename = os.path.basename(audio_path)
            audio_url = f"/api/audio/{audio_filename}"

            logging.info(f"自动播报生成: '{text[:50]}...' 使用语音: {selected_voice}")
            return {
                "success": True,
                "text": text,
                "audio_url": audio_url,
                "voice_used": selected_voice,
                "auto_play": True,
                "should_play_immediately": True  # 指示前端立即播放
            }
        else:
            return {
                "success": False,
                "message": "语音生成失败",
                "text": text
            }

    except Exception as e:
        logging.error(f"自动播报失败: {e}")
        return {
            "success": False,
            "message": f"自动播报失败: {str(e)}",
            "text": text
        }

# ==================== 主程序入口 ====================

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🎤 语音RAG集成服务 - Faster-Whisper版本 (灵动语音升级)")
    print("=" * 60)
    print(f"🌐 服务地址: http://{VoiceRAGConfig.HOST}:{VoiceRAGConfig.PORT}")
    print(f"🚀 Whisper后端: {VoiceRAGConfig.WHISPER_BACKEND}")
    print(f"🤖 模型: {VoiceRAGConfig.WHISPER_MODEL}")
    print(f"⚡ 计算类型: {VoiceRAGConfig.COMPUTE_TYPE}")
    print(f"🎯 束搜索: {VoiceRAGConfig.BEAM_SIZE}")
    print(f"💻 设备: {VoiceRAGConfig.WHISPER_DEVICE}")
    print(f"📊 RAG服务: {VoiceRAGConfig.RAG_SERVER_URL}")
    print(f"📱 活动服务: {VoiceRAGConfig.ACTIVITY_SERVER_URL}")
    print(f"🔧 FFmpeg: {check_ffmpeg()}")
    print(f"🎮 CUDA: {is_cuda_available()}")
    print("=" * 60)
    print("✨ 性能优势 (vs 原版Whisper):")
    print("  • 🚀 转录速度: 2-4倍提升")
    print("  • 💾 内存使用: 减少67%")
    print("  • ⚡ GPU优化: 显著改善")
    print("  • 🎯 量化支持: int8/float16")
    print("  • 📈 吞吐量: 大幅提升")
    print("=" * 60)
    print("🎵 语音合成升级 - 告别机械声音:")
    print(f"  • 🎭 主语音: {VoiceRAGConfig.TTS_VOICE} (晓晓 - 温暖自然)")
    print(f"  • 🧠 选择模式: {VoiceRAGConfig.VOICE_SELECTION_MODE} (智能适应)")
    print(f"  • 🎨 多样语音: {len(VoiceRAGConfig.VOICE_OPTIONS)}种不同风格")
    print(f"  • 😊 情感控制: {len(VoiceRAGConfig.EMOTION_STYLES)}种情感样式")
    print("  • 🌍 多语言支持: 中英日法德语音")
    print("  • 🎪 智能选择: 根据内容自动匹配语音风格")
    print("=" * 60)
    print("🔧 核心功能:")
    print("  • 智能后端选择 (Faster-Whisper优先)")
    print("  • 自动回退机制")
    print("  • 性能监控")
    print("  • 音频格式自动转换")
    print("  • 智能意图识别")
    print("  • 快速响应缓存")
    print("  • 🆕 情感化语音合成")
    print("  • 🆕 多风格语音选择")
    print("  • 🆕 SSML情感控制")
    print("=" * 60)
    print("🔗 新增API端点:")
    print("  • GET  /api/voices - 查看语音配置")
    print("  • POST /api/voices/test - 测试语音效果")
    print("  • POST /api/voices/config - 更新语音设置")
    print("=" * 60)

    # 启动服务
    uvicorn.run(
        app,
        host=VoiceRAGConfig.HOST,
        port=VoiceRAGConfig.PORT,
        log_level="info"
    )
