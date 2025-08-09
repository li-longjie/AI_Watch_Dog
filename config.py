"""配置文件
包含视频监控系统的所有可配置参数
"""

from typing import Dict, Any
import logging
import os
from dotenv import load_dotenv

# 在脚本的最开始加载 .env 文件
# 这会把 .env 文件中的键值对加载到环境变量中
load_dotenv()

# 视频源配置
class VideoConfig:
    # 摄像头配置
    CAMERA_INDEX = 0  # 小米摄像头的索引
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
    # --- 阿里云 DashScope 配置 (已注释) ---
    # Qwen (Multi-modal)
    # QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-ec7d738dba374ec4b5c4d3071e930da5")  # DashScope API密钥，支持环境变量
    # QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1" # DashScope endpoint
    # QWEN_MODEL = "qwen2.5-vl-3b-instruct" # DashScope Qwen model name

    # --- 硅基流动 (SiliconFlow) 统一配置 ---
    # 从环境变量中读取API密钥，如果未设置，则使用占位符
    QWEN_API_KEY = os.getenv("SILICONFLOW_API_KEY", "sk-xugvbuiyayzzfeoelfytnfioimnwvzouawxlavixynzuloui")
    DEEPSEEK_API_KEY = os.getenv("SILICONFLOW_API_KEY", "sk-xugvbuiyayzzfeoelfytnfioimnwvzouawxlavixynzuloui")

    # 硅基流动 (SiliconFlow) for Qwen
    QWEN_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
    QWEN_MODEL = "Pro/Qwen/Qwen2.5-VL-7B-Instruct"

    # 硅基流动 (SiliconFlow) for DeepSeek
    DEEPSEEK_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
    DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-V3"

    # OpenRouter
    # QWEN_API_KEY = os.getenv("OPENROUTER_API_KEY", "YOUR_OPENROUTER_API_KEY_HERE")
    # DEEPSEEK_API_KEY = os.getenv("OPENROUTER_API_KEY", "YOUR_OPENROUTER_API_KEY_HERE")
    # QWEN_API_URL = "https://openrouter.ai/api/v1/chat/completions"
    # QWEN_MODEL = "qwen/qwen2.5-vl-32b-instruct:free"
    # DEEPSEEK_API_URL = "https://openrouter.ai/api/v1/chat/completions"
    # DEEPSEEK_MODEL = "deepseek/deepseek-chat-v3-0324:free"
    
    # 检查环境变量是否已设置
    if QWEN_API_KEY.startswith("YOUR_") or DEEPSEEK_API_KEY.startswith("YOUR_"):
        print("警告: 硅基流动 API Key 未通过环境变量'SILICONFLOW_API_KEY'配置。")
        print("提示: 当前使用默认的硅基流动API密钥，如需更换请设置环境变量 SILICONFLOW_API_KEY")

    # API请求通用配置
    REQUEST_TIMEOUT = 60.0  # 请求超时时间（秒）
    TEMPERATURE = 0.7       # 控制随机性
    TOP_P = 0.7             # 控制核心词汇
    TOP_K = 50              # 控制核心词汇 (可能不被所有API支持)
    REPETITION_PENALTY = 0.5 # 控制重复性 (可能不被所有API支持，或映射到 frequency_penalty)

# RAG系统配置
class RAGConfig:
    # 知识库配置
    ENABLE_RAG = True
    VECTOR_API_URL = "http://localhost:8085/add_text/"  # 修改为正确的 RAG 服务器地址
    HISTORY_FILE = "video_history_info.txt"
    # 视频服务向量存储配置
    ENABLE_VIDEO_VECTOR_STORAGE = True  # 控制视频服务是否启用向量存储

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
    'level': logging.DEBUG,  # 临时改为DEBUG级别以便调试API问题
    'format': '%(asctime)s - %(levelname)s - %(message)s',
    'handlers': [
        {'type': 'file', 'filename': 'code.log'},
        {'type': 'stream'}
    ]
}

# 阿里云OSS配置
class OSSConfig:
    ENABLED = True  # 强制启用OSS，不使用回退
    ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
    ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")
    ENDPOINT = os.getenv("OSS_ENDPOINT", "oss-cn-beijing.aliyuncs.com")
    BUCKET = os.getenv("OSS_BUCKET", "")
    # 用于存储的路径前缀
    ALERT_PREFIX = 'video_warning/'
    ANALYSIS_PREFIX = 'analysis_frames/'
    
    # 检查OSS配置是否完整
    if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET or not BUCKET:
        print("警告: OSS配置不完整，请检查 .env 文件中的 OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET 配置")

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


