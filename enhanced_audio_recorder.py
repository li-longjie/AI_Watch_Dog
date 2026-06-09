#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版智能音频录制器 - 最大化识别准确率
===========================================

集成多种技术提升中文语音识别准确率：
- VAD智能分割
- 音频预处理增强
- 多级质量过滤
- 上下文优化
- 自定义词汇支持
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
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from collections import deque
import signal
import sys
import numpy as np

# 音频录制相关
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logging.warning("PyAudio 未安装")

# VAD语音活动检测
try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    logging.warning("WebRTC VAD 未安装")

# 音频处理增强
try:
    import librosa
    import soundfile as sf
    AUDIO_ENHANCEMENT_AVAILABLE = True
except ImportError:
    AUDIO_ENHANCEMENT_AVAILABLE = False
    logging.warning("音频增强库未安装: pip install librosa soundfile")

# 语音转文字相关
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

# 导入配置和依赖
from activity_retriever import create_db_connection, index_single_activity_record
from audio_config_optimized import OptimizedAudioConfig, OptimizedPresets

# 文本转换
try:
    from text_converter import convert_traditional_to_simplified
    TEXT_CONVERTER_AVAILABLE = True
except ImportError:
    TEXT_CONVERTER_AVAILABLE = False

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AudioEnhancer:
    """音频增强处理器"""

    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.enhancement_enabled = AUDIO_ENHANCEMENT_AVAILABLE

    def enhance_audio(self, audio_data: np.ndarray,
                     noise_reduction: float = 0.5,
                     normalize_volume: bool = True) -> np.ndarray:
        """
        音频增强处理

        Args:
            audio_data: 音频数据 (numpy array)
            noise_reduction: 降噪强度 (0-1)
            normalize_volume: 是否标准化音量

        Returns:
            增强后的音频数据
        """
        if not self.enhancement_enabled:
            return audio_data

        try:
            enhanced = audio_data.copy()

            # 音量标准化
            if normalize_volume:
                enhanced = librosa.util.normalize(enhanced)

            # 简单降噪 - 频谱减法
            if noise_reduction > 0:
                enhanced = self._simple_noise_reduction(enhanced, noise_reduction)

            return enhanced

        except Exception as e:
            logging.warning(f"音频增强失败: {e}")
            return audio_data

    def _simple_noise_reduction(self, audio: np.ndarray, strength: float) -> np.ndarray:
        """简单的频谱减法降噪"""
        try:
            # 短时傅里叶变换
            stft = librosa.stft(audio)
            magnitude = np.abs(stft)
            phase = np.angle(stft)

            # 估计噪声 (前几帧的平均)
            noise_magnitude = np.mean(magnitude[:, :5], axis=1, keepdims=True)

            # 频谱减法
            clean_magnitude = magnitude - strength * noise_magnitude
            clean_magnitude = np.maximum(clean_magnitude, 0.1 * magnitude)

            # 重构音频
            clean_stft = clean_magnitude * np.exp(1j * phase)
            clean_audio = librosa.istft(clean_stft)

            return clean_audio

        except Exception as e:
            logging.debug(f"降噪处理失败: {e}")
            return audio

