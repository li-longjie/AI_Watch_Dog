"""配置文件
包含视频监控系统的所有可配置参数
"""

from typing import Dict, Any
import logging

# 视频源配置
class VideoConfig:
    # 摄像头配置
    CAMERA_INDEX = 4  # 小米摄像头的索引
    CAMERA_WIDTH = 1280  # 或其他支持的分辨率
    CAMERA_HEIGHT = 720
    FPS = 30
    RETRY_INTERVAL = 1  # 重试间隔（秒）
    MAX_RETRIES = 3    # 最大重试次数
    
    # 视频处理配置
    VIDEO_INTERVAL = 1800  # 视频分段时长(秒)
    ANALYSIS_INTERVAL = 10  # 分析间隔(秒)
    BUFFER_DURATION = 11  # 滑窗分析时长
    JPEG_QUALITY = 80  # JPEG压缩质量
    
    # 活动检测配置
    ACTIVITY_THRESHOLD = 0.1  # 活动检测阈值

# 修改默认视频源为摄像头
VIDEO_SOURCE = VideoConfig.CAMERA_INDEX  # 使用摄像头索引

# API配置
class APIConfig:
    # 通义千问API配置
    QWEN_API_KEY = "sk-75b4138c4f4b495396dbe8743b5eec38"
    QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    QWEN_MODEL = "qwen-vl-plus-latest"
    


    # SiliconFlow DeepSeek API 配置
    DEEPSEEK_API_KEY = "sk-xugvbuiyayzzfeoelfytnfioimnwvzouawxlavixynzuloui"
    DEEPSEEK_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
    DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-V3"
    
    # API请求配置
    REQUEST_TIMEOUT = 60.0  # 请求超时时间（秒）
    TEMPERATURE = 0.7  # 调整为推荐值
    TOP_P = 0.7  # 调整为推荐值
    TOP_K = 50  # 调整为推荐值
    REPETITION_PENALTY = 0.5  # 作为 frequency_penalty 使用

# RAG系统配置
class RAGConfig:
    # 知识库配置
    ENABLE_RAG = True
    VECTOR_API_URL = "http://localhost:8085/add_text/"  # 修改为正确的 RAG 服务器地址
    HISTORY_FILE = "video_history_info.txt"

# 存档配置
ARCHIVE_DIR = "archive"

# 服务器配置
class ServerConfig:
    HOST = "0.0.0.0"
    PORT = 16532
    RELOAD = True
    WORKERS = 1

# 日志配置
LOG_CONFIG = {
    'level': logging.INFO,
    'format': '%(asctime)s - %(levelname)s - %(message)s',
    'handlers': [
        {'type': 'file', 'filename': 'code.log'},
        {'type': 'stream'}
    ]
}



def update_config(args: Dict[str, Any]) -> None:
    """使用命令行参数更新配置
    
    Args:
        args: 包含命令行参数的字典
    """
    global VIDEO_SOURCE
    
    # 更新视频源
    if args.get('video_source'):
        VIDEO_SOURCE = args['video_source']
    
    # 更新视频处理配置
    for key in ['video_interval', 'analysis_interval', 'buffer_duration',
               'ws_retry_interval', 'max_ws_queue', 'jpeg_quality']:
        if key in args:
            setattr(VideoConfig, key.upper(), args[key])
    
    # 更新服务器配置
    for key in ['host', 'port', 'reload', 'workers']:
        if key in args:
            setattr(ServerConfig, key.upper(), args[key])
            
    # 更新API配置
    for key in ['qwen_api_key', 'qwen_api_url', 'qwen_model',
               'deepseek_api_key', 'deepseek_api_url', 'deepseek_model',
               'request_timeout', 'temperature', 'top_p', 'top_k',
               'repetition_penalty']:
        if key in args:
            setattr(APIConfig, key.upper(), args[key])
            
    # 更新RAG配置
    for key in ['enable_rag', 'vector_api_url', 'history_file',
               'history_save_interval']:
        if key in args:
            setattr(RAGConfig, key.upper(), args[key])


