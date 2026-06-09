#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能音频录制器 - 集成VAD语音活动检测
=========================================

使用WebRTC VAD进行智能语音分割，确保句子完整性
"""

import os
import json
import asyncio
import logging
import threading
import time
import wave
import tempfile
import sqlite3
import struct
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import deque
import signal
import sys

# 音频录制相关
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logging.warning("PyAudio 未安装，音频录制功能将不可用。请运行: pip install pyaudio")

# VAD语音活动检测
try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    logging.warning("WebRTC VAD 未安装，请运行: pip install webrtcvad")

# 语音转文字相关
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logging.warning("OpenAI Whisper 未安装")

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logging.warning("Faster Whisper 未安装，请运行: pip install faster-whisper")

# 导入现有的数据库和索引功能
from activity_retriever import create_db_connection, index_single_activity_record

# 导入配置
from audio_config import AudioConfig, DEFAULT_CONFIG

# 导入文本转换功能
try:
    from text_converter import convert_traditional_to_simplified
    TEXT_CONVERTER_AVAILABLE = True
except ImportError:
    TEXT_CONVERTER_AVAILABLE = False
    logging.warning("文本转换模块未找到，将跳过繁简转换")

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VoiceActivityDetector:
    """语音活动检测器"""

    def __init__(self, sample_rate=16000, frame_duration_ms=30, aggressiveness=2):
        """
        初始化VAD

        Args:
            sample_rate: 采样率 (8000, 16000, 32000, 48000)
            frame_duration_ms: 帧时长毫秒 (10, 20, 30)
            aggressiveness: 激进程度 0-3 (0=最不激进, 3=最激进)
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.aggressiveness = aggressiveness

        if VAD_AVAILABLE:
            self.vad = webrtcvad.Vad(aggressiveness)
            self.frame_size = int(sample_rate * frame_duration_ms / 1000)  # 帧大小（样本数）
            self.frame_bytes = self.frame_size * 2  # 每帧字节数 (16bit = 2 bytes per sample)
            logging.info(f"VAD初始化成功 (激进程度: {aggressiveness}, 帧时长: {frame_duration_ms}ms)")
        else:
            self.vad = None
            logging.error("VAD不可用，将使用固定时长分割")

    def is_speech(self, frame_data: bytes) -> bool:
        """
        检测音频帧是否包含语音

        Args:
            frame_data: 音频帧数据 (PCM 16bit)

        Returns:
            True if speech detected, False otherwise
        """
        if not self.vad or len(frame_data) != self.frame_bytes:
            return False

        try:
            return self.vad.is_speech(frame_data, self.sample_rate)
        except Exception as e:
            logging.debug(f"VAD检测失败: {e}")
            return False

    def detect_speech_segments(self, audio_data: bytes, min_speech_duration=0.5, max_silence_duration=1.0) -> List[tuple]:
        """
        检测语音段落

        Args:
            audio_data: 完整音频数据
            min_speech_duration: 最小语音时长（秒）
            max_silence_duration: 最大静音时长（秒）

        Returns:
            List of (start_offset, end_offset) tuples
        """
        if not self.vad:
            # 回退到固定时长分割
            segments = []
            chunk_size = 5 * self.sample_rate * 2  # 5秒
            for i in range(0, len(audio_data), chunk_size):
                segments.append((i, min(i + chunk_size, len(audio_data))))
            return segments

        segments = []
        frames = []

        # 分帧处理
        for i in range(0, len(audio_data) - self.frame_bytes + 1, self.frame_bytes):
            frame = audio_data[i:i + self.frame_bytes]
            is_speech = self.is_speech(frame)
            frames.append((i, is_speech))

        # 分析语音段落
        current_segment_start = None
        speech_frames = 0
        silence_frames = 0

        min_speech_frames = int(min_speech_duration * 1000 / self.frame_duration_ms)
        max_silence_frames = int(max_silence_duration * 1000 / self.frame_duration_ms)

        for frame_offset, is_speech in frames:
            if is_speech:
                if current_segment_start is None:
                    current_segment_start = frame_offset
                speech_frames += 1
                silence_frames = 0
            else:
                silence_frames += 1

                # 如果静音时间过长，结束当前段落
                if current_segment_start is not None and silence_frames >= max_silence_frames:
                    if speech_frames >= min_speech_frames:
                        segments.append((current_segment_start, frame_offset))
                    current_segment_start = None
                    speech_frames = 0

        # 处理最后一个段落
        if current_segment_start is not None and speech_frames >= min_speech_frames:
            segments.append((current_segment_start, len(audio_data)))

        return segments