class TextProcessor:
    """文本后处理器"""

    def __init__(self, vocabulary: List[str] = None):
        self.custom_vocabulary = vocabulary or []
        self.correction_rules = self._load_correction_rules()

    def _load_correction_rules(self) -> Dict[str, str]:
        """加载文本纠错规则"""
        return {
            # 🔧 专有名词纠正
            "宴祖": "艳祖",
            "艳祖们": "艳祖们",
            "被家旁客": "贝加庞克",
            "被家庞客": "贝加庞克",
            "被加庞客": "贝加庞克",
            "家庞客": "贝加庞克",
            "贝加帕": "贝加庞克",
            "波密": "波妮",
            "波尼": "波妮",
            "波咪": "波妮",
            "大熊": "大雄",
            "土星": "土星",
            "吐星": "土星",
            "草貓": "草帽",
            "草猫": "草帽",
            "陆飞": "路飞",
            "浮兰奇": "弗兰奇",
            "山志": "山治",

            # 🔧 常见错字纠正
            "在哪": "在哪",
            "干嘛": "干嘛",
            "咋样": "怎样",
            "咋办": "怎办",
            "啥": "什么",
            "咋": "怎么",

            # 🔧 数字纠正
            "1个": "一个",
            "2个": "两个",
            "3个": "三个",

            # 🔧 专业术语
            "ai": "AI",
            "api": "API",
            "url": "URL",
            "http": "HTTP",

            # 🔧 动漫专用词汇
            "海贼王": "海贼王",
            "草帽海贼团": "草帽海贼团",
            "蛋头岛": "蛋头岛",
            "弹头岛": "蛋头岛"
        }

    def process_text(self, text: str, confidence: float = 1.0) -> Tuple[str, float]:
        """
        文本后处理

        Args:
            text: 原始文本
            confidence: 原始置信度

        Returns:
            (处理后文本, 调整后置信度)
        """
        if not text or not text.strip():
            return text, confidence

        processed = text.strip()

        # 应用纠错规则
        for wrong, correct in self.correction_rules.items():
            processed = processed.replace(wrong, correct)

        # 标点符号优化
        processed = self._optimize_punctuation(processed)

        # 计算文本质量分数
        quality_score = self._calculate_text_quality(processed)
        adjusted_confidence = confidence * quality_score

        return processed, adjusted_confidence

    def _optimize_punctuation(self, text: str) -> str:
        """优化标点符号"""
        # 确保句末有标点
        if text and text[-1] not in '。！？，、；：':
            if '?' in text or '吗' in text or '呢' in text:
                text += '？'
            elif '!' in text or '啊' in text:
                text += '！'
            else:
                text += '。'

        return text

    def _calculate_text_quality(self, text: str) -> float:
        """计算文本质量分数"""
        if not text:
            return 0.0

        score = 1.0

        # 长度惩罚 - 过短或过长
        length = len(text)
        if length < 3:
            score *= 0.5
        elif length > 200:
            score *= 0.8

        # 重复字符惩罚
        unique_chars = len(set(text))
        if unique_chars < length / 3:
            score *= 0.6

        # 数字占比过高惩罚
        digit_ratio = sum(1 for c in text if c.isdigit()) / length
        if digit_ratio > 0.5:
            score *= 0.7

        return min(score, 1.0)

class EnhancedVAD:
    """增强版VAD检测器"""

    def __init__(self, sample_rate=16000, aggressiveness=2):
        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        self.frame_duration_ms = 30
        self.frame_size = int(sample_rate * self.frame_duration_ms / 1000)
        self.frame_bytes = self.frame_size * 2

        if VAD_AVAILABLE:
            self.vad = webrtcvad.Vad(aggressiveness)
        else:
            self.vad = None

    def detect_speech_segments_advanced(self, audio_data: bytes,
                                      min_speech_duration: float = 0.3,
                                      max_silence_duration: float = 1.0,
                                      max_segment_duration: float = 12.0) -> List[Tuple[int, int, float]]:
        """
        高级语音段落检测

        Returns:
            List of (start_offset, end_offset, confidence) tuples
        """
        if not self.vad:
            # 固定分割回退
            segments = []
            chunk_size = int(max_segment_duration * self.sample_rate * 2)
            for i in range(0, len(audio_data), chunk_size):
                end = min(i + chunk_size, len(audio_data))
                segments.append((i, end, 0.8))
            return segments

        segments = []
        frames_data = []

        # 分帧分析
        for i in range(0, len(audio_data) - self.frame_bytes + 1, self.frame_bytes):
            frame = audio_data[i:i + self.frame_bytes]
            is_speech = self.vad.is_speech(frame, self.sample_rate)

            # 计算音频能量作为置信度参考
            energy = self._calculate_frame_energy(frame)
            frames_data.append((i, is_speech, energy))

        # 段落分析
        current_start = None
        speech_frames = 0
        silence_frames = 0
        segment_energies = []

        min_speech_frames = int(min_speech_duration * 1000 / self.frame_duration_ms)
        max_silence_frames = int(max_silence_duration * 1000 / self.frame_duration_ms)
        max_segment_frames = int(max_segment_duration * 1000 / self.frame_duration_ms)

        for frame_offset, is_speech, energy in frames_data:
            if is_speech:
                if current_start is None:
                    current_start = frame_offset
                    segment_energies = []

                speech_frames += 1
                silence_frames = 0
                segment_energies.append(energy)

                # 检查最大长度限制
                if speech_frames >= max_segment_frames:
                    if speech_frames >= min_speech_frames:
                        confidence = self._calculate_segment_confidence(segment_energies)
                        segments.append((current_start, frame_offset + self.frame_bytes, confidence))
                    current_start = None
                    speech_frames = 0
                    segment_energies = []

            else:
                silence_frames += 1

                # 静音时间过长，结束段落
                if current_start is not None and silence_frames >= max_silence_frames:
                    if speech_frames >= min_speech_frames:
                        confidence = self._calculate_segment_confidence(segment_energies)
                        segments.append((current_start, frame_offset, confidence))
                    current_start = None
                    speech_frames = 0
                    segment_energies = []

        # 处理最后一个段落
        if current_start is not None and speech_frames >= min_speech_frames:
            confidence = self._calculate_segment_confidence(segment_energies)
            segments.append((current_start, len(audio_data), confidence))

        return segments

    def _calculate_frame_energy(self, frame: bytes) -> float:
        """计算音频帧能量"""
        try:
            samples = struct.unpack(f'<{len(frame)//2}h', frame)
            return sum(s*s for s in samples) / len(samples)
        except:
            return 0.0

    def _calculate_segment_confidence(self, energies: List[float]) -> float:
        """计算段落置信度"""
        if not energies:
            return 0.5

        avg_energy = sum(energies) / len(energies)
        # 归一化到0-1范围
        confidence = min(avg_energy / 10000000, 1.0)
        return max(confidence, 0.3)

