import cv2 
import asyncio 
import json 
import argparse
from datetime import datetime 
from concurrent.futures import ThreadPoolExecutor 
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from collections import deque 
from typing import Optional, Dict, Any, List
import numpy as np 
import logging 
from multi_modal_analyzer import MultiModalAnalyzer
import time
import uvicorn 
from multiprocessing import set_start_method 
from config import VideoConfig, ServerConfig, VIDEO_SOURCE, LOG_CONFIG, ARCHIVE_DIR, update_config
import os
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from video_processor import VideoProcessor
import queue

# 配置日志记录
logging.basicConfig(
    level=LOG_CONFIG['level'],
    format=LOG_CONFIG['format'],
    handlers=[logging.FileHandler(LOG_CONFIG['handlers'][0]['filename'], encoding='utf-8'), logging.StreamHandler()]
)

# 解析命令行参数
def parse_args():
    parser = argparse.ArgumentParser(description='智能视频监控系统')
    parser.add_argument('--video_source', type=str, help='视频源路径')
    parser.add_argument('--video_interval', type=int, help='视频分段时长(秒)')
    parser.add_argument('--analysis_interval', type=int, help='分析间隔(秒)')
    parser.add_argument('--buffer_duration', type=int, help='滑窗分析时长')
    parser.add_argument('--ws_retry_interval', type=int, help='WebSocket重连间隔(秒)')
    parser.add_argument('--max_ws_queue', type=int, help='消息队列最大容量')
    parser.add_argument('--jpeg_quality', type=int, help='JPEG压缩质量')
    parser.add_argument('--host', type=str, help='服务器主机地址')
    parser.add_argument('--port', type=int, help='服务器端口')
    parser.add_argument('--reload', type=bool, help='是否启用热重载')
    parser.add_argument('--workers', type=int, help='工作进程数')
    
    args = parser.parse_args()
    return {k: v for k, v in vars(args).items() if v is not None}

# 更新配置
args = parse_args()
update_config(args)

# 初始化视频源
def get_video_source(source):
    """根据输入确定视频源类型"""
    if source is None:
        return VIDEO_SOURCE
    
    # 尝试将输入转换为整数（摄像头索引）
    try:
        cam_index = int(source)
        return cam_index
    except ValueError:
        # 如果不是整数，则视为文件路径
        return source

# 初始化视频源
video_source = get_video_source(args.get('video_source'))

# 创建视频处理器
try:
    video_processor = VideoProcessor(video_source)
except ValueError as e:
    print(f"错误: {e}")
    import sys
    sys.exit(1)

# 创建FastAPI应用
app = FastAPI(title="智能视频监控系统")

# 设置静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/video_warning", StaticFiles(directory="video_warning"), name="video_warning")

# 创建必要的目录
os.makedirs("video_warning", exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# 全局变量
active_connections = []
recent_alerts = []
MAX_ALERTS = 10
 
@app.on_event("startup") 
async def startup():
    """应用启动时的初始化"""
    # 启动视频处理
    asyncio.create_task(video_processor.start_processing())
    
    # 启动警报处理
    asyncio.create_task(alert_handler())

@app.on_event("shutdown")
async def shutdown_event():
    await video_processor.stop_processing()

@app.websocket("/video_feed")
async def video_feed(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    video_processor.start_push_queue = 1
    try:
        await video_processor.video_streamer(websocket)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        logging.error(f"Video feed error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)
    finally:
        video_processor.start_push_queue = 0

@app.websocket("/alerts")
async def alerts(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        # 发送已有的预警
        if recent_alerts:
            for alert in recent_alerts:
                await websocket.send_json(alert)
        
        # 保持连接
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception as e:
        logging.error(f"Alert WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

@app.get("/")
async def get_index():
    try:
        with open("static/html/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>404 - Index page not found</h1>", status_code=404)

@app.get("/alerts")
async def get_alerts():
    return {
        "status": "success",
        "alerts": recent_alerts
    }

@app.get("/test_alert")
async def test_alert():
    """测试预警系统 - 强制发送预警消息到所有客户端"""
    test_alert = {
        "type": "alert",
        "timestamp": datetime.now().strftime('%Y年%m月%d日%H点%M分'),
        "content": "测试预警：这是一条测试消息",
        "level": "important",
        "details": "这是一条测试预警，用于确认预警系统功能正常",
        "image_url": "/video_warning/test.jpg"
    }
    
    # 创建测试图像
    test_img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(test_img, "测试预警图像", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.imwrite("video_warning/test.jpg", test_img)
    
    # 添加到最近预警
    recent_alerts.append(test_alert)
    if len(recent_alerts) > MAX_ALERTS:
        recent_alerts.pop(0)
    
    # 发送到所有连接
    for connection in active_connections:
        try:
            await connection.send_json(test_alert)
        except Exception as e:
            logging.error(f"发送测试预警失败: {e}")
    
    return {"status": "success", "message": "测试预警已发送"}

async def alert_handler():
    """处理警报消息"""
    while True:
        try:
            # 检查预警队列
            if hasattr(video_processor, 'alert_queue') and not video_processor.alert_queue.empty():
                try:
                    alert = video_processor.alert_queue.get_nowait()
                    # 添加到最近预警
                    recent_alerts.append(alert)
                    if len(recent_alerts) > MAX_ALERTS:
                        recent_alerts.pop(0)
                    
                    # 实时发送给所有连接
                    disconnected = []
                    for connection in active_connections:
                        try:
                            await connection.send_json(alert)
                        except:
                            disconnected.append(connection)
                    
                    # 清理断开的连接
                    for conn in disconnected:
                        if conn in active_connections:
                            active_connections.remove(conn)
                except queue.Empty:
                    pass
            
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"Alert handler error: {e}")
            await asyncio.sleep(1)

@app.get("/behavior_analysis")
async def behavior_analysis():
    """行为分析页面"""
    try:
        with open("static/html/behavior.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>404 - Behavior analysis page not found</h1>", status_code=404)

# 添加行为数据API端点
@app.get("/api/behavior-data")
async def get_behavior_data():
    """获取行为分析数据"""
    # 这里返回模拟的行为数据
    # 实际应用中应从视频处理器获取真实数据
    return {
        "status": "success",
        "data": {
            "behaviors": [
                {"id": 1, "type": "专注工作", "count": 5, "timestamp": "2025-03-28 20:10:00"},
                {"id": 2, "type": "吃东西", "count": 3, "timestamp": "2025-03-28 20:12:30"},
                {"id": 7, "type": "其他", "count": 2, "timestamp": "2025-03-28 20:15:45"}
            ],
            "statistics": {
                "total_behaviors": 10,
                "unique_behaviors": 3,
                "most_frequent": "专注工作"
            }
        }
    }

if __name__ == "__main__":
    print(f"启动视频服务器 http://{ServerConfig.HOST}:{ServerConfig.PORT}")
    uvicorn.run( 
        app, 
        host=ServerConfig.HOST,
        port=ServerConfig.PORT,
        log_level="info"
    )