class SmartAudioRecorder:
    """智能音频录制器 - 集成VAD"""

    def __init__(self, config: AudioConfig = None, max_segment_duration=10):
        """
        初始化智能音频录制器

        Args:
            config: 音频配置对象
            max_segment_duration: 最大段落时长（秒）
        """
        if config is None:
            config = DEFAULT_CONFIG

        self.config = config
        self.max_segment_duration = max_segment_duration
        self.sample_rate = config.sample_rate if hasattr(config, 'sample_rate') else 16000
        self.channels = config.channels if hasattr(config, 'channels') else 1
        self.format = pyaudio.paInt16

        # VAD检测器
        self.vad = VoiceActivityDetector(
            sample_rate=self.sample_rate,
            frame_duration_ms=30,
            aggressiveness=2  # 中等激进程度
        )

        # 录制控制
        self.is_recording = False
        self.recording_thread = None
        self.processing_thread = None

        # 音频数据缓冲区 - 改为连续缓冲
        self.audio_buffer = bytearray()
        self.buffer_lock = threading.Lock()
        self.last_process_time = time.time()

        # PyAudio 实例
        self.audio_interface = None
        self.stream = None

        # Whisper 模型
        self.whisper_model = None
        self.faster_whisper_model = None

        # 统计信息
        self.stats = {
            'total_segments_processed': 0,
            'total_transcriptions': 0,
            'successful_transcriptions': 0,
            'failed_transcriptions': 0,
            'start_time': None,
            'vad_segments_detected': 0
        }

        # 初始化组件
        self._initialize_components()

    def _initialize_components(self):
        """初始化音频和语音转文字组件"""
        # 初始化 PyAudio
        if PYAUDIO_AVAILABLE:
            try:
                self.audio_interface = pyaudio.PyAudio()
                logging.info("PyAudio 初始化成功")
            except Exception as e:
                logging.error(f"PyAudio 初始化失败: {e}")
                self.audio_interface = None

        # 初始化 Whisper 模型
        self._initialize_whisper_model()

    def _initialize_whisper_model(self):
        """初始化Whisper模型"""
        backend = getattr(self.config, 'whisper_backend', 'faster-whisper')
        model_size = getattr(self.config, 'whisper_model_size', 'base')

        if backend == "faster-whisper" and FASTER_WHISPER_AVAILABLE:
            try:
                logging.info(f"正在加载 Faster-Whisper 模型 ({model_size})...")

                device = "cuda" if self._is_cuda_available() else "cpu"
                compute_type = getattr(self.config, 'compute_type', 'float16')

                if device == "cpu" and compute_type == "float16":
                    compute_type = "int8"
                    logging.info("CPU环境下自动切换到int8计算类型")

                self.faster_whisper_model = WhisperModel(
                    model_size,
                    device=device,
                    compute_type=compute_type
                )
                logging.info(f"Faster-Whisper 模型加载成功")

            except Exception as e:
                logging.error(f"Faster-Whisper 模型加载失败: {e}")
                self.faster_whisper_model = None

        elif backend == "openai-whisper" and WHISPER_AVAILABLE:
            try:
                logging.info(f"正在加载 OpenAI-Whisper 模型 ({model_size})...")
                self.whisper_model = whisper.load_model(model_size)
                logging.info(f"OpenAI-Whisper 模型加载成功")
            except Exception as e:
                logging.error(f"OpenAI-Whisper 模型加载失败: {e}")
                self.whisper_model = None

    def _is_cuda_available(self):
        """检查CUDA是否可用"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def start_recording(self, use_system_audio=True):
        """开始录制音频"""
        if not PYAUDIO_AVAILABLE:
            logging.error("PyAudio 未安装，无法开始录制")
            return False

        if not FASTER_WHISPER_AVAILABLE and not WHISPER_AVAILABLE:
            logging.error("缺少Whisper组件，无法开始录制")
            return False

        if self.is_recording:
            logging.warning("录制已在进行中")
            return False

        # 尝试创建音频流
        try:
            self.stream = self.audio_interface.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=1024
            )

            self.is_recording = True
            self.stats['start_time'] = datetime.now()

            # 启动录制线程
            self.recording_thread = threading.Thread(target=self._smart_recording_worker, daemon=True)
            self.recording_thread.start()

            # 启动处理线程
            self.processing_thread = threading.Thread(target=self._smart_processing_worker, daemon=True)
            self.processing_thread.start()

            logging.info("智能音频录制已启动 (VAD智能分割)")
            return True

        except Exception as e:
            logging.error(f"启动音频录制失败: {e}")
            self.is_recording = False
            return False

    def _smart_recording_worker(self):
        """智能录制工作线程"""
        while self.is_recording:
            try:
                # 读取音频数据
                data = self.stream.read(1024, exception_on_overflow=False)

                # 添加到连续缓冲区
                with self.buffer_lock:
                    self.audio_buffer.extend(data)

            except Exception as e:
                if self.is_recording:
                    logging.error(f"录制音频时出错: {e}")
                break

    def _smart_processing_worker(self):
        """智能处理工作线程"""
        while self.is_recording:
            try:
                current_time = time.time()

                # 每1秒检查一次缓冲区
                if current_time - self.last_process_time >= 1.0:
                    self._process_audio_buffer()
                    self.last_process_time = current_time

                time.sleep(0.1)

            except Exception as e:
                logging.error(f"处理音频时出错: {e}")

    def _process_audio_buffer(self):
        """处理音频缓冲区"""
        with self.buffer_lock:
            if len(self.audio_buffer) < self.sample_rate * 2:  # 少于1秒音频
                return

            # 复制缓冲区数据
            buffer_data = bytes(self.audio_buffer)

            # 保留最近2秒的数据，避免截断
            keep_size = self.sample_rate * 2 * 2  # 2秒
            if len(self.audio_buffer) > keep_size:
                self.audio_buffer = self.audio_buffer[-keep_size:]
            else:
                self.audio_buffer.clear()

        # VAD分析语音段落
        segments = self.vad.detect_speech_segments(
            buffer_data,
            min_speech_duration=0.5,  # 最短0.5秒
            max_silence_duration=1.5   # 最长1.5秒静音
        )

        if segments:
            self.stats['vad_segments_detected'] += len(segments)
            logging.info(f"VAD检测到 {len(segments)} 个语音段落")

            for start_offset, end_offset in segments:
                segment_data = buffer_data[start_offset:end_offset]
                segment_duration = len(segment_data) / (self.sample_rate * 2)

                # 只处理合理长度的段落
                if 0.5 <= segment_duration <= self.max_segment_duration:
                    self._process_audio_segment(segment_data, segment_duration)

    def _process_audio_segment(self, segment_data: bytes, duration: float):
        """处理单个音频段落"""
        try:
            # 创建临时音频文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name

                # 写入 WAV 文件
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(self.channels)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(self.sample_rate)
                    wav_file.writeframes(segment_data)

            # 使用 Whisper 进行语音转文字
            transcription = self._transcribe_audio(temp_path)

            # 清理临时文件
            os.unlink(temp_path)

            if transcription and transcription.strip():
                # 过滤明显的幻觉输出
                if self._is_valid_transcription(transcription):
                    # 保存转录结果到数据库
                    self._save_transcription(transcription, datetime.now())
                    self.stats['successful_transcriptions'] += 1
                    logging.info(f"语音段落转录成功 ({duration:.1f}s): {transcription[:50]}...")
                else:
                    self.stats['failed_transcriptions'] += 1
                    logging.debug(f"过滤低质量转录: {transcription[:30]}...")
            else:
                self.stats['failed_transcriptions'] += 1
                logging.debug(f"语音段落未检测到有效语音 ({duration:.1f}s)")

            self.stats['total_transcriptions'] += 1
            self.stats['total_segments_processed'] += 1

        except Exception as e:
            logging.error(f"处理音频段落时出错: {e}")
            self.stats['failed_transcriptions'] += 1

    def _is_valid_transcription(self, text: str) -> bool:
        """验证转录结果是否有效，过滤幻觉输出"""
        if not text or len(text.strip()) < 3:
            return False

        # 过滤常见的幻觉模式
        hallucination_patterns = [
            "以下是普通话的句子",
            "subtitle",
            "字幕",
            "请订阅",
            "关注我们",
            "谢谢观看",
            "下次见",
            "感谢收看"
        ]

        text_lower = text.lower().strip()

        # 检查是否包含幻觉模式
        for pattern in hallucination_patterns:
            if pattern in text_lower:
                return False

        # 检查重复模式（如"问问问问问"）
        if len(set(text.strip())) < len(text.strip()) / 3:
            return False

        # 检查是否只包含标点符号
        import re
        if re.sub(r'[^\w\s]', '', text).strip() == '':
            return False

        return True

    def _transcribe_audio(self, audio_path):
        """使用 Whisper 转录音频"""
        try:
            backend = getattr(self.config, 'whisper_backend', 'faster-whisper')

            if backend == "faster-whisper" and self.faster_whisper_model:
                return self._transcribe_with_faster_whisper(audio_path)
            elif backend == "openai-whisper" and self.whisper_model:
                return self._transcribe_with_openai_whisper(audio_path)
            else:
                logging.error("没有可用的Whisper模型")
                return None

        except Exception as e:
            logging.error(f"音频转录失败: {e}")
            return None

    def _transcribe_with_faster_whisper(self, audio_path):
        """使用 Faster-Whisper 转录音频"""
        try:
            # 获取配置参数
            language = getattr(self.config, 'whisper_language', 'zh')
            beam_size = getattr(self.config, 'beam_size', 1)
            best_of = getattr(self.config, 'best_of', 1)
            temperature = getattr(self.config, 'temperature', 0.0)
            condition_on_previous_text = getattr(self.config, 'condition_on_previous_text', False)
            no_speech_threshold = getattr(self.config, 'no_speech_threshold', 0.8)
            compression_ratio_threshold = getattr(self.config, 'compression_ratio_threshold', 2.4)
            log_prob_threshold = getattr(self.config, 'log_prob_threshold', -0.5)
            initial_prompt = getattr(self.config, 'whisper_initial_prompt', "")

            # 使用 Faster-Whisper 进行转录
            segments, info = self.faster_whisper_model.transcribe(
                audio_path,
                language=language,
                task='transcribe',
                beam_size=beam_size,
                best_of=best_of,
                temperature=temperature,
                condition_on_previous_text=condition_on_previous_text,
                no_speech_threshold=no_speech_threshold,
                compression_ratio_threshold=compression_ratio_threshold,
                log_prob_threshold=log_prob_threshold,
                initial_prompt=initial_prompt
            )

            # 拼接所有段落的文本
            text = "".join([segment.text for segment in segments]).strip()

            # 尝试将繁体中文转换为简体中文
            if text and TEXT_CONVERTER_AVAILABLE and getattr(self.config, 'use_simplified_chinese', True):
                try:
                    converted_text = convert_traditional_to_simplified(text)
                    if converted_text != text:
                        logging.debug(f"文本转换: {text[:30]}... -> {converted_text[:30]}...")
                        text = converted_text
                except Exception as e:
                    logging.warning(f"文本转换失败: {e}")

            return text

        except Exception as e:
            logging.error(f"Faster-Whisper 转录失败: {e}")
            return None

    def _transcribe_with_openai_whisper(self, audio_path):
        """使用 OpenAI-Whisper 转录音频"""
        try:
            language = getattr(self.config, 'whisper_language', 'zh')
            initial_prompt = getattr(self.config, 'whisper_initial_prompt', "")

            result = self.whisper_model.transcribe(
                audio_path,
                language=language,
                task='transcribe',
                initial_prompt=initial_prompt
            )

            text = result['text'].strip() if result and 'text' in result else None

            # 繁简转换
            if text and TEXT_CONVERTER_AVAILABLE and getattr(self.config, 'use_simplified_chinese', True):
                try:
                    converted_text = convert_traditional_to_simplified(text)
                    if converted_text != text:
                        logging.debug(f"文本转换: {text[:30]}... -> {converted_text[:30]}...")
                        text = converted_text
                except Exception as e:
                    logging.warning(f"文本转换失败: {e}")

            return text

        except Exception as e:
            logging.error(f"OpenAI-Whisper 转录失败: {e}")
            return None

    def _save_transcription(self, transcription_text, timestamp):
        """保存转录结果到数据库"""
        try:
            # 创建记录数据
            record_data = {
                'timestamp': timestamp.isoformat(),
                'record_type': 'audio_transcription_vad',
                'triggered_by': 'smart_audio_recorder',
                'event_type': 'vad_transcription',
                'window_title': 'System Audio (VAD)',
                'process_name': 'smart_audio_recorder',
                'app_name': 'System Audio VAD',
                'page_title': None,
                'url': None,
                'ocr_text': transcription_text,
                'parser_type': 'whisper_vad',
                'mouse_x': None,
                'mouse_y': None,
                'button': None
            }

            # 保存到数据库
            conn = create_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()

                    # 插入记录
                    insert_query = """
                        INSERT INTO activity_log (
                            timestamp, record_type, triggered_by, event_type,
                            window_title, process_name, app_name, page_title, url,
                            ocr_text, parser_type, mouse_x, mouse_y, button
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """

                    cursor.execute(insert_query, (
                        record_data['timestamp'],
                        record_data['record_type'],
                        record_data['triggered_by'],
                        record_data['event_type'],
                        record_data['window_title'],
                        record_data['process_name'],
                        record_data['app_name'],
                        record_data['page_title'],
                        record_data['url'],
                        record_data['ocr_text'],
                        record_data['parser_type'],
                        record_data['mouse_x'],
                        record_data['mouse_y'],
                        record_data['button']
                    ))

                    conn.commit()
                    record_id = cursor.lastrowid
                    record_data['id'] = record_id

                    # 索引到向量数据库
                    try:
                        success = index_single_activity_record(record_data)
                        if success:
                            logging.debug(f"VAD转录记录已索引，ID: {record_id}")
                    except Exception as e:
                        logging.error(f"索引VAD转录记录失败: {e}")

                except sqlite3.Error as e:
                    logging.error(f"保存VAD转录记录失败: {e}")
                finally:
                    conn.close()

        except Exception as e:
            logging.error(f"保存VAD转录记录时出错: {e}")

    def stop_recording(self):
        """停止录制音频"""
        if not self.is_recording:
            return

        logging.info("正在停止智能音频录制...")
        self.is_recording = False

        # 等待线程结束
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=5)

        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5)

        # 关闭音频流
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        logging.info("智能音频录制已停止")
        self._print_stats()

    def _print_stats(self):
        """打印统计信息"""
        if self.stats['start_time']:
            duration = datetime.now() - self.stats['start_time']
            logging.info(f"智能音频录制统计:")
            logging.info(f"  运行时长: {duration}")
            logging.info(f"  VAD段落检测: {self.stats['vad_segments_detected']}")
            logging.info(f"  处理段落: {self.stats['total_segments_processed']}")
            logging.info(f"  转录尝试: {self.stats['total_transcriptions']}")
            logging.info(f"  成功转录: {self.stats['successful_transcriptions']}")
            logging.info(f"  失败转录: {self.stats['failed_transcriptions']}")
            if self.stats['total_transcriptions'] > 0:
                success_rate = (self.stats['successful_transcriptions'] /
                              self.stats['total_transcriptions']) * 100
                logging.info(f"  成功率: {success_rate:.1f}%")

    def cleanup(self):
        """清理资源"""
        self.stop_recording()

        if self.audio_interface:
            self.audio_interface.terminate()
            self.audio_interface = None

        logging.info("智能音频录制器资源已清理")


def signal_handler(signum, frame):
    """信号处理器，用于优雅地停止服务"""
    logging.info("收到停止信号，正在关闭智能音频录制服务...")
    if 'recorder' in globals() and recorder:
        recorder.cleanup()
    sys.exit(0)


def main():
    """主函数"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 检查依赖
    if not PYAUDIO_AVAILABLE:
        logging.error("PyAudio 未安装")
        return

    if not VAD_AVAILABLE:
        logging.error("WebRTC VAD 未安装")
        return

    if not FASTER_WHISPER_AVAILABLE and not WHISPER_AVAILABLE:
        logging.error("Whisper 未安装")
        return

    # 创建智能音频录制器
    global recorder
    recorder = SmartAudioRecorder(max_segment_duration=8)  # 最大8秒段落

    # 开始录制
    if recorder.start_recording(use_system_audio=True):
        print("🎤 智能音频录制服务已启动")
        print("🧠 VAD智能分割已启用")
        print("📊 转录结果将自动优化为完整句子")
        print("按 Ctrl+C 停止服务")

        try:
            # 保持服务运行
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("收到键盘中断信号")
        finally:
            recorder.cleanup()
    else:
        logging.error("启动智能音频录制服务失败")


if __name__ == "__main__":
    main()