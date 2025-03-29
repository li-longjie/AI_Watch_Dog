"""智能视频监控系统 (2025.02.26版)
核心功能：
1. 实时视频流采集与缓冲 
2. 智能多模态异常检测 
3. 视频分段存储与特征归档 
4. WebSocket实时警报推送 
"""
 
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
from video_processor import VideoProcessor  # 重新导入VideoProcessor
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
        return int(source)
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
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>智能视频监控系统</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #4fd1c5;
            --primary-dark: #38b2ac;
            --secondary: #805ad5;
            --danger: #ff4d4d;
            --warning: #ffcc00;
            --dark-bg: #0a192f;
            --panel-bg: #172a45;
            --panel-border: #2d3748;
            --text-primary: #e6f1ff;
            --text-secondary: #8892b0;
            --transition: all 0.25s cubic-bezier(0.645, 0.045, 0.355, 1);
            --cyber-neon: #4fd1c5;
            --cyber-purple: #805ad5;
            --cyber-blue: #0088ff;
        }
        
        /* 全局背景网格效果 */
        body::before {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                linear-gradient(rgba(10, 25, 47, 0.8), rgba(10, 25, 47, 0.8)),
                repeating-linear-gradient(transparent, transparent 50px, rgba(79, 209, 197, 0.1) 50px, rgba(79, 209, 197, 0.1) 51px),
                repeating-linear-gradient(90deg, transparent, transparent 50px, rgba(79, 209, 197, 0.1) 50px, rgba(79, 209, 197, 0.1) 51px);
            z-index: -1;
            opacity: 0.4;
            pointer-events: none;
        }
        
        /* 赛博动态扫描线 */
        body::after {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, transparent, var(--cyber-neon), transparent);
            box-shadow: 0 0 15px 2px var(--cyber-neon);
            z-index: 999;
            animation: scanline 8s linear infinite;
            opacity: 0.6;
        }
        
        @keyframes scanline {
            0% { top: -10px; }
            100% { top: 100vh; }
        }
        
        /* 边框发光效果 */
        .panel {
            position: relative;
            border: 1px solid rgba(79, 209, 197, 0.3);
            box-shadow: 0 0 20px rgba(79, 209, 197, 0.2);
            overflow: hidden;
        }
        
        .panel::before {
            content: "";
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.2), transparent);
            animation: shine 6s linear infinite;
            pointer-events: none;
        }
        
        @keyframes shine {
            0% { left: -100%; }
            20%, 100% { left: 100%; }
        }
        
        /* 角落装饰 */
        .panel::after {
            content: "";
            position: absolute;
            width: 30px;
            height: 30px;
            border-top: 2px solid var(--cyber-neon);
            border-left: 2px solid var(--cyber-neon);
            top: 10px;
            left: 10px;
            animation: pulse 3s infinite;
        }
        
        .panel-title::after {
            content: "";
            position: absolute;
            width: 30px;
            height: 30px;
            border-bottom: 2px solid var(--cyber-neon);
            border-right: 2px solid var(--cyber-neon);
            bottom: -20px;
            right: 10px;
            animation: pulse 3s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 0.5; }
            50% { opacity: 1; }
        }
        
        /* 动态数据线 */
        .data-flow {
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, 
                transparent 0%, 
                var(--cyber-blue) 20%, 
                var(--cyber-neon) 50%,
                var(--cyber-purple) 80%, 
                transparent 100%);
            animation: dataflow 4s linear infinite;
        }
        
        @keyframes dataflow {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        /* 视频容器科技风格增强 */
        .video-container {
            position: relative;
            border: 1px solid rgba(79, 209, 197, 0.5);
            box-shadow: inset 0 0 30px rgba(79, 209, 197, 0.2);
        }
        
        .video-container::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border: 2px solid transparent;
            background: linear-gradient(45deg, transparent, rgba(79, 209, 197, 0.3)) border-box;
            -webkit-mask: linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: destination-out;
            mask-composite: exclude;
            pointer-events: none;
        }
        
        /* 角落指示器 */
        .video-container::after {
            content: "REC";
            position: absolute;
            top: 15px;
            right: 15px;
            color: var(--danger);
            font-size: 0.7rem;
            font-weight: bold;
            padding: 3px 6px;
            border-radius: 4px;
            background: rgba(0, 0, 0, 0.6);
            animation: blink 2s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        /* 增强按钮效果 */
        .qa-button {
            position: relative;
            overflow: hidden;
            z-index: 1;
        }
        
        .qa-button::before {
            content: "";
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: all 1s;
            z-index: -1;
        }
        
        .qa-button:hover::before {
            left: 100%;
            transition: all 1s;
        }
        
        /* 增强提问输入框 */
        .qa-input {
            border: 1px solid var(--cyber-neon);
            background: rgba(10, 25, 47, 0.7);
            box-shadow: 0 0 10px rgba(79, 209, 197, 0.2);
            transition: all 0.3s;
        }
        
        .qa-input:focus {
            border-color: var(--cyber-blue);
            box-shadow: 0 0 20px rgba(79, 209, 197, 0.4);
        }
        
        /* 动态标题装饰 */
        .panel-title {
            position: relative;
            padding-left: 20px;
        }
        
        .panel-title::before {
            position: absolute;
            left: 0;
            animation: titlePulse 3s infinite;
        }
        
        @keyframes titlePulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.1); opacity: 0.8; }
            100% { transform: scale(1); opacity: 1; }
        }
        
        /* 交互动画增强 */
        .alert:hover, .qa-button:hover, .control-btn:hover {
            transform: translateY(-3px) translateX(3px);
            box-shadow: -3px 3px 10px rgba(79, 209, 197, 0.3);
        }
        
        /* 状态栏改进 */
        .status-bar {
            position: relative;
            background: linear-gradient(90deg, rgba(23, 42, 69, 0.8), rgba(10, 25, 47, 0.8));
            backdrop-filter: blur(10px);
            border-top: 1px solid rgba(79, 209, 197, 0.3);
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 14px;
            color: var(--text-primary);
        }
        
        .status-bar::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 1px;
            background: linear-gradient(90deg, 
                transparent, 
                var(--cyber-neon), 
                transparent);
            opacity: 0.8;
        }
        
        .status-bar-left {
            display: flex;
            align-items: center;
            gap: 15px; /* 增加元素间距 */
        }
        
        .status-bar-right {
            display: flex;
            align-items: center;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            font-weight: 500;
            white-space: nowrap; /* 防止文本换行 */
            min-width: 120px; /* 确保有足够的空间 */
        }
        
        .memory-usage, .network-usage, .current-time {
            white-space: nowrap; /* 防止文本换行 */
            min-width: 90px; /* 确保有足够的空间 */
        }
        
        /* 数据数字闪烁效果 */
        .stat-value {
            font-family: 'Courier New', monospace;
            animation: numberFlicker 5s infinite;
        }
        
        @keyframes numberFlicker {
            0%, 100% { opacity: 1; }
            3% { opacity: 0.8; }
            6% { opacity: 1; }
            9% { opacity: 0.9; }
            12% { opacity: 1; }
            50% { opacity: 1; }
            52% { opacity: 0.9; }
            54% { opacity: 1; }
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0;
            padding: 0;
            background-color: var(--dark-bg);
            color: var(--text-primary);
            line-height: 1.6;
            overflow-x: hidden;
            overflow-y: hidden;
            height: 100vh;
        }
        
        /* 赛博朋克风格标题 - 居中调整 */
        .header {
            overflow: visible;
            padding-top: 15px;
            padding-bottom: 15px;
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .header h1 {
            position: relative;
            font-size: 1.8rem;
            color: #4fd1c5;
            letter-spacing: 3px;
            text-shadow: 0 0 15px rgba(79, 209, 197, 0.7);
            margin: 0;
            padding: 8px 20px;
            text-transform: uppercase;
            z-index: 2;
            text-align: center;
            width: auto;
            display: inline-block;
        }
        
        /* 主标题背景 - 调整为居中 */
        .title-backdrop {
            position: absolute;
            top: -8px;
            left: -15px;
            right: -15px;
            bottom: -8px;
            background-color: rgba(10, 25, 47, 0.8);
            border: 1px solid rgba(79, 209, 197, 0.6);
            transform: skewX(-10deg);
            z-index: -1;
            box-shadow: 0 0 20px rgba(79, 209, 197, 0.2),
                        inset 0 0 15px rgba(79, 209, 197, 0.2);
        }
        
        /* 标题装饰线 */
        .title-line {
            position: absolute;
            height: 2px;
            background-color: #4fd1c5;
            opacity: 0.8;
        }
        
        .title-line-top {
            top: -2px;
            left: 30px;
            right: 50px;
        }
        
        .title-line-bottom {
            bottom: -2px;
            left: 50px;
            right: 30px;
        }
        
        /* 闪烁效果 */
        .title-flicker {
            animation: titleFlicker 6s infinite;
        }
        
        @keyframes titleFlicker {
            0%, 100% { opacity: 1; }
            3% { opacity: 0.4; }
            6% { opacity: 0.8; }
            9% { opacity: 0.6; }
            12% { opacity: 1; }
            60% { opacity: 1; }
            62% { opacity: 0.2; }
            64% { opacity: 1; }
        }
        
        /* 电路板图形装饰 */
        .circuit-decoration {
            position: absolute;
            z-index: -1;
            opacity: 0.6;
        }
        
        .circuit-left {
            left: -70px;
            top: 50%;
            transform: translateY(-50%);
            width: 60px;
            height: 30px;
            border-right: 2px solid #4fd1c5;
            border-top: 2px solid #4fd1c5;
            border-bottom: 2px solid #4fd1c5;
            border-radius: 0 0 0 10px;
        }
        
        .circuit-left::before {
            content: "";
            position: absolute;
            right: 10px;
            top: -8px;
            width: 5px;
            height: 5px;
            border-radius: 50%;
            background-color: #4fd1c5;
            box-shadow: 0 0 8px #4fd1c5;
            animation: circuitPulse 2s infinite alternate;
        }
        
        .circuit-right {
            right: -70px;
            top: 50%;
            transform: translateY(-50%);
            width: 60px;
            height: 30px;
            border-left: 2px solid #4fd1c5;
            border-top: 2px solid #4fd1c5;
            border-bottom: 2px solid #4fd1c5;
            border-radius: 0 0 10px 0;
        }
        
        .circuit-right::before {
            content: "";
            position: absolute;
            left: 10px;
            bottom: -8px;
            width: 5px;
            height: 5px;
            border-radius: 50%;
            background-color: #4fd1c5;
            box-shadow: 0 0 8px #4fd1c5;
            animation: circuitPulse 2s infinite alternate-reverse;
        }
        
        @keyframes circuitPulse {
            0% { opacity: 0.5; transform: scale(0.8); }
            100% { opacity: 1; transform: scale(1.2); }
        }
        
        /* 标题标记 */
        .title-badge {
            position: absolute;
            background-color: rgba(10, 25, 47, 0.9);
            border: 1px solid #4fd1c5;
            color: #4fd1c5;
            font-size: 0.7rem;
            padding: 2px 8px;
            text-transform: uppercase;
        }
        
        .badge-left {
            left: -40px;
            top: 5px;
            transform: skewX(-20deg);
        }
        
        .badge-right {
            right: -40px;
            bottom: 5px;
            transform: skewX(-20deg);
        }
        
        /* 确保箭头正确布局 */
        .header-arrow-left,
        .header-arrow-right {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            color: #4fd1c5;
            font-family: monospace;
            font-size: 1rem;
            z-index: 1;
        }
        
        .header-arrow-left {
            left: 15px;
        }
        
        .header-arrow-right {
            right: 15px;
            transform: translateY(-50%) scaleX(-1);
        }
        
        /* 高级装饰线动画 */
        .header::before,
        .header::after {
            content: "";
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            height: 2px;
            width: 25%;
            background: linear-gradient(90deg, transparent, #4fd1c5, transparent);
            z-index: 1;
            animation: advancedLineFlow 8s infinite cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .header::before {
            left: 0;
        }
        
        .header::after {
            right: 0;
            animation-delay: 4s;
        }
        
        @keyframes advancedLineFlow {
            0% { 
                opacity: 0.3; 
                width: 5%;
                background: linear-gradient(90deg, transparent, #4fd1c5, transparent);
            }
            50% { 
                opacity: 1; 
                width: 25%;
                background: linear-gradient(90deg, transparent, #4fd1c5 50%, #00b3ff 75%, transparent);
            }
            100% { 
                opacity: 0.3; 
                width: 5%;
                background: linear-gradient(90deg, transparent, #4fd1c5, transparent);
            }
        }
        
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: auto auto;
            gap: 1.5rem;
            padding: 1.5rem;
            height: calc(100vh - 72px - 36px);
            overflow: hidden;
        }
        
        /* 增强毛玻璃渐变效果 */
        .panel {
            background-color: rgba(10, 25, 47, 0.4); /* 降低背景不透明度 */
            position: relative;
            border-radius: 8px;
            padding: 15px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            width: 100%;
            max-width: 560px;
            margin: 0 auto;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            backdrop-filter: blur(15px); /* 增加模糊强度 */
            -webkit-backdrop-filter: blur(15px);
            border: 1px solid rgba(79, 209, 197, 0.5); /* 增加边框亮度 */
            z-index: 1;
        }
        
        /* 增强面板渐变背景 - 每个面板使用不同的更亮渐变色 */
        .monitoring-panel {
            background-image: linear-gradient(135deg, 
                rgba(10, 25, 47, 0.3) 0%, /* 减少深蓝色不透明度 */
                rgba(79, 209, 197, 0.3) 100%); /* 增加青色不透明度 */
        }
        
        .alerts-panel {
            background-image: linear-gradient(135deg, 
                rgba(10, 25, 47, 0.3) 0%, 
                rgba(79, 209, 197, 0.35) 100%);
        }
        
        .playback-panel {
            background-image: linear-gradient(135deg, 
                rgba(10, 25, 47, 0.3) 0%, 
                rgba(128, 90, 213, 0.3) 100%);
        }
        
        .qa-panel {
            background-image: linear-gradient(135deg, 
                rgba(10, 25, 47, 0.3) 0%, 
                rgba(128, 90, 213, 0.35) 100%);
        }
        
        /* 添加玻璃反光效果 */
        .panel::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 30px;
            background: linear-gradient(to bottom, 
                rgba(255, 255, 255, 0.15), 
                rgba(255, 255, 255, 0));
            z-index: -1;
            border-radius: 8px 8px 0 0;
        }
        
        /* 增强边框发光效果 */
        .panel::after {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: 8px;
            box-shadow: inset 0 0 2px rgba(79, 209, 197, 0.6);
            pointer-events: none;
            z-index: -1;
        }
        
        /* 确保面板内部元素可见性和对比度 */
        .panel-title {
            color: var(--text-primary);
            font-weight: 600;
            z-index: 2;
            position: relative;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        /* 调整视频容器在毛玻璃背景上的显示 */
        .video-container {
            background-color: rgba(10, 25, 47, 0.3);
            backdrop-filter: blur(4px);
            border: 1px solid rgba(79, 209, 197, 0.2);
        }
        
        .panel:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.25);
        }
        
        .panel:after {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--primary), var(--dark-bg), var(--primary));
            opacity: 0.7;
        }
        
        .video-panel {
            grid-row: 1;
            grid-column: 1;
        }
        
        .warning-panel {
            grid-row: 2;
            grid-column: 1;
        }
        
        .warning-panel .panel-title {
            color: var(--danger);
        }
        
        .warning-panel .panel-title:before {
            background-color: var(--danger);
            box-shadow: 0 0 10px var(--danger);
        }
        
        .warning-panel:after {
            background: linear-gradient(90deg, var(--danger), var(--dark-bg), var(--danger));
        }
        
        .alerts-panel {
            grid-row: 1;
            grid-column: 2;
        }
        
        .qa-panel {
            grid-row: 2;
            grid-column: 2;
        }
        
        /* 调整视频面板宽度 */
        .video-panel {
            display: flex;
            flex-direction: column;
            height: 100%;
            width: 100%;
            max-width: 720px; /* 限制最大宽度 */
            margin: 0 auto; /* 居中显示 */
        }
        
        /* 调整视频容器样式，确保视频完整显示 */
        .video-container {
            position: relative;
            width: 100%;
            height: 400px; /* 使用固定高度替代比例高度 */
            background-color: #0a192f;
            border-radius: 4px;
            margin: 10px auto;
            overflow: hidden;
        }
        
        /* 调整视频元素样式 */
        .video-container video,
        .video-container img,
        .video-container iframe {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: contain; /* 保持原始比例 */
            background-color: #000; /* 视频背景色 */
        }
        
        /* 调整预警回放视频播放器尺寸 */
        .playback-panel .video-container {
            height: 400px; /* 确保与实时监控视频高度一致 */
        }
        
        /* 修复播放器控件样式 */
        .video-container .h5player-controls {
            width: 100%;
            position: absolute;
            bottom: 0;
            left: 0;
            z-index: 10;
        }
        
        /* 确保每个面板内容居中且完整显示 */
        .monitoring-panel, .playback-panel {
            display: flex;
            flex-direction: column;
            padding: 15px;
        }
        
        /* 确保面板标题不占用过多空间 */
        .panel-title {
            margin-bottom: 10px;
            flex-shrink: 0;
        }
        
        #video-feed, #warning-video {
            width: 100%;
            height: 100%;
            object-fit: contain;
            transition: var(--transition);
        }
        
        #video-feed:hover, #warning-video:hover {
            transform: scale(1.02);
        }
        
        .video-timestamp {
            position: absolute;
            bottom: 1rem;
            right: 1rem;
            background-color: rgba(0, 0, 0, 0.7);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-family: 'Roboto Mono', monospace;
            font-size: 0.9rem;
            color: var(--primary);
            backdrop-filter: blur(5px);
        }
        
        .alerts-container {
            overflow-y: auto;
            height: calc(100% - 45px);
            padding-right: 0.5rem;
            scrollbar-width: thin;
            scrollbar-color: var(--primary) var(--panel-bg);
        }
        
        .alerts-container::-webkit-scrollbar {
            width: 6px;
        }
        
        .alerts-container::-webkit-scrollbar-track {
            background: var(--panel-bg);
            border-radius: 3px;
        }
        
        .alerts-container::-webkit-scrollbar-thumb {
            background-color: var(--primary);
            border-radius: 3px;
        }
        
        /* 预警信息样式修改 */
        .alert {
            border-left: 4px solid #4fd1c5;
            background-color: rgba(15, 40, 70, 0.6);
            margin-bottom: 10px;
            padding: 10px;
            border-radius: 4px;
            position: relative;
            overflow: hidden;
            transition: background-color 0.3s;
        }
        
        .alert.important {
            border-left-color: #48bb78; /* 绿色边框 */
            background-color: rgba(15, 70, 40, 0.2); /* 绿色背景 */
        }

        /* 修改悬停效果，防止变成红色 */
        .alert:hover {
            background-color: rgba(15, 40, 70, 0.8); /* 稍微深一点的背景，但不是红色 */
            border-left-color: #4fd1c5; /* 保持原来的边框颜色 */
        }
        
        .alert.important:hover {
            background-color: rgba(15, 70, 40, 0.3); /* 稍微深一点的绿色背景 */
            border-left-color: #48bb78; /* 保持绿色边框 */
        }

        /* 确保即使父元素有其他悬停样式也不会覆盖 */
        .alerts-panel .alert:hover {
            border-left-color: #48bb78 !important; /* 强制保持绿色边框 */
            background-color: rgba(15, 70, 40, 0.3) !important; /* 强制保持绿色背景 */
        }
        
        .alert-time {
            color: var(--text-secondary);
            font-size: 0.8rem;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .alert-content {
            margin-top: 0.5rem;
            color: var(--text-primary);
            font-weight: 500;
        }
        
        .alert-details {
            margin-top: 0.5rem;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }
        
        .alert-icon {
            font-size: 1.2em;
        }
        
        .qa-input {
            width: 100%;
            padding: 1rem;
            margin-bottom: 1rem;
            border: 1px solid var(--primary);
            border-radius: 8px;
            background-color: rgba(10, 25, 47, 0.5);
            color: var(--text-primary);
            font-family: inherit;
            font-size: 1rem;
            transition: var(--transition);
            backdrop-filter: blur(5px);
        }
        
        .qa-input:focus {
            outline: none;
            border-color: var(--primary-dark);
            box-shadow: 0 0 0 3px rgba(79, 209, 197, 0.3);
        }
        
        .qa-input::placeholder {
            color: var(--text-secondary);
            opacity: 0.7;
        }
        
        .qa-button {
            padding: 0.75rem 1.5rem;
            background-color: var(--primary);
            color: var(--dark-bg);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-family: inherit;
            font-size: 1rem;
            transition: var(--transition);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }
        
        .qa-button:hover {
            background-color: var(--primary-dark);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(79, 209, 197, 0.3);
        }
        
        .qa-history {
            overflow-y: auto;
            height: calc(100% - 90px);
            margin-top: 1rem;
            padding-right: 0.5rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        
        .question {
            background-color: rgba(79, 209, 197, 0.1);
            padding: 1rem;
            border-radius: 8px;
            border-left: 3px solid var(--primary);
            position: relative;
        }
        
        .question:before {
            content: "Q";
            position: absolute;
            top: -10px;
            left: -10px;
            width: 20px;
            height: 20px;
            background-color: var(--primary);
            color: var(--dark-bg);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: bold;
        }
        
        .answer {
            background-color: rgba(255, 255, 255, 0.05);
            padding: 1rem;
            border-radius: 8px;
            border-left: 3px solid var(--secondary);
            position: relative;
        }
        
        .answer:before {
            content: "A";
            position: absolute;
            top: -10px;
            left: -10px;
            width: 20px;
            height: 20px;
            background-color: var(--secondary);
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: bold;
        }
        
        .no-data {
            color: var(--text-secondary);
            text-align: center;
            margin-top: 2rem;
            font-size: 0.9rem;
            opacity: 0.7;
        }
        
        .pulse {
            animation: pulse-animation 2s infinite;
        }
        
        @keyframes pulse-animation {
            0% { box-shadow: 0 0 0 0 rgba(79, 209, 197, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(79, 209, 197, 0); }
            100% { box-shadow: 0 0 0 0 rgba(79, 209, 197, 0); }
        }
        
        .status-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            display: flex;
            justify-content: space-between;
            padding: 0.75rem 2rem;
            background-color: var(--panel-bg);
            border-top: 1px solid rgba(79, 209, 197, 0.2);
            font-size: 0.85rem;
            z-index: 10;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .status-indicator:before {
            content: "";
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--primary);
            margin-right: 0;
            animation: pulse-animation 2s infinite;
        }
        
        .system-stats {
            display: flex;
            gap: 1.5rem;
        }
        
        .stat-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        .stat-value {
            color: var(--text-primary);
            font-weight: 500;
        }
        
        @media (max-width: 1024px) {
            .container {
                grid-template-columns: 1fr;
                grid-template-rows: repeat(4, auto);
                height: auto;
                min-height: 100vh;
                padding-bottom: 4rem;
            }
            
            .video-panel, .warning-panel, .alerts-panel, .qa-panel {
                grid-column: 1;
            }
            
            .video-panel { grid-row: 1; }
            .warning-panel { grid-row: 2; }
            .alerts-panel { grid-row: 3; }
            .qa-panel { grid-row: 4; }
            
            .video-container {
                height: 400px;
            }
            
            .header h1 {
                font-size: 1.3rem;
            }
        }
        
        /* 加载动画 */
        .loader {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(79, 209, 197, 0.3);
            border-radius: 50%;
            border-top-color: var(--primary);
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* 通知徽章 */
        .badge {
            position: absolute;
            top: -5px;
            right: -5px;
            background-color: var(--danger);
            color: white;
            border-radius: 50%;
            width: 18px;
            height: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: bold;
            animation: pulse-animation 2s infinite;
        }
        
        /* 工具提示 */
        .tooltip {
            position: relative;
        }
        
        .tooltip:after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background-color: var(--panel-bg);
            color: var(--text-primary);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-size: 0.8rem;
            white-space: nowrap;
            opacity: 0;
            visibility: hidden;
            transition: var(--transition);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
            border: 1px solid var(--panel-border);
            z-index: 100;
        }
        
        .tooltip:hover:after {
            opacity: 1;
            visibility: visible;
            bottom: calc(100% + 10px);
        }
        
        /* 标题两侧装饰元素 */
        .header {
            position: relative;
        }
        
        /* 添加动态数据线装饰 */
        .header-decorations {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            overflow: hidden;
        }
        
        /* 左侧装饰元素 */
        .header-left-decor {
            position: absolute;
            top: 50%;
            left: 80px;
            transform: translateY(-50%);
            display: flex;
            gap: 3px;
            align-items: center;
        }
        
        .data-cube {
            width: 5px;
            height: 10px;
            background: rgba(79, 209, 197, 0.7);
            animation: dataCubeAnim 2s infinite ease-in-out;
        }
        
        .data-cube:nth-child(2) {
            animation-delay: 0.3s;
            height: 14px;
        }
        
        .data-cube:nth-child(3) {
            animation-delay: 0.6s;
            height: 8px;
        }
        
        .data-cube:nth-child(4) {
            animation-delay: 0.9s;
            height: 16px;
        }
        
        @keyframes dataCubeAnim {
            0%, 100% { opacity: 0.4; transform: scaleY(0.8); }
            50% { opacity: 1; transform: scaleY(1.2); }
        }
        
        /* 右侧装饰元素 */
        .header-right-decor {
            position: absolute;
            top: 50%;
            right: 80px;
            transform: translateY(-50%);
        }
        
        .radar-circle {
            position: relative;
            width: 30px;
            height: 30px;
            border: 1px solid rgba(79, 209, 197, 0.6);
            border-radius: 50%;
        }
        
        .radar-circle::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(79, 209, 197, 0.5) 0%, transparent 70%);
            opacity: 0;
            animation: radarPulse 3s infinite;
        }
        
        .radar-circle::after {
            content: "";
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            background: rgba(79, 209, 197, 0.8);
            box-shadow: 0 0 10px rgba(79, 209, 197, 0.8);
            border-radius: 50%;
            transform: translate(-50%, -50%);
            animation: radarDot 3s infinite;
        }
        
        @keyframes radarPulse {
            0%, 100% { opacity: 0; transform: scale(0.3); }
            50% { opacity: 0.5; transform: scale(1.2); }
        }
        
        @keyframes radarDot {
            0%, 100% { width: 2px; height: 2px; }
            50% { width: 4px; height: 4px; }
        }
        
        /* 扫描线动画 */
        .scan-line {
            position: absolute;
            left: 120px;
            right: 120px;
            top: 10px;
            height: 1px;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(79, 209, 197, 0.8), 
                transparent);
            animation: scanLineMove 4s infinite ease-in-out;
        }
        
        .scan-line:nth-child(2) {
            top: auto;
            bottom: 10px;
            animation-delay: 2s;
        }
        
        @keyframes scanLineMove {
            0%, 100% { opacity: 0; }
            50% { opacity: 1; }
        }
        
        /* 浮动数据点装饰 */
        .data-point {
            position: absolute;
            width: 4px;
            height: 4px;
            background: #4fd1c5;
            border-radius: 50%;
            box-shadow: 0 0 5px rgba(79, 209, 197, 0.8);
            animation: dataPointFloat 6s infinite ease-in-out;
        }
        
        .data-point:nth-child(1) {
            top: 15px;
            left: 130px;
        }
        
        .data-point:nth-child(2) {
            bottom: 15px;
            left: 160px;
            animation-delay: 1s;
        }
        
        .data-point:nth-child(3) {
            top: 20px;
            right: 150px;
            animation-delay: 2s;
        }
        
        .data-point:nth-child(4) {
            bottom: 10px;
            right: 130px;
            animation-delay: 3s;
        }
        
        @keyframes dataPointFloat {
            0%, 100% { transform: translate(0, 0); }
            25% { transform: translate(5px, -5px); }
            50% { transform: translate(10px, 0); }
            75% { transform: translate(5px, 5px); }
        }
        
        /* 额外的标题装饰元素 */
        
        /* 数字计数器 */
        .digital-counter {
            position: absolute;
            left: 150px;
            top: 15px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            color: #4fd1c5;
            text-shadow: 0 0 5px rgba(79, 209, 197, 0.5);
        }
        
        .counter-value {
            animation: counterChange 10s infinite steps(10);
        }
        
        @keyframes counterChange {
            0% { content: "0127"; }
            10% { content: "0394"; }
            20% { content: "0582"; }
            30% { content: "0671"; }
            40% { content: "0744"; }
            50% { content: "0892"; }
            60% { content: "0923"; }
            70% { content: "0157"; }
            80% { content: "0238"; }
            90% { content: "0347"; }
            100% { content: "0127"; }
        }
        
        /* 脉冲波形图 */
        .waveform {
            position: absolute;
            right: 150px;
            top: 15px;
            display: flex;
            gap: 2px;
            align-items: center;
        }
        
        .wave-line {
            width: 2px;
            height: 10px;
            background: rgba(79, 209, 197, 0.6);
            border-radius: 1px;
            transform-origin: bottom;
        }
        
        .wave-line:nth-child(1) { animation: wavePulse 1.0s infinite ease-in-out; }
        .wave-line:nth-child(2) { animation: wavePulse 1.0s infinite ease-in-out 0.1s; }
        .wave-line:nth-child(3) { animation: wavePulse 1.0s infinite ease-in-out 0.2s; }
        .wave-line:nth-child(4) { animation: wavePulse 1.0s infinite ease-in-out 0.3s; }
        .wave-line:nth-child(5) { animation: wavePulse 1.0s infinite ease-in-out 0.4s; }
        .wave-line:nth-child(6) { animation: wavePulse 1.0s infinite ease-in-out 0.5s; }
        .wave-line:nth-child(7) { animation: wavePulse 1.0s infinite ease-in-out 0.6s; }
        
        @keyframes wavePulse {
            0%, 100% { transform: scaleY(0.3); }
            50% { transform: scaleY(2); }
        }
        
        /* 科技框架 */
        .tech-frame {
            position: absolute;
            left: 120px;
            bottom: 12px;
            width: 50px;
            height: 15px;
            border: 1px solid rgba(79, 209, 197, 0.5);
            box-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
        }
        
        .tech-frame::before,
        .tech-frame::after {
            content: "";
            position: absolute;
            background: rgba(79, 209, 197, 0.8);
        }
        
        .tech-frame::before {
            top: 50%;
            left: -5px;
            width: 5px;
            height: 1px;
        }
        
        .tech-frame::after {
            top: -5px;
            left: 50%;
            width: 1px;
            height: 5px;
        }
        
        /* 旋转标记 */
        .rotating-mark {
            position: absolute;
            right: 130px;
            bottom: 15px;
            width: 20px;
            height: 20px;
            border: 1px dashed rgba(79, 209, 197, 0.5);
            border-radius: 50%;
            animation: rotateMark 10s infinite linear;
        }
        
        .rotating-mark::before {
            content: "+";
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: rgba(79, 209, 197, 0.8);
            font-size: 10px;
        }
        
        @keyframes rotateMark {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* 数据流动画 */
        .data-stream {
            position: absolute;
            left: 40px;
            top: 50%;
            width: 30px;
            height: 1px;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(79, 209, 197, 1), 
                transparent);
            transform: translateY(-50%);
            animation: dataStreamFlow 2s infinite;
        }
        
        .data-stream:nth-child(2) {
            right: 40px;
            left: auto;
            animation-delay: 1s;
            animation-direction: reverse;
        }
        
        @keyframes dataStreamFlow {
            0% { transform: translateY(-50%) translateX(-100%); opacity: 0; }
            50% { opacity: 1; }
            100% { transform: translateY(-50%) translateX(100%); opacity: 0; }
        }
        
        /* 标题文本周围装饰 */
        .header h1 {
            position: relative;
            padding: 0 20px;
            margin: 0 auto;
            display: inline-block;
        }
        
        /* 标题文本框架 */
        .title-frame {
            position: absolute;
            top: -8px;
            left: -20px;
            right: -20px;
            bottom: -8px;
            border: 1px solid rgba(79, 209, 197, 0.3);
            pointer-events: none;
            z-index: -1;
        }
        
        /* 添加角标装饰 */
        .title-frame::before,
        .title-frame::after {
            content: "";
            position: absolute;
            width: 10px;
            height: 10px;
            border-color: rgba(79, 209, 197, 0.7);
            border-style: solid;
        }
        
        .title-frame::before {
            top: -5px;
            left: -5px;
            border-width: 2px 0 0 2px;
        }
        
        .title-frame::after {
            top: -5px;
            right: -5px;
            border-width: 2px 2px 0 0;
        }
        
        .title-frame-bottom::before,
        .title-frame-bottom::after {
            content: "";
            position: absolute;
            width: 10px;
            height: 10px;
            border-color: rgba(79, 209, 197, 0.7);
            border-style: solid;
        }
        
        .title-frame-bottom::before {
            bottom: -5px;
            left: -5px;
            border-width: 0 0 2px 2px;
        }
        
        .title-frame-bottom::after {
            bottom: -5px;
            right: -5px;
            border-width: 0 2px 2px 0;
        }
        
        /* 标题两侧的装饰线 */
        .title-side-line {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            width: 40px;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.8));
        }
        
        .title-side-line.left {
            right: calc(100% + 10px);
        }
        
        .title-side-line.right {
            left: calc(100% + 10px);
            transform: translateY(-50%) scaleX(-1);
        }
        
        /* 标题周围的点状装饰 */
        .title-decoration-dot {
            position: absolute;
            width: 4px;
            height: 4px;
            background: rgba(79, 209, 197, 0.8);
            border-radius: 50%;
            box-shadow: 0 0 5px rgba(79, 209, 197, 0.5);
        }
        
        .title-decoration-dot:nth-child(1) {
            top: -12px;
            left: 10%;
        }
        
        .title-decoration-dot:nth-child(2) {
            top: -10px;
            left: 30%;
        }
        
        .title-decoration-dot:nth-child(3) {
            top: -12px;
            left: 70%;
        }
        
        .title-decoration-dot:nth-child(4) {
            top: -10px;
            left: 90%;
        }
        
        .title-decoration-dot:nth-child(5) {
            bottom: -12px;
            left: 20%;
        }
        
        .title-decoration-dot:nth-child(6) {
            bottom: -10px;
            left: 40%;
        }
        
        .title-decoration-dot:nth-child(7) {
            bottom: -12px;
            left: 60%;
        }
        
        .title-decoration-dot:nth-child(8) {
            bottom: -10px;
            left: 80%;
        }
        
        /* 标题背景特效 */
        .title-bg {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(circle, rgba(79, 209, 197, 0.1) 0%, transparent 70%);
            filter: blur(5px);
            z-index: -2;
            opacity: 0.5;
            animation: titleBgPulse 4s infinite ease-in-out;
        }
        
        @keyframes titleBgPulse {
            0%, 100% { opacity: 0.3; transform: scale(0.95); }
            50% { opacity: 0.7; transform: scale(1.05); }
        }
        
        /* 背景网格特效 */
        .title-grid {
            position: absolute;
            top: -50%;
            left: -50%;
            right: -50%;
            bottom: -50%;
            background-image: 
                linear-gradient(rgba(79, 209, 197, 0.1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(79, 209, 197, 0.1) 1px, transparent 1px);
            background-size: 10px 10px;
            z-index: -3;
            opacity: 0.2;
            transform: perspective(500px) rotateX(30deg);
            animation: gridMove 20s infinite linear;
        }
        
        @keyframes gridMove {
            0% { background-position: 0 0; }
            100% { background-position: 10px 10px; }
        }
        
        /* 更简洁的标题装饰 */
        .header h1 {
            position: relative;
            padding: 0 25px;
            margin: 0 auto;
            display: inline-block;
        }
        
        /* 标题简洁边框 */
        .title-border {
            position: absolute;
            top: -5px;
            left: -15px;
            right: -15px;
            bottom: -5px;
            border: none;
            pointer-events: none;
            z-index: -1;
            overflow: hidden;
        }
        
        /* 角落标记 */
        .corner-mark {
            position: absolute;
            width: 15px;
            height: 15px;
        }
        
        .corner-mark-tl {
            top: 0;
            left: 0;
            border-top: 2px solid rgba(79, 209, 197, 0.8);
            border-left: 2px solid rgba(79, 209, 197, 0.8);
        }
        
        .corner-mark-tr {
            top: 0;
            right: 0;
            border-top: 2px solid rgba(79, 209, 197, 0.8);
            border-right: 2px solid rgba(79, 209, 197, 0.8);
        }
        
        .corner-mark-bl {
            bottom: 0;
            left: 0;
            border-bottom: 2px solid rgba(79, 209, 197, 0.8);
            border-left: 2px solid rgba(79, 209, 197, 0.8);
        }
        
        .corner-mark-br {
            bottom: 0;
            right: 0;
            border-bottom: 2px solid rgba(79, 209, 197, 0.8);
            border-right: 2px solid rgba(79, 209, 197, 0.8);
        }
        
        /* 简单的辉光背景 */
        .title-glow {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(ellipse at center, 
                rgba(79, 209, 197, 0.15) 0%, 
                transparent 70%);
            filter: blur(8px);
            z-index: -2;
            opacity: 0.7;
            animation: simplePulse 4s infinite ease-in-out;
        }
        
        @keyframes simplePulse {
            0%, 100% { opacity: 0.5; transform: scale(0.98); }
            50% { opacity: 0.8; transform: scale(1.02); }
        }
        
        /* 简洁侧边装饰 */
        .side-indicator {
            position: absolute;
            top: 50%;
            height: 2px;
            width: 20px;
            background-color: rgba(79, 209, 197, 0.8);
            transform: translateY(-50%);
        }
        
        .side-indicator-left {
            left: -30px;
        }
        
        .side-indicator-right {
            right: -30px;
        }
        
        /* 侧标记动画 */
        .side-indicator::before {
            content: "";
            position: absolute;
            top: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(79, 209, 197, 1), 
                transparent);
            animation: sideIndicatorPulse 2s infinite;
        }
        
        @keyframes sideIndicatorPulse {
            0%, 100% { opacity: 0; transform: translateX(-100%); }
            50% { opacity: 1; transform: translateX(100%); }
        }
        
        /* 前卫科技风格标题 */
        .header h1 {
            position: relative;
            margin: 0 auto;
            font-size: 1.8rem;
            font-weight: 600;
            color: #4fd1c5;
            text-transform: uppercase;
            text-shadow: 0 0 10px rgba(79, 209, 197, 0.6);
            padding: 10px 30px;
            letter-spacing: 1px;
        }
        
        /* 双层标题框架 */
        .title-container {
            position: absolute;
            top: -5px;
            left: -10px;
            right: -10px;
            bottom: -5px;
            border: 1px solid rgba(79, 209, 197, 0.7);
            box-shadow: 0 0 10px rgba(79, 209, 197, 0.3);
            z-index: -1;
            overflow: hidden;
        }
        
        .title-container::after {
            content: "";
            position: absolute;
            top: 3px;
            left: 3px;
            right: 3px;
            bottom: 3px;
            border: 1px dashed rgba(79, 209, 197, 0.5);
        }
        
        /* 标题装饰标记 */
        .tech-marker {
            position: absolute;
            color: rgba(79, 209, 197, 0.8);
            font-family: monospace;
            font-size: 11px;
            font-weight: bold;
            text-shadow: 0 0 5px rgba(79, 209, 197, 0.5);
        }
        
        .tech-marker.top-left {
            top: -3px;
            left: 10px;
        }
        
        .tech-marker.top-right {
            top: -3px;
            right: 10px;
        }
        
        .tech-marker.bottom-left {
            bottom: -3px;
            left: 10px;
        }
        
        .tech-marker.bottom-right {
            bottom: -3px;
            right: 10px;
        }
        
        /* 标题扫描线 */
        .scan-beam {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            overflow: hidden;
            z-index: -1;
        }
        
        .scan-beam::before {
            content: "";
            position: absolute;
            top: 0;
            left: -100%;
            width: 300%;
            height: 100%;
            background: linear-gradient(90deg,
                transparent 0%,
                rgba(79, 209, 197, 0.1) 45%,
                rgba(79, 209, 197, 0.4) 50%,
                rgba(79, 209, 197, 0.1) 55%,
                transparent 100%);
            animation: scanMove 5s infinite;
        }
        
        @keyframes scanMove {
            0% { transform: translateX(0); }
            100% { transform: translateX(33.33%); }
        }
        
        /* 标题背景 */
        .title-bg-grid {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(rgba(79, 209, 197, 0.1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(79, 209, 197, 0.1) 1px, transparent 1px);
            background-size: 20px 10px;
            opacity: 0.3;
            z-index: -2;
            perspective: 500px;
            transform-style: preserve-3d;
            transform: perspective(200px) rotateX(40deg) scale(1.5);
            transform-origin: center bottom;
            animation: gridPulse 8s infinite ease-in-out;
        }
        
        @keyframes gridPulse {
            0%, 100% { opacity: 0.2; }
            50% { opacity: 0.4; }
        }
        
        /* 标题边角特效 */
        .corner-accent {
            position: absolute;
            width: 20px;
            height: 20px;
        }
        
        .corner-tl {
            top: -3px;
            left: -3px;
            border-top: 2px solid #4fd1c5;
            border-left: 2px solid #4fd1c5;
            box-shadow: -1px -1px 10px rgba(79, 209, 197, 0.6);
        }
        
        .corner-tr {
            top: -3px;
            right: -3px;
            border-top: 2px solid #4fd1c5;
            border-right: 2px solid #4fd1c5;
            box-shadow: 1px -1px 10px rgba(79, 209, 197, 0.6);
        }
        
        .corner-bl {
            bottom: -3px;
            left: -3px;
            border-bottom: 2px solid #4fd1c5;
            border-left: 2px solid #4fd1c5;
            box-shadow: -1px 1px 10px rgba(79, 209, 197, 0.6);
        }
        
        .corner-br {
            bottom: -3px;
            right: -3px;
            border-bottom: 2px solid #4fd1c5;
            border-right: 2px solid #4fd1c5;
            box-shadow: 1px 1px 10px rgba(79, 209, 197, 0.6);
        }
        
        /* 添加更多标题两侧装饰，填充空白区域 */
        .header-bg-extensions {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
            z-index: 0;
        }
        
        /* 左侧科技面板 */
        .tech-panel-left {
            position: absolute;
            left: 70px;
            top: 50%;
            transform: translateY(-50%);
            width: 150px;
            height: 60%;
            border-top: 1px solid rgba(79, 209, 197, 0.7);
            border-bottom: 1px solid rgba(79, 209, 197, 0.7);
            border-left: 1px solid rgba(79, 209, 197, 0.7);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 5px;
        }
        
        /* 右侧科技面板 */
        .tech-panel-right {
            position: absolute;
            right: 70px;
            top: 50%;
            transform: translateY(-50%);
            width: 150px;
            height: 60%;
            border-top: 1px solid rgba(79, 209, 197, 0.7);
            border-bottom: 1px solid rgba(79, 209, 197, 0.7);
            border-right: 1px solid rgba(79, 209, 197, 0.7);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: flex-end;
            padding: 5px;
        }
        
        /* 数据监控线 */
        .monitor-line {
            height: 2px;
            background: rgba(79, 209, 197, 0.5);
            position: relative;
            margin: 4px 0;
        }
        
        .monitor-line::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            width: 30%;
            background: rgba(79, 209, 197, 0.9);
            animation: monitorPulse 3s infinite ease-in-out;
        }
        
        .monitor-line:nth-child(2)::before {
            animation-delay: 0.5s;
            width: 60%;
        }
        
        .monitor-line:nth-child(3)::before {
            animation-delay: 1s;
            width: 40%;
        }
        
        .tech-panel-right .monitor-line::before {
            left: auto;
            right: 0;
        }
        
        @keyframes monitorPulse {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 1; }
        }
        
        /* 装饰点 */
        .tech-dot {
            position: absolute;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #4fd1c5;
            box-shadow: 0 0 8px rgba(79, 209, 197, 0.8);
        }
        
        .dot-1 { left: 220px; top: 20%; }
        .dot-2 { left: 180px; top: 80%; }
        .dot-3 { right: 220px; top: 20%; }
        .dot-4 { right: 180px; top: 80%; }
        
        /* 状态指示器 */
        .status-indicator {
            position: absolute;
            color: rgba(79, 209, 197, 0.9);
            font-family: 'Courier New', monospace;
            font-size: 12px;
            text-transform: uppercase;
        }
        
        .status-left {
            left: 250px;
            top: 25%;
        }
        
        .status-right {
            right: 250px;
            top: 25%;
        }
        
        /* 扫描线 */
        .horizontal-scan {
            position: absolute;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, 
                transparent 0%,
                rgba(79, 209, 197, 0.5) 30%,
                rgba(79, 209, 197, 0.8) 50%,
                rgba(79, 209, 197, 0.5) 70%,
                transparent 100%);
            opacity: 0;
            animation: horizontalScan 5s infinite ease-in-out;
        }
        
        .scan-top {
            top: 5px;
        }
        
        .scan-bottom {
            bottom: 5px;
            animation-delay: 2.5s;
        }
        
        @keyframes horizontalScan {
            0%, 100% { opacity: 0; }
            50% { opacity: 0.7; }
        }
        
        /* 网格背景扩展 */
        .background-grid {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(rgba(79, 209, 197, 0.1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(79, 209, 197, 0.1) 1px, transparent 1px);
            background-size: 20px 20px;
            opacity: 0.2;
            z-index: -1;
        }
        
        /* 预警信息样式 */
        .alert-item {
            border-left: 4px solid #4fd1c5;
            background-color: rgba(15, 40, 70, 0.6);
            margin-bottom: 10px;
            padding: 10px;
            border-radius: 4px;
            font-size: 0.9rem;
            position: relative;
            overflow: hidden;
        }
        
        .alert-item.important {
            border-left-color: #48bb78; /* 改为绿色边框 */
            background-color: rgba(15, 70, 40, 0.2); /* 从红色背景改为绿色背景 */
        }
        
        /* 调整面板布局和宽度 */
        .main-panel {
            display: grid;
            grid-template-columns: minmax(auto, 560px) 1fr; /* 左侧面板最大宽度减小到560px */
            grid-template-rows: repeat(2, 1fr);
            gap: 15px;
            height: calc(100vh - 120px);
            margin-top: 15px;
            padding: 0 15px;
        }
        
        /* 左侧面板特定样式 - 进一步减小宽度 */
        .monitoring-panel, .playback-panel {
            max-width: 560px; /* 减小最大宽度 */
            width: 100%;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            padding: 15px;
        }
        
        /* 视频容器宽度缩小，消除黑边 */
        .video-container {
            position: relative;
            width: 90%; /* 缩小视频容器宽度 */
            height: 380px; /* 稍微减小高度 */
            background-color: #0a192f;
            border-radius: 4px;
            margin: 10px auto;
            overflow: hidden;
        }
        
        /* 优化视频显示，消除黑边 */
        .video-container video,
        .video-container img,
        .video-container iframe {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover; /* 改为cover以填充容器 */
            background-color: transparent; /* 移除背景色 */
        }
        
        /* 确保预警面板宽度不过大 */
        .alerts-panel {
            max-width: none; /* 移除之前可能设置的最大宽度 */
        }
        
        /* 确保问答面板宽度不过大 */
        .qa-panel {
            max-width: none; /* 移除之前可能设置的最大宽度 */
        }
        
        /* 优化左侧面板毛玻璃效果 */
        .monitoring-panel, .playback-panel {
            background-color: rgba(10, 25, 47, 0.25); /* 更低的背景不透明度 */
            backdrop-filter: blur(20px); /* 增强模糊效果 */
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(79, 209, 197, 0.6); /* 更明显的边框 */
            max-width: 560px;
            width: 100%;
        }
        
        /* 优化左侧面板渐变 */
        .monitoring-panel {
            background-image: linear-gradient(135deg, 
                rgba(10, 25, 47, 0.2) 0%, 
                rgba(79, 209, 197, 0.25) 100%);
        }
        
        .playback-panel {
            background-image: linear-gradient(135deg, 
                rgba(10, 25, 47, 0.2) 0%, 
                rgba(79, 209, 197, 0.25) 100%);
        }
        
        /* 调整视频容器宽度 */
        .monitoring-panel .video-container,
        .playback-panel .video-container {
            width: 95%; /* 增加宽度占比 */
            margin: 10px auto;
        }
        
        /* 增加反光效果 */
        .monitoring-panel::before, 
        .playback-panel::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 40px;
            background: linear-gradient(to bottom, 
                rgba(255, 255, 255, 0.2), 
                rgba(255, 255, 255, 0));
            z-index: -1;
            border-radius: 8px 8px 0 0;
        }
        
        /* 右下角行为分析按钮 */
        .behavior-analysis-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 120px;
            height: 45px;
            background: linear-gradient(135deg, #4fd1c5 0%, #3182ce 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            z-index: 1000;
            text-decoration: none;
            backdrop-filter: blur(5px);
        }
        
        .behavior-analysis-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 15px rgba(0, 0, 0, 0.4);
            background: linear-gradient(135deg, #3182ce 0%, #4fd1c5 100%);
        }
        
        .behavior-analysis-btn:active {
            transform: translateY(1px);
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }
        
        /* 为按钮添加科技感装饰 */
        .behavior-analysis-btn::before {
            content: "";
            position: absolute;
            top: -3px;
            left: -3px;
            right: -3px;
            bottom: -3px;
            border: 1px solid rgba(79, 209, 197, 0.5);
            border-radius: 10px;
            pointer-events: none;
            animation: buttonPulse 2s infinite;
        }
        
        @keyframes buttonPulse {
            0% { opacity: 0.6; }
            50% { opacity: 1; }
            100% { opacity: 0.6; }
        }
        
        /* 状态栏按钮样式 */
        .status-bar-btn {
            background: linear-gradient(135deg, #4fd1c5 0%, #3182ce 100%);
            color: white;
            border: none;
            border-radius: 8px; /* 改为矩形圆角 */
            padding: 8px 15px;
            margin-left: 20px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            text-decoration: none;
            height: 34px;
            width: 120px; /* 固定宽度 */
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
        }
        
        .status-bar-btn:hover {
            background: linear-gradient(135deg, #3182ce 0%, #4fd1c5 100%);
            transform: translateY(-2px);
            box-shadow: 0 6px 15px rgba(0, 0, 0, 0.4);
        }
        
        .status-bar-btn:active {
            transform: translateY(1px);
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }
        
        /* 为按钮添加原来的科技感装饰 */
        .status-bar-btn::before {
            content: "";
            position: absolute;
            top: -3px;
            left: -3px;
            right: -3px;
            bottom: -3px;
            border: 1px solid rgba(79, 209, 197, 0.5);
            border-radius: 10px;
            pointer-events: none;
            animation: buttonPulse 2s infinite;
        }
        
        /* 状态栏容器 */
        .status-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: rgba(10, 25, 47, 0.7);
            backdrop-filter: blur(10px);
            border-top: 1px solid rgba(79, 209, 197, 0.3);
            padding: 8px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            z-index: 1000;
        }
        
        .status-bar-left {
            display: flex;
            align-items: center;
        }
        
        .status-bar-right {
            display: flex;
            align-items: center;
        }
        
        /* 图表容器样式调整 */
        .chart-container {
            width: 100%;
            height: 300px; /* 增加高度从220px到300px */
            position: relative;
            margin-bottom: 10px;
        }
        
        /* 确保图表正确渲染的辅助样式 */
        canvas {
            width: 100% !important;
            height: 100% !important;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="circuit-bg"></div>
        <div class="header-decorations">
            <div class="scan-line"></div>
            <div class="scan-line"></div>
            <div class="data-point"></div>
            <div class="data-point"></div>
            <div class="data-point"></div>
            <div class="data-point"></div>
            <div class="header-left-decor">
                <div class="data-cube"></div>
                <div class="data-cube"></div>
                <div class="data-cube"></div>
                <div class="data-cube"></div>
            </div>
            <div class="header-right-decor">
                <div class="radar-circle"></div>
            </div>
            
            <!-- 新添加的元素 -->
            <div class="digital-counter">ID:<span class="counter-value" data-value="0127"></span></div>
            <div class="waveform">
                <div class="wave-line"></div>
                <div class="wave-line"></div>
                <div class="wave-line"></div>
                <div class="wave-line"></div>
                <div class="wave-line"></div>
                <div class="wave-line"></div>
                <div class="wave-line"></div>
            </div>
            <div class="tech-frame"></div>
            <div class="rotating-mark"></div>
            <div class="data-stream"></div>
            <div class="data-stream"></div>
        </div>
        
        <!-- 新增两侧装饰元素 -->
        <div class="header-bg-extensions">
            <div class="background-grid"></div>
            
            <div class="tech-panel-left">
                <div class="monitor-line"></div>
                <div class="monitor-line"></div>
                <div class="monitor-line"></div>
            </div>
            
            <div class="tech-panel-right">
                <div class="monitor-line"></div>
                <div class="monitor-line"></div>
                <div class="monitor-line"></div>
            </div>
            
            <div class="tech-dot dot-1"></div>
            <div class="tech-dot dot-2"></div>
            <div class="tech-dot dot-3"></div>
            <div class="tech-dot dot-4"></div>
            
            <div class="status-indicator status-left">系统在线</div>
            <div class="status-indicator status-right">安全监控</div>
            
            <div class="horizontal-scan scan-top"></div>
            <div class="horizontal-scan scan-bottom"></div>
        </div>
        
        <div class="header-arrow-left">&gt; &gt; &gt; &gt;</div>
        <h1>
            <div class="title-backdrop">
                <div class="title-line title-line-top"></div>
                <div class="title-line title-line-bottom"></div>
            </div>
            <span class="title-flicker">行为监测</span>与可视化系统
            <div class="circuit-decoration circuit-left"></div>
            <div class="circuit-decoration circuit-right"></div>
            <div class="title-badge badge-left">v2.1</div>
            <div class="title-badge badge-right">secure</div>
        </h1>
        <div class="header-arrow-right">&gt; &gt; &gt; &gt;</div>
    </div>
    
    <div class="container">
        <div class="panel video-panel">
            <div class="panel-title">实时监控</div>
            <div class="video-container">
                <img id="video-feed" src="" alt="实时监控画面">
                <div class="video-timestamp" id="current-time"></div>
                <div class="data-flow"></div>
            </div>
        </div>
        
        <div class="panel warning-panel">
            <div class="panel-title">预警回放</div>
            <div class="video-container">
                <video id="warning-video" controls>
                    <source id="warning-video-source" src="/video_warning/output.mp4" type="video/mp4">
                    您的浏览器不支持视频播放
                </video>
                <div class="data-flow"></div>
            </div>
        </div>
        
        <div class="panel alerts-panel">
            <div class="panel-title">
                预警信息
                <div class="badge" id="alert-count">0</div>
            </div>
            <div class="alerts-container" id="alerts">
                <div class="no-data">暂无预警信息</div>
            </div>
            <div class="data-flow"></div>
        </div>
        
        <div class="panel qa-panel">
            <div class="panel-title">智能问答</div>
            <input type="text" id="question" class="qa-input" placeholder="输入您的问题...">
            <button onclick="askQuestion()" class="qa-button">
                <span id="ask-text">提问</span>
                <span id="ask-loader" class="loader" style="display: none;"></span>
            </button>
            <div class="qa-history" id="qa-history"></div>
            <div class="data-flow"></div>
        </div>
    </div>
    
    <div class="status-bar">
        <div class="status-indicator">系统运行中</div>
        <div class="system-stats">
            <div class="stat-item">
                <span>CPU:</span>
                <span class="stat-value" id="cpu-usage">12%</span>
            </div>
            <div class="stat-item">
                <span>内存:</span>
                <span class="stat-value" id="mem-usage">24%</span>
            </div>
            <div class="stat-item">
                <span>网络:</span>
                <span class="stat-value" id="net-usage">1.2 Mbps</span>
            </div>
            <div id="server-time"></div>
        </div>
    </div>

    <script>
        // WebSocket连接
        const videoWs = new WebSocket(`ws://${window.location.host}/video_feed`);
        const alertWs = new WebSocket(`ws://${window.location.host}/alerts`);
        const videoElement = document.getElementById('video-feed');
        const warningVideoElement = document.getElementById('warning-video');
        const warningVideoSource = document.getElementById('warning-video-source');
        const alertsDiv = document.getElementById('alerts');
        const qaHistory = document.getElementById('qa-history');
        const currentTimeElement = document.getElementById('current-time');
        const serverTimeElement = document.getElementById('server-time');
        const alertCountElement = document.getElementById('alert-count');
        const askTextElement = document.getElementById('ask-text');
        const askLoaderElement = document.getElementById('ask-loader');
        
        let alertCount = 0;

        // 更新时间显示
        function updateTime() {
            const now = new Date();
            const timeStr = `${now.getFullYear()}/` + 
                           `${(now.getMonth()+1).toString().padStart(2, '0')}/` + 
                           `${now.getDate().toString().padStart(2, '0')} ` + 
                           `${now.getHours().toString().padStart(2, '0')}:` + 
                           `${now.getMinutes().toString().padStart(2, '0')}:` + 
                           `${now.getSeconds().toString().padStart(2, '0')}`;
            document.getElementById('current-time').textContent = timeStr;
            serverTimeElement.textContent = `${timeStr}`;
            
            // 模拟系统状态更新
            if (Math.random() > 0.7) {
                document.getElementById('cpu-usage').textContent = `${Math.floor(Math.random() * 30) + 5}%`;
                document.getElementById('mem-usage').textContent = `${Math.floor(Math.random() * 40) + 10}%`;
                document.getElementById('net-usage').textContent = `${(Math.random() * 2 + 0.5).toFixed(1)} Mbps`;
            }
            
            setTimeout(updateTime, 1000);
        }
        updateTime();

        // 视频流处理
        videoWs.onmessage = function(event) {
            event.data.arrayBuffer().then(buffer => {
                const blob = new Blob([buffer], {type: 'image/jpeg'});
                videoElement.src = URL.createObjectURL(blob);
            });
        };

        videoElement.onload = function() {
            if (videoElement.src.startsWith('blob:')) {
                URL.revokeObjectURL(videoElement.src);
            }
        };

        // 更新预警视频
        function updateWarningVideo() {
            const timestamp = new Date().getTime();
            warningVideoSource.src = `/video_warning/output.mp4?t=${timestamp}`;
            warningVideoElement.load();
            warningVideoElement.play().catch(e => console.log("自动播放失败，可能需要用户交互:", e));
            
            // 添加脉冲动画效果
            warningVideoElement.parentElement.classList.add('pulse');
            setTimeout(() => {
                warningVideoElement.parentElement.classList.remove('pulse');
            }, 3000);
        }

        // WebSocket连接处理
        function setupWebSocketReconnection(socket, name) {
            socket.onclose = function(event) {
                console.log(`${name} 连接关闭，尝试重新连接...`);
                setTimeout(function() {
                    console.log(`尝试重新连接 ${name}...`);
                    if (name === '预警消息') {
                        alertWs = new WebSocket(`ws://${window.location.host}/alerts`);
                        setupWebSocketReconnection(alertWs, name);
                        setupAlertHandlers(alertWs);
                    } else {
                        videoWs = new WebSocket(`ws://${window.location.host}/video_feed`);
                        setupWebSocketReconnection(videoWs, name);
                        setupVideoHandlers(videoWs);
                    }
                }, 3000);
            };
        }

        // 预警消息处理
        function setupAlertHandlers(ws) {
            ws.onmessage = function(event) {
                console.log("收到WebSocket消息:", event.data);
                
                // 删除"暂无预警信息"提示
                const noDataDiv = document.querySelector('.alerts-panel .no-data');
                if (noDataDiv) {
                    noDataDiv.remove();
                }
                
                try {
                    const data = JSON.parse(event.data);
                    console.log("解析后数据:", data);
                    
                    // 更新预警计数
                    alertCount++;
                    alertCountElement.textContent = alertCount;
                    alertCountElement.style.display = 'flex';
                    
                    // 创建预警元素
                    const alertDiv = document.createElement('div');
                    
                    // 根据消息类型设置不同的样式
                    let className = 'alert';
                    let icon = 'ℹ️';
                    
                    if (data.level === "important" || data.content.includes("人员进行了")) {
                        className = 'alert important';
                        icon = '⚠️';
                    } 
                    else if (data.level === "warning") {
                        className = 'alert';
                        icon = '❗';
                    }
                    
                    alertDiv.className = className;
                    
                    alertDiv.innerHTML = `
                        <div class="alert-time">
                            <span class="alert-icon">${icon}</span>
                            ${new Date(data.timestamp).toLocaleString()}
                        </div>
                        <div class="alert-content">${data.content}</div>
                        ${data.details ? `<div class="alert-details">${data.details.substring(0, 80)}...</div>` : ''}
                    `;
                    
                    // 添加到预警区域顶部
                    alertsDiv.insertBefore(alertDiv, alertsDiv.firstChild);
                    
                    // 添加动画效果
                    alertDiv.style.opacity = '0';
                    alertDiv.style.transform = 'translateX(-20px)';
                    setTimeout(() => {
                        alertDiv.style.transition = 'all 0.3s ease';
                        alertDiv.style.opacity = '1';
                        alertDiv.style.transform = 'translateX(0)';
                    }, 10);
                    
                    // 更新预警视频
                    if (data.image_url) {
                        updateWarningVideo();
                    }
                    
                    // 限制显示的预警数量
                    if (alertsDiv.children.length > 20) {
                        alertsDiv.removeChild(alertsDiv.lastChild);
                    }
                    
                    // 播放通知声音
                    playNotificationSound();
                    
                } catch(e) {
                    console.error("JSON解析错误:", e);
                }
            };
        }

        // 播放通知声音
        function playNotificationSound() {
            const audio = new Audio('https://assets.mixkit.co/sfx/preview/mixkit-alarm-digital-clock-beep-989.mp3');
            audio.volume = 0.3;
            audio.play().catch(e => console.log("音频播放失败:", e));
        }

        // 初始设置
        alertWs.onopen = function() {
            console.log("预警WebSocket连接已建立");
        };

        // 应用连接机制
        setupWebSocketReconnection(videoWs, '视频流');
        setupWebSocketReconnection(alertWs, '预警消息');
        setupAlertHandlers(alertWs);

        // 问答功能
        async function askQuestion() {
            const questionInput = document.getElementById('question');
            const question = questionInput.value.trim();
            if (!question) return;

            // 显示加载状态
            askTextElement.style.display = 'none';
            askLoaderElement.style.display = 'block';
            
            // 添加问题到历史记录
            const questionDiv = document.createElement('div');
            questionDiv.className = 'question';
            questionDiv.textContent = question;
            qaHistory.insertBefore(questionDiv, qaHistory.firstChild);
            
            // 滚动到最新问题
            qaHistory.scrollTop = 0;

            try {
                const response = await fetch('http://localhost:8085/search/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: question,
                        k: 3
                    })
                });

                const result = await response.json();
                
                // 恢复按钮状态
                askTextElement.style.display = 'block';
                askLoaderElement.style.display = 'none';
                
                if (result.status === 'success') {
                    // 添加回答到历史记录
                    const answerDiv = document.createElement('div');
                    answerDiv.className = 'answer';
                    answerDiv.textContent = result.answer;
                    qaHistory.insertBefore(answerDiv, questionDiv.nextSibling);
                } else {
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'answer';
                    errorDiv.textContent = `错误：${result.message || '查询失败'}`;
                    qaHistory.insertBefore(errorDiv, questionDiv.nextSibling);
                }

            } catch (error) {
                console.error('问答出错:', error);
                // 恢复按钮状态
                askTextElement.style.display = 'block';
                askLoaderElement.style.display = 'none';
                
                const errorDiv = document.createElement('div');
                errorDiv.className = 'answer';
                errorDiv.textContent = `错误：${error.message}`;
                qaHistory.insertBefore(errorDiv, questionDiv.nextSibling);
            }

            // 清空输入框
            questionInput.value = '';
        }

        // 回车键提交问题
        document.getElementById('question').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                askQuestion();
            }
        });

        // 加载历史预警信息
        fetch('/alerts')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success' && data.alerts.length > 0) {
                    // 清除"暂无预警信息"提示
                    const noDataDiv = document.querySelector('.alerts-panel .no-data');
                    if (noDataDiv) {
                        noDataDiv.remove();
                    }
                    
                    alertCount = data.alerts.length;
                    alertCountElement.textContent = alertCount;
                    alertCountElement.style.display = 'flex';
                    
                    data.alerts.forEach(alert => {
                        const isImportant = alert.content.includes("人员进行了") || alert.level === "important";
                        const icon = isImportant ? '⚠️' : '❗';
                        
                        const alertDiv = document.createElement('div');
                        alertDiv.className = isImportant ? 'alert important' : 'alert';
                        
                        alertDiv.innerHTML = `
                            <div class="alert-time">
                                <span class="alert-icon">${icon}</span>
                                ${new Date(alert.timestamp).toLocaleString()}
                            </div>
                            <div class="alert-content">${alert.content}</div>
                            ${alert.details ? `<div class="alert-details">${alert.details.substring(0, 80)}...</div>` : ''}
                        `;
                        alertsDiv.appendChild(alertDiv);
                    });
                    
                    // 更新预警视频
                    updateWarningVideo();
                }
            });
            
        // 模拟一些系统通知
        setTimeout(() => {
            const sampleAlerts = [
                {
                    timestamp: new Date().toISOString(),
                    content: "系统自检完成，所有功能正常",
                    level: "info"
                },
                {
                    timestamp: new Date().toISOString(),
                    content: "检测到摄像头已连接", /* 移除了"3个" */
                    level: "info"
                }
            ];
            
            sampleAlerts.forEach(alert => {
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert';
                alertDiv.innerHTML = `
                    <div class="alert-time">
                        <span class="alert-icon">ℹ️</span>
                        ${new Date(alert.timestamp).toLocaleString()}
                    </div>
                    <div class="alert-content">${alert.content}</div>
                `;
                alertsDiv.insertBefore(alertDiv, alertsDiv.firstChild);
            });
            
            // 移除"暂无预警信息"提示
            const noDataDiv = document.querySelector('.alerts-panel .no-data');
            if (noDataDiv) {
                noDataDiv.remove();
            }
        }, 2000);
    </script>
    <!-- 删除浮动的行为分析按钮 -->
    <div class="status-bar">
        <div class="status-bar-left">
            <span class="status-indicator" id="status-text">🟢 系统运行中</span>
            <span class="memory-usage">内存: 39%</span>
            <span class="network-usage">网络: 2.2 Mbps</span>
            <span class="current-time" id="current-time">2025/03/28 20:15:22</span>
        </div>
        <div class="status-bar-right">
            <a href="/behavior_analysis" class="status-bar-btn">行为分析</a>
        </div>
    </div>
