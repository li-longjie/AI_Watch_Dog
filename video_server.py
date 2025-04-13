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
active_connections: List[WebSocket] = [] # 添加类型提示
MAX_ALERTS = 10
recent_alerts: deque = deque(maxlen=MAX_ALERTS) # 再使用 deque 并设置最大长度
 
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
    
    # 为每个连接维护一个已发送预警ID集合
    connection_sent_alerts = set()
    
    try:
        # 发送已有的预警，但确保不重复
        if recent_alerts:
            for alert in recent_alerts:
                # 提取预警的唯一标识
                alert_key = alert.get("alert_key")
                if not alert_key:
                    # 如果没有alert_key，根据内容和时间戳生成一个更可靠的后备key
                    timestamp = alert.get("timestamp", "")
                    content = alert.get("content", "")
                    # 移除可能为空的 start/end time，避免它们引起不一致
                    alert_key = f"{content}_{timestamp}"
                
                if alert_key not in connection_sent_alerts:
                    await websocket.send_json(alert)
                    connection_sent_alerts.add(alert_key)
                    
                    # 限制sent_alerts大小
                    if len(connection_sent_alerts) > 100:
                        connection_sent_alerts = set(list(connection_sent_alerts)[-100:])
        
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


@app.get("/api/alerts")
async def get_alerts_api(): # 修改函数名以示区分
    # 注意：现在 recent_alerts 是 deque
    return {
        "status": "success",
        "alerts": list(recent_alerts) # 返回列表
    }

@app.get("/test_alert")
async def test_alert():
    """测试预警系统 - 强制发送预警消息到所有客户端"""
    test_alert_data = { # 重命名变量避免覆盖内置函数
        "type": "alert",
        "timestamp": datetime.now().isoformat(), # 使用 ISO 格式
        "content": "测试预警：这是一条测试消息",
        "level": "important",
        "details": "这是一条测试预警，用于确认预警系统功能正常",
        "image_url": "/video_warning/test.jpg" # 确保路径正确
    }
    
    # 创建测试图像 (确保 cv2 和 numpy 已导入)
    # import numpy as np
    # import cv2
    test_img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(test_img, "Test Alert Image", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    # 确保 video_warning 目录存在
    os.makedirs("video_warning", exist_ok=True)
    cv2.imwrite("video_warning/test.jpg", test_img)
    
    # 添加到最近预警
    recent_alerts.append(test_alert_data)
    # deque 会自动处理长度限制
    
    # 发送到所有连接
    disconnected = []
    # 使用 asyncio.gather 来并发发送
    tasks = []
    for connection in active_connections:
         if connection.client_state == WebSocketState.CONNECTED:
             tasks.append(connection.send_json(test_alert_data))
         else:
             disconnected.append(connection)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理发送失败和断开的连接
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logging.error(f"发送测试预警失败: {result}")
            disconnected.append(active_connections[i]) # 假设 tasks 和 active_connections 顺序一致

    # 清理断开的连接
    for conn in set(disconnected): # 使用 set 去重
        if conn in active_connections:
            active_connections.remove(conn)
            logging.info(f"移除了断开的连接: {conn.client}")
    
    return {"status": "success", "message": "测试预警已发送"}

async def alert_handler():
    """处理警报消息"""
    # 用于跟踪已处理的预警
    processed_alerts = set()
    
    while True:
        try:
            # 检查预警队列
            if hasattr(video_processor, 'alert_queue') and not video_processor.alert_queue.empty():
                try:
                    alert = video_processor.alert_queue.get_nowait()
                    
                    # 提取预警的唯一标识
                    alert_key = alert.get("alert_key")
                    if not alert_key:
                        # 如果没有alert_key，根据内容和时间戳生成一个更可靠的后备key
                        timestamp = alert.get("timestamp", "")
                        content = alert.get("content", "")
                        # 移除可能为空的 start/end time，避免它们引起不一致
                        alert_key = f"{content}_{timestamp}"
                    
                    # 检查是否已经处理过这个预警
                    if alert_key in processed_alerts:
                        logging.info(f"预警已处理，跳过: {alert_key}")
                        continue  # 跳过已处理的预警
                    
                    # 标记此预警已处理
                    processed_alerts.add(alert_key)
                    
                    # 限制processed_alerts的大小，避免内存无限增长
                    if len(processed_alerts) > 100:  # 保留最近100个预警记录
                        processed_alerts = set(list(processed_alerts)[-100:])
                    
                    # 检查recent_alerts中是否已存在相同预警，避免重复添加
                    duplicate = False
                    for existing_alert in recent_alerts:
                        existing_key = existing_alert.get("alert_key")
                        if existing_key and existing_key == alert_key:
                            duplicate = True
                            break
                    
                    if not duplicate:
                        # 添加到最近预警 (deque 自动处理)
                        recent_alerts.append(alert)
                    
                    # 实时发送给所有连接
                    disconnected = []
                    tasks = []
                    for connection in active_connections:
                        if connection.client_state == WebSocketState.CONNECTED:
                            tasks.append(connection.send_json(alert))
                        else:
                            disconnected.append(connection)

                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # 处理发送失败和断开的连接
                    for i, result in enumerate(results):
                         if isinstance(result, Exception):
                             logging.error(f"发送警报失败: {result}")
                             # 找到对应的连接并添加到 disconnected 列表
                             # (需要更可靠的方式关联 task 和 connection，或者直接在循环中处理异常)
                             # 简化处理：如果发送失败，则标记为断开
                             conn_to_remove = None
                             task_index = 0
                             for conn_idx, conn in enumerate(active_connections):
                                 if conn.client_state == WebSocketState.CONNECTED:
                                     if task_index == i:
                                         conn_to_remove = conn
                                         break
                                     task_index += 1
                             if conn_to_remove:
                                 disconnected.append(conn_to_remove)

                    
                    # 清理断开的连接
                    for conn in set(disconnected): # 使用 set 去重
                        if conn in active_connections:
                            active_connections.remove(conn)
                            logging.info(f"移除了断开的连接: {conn.client}")

                except queue.Empty:
                    pass # 队列为空，正常情况
                except Exception as e: # 捕获处理单个警报时的其他异常
                    logging.error(f"处理单个警报时出错: {e}")
            
        except Exception as e:
            logging.error(f"Alert handler 主循环错误: {e}")
        finally:
             # 无论如何都短暂休眠，防止空转 CPU 占用过高
             await asyncio.sleep(0.1)



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
    # 确保设置了正确的启动方法 (如果需要)
    # try:
    #     set_start_method("spawn")
    # except RuntimeError:
    #     pass
    print(f"启动视频服务器 http://{ServerConfig.HOST}:{ServerConfig.PORT}")
    uvicorn.run( 
        "video_server:app", # 使用字符串形式以支持热重载
        host=ServerConfig.HOST,
        port=ServerConfig.PORT,
        log_level="info",
        reload=False
        #reload=ServerConfig.RELOAD # 从配置读取是否热重载
    )
