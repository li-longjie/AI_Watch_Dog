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
from fastapi.responses import HTMLResponse, FileResponse
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
        }
        
        .header {
            background-color: var(--panel-bg);
            padding: 1rem 2rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: relative;
            z-index: 10;
            border-bottom: 1px solid rgba(79, 209, 197, 0.2);
        }
        
        .header h1 {
            margin: 0;
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--primary);
            display: flex;
            align-items: center;
            letter-spacing: 0.5px;
        }
        
        .header h1:before {
            content: "🔍";
            margin-right: 12px;
            font-size: 1.3em;
        }
        
        .header-controls {
            display: flex;
            gap: 1rem;
        }
        
        .control-btn {
            background: rgba(79, 209, 197, 0.1);
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: var(--transition);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .control-btn:hover {
            background: rgba(79, 209, 197, 0.2);
            transform: translateY(-2px);
        }
        
        .control-btn i {
            font-size: 1.1em;
        }
        
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: auto auto;
            gap: 1.5rem;
            padding: 1.5rem;
            height: calc(100vh - 72px);
        }
        
        .panel {
            background-color: var(--panel-bg);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
            display: flex;
            flex-direction: column;
            position: relative;
            overflow: hidden;
            border: 1px solid var(--panel-border);
            transition: var(--transition);
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
        
        .panel-title {
            color: var(--primary);
            display: flex;
            align-items: center;
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid rgba(79, 209, 197, 0.2);
        }
        
        .panel-title:before {
            content: "";
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--primary);
            margin-right: 12px;
            box-shadow: 0 0 10px var(--primary);
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
        
        .video-container {
            position: relative;
            width: 100%;
            height: calc(100% - 45px);
            overflow: hidden;
            border-radius: 8px;
            background-color: #000;
            box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.5);
        }
        
        #video-feed, #warning-video {
            width: 100%;
            height: 100%;
            object-fit: cover;
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
        
        .alert {
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 8px;
            background-color: rgba(255, 77, 77, 0.08);
            border-left: 3px solid var(--danger);
            position: relative;
            transition: var(--transition);
            cursor: pointer;
        }
        
        .alert:hover {
            background-color: rgba(255, 77, 77, 0.15);
            transform: translateX(5px);
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
        
        .alert.important {
            background-color: rgba(255, 204, 0, 0.08);
            border-left: 3px solid var(--warning);
        }
        
        .alert.important:hover {
            background-color: rgba(255, 204, 0, 0.15);
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
            
            .header-controls {
                display: none;
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
    </style>
</head>
<body>
    <div class="header">
        <h1>智能视频监控系统</h1>
        <div class="header-controls">
            <button class="control-btn tooltip" id="behavior-analysis-btn" data-tooltip="分析视频中的行为">
                <i>⏺️</i> 行为分析
            </button>
        </div>
    </div>
    
    <div class="container">
        <div class="panel video-panel">
            <div class="panel-title">实时监控</div>
            <div class="video-container">
                <img id="video-feed" src="" alt="实时监控画面">
                <div class="video-timestamp" id="current-time"></div>
            </div>
        </div>
        
        <div class="panel warning-panel">
            <div class="panel-title">预警回放</div>
            <div class="video-container">
                <video id="warning-video" controls>
                    <source id="warning-video-source" src="/video_warning/output.mp4" type="video/mp4">
                    您的浏览器不支持视频播放
                </video>
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
        </div>
        
        <div class="panel qa-panel">
            <div class="panel-title">智能问答</div>
            <input type="text" id="question" class="qa-input" placeholder="输入您的问题...">
            <button onclick="askQuestion()" class="qa-button">
                <span id="ask-text">提问</span>
                <span id="ask-loader" class="loader" style="display: none;"></span>
            </button>
            <div class="qa-history" id="qa-history"></div>
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
        
        // 添加行为分析按钮点击事件
        document.getElementById('behavior-analysis-btn').addEventListener('click', function() {
            // 直接跳转到行为分析页面
            window.location.href = '/behavior_analysis';
        });
        
        let alertCount = 0;

        // 更新时间显示
        function updateTime() {
            const now = new Date();
            const timeString = now.toLocaleTimeString();
            const dateString = now.toLocaleDateString();
            currentTimeElement.textContent = timeString;
            serverTimeElement.textContent = `${dateString} ${timeString}`;
            
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
                    content: "检测到3个摄像头已连接",
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
</body>
</html>
    """)

# 添加新路由来启动行为分析程序
@app.get("/launch_behavior_analysis")
async def launch_behavior_analysis():
    try:
        # 更彻底地释放摄像头资源
        if hasattr(video_processor, 'cap') and video_processor.cap is not None:
            try:
                logging.info("正在释放摄像头资源...")
                video_processor.cap.release()
                video_processor.cap = None
                # 使用系统命令释放摄像头
                import platform
                if platform.system() == "Windows":
                    os.system("taskkill /F /IM opencv_videoio*.exe 2>nul")
                else:
                    os.system("pkill -f 'python.*opencv' 2>/dev/null")
            except Exception as e:
                logging.warning(f"释放摄像头时出错: {e}")
        
        # 增加等待时间
        await asyncio.sleep(5)
        
        # 使用子进程启动diagram.py
        import subprocess
        import sys
        import os
        
        # 获取当前脚本的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        diagram_path = os.path.join(current_dir, "diagram.py")
        
        # 确保传递必要的环境参数
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{current_dir}:{env.get('PYTHONPATH', '')}"
        
        # 使用Python解释器启动diagram.py
        subprocess.Popen([sys.executable, diagram_path], env=env)
        
        # 返回成功消息或重定向回主页
        return {"status": "success", "message": "行为分析程序已启动"}
    except Exception as e:
        logging.error(f"启动行为分析程序时出错: {e}")
        return {"status": "error", "message": str(e)}

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

# 添加新路由来显示行为分析界面
@app.get("/behavior_analysis")
async def behavior_analysis_page():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>行为监测与可视化系统</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --primary: #4fd1c5;
            --primary-dark: #38b2ac;
            --secondary: #805ad5;
            --danger: #ff4d4d;
            --warning: #ffcc00;
            --dark-bg: #1a1a1a;
            --panel-bg: #172a45;
            --panel-border: #2d3748;
            --text-primary: #e6f1ff;
            --text-secondary: #8892b0;
            --transition: all 0.25s cubic-bezier(0.645, 0.045, 0.355, 1);
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
        }
        
        .header {
            background-color: var(--panel-bg);
            padding: 1rem 2rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: relative;
            z-index: 10;
            border-bottom: 1px solid rgba(79, 209, 197, 0.2);
        }
        
        .header h1 {
            margin: 0;
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--primary);
            display: flex;
            align-items: center;
            letter-spacing: 0.5px;
        }
        
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: auto auto;
            gap: 1.5rem;
            padding: 1.5rem;
            height: calc(100vh - 72px);
        }
        
        .panel {
            background-color: var(--panel-bg);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
            display: flex;
            flex-direction: column;
            position: relative;
            overflow: hidden;
            border: 1px solid var(--panel-border);
            transition: var(--transition);
        }
        
        .panel-title {
            color: var(--primary);
            display: flex;
            align-items: center;
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid rgba(79, 209, 197, 0.2);
        }
        
        .camera-panel {
            grid-row: 1;
            grid-column: 1;
        }
        
        .line-chart-panel {
            grid-row: 1;
            grid-column: 2;
        }
        
        .pie-chart-panel {
            grid-row: 2;
            grid-column: 1;
        }
        
        .stats-panel {
            grid-row: 2;
            grid-column: 2;
        }
        
        .camera-container {
            position: relative;
            width: 100%;
            height: calc(100% - 45px);
            overflow: hidden;
            border-radius: 8px;
            background-color: #000;
            box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.5);
        }
        
        #camera-feed {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: var(--transition);
        }
        
        .chart-container {
            width: 100%;
            height: calc(100% - 45px);
            position: relative;
        }
        
        .behavior-label {
            position: absolute;
            bottom: 1rem;
            left: 1rem;
            background-color: rgba(0, 0, 0, 0.7);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-size: 0.9rem;
            color: var(--primary);
            backdrop-filter: blur(5px);
        }
        
        .control-btn {
            background: rgba(79, 209, 197, 0.1);
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: var(--transition);
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        
        .control-btn:hover {
            background: rgba(79, 209, 197, 0.2);
            transform: translateY(-2px);
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
        
        .behavior-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.8rem;
        }
        
        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }
        
        .back-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid white;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: var(--transition);
        }
        
        .back-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        @keyframes pulse-animation {
            0% { box-shadow: 0 0 0 0 rgba(79, 209, 197, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(79, 209, 197, 0); }
            100% { box-shadow: 0 0 0 0 rgba(79, 209, 197, 0); }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>行为监测与可视化系统</h1>
        <button class="back-btn" onclick="window.location.href='/'">返回监控系统</button>
    </div>
    
    <div class="container">
        <div class="panel camera-panel">
            <div class="panel-title">实时监控</div>
            <div class="camera-container">
                <img id="camera-feed" src="/static/loading.gif" alt="实时监控画面">
                <div class="behavior-label" id="current-behavior">当前行为: 等待分析...</div>
            </div>
            <button class="control-btn" id="refresh-btn">
                <i>🔄</i> 刷新数据
            </button>
        </div>
        
        <div class="panel line-chart-panel">
            <div class="panel-title">行为随时间变化</div>
            <div class="chart-container">
                <canvas id="line-chart"></canvas>
            </div>
        </div>
        
        <div class="panel pie-chart-panel">
            <div class="panel-title">行为分布</div>
            <div class="chart-container">
                <canvas id="pie-chart"></canvas>
            </div>
            <div class="behavior-legend">
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #4CAF50;"></div>
                    <span>专注工作</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #FFC107;"></div>
                    <span>吃东西</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #2196F3;"></div>
                    <span>喝水</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #9C27B0;"></div>
                    <span>喝饮料</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #F44336;"></div>
                    <span>玩手机</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #607D8B;"></div>
                    <span>睡觉</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #795548;"></div>
                    <span>其他</span>
                </div>
            </div>
        </div>
        
        <div class="panel stats-panel">
            <div class="panel-title">行为统计</div>
            <div id="behavior-stats">
                <p>专注工作: <span id="work-count">0</span> 次</p>
                <p>吃东西: <span id="eat-count">0</span> 次</p>
                <p>喝水: <span id="water-count">0</span> 次</p>
                <p>喝饮料: <span id="drink-count">0</span> 次</p>
                <p>玩手机: <span id="phone-count">0</span> 次</p>
                <p>睡觉: <span id="sleep-count">0</span> 次</p>
                <p>其他: <span id="other-count">0</span> 次</p>
            </div>
            <button class="control-btn" id="refresh-btn-stats">
                <i>🔄</i> 刷新数据
            </button>
        </div>
    </div>
    
    <div class="status-bar">
        <div class="status-indicator" id="status-text">系统就绪</div>
        <div id="current-time"></div>
    </div>

    <script>
        // 增强的WebSocket处理代码
        let videoWs;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;
        
        function connectWebSocket() {
            try {
                console.log("正在连接视频WebSocket...");
                videoWs = new WebSocket(`ws://${window.location.host}/video_feed`);
                
                videoWs.onopen = function() {
                    console.log("WebSocket连接已建立");
                    document.getElementById('status-text').textContent = "视频流已连接";
                    reconnectAttempts = 0;
                };
                
                videoWs.onmessage = function(event) {
                    try {
                        event.data.arrayBuffer().then(buffer => {
                            try {
                                const blob = new Blob([buffer], {type: 'image/jpeg'});
                                document.getElementById('camera-feed').src = URL.createObjectURL(blob);
                            } catch (err) {
                                console.error("处理视频帧时出错:", err);
                            }
                        }).catch(err => {
                            console.error("读取视频数据时出错:", err);
                        });
                    } catch (err) {
                        console.error("WebSocket消息处理错误:", err);
                    }
                };
                
                videoWs.onclose = function(event) {
                    console.log("WebSocket连接已关闭", event);
                    if (reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        document.getElementById('status-text').textContent = `视频流断开，尝试重连 (${reconnectAttempts}/${maxReconnectAttempts})...`;
                        setTimeout(connectWebSocket, 2000);
                    } else {
                        document.getElementById('status-text').textContent = "视频流连接失败，使用模拟数据";
                        // 使用占位图像
                        document.getElementById('camera-feed').src = "https://via.placeholder.com/640x480.png?text=Video+Stream+Unavailable";
                    }
                };
                
                videoWs.onerror = function(error) {
                    console.error("WebSocket错误:", error);
                    document.getElementById('status-text').textContent = "视频流连接出错";
                };
            } catch (err) {
                console.error("创建WebSocket时出错:", err);
                document.getElementById('status-text').textContent = "无法创建视频连接";
                document.getElementById('camera-feed').src = "https://via.placeholder.com/640x480.png?text=Connection+Error";
            }
        }
        
        // 清理资源函数
        function cleanupWebSocket() {
            if (videoWs) {
                try {
                    videoWs.close();
                } catch (err) {
                    console.error("关闭WebSocket时出错:", err);
                }
            }
        }
        
        // 清理图像URL资源
        function cleanupImageURLs() {
            const img = document.getElementById('camera-feed');
            if (img && img.src && img.src.startsWith('blob:')) {
                URL.revokeObjectURL(img.src);
            }
        }
        
        // 页面加载和卸载事件
        window.addEventListener('load', function() {
            console.log("页面加载 - 初始化视频和行为分析");
            connectWebSocket();
            simulateBehaviorDetection();
        });
        
        window.addEventListener('beforeunload', function() {
            console.log("页面卸载 - 清理资源");
            cleanupWebSocket();
            cleanupImageURLs();
        });
        
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
            "1": "#4CAF50",  // 绿色表示工作
            "2": "#FFC107",  // 琥珀色表示吃东西
            "3": "#2196F3",  // 蓝色表示喝水
            "4": "#9C27B0",  // 紫色表示喝饮料
            "5": "#F44336",  // 红色表示玩手机
            "6": "#607D8B",  // 蓝灰色表示睡觉
            "7": "#795548"   // 棕色表示其他
        };
        
        // 模拟数据
        let behaviorHistory = [];
        let behaviorCounts = {
            "1": 0,
            "2": 0,
            "3": 0,
            "4": 0,
            "5": 0,
            "6": 0,
            "7": 0
        };
        
        // 初始化图表
        const lineCtx = document.getElementById('line-chart').getContext('2d');
        const pieCtx = document.getElementById('pie-chart').getContext('2d');
        
        // 折线图
        const lineChart = new Chart(lineCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '行为类型',
                    data: [],
                    backgroundColor: 'rgba(79, 209, 197, 0.2)',
                    borderColor: 'rgba(79, 209, 197, 1)',
                    borderWidth: 2,
                    pointBackgroundColor: function(context) {
                        const index = context.dataIndex;
                        const value = context.dataset.data[index];
                        return behaviorColors[value] || 'rgba(79, 209, 197, 1)';
                    },
                    pointRadius: 5,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        min: 0.5,
                        max: 7.5,
                        ticks: {
                            callback: function(value) {
                                return behaviorMap[value] || '';
                            },
                            color: 'white'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    },
                    x: {
                        ticks: {
                            color: 'white'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
        
        // 饼图
        const pieChart = new Chart(pieCtx, {
            type: 'pie',
            data: {
                labels: Object.values(behaviorMap),
                datasets: [{
                    data: Object.values(behaviorCounts),
                    backgroundColor: Object.values(behaviorColors),
                    borderColor: 'rgba(255, 255, 255, 0.2)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
        
        // 模拟行为检测
        function simulateBehaviorDetection() {
            setInterval(() => {
                // 随机生成行为
                const behaviorNum = String(Math.floor(Math.random() * 7) + 1);
                const behaviorDesc = behaviorMap[behaviorNum];
                const timestamp = new Date();
                
                // 添加到历史
                behaviorHistory.push({
                    timestamp: timestamp,
                    behavior: behaviorNum
                });
                
                // 限制历史长度
                if (behaviorHistory.length > 20) {
                    behaviorHistory.shift();
                }
                
                // 更新计数
                behaviorCounts[behaviorNum]++;
                
                // 更新UI
                updateUI(behaviorNum, behaviorDesc);
                
                // 更新图表
                updateCharts();
                
            }, 5000); // 每5秒检测一次
        }
        
        // 更新UI
        function updateUI(behaviorNum, behaviorDesc) {
            // 更新当前行为标签
            document.getElementById('current-behavior').textContent = `当前行为: ${behaviorDesc}`;
            document.getElementById('current-behavior').style.color = behaviorColors[behaviorNum];
            
            // 更新统计
            document.getElementById('work-count').textContent = behaviorCounts["1"];
            document.getElementById('eat-count').textContent = behaviorCounts["2"];
            document.getElementById('water-count').textContent = behaviorCounts["3"];
            document.getElementById('drink-count').textContent = behaviorCounts["4"];
            document.getElementById('phone-count').textContent = behaviorCounts["5"];
            document.getElementById('sleep-count').textContent = behaviorCounts["6"];
            document.getElementById('other-count').textContent = behaviorCounts["7"];
            
            // 更新状态
            document.getElementById('status-text').textContent = `检测到行为: ${behaviorDesc}`;
        }
        
        // 更新图表
        function updateCharts() {
            // 更新折线图
            lineChart.data.labels = behaviorHistory.map(item => {
                const time = item.timestamp;
                return time.getHours() + ':' + 
                       (time.getMinutes() < 10 ? '0' : '') + time.getMinutes() + ':' + 
                       (time.getSeconds() < 10 ? '0' : '') + time.getSeconds();
            });
            lineChart.data.datasets[0].data = behaviorHistory.map(item => item.behavior);
            lineChart.update();
            
            // 更新饼图
            pieChart.data.datasets[0].data = Object.values(behaviorCounts);
            pieChart.update();
        }
        
        // 刷新按钮
        document.getElementById('refresh-btn').addEventListener('click', function() {
            // 触发一次行为检测
            const behaviorNum = String(Math.floor(Math.random() * 7) + 1);
            const behaviorDesc = behaviorMap[behaviorNum];
            const timestamp = new Date();
            
            behaviorHistory.push({
                timestamp: timestamp,
                behavior: behaviorNum
            });
            
            if (behaviorHistory.length > 20) {
                behaviorHistory.shift();
            }
            
            behaviorCounts[behaviorNum]++;
            
            updateUI(behaviorNum, behaviorDesc);
            updateCharts();
            
            document.getElementById('status-text').textContent = '数据已刷新';
        });
        
        document.getElementById('refresh-btn-stats').addEventListener('click', function() {
            updateCharts();
            document.getElementById('status-text').textContent = '统计数据已刷新';
        });
    </script>
</body>
</html>
    """)

# 添加一个路由来加载默认图像，以防loading.gif不存在
@app.get("/static/loading.gif", include_in_schema=False)
async def get_loading_gif():
    from fastapi.responses import FileResponse
    import os
    
    # 检查loading.gif是否存在
    loading_path = os.path.join("static", "loading.gif")
    if os.path.exists(loading_path):
        return FileResponse(loading_path)
    
    # 如果不存在，返回默认图像
    default_image = os.path.join("static", "default_loading.jpg")
    if os.path.exists(default_image):
        return FileResponse(default_image)
    
    # 如果都不存在，返回占位符文本
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("Loading...")

if __name__ == "__main__":
    print(f"启动视频服务器 http://{ServerConfig.HOST}:{ServerConfig.PORT}")
    uvicorn.run( 
        app, 
        host=ServerConfig.HOST,
        port=ServerConfig.PORT,
        log_level="info"
    )

# python video_server.py --video_source "./测试视频/小猫开门.mp4"