class EnhancedAudioRecorder:
    """增强版音频录制器"""

    def __init__(self, config: OptimizedAudioConfig = None, scenario: str = "balanced"):
        """
        初始化增强录制器

        Args:
            config: 配置对象
            scenario: 使用场景 ("meeting", "daily", "noisy", etc.)
        """
        if config is None:
            if scenario == "meeting":
                config = OptimizedPresets.high_accuracy_config()
            elif scenario == "noisy":
                config = OptimizedPresets.noise_resistant_config()
            elif scenario == "fast":
                config = OptimizedPresets.fast_config()
            else:
                config = OptimizedPresets.balanced_config()

        self.config = config
        self.sample_rate = 16000
        self.channels = 1
        self.format = pyaudio.paInt16

        # 初始化组件
        self.vad = EnhancedVAD(self.sample_rate, config.vad_aggressiveness)
        self.enhancer = AudioEnhancer(self.sample_rate)
        self.text_processor = TextProcessor(config.custom_vocabulary)

        # 录制控制
        self.is_recording = False
        self.recording_thread = None
        self.processing_thread = None

        # 音频缓冲
        self.audio_buffer = bytearray()
        self.buffer_lock = threading.Lock()
        self.last_process_time = time.time()

        # PyAudio
        self.audio_interface = None
        self.stream = None

        # Whisper模型
        self.whisper_model = None
        self.faster_whisper_model = None

        # 统计
        self.stats = {
            'total_segments': 0,
            'successful_transcriptions': 0,
            'failed_transcriptions': 0,
            'avg_confidence': 0.0,
            'high_quality_ratio': 0.0,
            'start_time': None
        }

        self._initialize_components()

    def _initialize_components(self):
        """初始化组件"""
        # PyAudio
        if PYAUDIO_AVAILABLE:
            try:
                self.audio_interface = pyaudio.PyAudio()
                logging.info("PyAudio 初始化成功")
            except Exception as e:
                logging.error(f"PyAudio 初始化失败: {e}")

        # Whisper模型
        self._initialize_whisper_model()

    def _initialize_whisper_model(self):
        """初始化优化的Whisper模型"""
        backend = self.config.whisper_backend
        model_size = self.config.whisper_model_size

        if backend == "faster-whisper" and FASTER_WHISPER_AVAILABLE:
            try:
                logging.info(f"加载优化的 Faster-Whisper 模型 ({model_size})...")

                device = "cuda" if self._is_cuda_available() else "cpu"
                compute_type = self.config.compute_type

                if device == "cpu" and compute_type == "float16":
                    compute_type = "int8"

                self.faster_whisper_model = WhisperModel(
                    model_size,
                    device=device,
                    compute_type=compute_type
                )
                logging.info(f"Faster-Whisper 模型加载成功")

            except Exception as e:
                logging.error(f"Faster-Whisper 模型加载失败: {e}")

    def _is_cuda_available(self):
        """检查CUDA"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def start_recording(self, use_system_audio=True):
        """开始录制"""
        if not PYAUDIO_AVAILABLE or not (FASTER_WHISPER_AVAILABLE or WHISPER_AVAILABLE):
            logging.error("缺少必要组件")
            return False

        if self.is_recording:
            return False

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

            # 启动线程
            self.recording_thread = threading.Thread(target=self._recording_worker, daemon=True)
            self.processing_thread = threading.Thread(target=self._processing_worker, daemon=True)

            self.recording_thread.start()
            self.processing_thread.start()

            logging.info("增强版音频录制已启动")
            return True

        except Exception as e:
            logging.error(f"启动录制失败: {e}")
            return False

    def _recording_worker(self):
        """录制工作线程"""
        while self.is_recording:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)

                with self.buffer_lock:
                    self.audio_buffer.extend(data)

            except Exception as e:
                if self.is_recording:
                    logging.error(f"录制错误: {e}")
                break

    def _processing_worker(self):
        """处理工作线程"""
        while self.is_recording:
            try:
                current_time = time.time()

                if current_time - self.last_process_time >= 1.0:
                    self._process_buffer()
                    self.last_process_time = current_time

                time.sleep(0.1)

            except Exception as e:
                logging.error(f"处理错误: {e}")

    def _process_buffer(self):
        """处理音频缓冲区"""
        with self.buffer_lock:
            if len(self.audio_buffer) < self.sample_rate * 2:
                return

            buffer_data = bytes(self.audio_buffer)

            # 保留重叠数据
            keep_size = self.sample_rate * 2 * 2
            if len(self.audio_buffer) > keep_size:
                self.audio_buffer = self.audio_buffer[-keep_size:]
            else:
                self.audio_buffer.clear()

        # VAD分析
        segments = self.vad.detect_speech_segments_advanced(
            buffer_data,
            min_speech_duration=self.config.min_speech_duration,
            max_silence_duration=self.config.max_silence_duration,
            max_segment_duration=self.config.max_segment_duration
        )

        for start_offset, end_offset, vad_confidence in segments:
            segment_data = buffer_data[start_offset:end_offset]
            duration = len(segment_data) / (self.sample_rate * 2)

            if 0.3 <= duration <= self.config.max_segment_duration:
                self._process_audio_segment(segment_data, duration, vad_confidence)

    def _process_audio_segment(self, segment_data: bytes, duration: float, vad_confidence: float):
        """处理音频段落"""
        try:
            # 音频增强
            if self.config.enable_audio_enhancement:
                # 转换为numpy数组
                audio_array = np.frombuffer(segment_data, dtype=np.int16).astype(np.float32) / 32768.0

                # 音频增强
                enhanced_array = self.enhancer.enhance_audio(
                    audio_array,
                    noise_reduction=self.config.noise_reduction_strength,
                    normalize_volume=self.config.volume_normalization
                )

                # 转回bytes
                enhanced_int16 = (enhanced_array * 32767).astype(np.int16)
                segment_data = enhanced_int16.tobytes()

            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name

                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(self.channels)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(self.sample_rate)
                    wav_file.writeframes(segment_data)

            # Whisper转录
            transcription, whisper_confidence = self._transcribe_audio_enhanced(temp_path)

            # 清理临时文件
            os.unlink(temp_path)

            # 🔍 添加详细的调试日志
            logging.info(f"🎤 音频段落 ({duration:.1f}s) 转录结果: '{transcription}' (Whisper置信度: {whisper_confidence:.2f})")

            if transcription and transcription.strip():
                # 文本后处理
                processed_text, final_confidence = self.text_processor.process_text(
                    transcription, whisper_confidence
                )

                # 置信度过滤
                combined_confidence = (vad_confidence + final_confidence) / 2

                logging.info(f"📝 文本处理完成: '{processed_text}' (VAD:{vad_confidence:.2f}, 最终:{combined_confidence:.2f}, 阈值:{self.config.min_confidence_threshold})")

                if (not self.config.enable_confidence_filtering or
                    combined_confidence >= self.config.min_confidence_threshold):

                    self._save_transcription(processed_text, datetime.now(), combined_confidence)
                    self.stats['successful_transcriptions'] += 1

                    # 更新统计
                    self._update_stats(combined_confidence, True)

                    logging.info(f"✅ 转录成功保存: {processed_text}")
                else:
                    self.stats['failed_transcriptions'] += 1
                    self._update_stats(combined_confidence, False)
                    logging.warning(f"❌ 置信度过低，过滤转录: {combined_confidence:.2f} < {self.config.min_confidence_threshold} - '{processed_text}'")
            else:
                self.stats['failed_transcriptions'] += 1
                self._update_stats(0.0, False)
                logging.warning(f"❌ 转录失败或为空 ({duration:.1f}s) - 原始结果: '{transcription}'")

            self.stats['total_segments'] += 1

        except Exception as e:
            logging.error(f"处理音频段落错误: {e}")
            self.stats['failed_transcriptions'] += 1

    def _transcribe_audio_enhanced(self, audio_path: str) -> Tuple[str, float]:
        """增强版音频转录"""
        try:
            logging.info(f"🔧 开始转录音频文件: {audio_path}")

            if self.config.whisper_backend == "faster-whisper" and self.faster_whisper_model:
                logging.info(f"🤖 使用Faster-Whisper模型转录 (模型: {self.config.whisper_model_size})")

                # 使用优化配置
                segments, info = self.faster_whisper_model.transcribe(
                    audio_path,
                    language=self.config.whisper_language,
                    task='transcribe',
                    beam_size=self.config.beam_size,
                    best_of=self.config.best_of,
                    temperature=self.config.temperature,
                    condition_on_previous_text=self.config.condition_on_previous_text,
                    no_speech_threshold=self.config.no_speech_threshold,
                    compression_ratio_threshold=self.config.compression_ratio_threshold,
                    log_prob_threshold=self.config.log_prob_threshold,
                    initial_prompt=self.config.whisper_initial_prompt
                )

                logging.info(f"📊 Whisper转录信息: 语言={info.language}, 概率={info.language_probability:.2f}")

                # 拼接文本并计算置信度
                text_segments = []
                confidences = []

                segment_count = 0
                for segment in segments:
                    segment_count += 1
                    logging.info(f"🎵 段落{segment_count}: '{segment.text}' (概率: {segment.avg_logprob:.2f})")
                    text_segments.append(segment.text)
                    # 使用平均对数概率作为置信度近似
                    confidences.append(max(0.0, min(1.0, (segment.avg_logprob + 1.0))))

                text = "".join(text_segments).strip()
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

                logging.info(f"📝 拼接后文本: '{text}' (段落数: {segment_count}, 平均置信度: {avg_confidence:.2f})")

                # 繁简转换
                if text and TEXT_CONVERTER_AVAILABLE and self.config.use_simplified_chinese:
                    original_text = text
                    text = convert_traditional_to_simplified(text)
                    if text != original_text:
                        logging.info(f"🔄 繁简转换: '{original_text}' -> '{text}'")

                logging.info(f"✅ 转录完成，最终结果: '{text}' (置信度: {avg_confidence:.2f})")
                return text, avg_confidence
            else:
                logging.error("❌ Faster-Whisper模型未初始化")
                return None, 0.0

        except Exception as e:
            logging.error(f"❌ 转录异常: {e}")
            return None, 0.0

    def _update_stats(self, confidence: float, is_high_quality: bool):
        """更新统计信息"""
        total_transcriptions = self.stats['successful_transcriptions'] + self.stats['failed_transcriptions']

        if total_transcriptions > 0:
            # 更新平均置信度
            old_avg = self.stats['avg_confidence']
            self.stats['avg_confidence'] = (old_avg * (total_transcriptions - 1) + confidence) / total_transcriptions

            # 更新高质量比例
            if is_high_quality:
                high_quality_count = int(self.stats['high_quality_ratio'] * (total_transcriptions - 1)) + 1
            else:
                high_quality_count = int(self.stats['high_quality_ratio'] * (total_transcriptions - 1))

            self.stats['high_quality_ratio'] = high_quality_count / total_transcriptions

    def _save_transcription(self, text: str, timestamp: datetime, confidence: float):
        """保存转录结果"""
        try:
            record_data = {
                'timestamp': timestamp.isoformat(),
                'record_type': 'audio_transcription_enhanced',
                'triggered_by': 'enhanced_audio_recorder',
                'event_type': 'enhanced_transcription',
                'window_title': f'Enhanced Audio (conf: {confidence:.2f})',
                'process_name': 'enhanced_audio_recorder',
                'app_name': 'Enhanced Audio System',
                'page_title': None,
                'url': None,
                'ocr_text': text,
                'parser_type': 'whisper_enhanced',
                'mouse_x': None,
                'mouse_y': None,
                'button': None
            }

            conn = create_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()

                    insert_query = """
                        INSERT INTO activity_log (
                            timestamp, record_type, triggered_by, event_type,
                            window_title, process_name, app_name, page_title, url,
                            ocr_text, parser_type, mouse_x, mouse_y, button
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """

                    cursor.execute(insert_query, (
                        record_data['timestamp'], record_data['record_type'],
                        record_data['triggered_by'], record_data['event_type'],
                        record_data['window_title'], record_data['process_name'],
                        record_data['app_name'], record_data['page_title'],
                        record_data['url'], record_data['ocr_text'],
                        record_data['parser_type'], record_data['mouse_x'],
                        record_data['mouse_y'], record_data['button']
                    ))

                    conn.commit()
                    record_id = cursor.lastrowid
                    record_data['id'] = record_id

                    # 索引到向量数据库
                    try:
                        index_single_activity_record(record_data)
                    except Exception as e:
                        logging.debug(f"索引失败: {e}")

                except sqlite3.Error as e:
                    logging.error(f"保存转录失败: {e}")
                finally:
                    conn.close()

        except Exception as e:
            logging.error(f"保存转录错误: {e}")

    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            return

        self.is_recording = False

        # 等待线程结束
        if self.recording_thread:
            self.recording_thread.join(timeout=5)
        if self.processing_thread:
            self.processing_thread.join(timeout=5)

        # 关闭音频流
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        logging.info("增强版音频录制已停止")
        self._print_enhanced_stats()

    def _print_enhanced_stats(self):
        """打印增强统计信息"""
        if self.stats['start_time']:
            duration = datetime.now() - self.stats['start_time']
            total = self.stats['successful_transcriptions'] + self.stats['failed_transcriptions']

            print("🎯 增强版音频录制统计")
            print("=" * 50)
            print(f"📊 运行时长: {duration}")
            print(f"🔢 处理段落: {self.stats['total_segments']}")
            print(f"✅ 成功转录: {self.stats['successful_transcriptions']}")
            print(f"❌ 失败转录: {self.stats['failed_transcriptions']}")

            if total > 0:
                success_rate = (self.stats['successful_transcriptions'] / total) * 100
                print(f"📈 成功率: {success_rate:.1f}%")
                print(f"🎯 平均置信度: {self.stats['avg_confidence']:.2f}")
                print(f"⭐ 高质量比例: {self.stats['high_quality_ratio']:.1%}")

    def cleanup(self):
        """清理资源"""
        self.stop_recording()

        if self.audio_interface:
            self.audio_interface.terminate()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="增强版音频录制器")
    parser.add_argument("--scenario", choices=["meeting", "daily", "fast", "noisy"],
                       default="daily", help="使用场景")
    parser.add_argument("--model", choices=["base", "small", "medium"],
                       default="small", help="Whisper模型大小")

    args = parser.parse_args()

    print(f"🎯 启动增强版音频录制器 - {args.scenario}场景")
    print("=" * 60)

    # 创建录制器
    global recorder
    recorder = EnhancedAudioRecorder(scenario=args.scenario)

    # 信号处理
    def signal_handler(signum, frame):
        logging.info("停止信号接收")
        if recorder:
            recorder.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 开始录制
    if recorder.start_recording():
        print("🚀 增强版音频录制已启动")
        print(f"📊 场景: {args.scenario}")
        print(f"🧠 模型: {recorder.config.whisper_model_size}")
        print(f"🎯 置信度阈值: {recorder.config.min_confidence_threshold}")
        print("按 Ctrl+C 停止")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            recorder.cleanup()
    else:
        print("❌ 启动失败")

if __name__ == "__main__":
    main()