</body>
</html>
    """)

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
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>行为监测与可视化系统</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --primary: #4fd1c5;
            --dark-bg: #0a192f;
            --panel-bg: #172a45;
            --text-primary: #e6f1ff;
            --glow-color: rgba(79, 209, 197, 0.6);
            --accent: #66fcf1;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--dark-bg);
            color: var(--text-primary);
            line-height: 1.6;
            background-image: radial-gradient(circle at top right, rgba(23, 42, 69, 0.5), rgba(10, 25, 47, 0.5));
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        /* 重新设计的高科技标题 */
        .header {
            position: relative;
            height: 80px;
            width: 100%;
            background-color: rgba(6, 18, 36, 0.9);
            border-bottom: 1px solid rgba(79, 209, 197, 0.3);
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }

        /* 添加网格背景 */
        .header::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: 
                linear-gradient(rgba(0, 0, 0, 0) 9px, rgba(79, 209, 197, 0.1) 10px),
                linear-gradient(90deg, rgba(0, 0, 0, 0) 9px, rgba(79, 209, 197, 0.1) 10px);
            background-size: 10px 10px;
            opacity: 0.4;
        }

        /* 添加扫描线效果 */
        .header::after {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(79, 209, 197, 0.7), 
                transparent);
            animation: scanline 8s linear infinite;
            opacity: 0.7;
        }

        @keyframes scanline {
            0% { top: -10px; }
            100% { top: 80px; }
        }

        /* 标题文本和装饰 */
        .header h1 {
            color: var(--accent);
            font-size: 28px;
            font-weight: 600;
            text-align: center;
            position: relative;
            z-index: 10;
            letter-spacing: 1px;
            text-shadow: 0 0 15px rgba(102, 252, 241, 0.4);
        }

        /* 两侧装饰线 */
        .header h1::before,
        .header h1::after {
            content: "";
            position: absolute;
            top: 50%;
            width: 120px;
            height: 1px;
            background: linear-gradient(90deg, 
                rgba(102, 252, 241, 0) 0%, 
                rgba(102, 252, 241, 0.8) 50%,
                rgba(102, 252, 241, 0) 100%);
        }

        .header h1::before {
            right: 100%;
            margin-right: 20px;
        }

        .header h1::after {
            left: 100%;
            margin-left: 20px;
        }

        /* 左右箭头装饰 */
        .arrow-left, .arrow-right {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            color: var(--accent);
            font-size: 14px;
            letter-spacing: -3px;
            opacity: 0.8;
        }

        .arrow-left {
            left: 20px;
        }

        .arrow-right {
            right: 20px;
        }

        /* 版本和安全标签 */
        .header-badge {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background-color: transparent;
            border: 1px solid var(--accent);
            color: var(--accent);
            font-size: 12px;
            padding: 3px 8px;
            margin: 0 5px;
            border-radius: 4px;
            z-index: 5;
        }

        .badge-version {
            right: 120px;
        }

        .badge-secure {
            right: 40px;
        }

        /* 左侧系统状态 */
        .system-status {
            position: absolute;
            left: 120px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--accent);
            font-size: 12px;
            display: flex;
            align-items: center;
            opacity: 0.8;
        }

        .system-status::before {
            content: "●";
            font-size: 10px;
            margin-right: 5px;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        /* 动态数据流效果 */
        .data-stream {
            position: absolute;
            top: 0;
            height: 100%;
            width: 2px;
            background: linear-gradient(to bottom, 
                transparent, 
                rgba(79, 209, 197, 0.8), 
                transparent);
            opacity: 0.6;
            z-index: 1;
        }

        .data-stream:nth-child(1) {
            left: 200px;
            animation: dataflow 8s linear infinite;
        }

        .data-stream:nth-child(2) {
            right: 200px;
            animation: dataflow 8s linear infinite reverse;
        }

        @keyframes dataflow {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100%); }
        }
        
        /* 其他样式保持不变 */
        .dashboard {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-gap: 20px;
            padding: 20px;
            flex: 1;
        }
        
        .panel {
            background: linear-gradient(135deg, rgba(23, 42, 69, 0.9), rgba(10, 25, 47, 0.9));
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(79, 209, 197, 0.2);
            height: 100%;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
            backdrop-filter: blur(5px);
        }
        
        .panel::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, 
                rgba(79, 209, 197, 0) 0%, 
                rgba(79, 209, 197, 0.5) 50%, 
                rgba(79, 209, 197, 0) 100%);
        }
        
        .panel:hover {
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4), 0 0 20px rgba(79, 209, 197, 0.2);
            transform: translateY(-5px);
        }
        
        .panel-title {
            color: var(--primary);
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 15px;
            border-bottom: 1px solid rgba(79, 209, 197, 0.2);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            text-shadow: 0 0 10px rgba(79, 209, 197, 0.3);
        }
        
        .panel-title::before {
            content: "⬤";
            color: var(--primary);
            font-size: 12px;
            margin-right: 8px;
            opacity: 0.7;
        }
        
        .video-container {
            width: 100%;
            height: 350px; /* 增加高度 */
            background-color: #000;
            position: relative;
            overflow: hidden;
            border-radius: 8px;
            box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.5), 0 0 15px rgba(79, 209, 197, 0.2);
            border: 1px solid rgba(79, 209, 197, 0.3);
        }
        
        #camera-feed {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: all 0.5s;
        }
        
        .behavior-label {
            position: absolute;
            bottom: 10px;
            left: 10px;
            background-color: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 14px;
        }
        
        .chart-container {
            width: 100%;
            height: 220px;
            position: relative;
            margin-bottom: 10px;
        }
        
        .no-data {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: var(--text-primary);
            opacity: 0.5;
            font-size: 16px;
            text-align: center;
        }
        
        .behavior-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-gap: 10px 20px;
            margin-bottom: 20px;
        }
        
        .behavior-stats div {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px dashed rgba(79, 209, 197, 0.2);
        }
        
        .behavior-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 10px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            margin-right: 15px;
            font-size: 14px;
        }
        
        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 2px;
            margin-right: 5px;
        }
        
        /* 底部状态栏 */
        .status-bar {
            background-color: rgba(10, 25, 47, 0.9);
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid rgba(79, 209, 197, 0.3);
            font-size: 14px;
            color: var(--text-primary);
        }
        
        .status-bar-left {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .status-bar-right {
            display: flex;
            align-items: center;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            font-weight: 500;
        }
        
        .refresh-btn {
            background-color: rgba(79, 209, 197, 0.2);
            color: var(--primary);
            border: 1px solid rgba(79, 209, 197, 0.5);
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
        }
        
        .refresh-btn:hover {
            background-color: rgba(79, 209, 197, 0.3);
            transform: translateY(-2px);
        }
        
        .refresh-btn:active {
            transform: translateY(1px);
        }
        
        /* 状态栏返回按钮 - 使用与return-btn相同的样式 */
        .status-bar-btn {
            background: linear-gradient(135deg, #4fd1c5 0%, #3182ce 100%);
            color: #fff;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
            text-decoration: none;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
        }
        
        .status-bar-btn:hover {
            background: linear-gradient(135deg, #3182ce 0%, #4fd1c5 100%);
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="header">
        <!-- 左右数据流装饰 -->
        <div class="data-stream"></div>
        <div class="data-stream"></div>
        
        <!-- 左侧系统状态 -->
        <div class="system-status">系统在线</div>
        
        <!-- 左侧箭头 -->
        <div class="arrow-left">&gt;&gt;&gt;&gt;</div>
        
        <!-- 主标题 -->
        <h1>行为监测与可视化系统</h1>
        
        <!-- 右侧箭头 -->
        <div class="arrow-right">&gt;&gt;&gt;&gt;</div>
        
        <!-- 标签 -->
        <div class="header-badge badge-version">V2.1</div>
        <div class="header-badge badge-secure">SECURE</div>
    </div>
    
    <div class="dashboard">
        <!-- 实时监控面板 -->
        <div class="panel">
            <div class="panel-title">实时监控</div>
            <div class="video-container">
                <img id="camera-feed" src="" alt="实时监控画面">
                <div class="behavior-label" id="current-behavior">当前行为: 等待检测...</div>
            </div>
        </div>
        
        <!-- 行为随时间变化面板 -->
        <div class="panel">
            <div class="panel-title">行为随时间变化</div>
            <div class="chart-container">
                <canvas id="timeline-chart"></canvas>
                <div class="no-data" id="timeline-no-data">等待行为数据...</div>
            </div>
            <div class="behavior-legend">
                <div class="legend-item"><div class="legend-color" style="background-color: #4CAF50;"></div>专注工作</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #FF9800;"></div>吃东西</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #2196F3;"></div>喝水</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #9C27B0;"></div>喝饮料</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #F44336;"></div>玩手机</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #607D8B;"></div>睡觉</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #795548;"></div>其他</div>
            </div>
        </div>
        
        <!-- 行为分布面板 -->
        <div class="panel">
            <div class="panel-title">行为分布</div>
            <div class="chart-container">
                <canvas id="distribution-chart"></canvas>
                <div class="no-data" id="distribution-no-data">等待行为数据...</div>
            </div>
            <div class="behavior-legend">
                <div class="legend-item"><div class="legend-color" style="background-color: #4CAF50;"></div>专注工作</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #FF9800;"></div>吃东西</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #2196F3;"></div>喝水</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #9C27B0;"></div>喝饮料</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #F44336;"></div>玩手机</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #607D8B;"></div>睡觉</div>
                <div class="legend-item"><div class="legend-color" style="background-color: #795548;"></div>其他</div>
            </div>
        </div>
        
        <!-- 行为统计面板 -->
        <div class="panel">
            <div class="panel-title">行为统计</div>
            <div class="behavior-stats">
                <div><span>专注工作:</span> <span id="work-count">0 次</span></div>
                <div><span>吃东西:</span> <span id="eat-count">0 次</span></div>
                <div><span>喝水:</span> <span id="water-count">0 次</span></div>
                <div><span>喝饮料:</span> <span id="drink-count">0 次</span></div>
                <div><span>玩手机:</span> <span id="phone-count">0 次</span></div>
                <div><span>睡觉:</span> <span id="sleep-count">0 次</span></div>
                <div><span>其他:</span> <span id="other-count">0 次</span></div>
            </div>
            <button class="refresh-btn" id="refresh-stats-btn">
                <span>🔄</span> 重置统计
            </button>
        </div>
    </div>
    
    <div class="status-bar">
        <div class="status-bar-left">
            <span class="status-indicator" id="status-text">🟢 等待行为检测...</span>
            <span class="memory-usage">内存: 42%</span>
            <span class="network-usage">网络: 1.8 Mbps</span>
            <span class="current-time" id="current-time">2025/03/29 10:32:03</span>
        </div>
        <div class="status-bar-right">
            <a href="/" class="status-bar-btn">返回监控系统</a>
        </div>
    </div>
    
    <script>
        // 当前WebSocket连接
        let videoSocket = null;
        
        // 行为数据
        let behaviorHistory = [];
        let behaviorCounts = {
            "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0
        };
        
        // 图表对象
        let timelineChart = null;
        let distributionChart = null;
        
        // 行为映射
        const behaviorMap = {
            "1": "专注工作",
            "2": "吃东西",
            "3": "喝水",
            "4": "喝饮料",
            "5": "玩手机",
            "6": "睡觉",
            "7": "其他"
        };
        
        // 行为颜色
        const behaviorColors = {
            "1": "#4CAF50",
            "2": "#FF9800",
            "3": "#2196F3",
            "4": "#9C27B0",
            "5": "#F44336",
            "6": "#607D8B",
            "7": "#795548"
        };
        
        // 连接WebSocket
        function connectWebSocket() {
            if (videoSocket && videoSocket.readyState === WebSocket.OPEN) {
                console.log('WebSocket已连接');
                return;
            }
            
            try {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                videoSocket = new WebSocket(`${protocol}//${window.location.host}/video_feed`);
                 
                videoSocket.onopen = function() {
                    console.log('WebSocket连接已建立');
                    document.getElementById('status-text').textContent = '🟢 已连接到视频流';
                    
                    // 隐藏"无数据"提示
                    document.getElementById('timeline-no-data').style.display = 'none';
                    document.getElementById('distribution-no-data').style.display = 'none';
                };
                
                videoSocket.onclose = function() {
                    console.log('WebSocket连接已关闭');
                    document.getElementById('status-text').textContent = '🔴 视频连接已断开';
                };
                
                videoSocket.onerror = function(error) {
                    console.error('WebSocket错误:', error);
                    document.getElementById('status-text').textContent = '🔴 连接错误';
                };
                
                videoSocket.onmessage = function(event) {
                    // 处理图像数据
                    if (event.data instanceof Blob) {
                        event.data.arrayBuffer().then(buffer => {
                            const blob = new Blob([buffer], {type: 'image/jpeg'});
                            document.getElementById('camera-feed').src = URL.createObjectURL(blob);
                        });
                        return;
                    }
                    
                    // 处理JSON数据
                    try {
                        const data = JSON.parse(event.data);
                        
                        if (data.type === 'behavior') {
                            // 从content字段中提取行为编号
                            let behaviorNum = '7'; // 默认其他
                             
                            if (data.content && typeof data.content === 'string') {
                                const match = data.content.match(/检测到行为: (\d+)/);
                                if (match && match[1]) {
                                    behaviorNum = match[1];
                                }
                            }
                             
                            // 从details字段中提取行为
                            if (data.details && typeof data.details === 'string') {
                                if (data.details.includes('专注工作')) behaviorNum = '1';
                                else if (data.details.includes('吃东西')) behaviorNum = '2';
                                else if (data.details.includes('喝水')) behaviorNum = '3';
                                else if (data.details.includes('喝饮料')) behaviorNum = '4';
                                else if (data.details.includes('玩手机')) behaviorNum = '5';
                                else if (data.details.includes('睡觉')) behaviorNum = '6';
                            }
                            
                            updateBehaviorData(behaviorNum);
                        } else {
                            // 尝试解析异常检测结果
                            try {
                                if (data.data && typeof data.data === 'string' && data.data.includes('reason')) {
                                    const jsonMatch = data.data.match(/```json\s*({[^}]+})\s*```/);
                                    if (jsonMatch && jsonMatch[1]) {
                                        const result = JSON.parse(jsonMatch[1]);
                                        if (result.reason) {
                                            // 匹配行为关键词
                                            let behaviorNum = '7'; // 默认其他
                                            if (result.reason.includes('专注工作')) behaviorNum = '1';
                                            else if (result.reason.includes('吃东西')) behaviorNum = '2';
                                            else if (result.reason.includes('喝水')) behaviorNum = '3';
                                            else if (result.reason.includes('喝饮料')) behaviorNum = '4';
                                            else if (result.reason.includes('玩手机')) behaviorNum = '5';
                                            else if (result.reason.includes('睡觉')) behaviorNum = '6';
                                            
                                            updateBehaviorData(behaviorNum);
                                        }
                                    }
                                }
                            } catch (e) {
                                console.error('解析异常检测结果错误:', e);
                            }
                        }
                    } catch (error) {
                        // 尝试直接从文本中提取行为信息
                        try {
                            const text = event.data;
                            if (typeof text === 'string') {
                                // 查找行为关键词
                                let behaviorNum = '7'; // 默认其他
                                if (text.includes('专注工作')) behaviorNum = '1';
                                else if (text.includes('吃东西')) behaviorNum = '2';
                                else if (text.includes('喝水')) behaviorNum = '3';
                                else if (text.includes('喝饮料')) behaviorNum = '4';
                                else if (text.includes('玩手机')) behaviorNum = '5';
                                else if (text.includes('睡觉')) behaviorNum = '6';
                                
                                updateBehaviorData(behaviorNum);
                            }
                        } catch (e) {
                            console.error('处理文本数据错误:', e);
                        }
                    }
                };
            } catch (error) {
                console.error('WebSocket连接失败:', error);
                document.getElementById('status-text').textContent = '🔴 连接失败';
            }
        }
        
        // 更新行为数据
        function updateBehaviorData(behaviorNum) {
            // 更新当前行为显示
            const behaviorDesc = behaviorMap[behaviorNum];
            document.getElementById('current-behavior').textContent = `当前行为: ${behaviorDesc}`;
            document.getElementById('current-behavior').style.color = behaviorColors[behaviorNum];
                           
            // 添加到历史记录
            behaviorHistory.push({
                behavior: behaviorNum,
                timestamp: new Date()
            });
             
            // 限制历史记录长度
            if (behaviorHistory.length > 30) {
                behaviorHistory.shift();
            }
             
            // 更新计数
            behaviorCounts[behaviorNum]++;
             
            // 更新统计显示
            document.getElementById('work-count').textContent = `${behaviorCounts["1"]} 次`;
            document.getElementById('eat-count').textContent = `${behaviorCounts["2"]} 次`;
            document.getElementById('water-count').textContent = `${behaviorCounts["3"]} 次`;
            document.getElementById('drink-count').textContent = `${behaviorCounts["4"]} 次`;
            document.getElementById('phone-count').textContent = `${behaviorCounts["5"]} 次`;
            document.getElementById('sleep-count').textContent = `${behaviorCounts["6"]} 次`;
            document.getElementById('other-count').textContent = `${behaviorCounts["7"]} 次`;
            
            // 更新图表
            updateCharts();
        }
        
        // 重置数据
        function resetData() {
            behaviorHistory = [];
            behaviorCounts = {
                "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0
            };
            
            document.getElementById('work-count').textContent = '0 次';
            document.getElementById('eat-count').textContent = '0 次';
            document.getElementById('water-count').textContent = '0 次';
            document.getElementById('drink-count').textContent = '0 次';
            document.getElementById('phone-count').textContent = '0 次';
            document.getElementById('sleep-count').textContent = '0 次';
            document.getElementById('other-count').textContent = '0 次';
            
            document.getElementById('current-behavior').textContent = '当前行为: 等待检测...';
            document.getElementById('current-behavior').style.color = '';
            
            updateCharts();
            
            document.getElementById('timeline-no-data').style.display = 'block';
            document.getElementById('distribution-no-data').style.display = 'block';
             
            document.getElementById('status-text').textContent = "🟢 数据已重置";
        }
        
        // 初始化图表
        function initCharts() {
            // 时间线图表
            const timelineCtx = document.getElementById('timeline-chart').getContext('2d');
            timelineChart = new Chart(timelineCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: '行为',
                        data: [],
                        backgroundColor: function(context) {
                            const index = context.dataIndex;
                            const value = context.dataset.data[index];
                            return behaviorColors[value] || 'rgba(79, 209, 197, 1)';
                        },
                        borderColor: function(context) {
                            const index = context.dataIndex;
                            const value = context.dataset.data[index];
                            return behaviorColors[value] || 'rgba(79, 209, 197, 1)';
                        },
                        pointBorderColor: 'rgba(255, 255, 255, 0.8)',
                        pointRadius: 5,
                        tension: 0.2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            min: 0.5,
                            max: 7.5,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            ticks: {
                                color: 'rgba(255, 255, 255, 0.7)',
                                callback: function(value) {
                                    return behaviorMap[value] || '';
                                },
                                font: {
                                    size: 11 // 减小字体大小
                                },
                                padding: 8 // 增加标签间距
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            ticks: {
                                color: 'rgba(255, 255, 255, 0.7)',
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const behavior = behaviorMap[context.raw] || '未知';
                                    return `行为: ${behavior}`;
                                }
                            }
                        }
                    }
                }
            });
            
            // 分布图
            const distributionCtx = document.getElementById('distribution-chart').getContext('2d');
            distributionChart = new Chart(distributionCtx, {
                type: 'doughnut',
                data: {
                    labels: Object.values(behaviorMap),
                    datasets: [{
                        data: Object.values(behaviorCounts),
                        backgroundColor: Object.values(behaviorColors),
                        borderColor: 'rgba(25, 41, 68, 0.8)',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.raw || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    },
                    cutout: '60%'
                }
            });
            
            // 显示"无数据"提示
            document.getElementById('timeline-no-data').style.display = 'block';
            document.getElementById('distribution-no-data').style.display = 'block';
        }
        
        // 更新图表时，清除演示数据
        function updateBehaviorData(behaviorNum) {
            // 如果是第一个真实数据点，清除演示数据
            if (behaviorHistory.length === 0) {
                // 清除演示数据
                timelineChart.data.labels = [];
                timelineChart.data.datasets[0].data = [];
                
                // 重置分布图数据
                distributionChart.data.datasets[0].data = Object.values(behaviorCounts);
                distributionChart.update();
            }
            
            // ...现有的更新逻辑保持不变...
        }
        
        // 更新图表
        function updateCharts() {
            if (!timelineChart || !distributionChart) return;
            
            // 更新时间线图表
            timelineChart.data.labels = behaviorHistory.map(item => {
                const time = item.timestamp;
                return `${time.getHours()}:${time.getMinutes().toString().padStart(2, '0')}:${time.getSeconds().toString().padStart(2, '0')}`;
            });
            timelineChart.data.datasets[0].data = behaviorHistory.map(item => item.behavior);
            timelineChart.update();
            
            // 更新分布图
            distributionChart.data.datasets[0].data = Object.values(behaviorCounts);
            distributionChart.update();
            
            // 更新"无数据"提示
            document.getElementById('timeline-no-data').style.display = behaviorHistory.length === 0 ? 'block' : 'none';
            document.getElementById('distribution-no-data').style.display = 
                Object.values(behaviorCounts).every(count => count === 0) ? 'block' : 'none';
        }
        
        // 更新时间
        function updateTime() {
            const now = new Date();
            const timeStr = `${now.getFullYear()}/` + 
                           `${(now.getMonth()+1).toString().padStart(2, '0')}/` + 
                           `${now.getDate().toString().padStart(2, '0')} ` + 
                           `${now.getHours().toString().padStart(2, '0')}:` + 
                           `${now.getMinutes().toString().padStart(2, '0')}:` + 
                           `${now.getSeconds().toString().padStart(2, '0')}`;
            document.getElementById('current-time').textContent = timeStr;
        }
        
        // 添加按钮事件
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('refresh-stats-btn').addEventListener('click', resetData);
        });
        
        // 页面加载时初始化
        window.addEventListener('load', function() {
            initCharts();
            connectWebSocket();
            updateTime();
            setInterval(updateTime, 1000);
        });
        
        // 页面关闭时清理
        window.addEventListener('beforeunload', function() {
            if (videoSocket) {
                videoSocket.close();
            }
        });
    </script>
</body>
</html>
    """)

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

# python video_server.py --video_source "./测试视频/小猫开门.mp4"