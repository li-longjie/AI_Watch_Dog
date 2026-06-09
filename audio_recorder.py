# audio_recorder.py

import os
import json
import asyncio
import logging
import threading
import time
import wave
import tempfile
import sqlite3
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

class AudioRecorder:
    def __init__(self,
                 config: AudioConfig = None,  # 使用配置对象
                 chunk_duration=5,   # 每5秒处理一次音频（准实时）
                 sample_rate=16000,  # 采样率
                 channels=1,         # 单声道
                 format=pyaudio.paInt16,  # 16位音频
                 device_index=None,  # 音频设备索引
                 whisper_model_size="base"):  # Whisper 模型大小
        """
        初始化音频录制器

        Args:
            config: 音频配置对象
            chunk_duration: 每次处理的音频时长（秒）
            sample_rate: 采样率
            channels: 声道数
            format: 音频格式
            device_index: 音频设备索引，None表示使用默认设备
        """
        # 使用配置对象或向后兼容的参数
        if config is None:
            config = DEFAULT_CONFIG

        self.config = config
        self.chunk_duration = config.chunk_duration if hasattr(config, 'chunk_duration') else chunk_duration
        self.sample_rate = config.sample_rate if hasattr(config, 'sample_rate') else sample_rate
        self.channels = config.channels if hasattr(config, 'channels') else channels
        self.format = format
        self.device_index = config.device_index if hasattr(config, 'device_index') else device_index
        self.whisper_model_size = config.whisper_model_size if hasattr(config, 'whisper_model_size') else whisper_model_size

        # 录制控制
        self.is_recording = False
        self.recording_thread = None
        self.processing_thread = None

        # 音频数据缓冲区
        self.audio_buffer = deque()
        self.buffer_lock = threading.Lock()

        # PyAudio 实例
        self.audio_interface = None
        self.stream = None

        # Whisper 模型
        self.whisper_model = None
        self.faster_whisper_model = None

        # 统计信息
        self.stats = {
            'total_chunks_processed': 0,
            'total_transcriptions': 0,
            'successful_transcriptions': 0,
            'failed_transcriptions': 0,
            'start_time': None
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
                self._list_audio_devices()
            except Exception as e:
                logging.error(f"PyAudio 初始化失败: {e}")
                self.audio_interface = None

        # 初始化 Whisper 模型
        self._initialize_whisper_model()

    def _initialize_whisper_model(self):
        """初始化Whisper模型"""
        backend = getattr(self.config, 'whisper_backend', 'faster-whisper')

        if backend == "faster-whisper" and FASTER_WHISPER_AVAILABLE:
            try:
                logging.info(f"正在加载 Faster-Whisper 模型 ({self.whisper_model_size})...")

                # 获取faster-whisper配置
                device = "cuda" if self._is_cuda_available() else "cpu"
                compute_type = getattr(self.config, 'compute_type', 'float16')

                # 如果是CPU，自动调整compute_type
                if device == "cpu" and compute_type == "float16":
                    compute_type = "int8"
                    logging.info("CPU环境下自动切换到int8计算类型")

                self.faster_whisper_model = WhisperModel(
                    self.whisper_model_size,
                    device=device,
                    compute_type=compute_type
                )
                logging.info(f"Faster-Whisper 模型 ({self.whisper_model_size}, {compute_type}) 加载成功")

            except Exception as e:
                logging.error(f"Faster-Whisper 模型加载失败: {e}")
                self.faster_whisper_model = None

        elif backend == "openai-whisper" and WHISPER_AVAILABLE:
            try:
                logging.info(f"正在加载 OpenAI-Whisper 模型 ({self.whisper_model_size})...")
                self.whisper_model = whisper.load_model(self.whisper_model_size)
                logging.info(f"OpenAI-Whisper 模型 ({self.whisper_model_size}) 加载成功")
            except Exception as e:
                logging.error(f"OpenAI-Whisper 模型加载失败: {e}")
                self.whisper_model = None
        else:
            logging.error(f"未找到可用的Whisper后端: {backend}")

    def _is_cuda_available(self):
        """检查CUDA是否可用"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def _list_audio_devices(self):
        """列出可用的音频设备"""
        if not self.audio_interface:
            return

        logging.info("可用的音频设备:")
        for i in range(self.audio_interface.get_device_count()):
            device_info = self.audio_interface.get_device_info_by_index(i)
            logging.info(f"  设备 {i}: {device_info['name']} "
                        f"(输入通道: {device_info['maxInputChannels']}, "
                        f"输出通道: {device_info['maxOutputChannels']})")

    def get_default_input_device(self):
        """获取默认输入设备"""
        if not self.audio_interface:
            return None

        try:
            default_device_info = self.audio_interface.get_default_input_device_info()
            logging.info(f"默认输入设备: {default_device_info['name']}")
            return default_device_info
        except Exception as e:
            logging.error(f"获取默认输入设备失败: {e}")
            return None

    def find_system_audio_device(self):
        """尝试找到系统音频设备（立体声混音等）"""
        if not self.audio_interface:
            return None

        # 常见的系统音频设备名称关键词
        system_audio_keywords = [
            "立体声混音", "stereo mix", "混音", "loopback",
            "system audio", "what u hear", "wave out mix"
        ]

        for i in range(self.audio_interface.get_device_count()):
            device_info = self.audio_interface.get_device_info_by_index(i)
            device_name = device_info['name'].lower()

            # 检查是否是输入设备且名称包含系统音频关键词
            if (device_info['maxInputChannels'] > 0 and
                any(keyword in device_name for keyword in system_audio_keywords)):
                logging.info(f"找到系统音频设备: {device_info['name']} (索引: {i})")
                return i

        logging.warning("未找到系统音频设备，将使用默认输入设备")
        return None

    def start_recording(self, use_system_audio=True):
        """开始录制音频"""
        if not PYAUDIO_AVAILABLE:
            logging.error("PyAudio 未安装，无法开始录制")
            return False

        if not WHISPER_AVAILABLE and not FASTER_WHISPER_AVAILABLE:
            logging.error("缺少Whisper组件，无法开始录制")
            return False

        if self.is_recording:
            logging.warning("录制已在进行中")
            return False

        # 确定使用的音频设备
        original_device_index = self.device_index
        if use_system_audio:
            system_device = self.find_system_audio_device()
            if system_device is not None:
                self.device_index = system_device

        # 尝试多个设备，直到找到可用的
        devices_to_try = []

        if self.device_index is not None:
            devices_to_try.append(self.device_index)

        # 添加其他可能的输入设备作为备选
        if self.audio_interface:
            for i in range(self.audio_interface.get_device_count()):
                device_info = self.audio_interface.get_device_info_by_index(i)
                if (device_info['maxInputChannels'] > 0 and
                    i not in devices_to_try):
                    devices_to_try.append(i)

        # 如果没有指定设备，尝试默认设备
        if not devices_to_try:
            devices_to_try.append(None)

        for device_idx in devices_to_try:
            try:
                logging.info(f"尝试使用音频设备索引: {device_idx}")

                # 创建音频流
                self.stream = self.audio_interface.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=device_idx,
                    frames_per_buffer=1024
                )

                # 如果成功创建流，更新设备索引并跳出循环
                self.device_index = device_idx
                logging.info(f"成功使用音频设备索引: {device_idx}")
                break

            except Exception as e:
                logging.warning(f"设备索引 {device_idx} 不可用: {e}")
                if self.stream:
                    try:
                        self.stream.close()
                    except:
                        pass
                    self.stream = None
                continue

        if not self.stream:
            logging.error("无法找到可用的音频设备")
            return False

        try:

            self.is_recording = True
            self.stats['start_time'] = datetime.now()

            # 启动录制线程
            self.recording_thread = threading.Thread(target=self._recording_worker, daemon=True)
            self.recording_thread.start()

            # 启动处理线程
            self.processing_thread = threading.Thread(target=self._processing_worker, daemon=True)
            self.processing_thread.start()

            logging.info(f"开始音频录制，设备索引: {self.device_index}")
            return True

        except Exception as e:
            logging.error(f"启动音频录制失败: {e}")
            self.is_recording = False
            if self.stream:
                self.stream.close()
                self.stream = None
            return False

    def stop_recording(self):
        """停止录制音频"""
        if not self.is_recording:
            return

        logging.info("正在停止音频录制...")
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

        logging.info("音频录制已停止")
        self._print_stats()

    def _recording_worker(self):
        """录制工作线程"""
        chunk_frames = int(self.sample_rate * self.chunk_duration)
        current_chunk = []

        while self.is_recording:
            try:
                # 读取音频数据
                data = self.stream.read(1024, exception_on_overflow=False)
                current_chunk.append(data)

                # 检查是否达到块大小
                if len(b''.join(current_chunk)) >= chunk_frames * 2:  # 2 bytes per sample for paInt16
                    # 将音频块添加到缓冲区
                    with self.buffer_lock:
                        self.audio_buffer.append({
                            'data': b''.join(current_chunk),
                            'timestamp': datetime.now(),
                            'sample_rate': self.sample_rate,
                            'channels': self.channels,
                            'format': self.format
                        })

                    current_chunk = []
                    self.stats['total_chunks_processed'] += 1

            except Exception as e:
                if self.is_recording:  # 只有在仍在录制时才记录错误
                    logging.error(f"录制音频时出错: {e}")
                break

    def _processing_worker(self):
        """音频处理工作线程"""
        while self.is_recording or self.audio_buffer:
            try:
                # 从缓冲区获取音频数据
                audio_chunk = None
                with self.buffer_lock:
                    if self.audio_buffer:
                        audio_chunk = self.audio_buffer.popleft()

                if audio_chunk:
                    self._process_audio_chunk(audio_chunk)
                else:
                    time.sleep(0.1)  # 没有数据时短暂休眠

            except Exception as e:
                logging.error(f"处理音频时出错: {e}")

    def _process_audio_chunk(self, audio_chunk):
        """处理单个音频块"""
        try:
            # 创建临时音频文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name

                # 写入 WAV 文件
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(audio_chunk['channels'])
                    wav_file.setsampwidth(self.audio_interface.get_sample_size(audio_chunk['format']))
                    wav_file.setframerate(audio_chunk['sample_rate'])
                    wav_file.writeframes(audio_chunk['data'])

            # 使用 Whisper 进行语音转文字
            transcription = self._transcribe_audio(temp_path)

            # 清理临时文件
            os.unlink(temp_path)

            if transcription and transcription.strip():
                # 过滤明显的幻觉输出
                if self._is_valid_transcription(transcription):
                    # 保存转录结果到数据库
                    self._save_transcription(transcription, audio_chunk['timestamp'])
                    self.stats['successful_transcriptions'] += 1
                    logging.info(f"音频转录成功: {transcription[:50]}...")
                else:
                    self.stats['failed_transcriptions'] += 1
                    logging.debug(f"过滤低质量转录: {transcription[:30]}...")
            else:
                self.stats['failed_transcriptions'] += 1
                logging.debug("音频块未检测到有效语音")

            self.stats['total_transcriptions'] += 1

        except Exception as e:
            logging.error(f"处理音频块时出错: {e}")
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
        if len(set(text.strip())) < len(text.strip()) / 3:  # 字符重复度过高
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
            beam_size = getattr(self.config, 'beam_size', 5)
            best_of = getattr(self.config, 'best_of', 5)
            temperature = getattr(self.config, 'temperature', 0.0)
            condition_on_previous_text = getattr(self.config, 'condition_on_previous_text', True)
            no_speech_threshold = getattr(self.config, 'no_speech_threshold', 0.6)
            compression_ratio_threshold = getattr(self.config, 'compression_ratio_threshold', 2.4)
            log_prob_threshold = getattr(self.config, 'log_prob_threshold', -1.0)
            initial_prompt = getattr(self.config, 'whisper_initial_prompt', "以下是普通话的句子。")

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
                        logging.debug(f"文本转换: {text[:50]}... -> {converted_text[:50]}...")
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
            initial_prompt = getattr(self.config, 'whisper_initial_prompt', "以下是普通话的句子。")

            # 使用 OpenAI-Whisper 进行转录
            result = self.whisper_model.transcribe(
                audio_path,
                language=language,
                task='transcribe',
                initial_prompt=initial_prompt
            )

            text = result['text'].strip() if result and 'text' in result else None

            # 尝试将繁体中文转换为简体中文
            if text and TEXT_CONVERTER_AVAILABLE and getattr(self.config, 'use_simplified_chinese', True):
                try:
                    converted_text = convert_traditional_to_simplified(text)
                    if converted_text != text:
                        logging.debug(f"文本转换: {text[:50]}... -> {converted_text[:50]}...")
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
                'record_type': 'audio_transcription',
                'triggered_by': 'audio_recorder',
                'event_type': 'transcription',
                'window_title': 'System Audio',
                'process_name': 'audio_recorder',
                'app_name': 'System Audio',
                'page_title': None,
                'url': None,
                'ocr_text': transcription_text,
                'parser_type': 'whisper',
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

                    # 获取插入的记录ID
                    record_id = cursor.lastrowid
                    record_data['id'] = record_id

                    logging.debug(f"音频转录记录已保存到数据库，ID: {record_id}")

                    # 索引到向量数据库
                    try:
                        success = index_single_activity_record(record_data)
                        if success:
                            logging.debug(f"音频转录记录已索引到向量数据库，ID: {record_id}")
                        else:
                            logging.warning(f"音频转录记录索引到向量数据库失败，ID: {record_id}")
                    except Exception as e:
                        logging.error(f"索引音频转录记录到向量数据库时出错: {e}")

                except sqlite3.Error as e:
                    logging.error(f"保存音频转录记录到数据库失败: {e}")
                finally:
                    conn.close()
            else:
                logging.error("无法连接到数据库，音频转录记录未保存")

        except Exception as e:
            logging.error(f"保存音频转录记录时出错: {e}")

    def _print_stats(self):
        """打印统计信息"""
        if self.stats['start_time']:
            duration = datetime.now() - self.stats['start_time']
            logging.info(f"音频录制统计:")
            logging.info(f"  运行时长: {duration}")
            logging.info(f"  处理音频块: {self.stats['total_chunks_processed']}")
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

        logging.info("音频录制器资源已清理")


def signal_handler(signum, frame):
    """信号处理器，用于优雅地停止服务"""
    logging.info("收到停止信号，正在关闭音频录制服务...")
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
        logging.error("PyAudio 未安装，请运行: pip install pyaudio")
        return

    if not WHISPER_AVAILABLE:
        logging.error("Whisper 未安装，请运行: pip install openai-whisper")
        return

    # 创建音频录制器
    global recorder
    recorder = AudioRecorder(
        chunk_duration=5,   # 5秒一个处理块（准实时转录）
        sample_rate=16000,  # 16kHz 采样率，适合语音识别
        channels=1          # 单声道
    )

    # 开始录制
    if recorder.start_recording(use_system_audio=True):
        logging.info("音频录制服务已启动")
        logging.info("按 Ctrl+C 停止服务")

        try:
            # 保持服务运行
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("收到键盘中断信号")
        finally:
            recorder.cleanup()
    else:
        logging.error("启动音频录制服务失败")


if __name__ == "__main__":
    main()