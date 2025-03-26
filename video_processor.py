import cv2
import threading
import queue
import time
import asyncio
from datetime import datetime
import numpy as np
from typing import Optional, Dict, Union
import logging
import os
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from multi_modal_analyzer import MultiModalAnalyzer
from config import VideoConfig

class VideoProcessor:
    def __init__(self, video_source: Union[int, str]):
        self.video_source = video_source
        self.is_camera = isinstance(video_source, int)
        
        # 初始化视频捕获
        if self.is_camera:
            # 摄像头模式
            self.cap = cv2.VideoCapture(video_source, cv2.CAP_DSHOW)
            # 设置摄像头参数
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, VideoConfig.CAMERA_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VideoConfig.CAMERA_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, VideoConfig.FPS)
        else:
            # 本地视频文件模式
            if not os.path.exists(video_source):
                raise ValueError(f"视频文件不存在: {video_source}")
            self.cap = cv2.VideoCapture(video_source)
        
        # 检查视频源是否成功打开
        if not self.cap.isOpened():
            raise ValueError(f"无法打开视频源: {video_source}")
            
        # 获取实际的FPS
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or VideoConfig.FPS
        self.frame_interval = 1.0 / self.fps
        
        print(f"视频源: {video_source}, FPS: {self.fps}")
        
        # 线程控制
        self.running = True
        self.processing = False
        
        # 实时显示帧
        self.display_frame = None
        self.display_lock = threading.Lock()
        
        # 分析用帧列表
        self.analysis_frames = []
        self.analysis_timestamps = []
        self.last_analysis = time.time()
        
        # 分析器
        self.analyzer = MultiModalAnalyzer()
        
        # 消息队列
        self.alert_queue = queue.Queue()
        
        # 创建摄像头线程
        self.webcam_thread = threading.Thread(target=self._process_webcam)
        self.webcam_thread.daemon = True
        
        self.start_push_queue = 0

    async def start_processing(self):
        """启动处理"""
        self.running = True
        # 启动摄像头线程
        self.webcam_thread.start()
        
        # 启动警报处理
        asyncio.create_task(self._process_alerts())
        
        # 返回一个永不完成的任务，保持处理运行
        while self.running:
            await asyncio.sleep(1)

    async def stop_processing(self):
        """停止处理"""
        self.running = False
        if hasattr(self, 'webcam_thread') and self.webcam_thread.is_alive():
            self.webcam_thread.join(timeout=1.0)
        if self.cap and self.cap.isOpened():
            self.cap.release()

    def _process_webcam(self):
        """主摄像头处理循环 - 只保持最新帧"""
        last_analysis_update = time.time()
        frame_count = 0
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                
                # 处理视频文件循环播放
                if not ret:
                    if not self.is_camera:
                        # 本地视频文件结束，重新开始
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.cap.read()
                        if not ret:
                            time.sleep(0.1)
                            continue
                    else:
                        # 摄像头错误，尝试重新连接
                        time.sleep(0.1)
                        continue

                current_time = time.time()
                frame_count += 1
                
                # 更新显示帧
                with self.display_lock:
                    self.display_frame = frame.copy()
                
                # 收集分析帧
                if current_time - last_analysis_update >= 1.0:  # 每秒收集一帧用于分析
                    self.analysis_frames.append(frame.copy())
                    self.analysis_timestamps.append(datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
                    
                    # 保持分析帧数量
                    max_frames = int(VideoConfig.BUFFER_DURATION)
                    if len(self.analysis_frames) > max_frames:
                        self.analysis_frames = self.analysis_frames[-max_frames:]
                        self.analysis_timestamps = self.analysis_timestamps[-max_frames:]
                    
                    last_analysis_update = current_time
                
                # 检查是否需要触发分析
                if current_time - self.last_analysis >= VideoConfig.ANALYSIS_INTERVAL and not self.processing:
                    if len(self.analysis_frames) >= 2:
                        # 创建分析任务
                        analysis_task = threading.Thread(
                            target=self._run_analysis,
                            args=(self.analysis_frames.copy(), self.analysis_timestamps.copy())
                        )
                        analysis_task.daemon = True
                        analysis_task.start()
                        
                        self.last_analysis = current_time
                
                # 控制帧率 - 对于本地视频文件，我们需要控制播放速度
                if not self.is_camera:
                    time.sleep(max(0, self.frame_interval - (time.time() - current_time)))
                
            except Exception as e:
                logging.error(f"视频处理错误: {e}")
                time.sleep(0.1)

    def _run_analysis(self, frames, timestamps):
        """在单独的线程中运行分析"""
        try:
            self.processing = True
            print("开始分析视频片段")
            
            # 创建事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行分析
            result = loop.run_until_complete(
                self.analyzer.analyze(frames, self.fps, (timestamps[0], timestamps[-1]))
            )
            
            # 只处理重要和异常情况
            if isinstance(result, dict) and result.get("type") in ["important", "warning"]:
                print(f"分析结果: {result}")
                
                # 保存预警图像
                output_filename = f"video_warning/alert_{int(time.time())}.jpg"
                cv2.imwrite(output_filename, frames[-1])
                
                # 确保alert字段是字符串
                alert_content = result["alert"] if isinstance(result["alert"], str) else str(result["alert"])
                
                # 创建正确格式的预警消息
                alert = {
                    "type": "alert",
                    "timestamp": datetime.now().strftime('%Y年%m月%d日%H点%M分'),
                    "content": alert_content,  # 使用字符串内容
                    "level": result.get("type", "normal"),
                    "details": result.get("details", ""),
                    "image_url": f"/{output_filename}"
                }
                
                # 发送到警报队列
                self.alert_queue.put(alert)
                print(f"已添加预警到队列: {alert_content}")
            else:
                print(f"未检测到需要预警的情况")
            
            loop.close()
            
        except Exception as e:
            logging.error(f"分析错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.processing = False

    async def video_streamer(self, websocket: WebSocket):
        """流式传输视频帧"""
        last_frame_time = time.time()
        empty_frames_count = 0
        
        try:
            while self.running and self.start_push_queue:
                try:
                    current_time = time.time()
                    frame_delay = max(0, self.frame_interval - (current_time - last_frame_time))
                    
                    # 添加小延迟以保持帧率
                    if frame_delay > 0:
                        await asyncio.sleep(frame_delay)
                    
                    # 获取当前帧
                    with self.display_lock:
                        if self.display_frame is None:
                            empty_frames_count += 1
                            if empty_frames_count > 10:  # 允许最多10帧丢失
                                # 发送黑色帧防止客户端断开
                                black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                                _, buffer = cv2.imencode('.jpg', black_frame, [cv2.IMWRITE_JPEG_QUALITY, VideoConfig.JPEG_QUALITY])
                                await websocket.send_bytes(buffer.tobytes())
                                await asyncio.sleep(0.1)
                            continue
                        frame = self.display_frame.copy()
                        empty_frames_count = 0
                    
                    # 添加时间戳
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    cv2.putText(frame, timestamp, (frame.shape[1] - 120, frame.shape[0] - 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    # 压缩和发送
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, VideoConfig.JPEG_QUALITY])
                    await websocket.send_bytes(buffer.tobytes())
                    
                    last_frame_time = current_time
                    
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logging.error(f"视频流错误: {str(e)}")
                    await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"视频流失败: {str(e)}")
        finally:
            logging.info("视频流结束")

    async def _process_alerts(self):
        """处理警报消息"""
        while self.running:
            try:
                try:
                    alert = self.alert_queue.get_nowait()
                    await self.send_alert(alert)
                except queue.Empty:
                    await asyncio.sleep(0.1)
            except Exception as e:
                logging.error(f"警报处理错误: {e}")
                await asyncio.sleep(1)

    async def send_alert(self, alert):
        """发送预警信息"""
        try:
            # 重要：直接引入相关变量
            from video_server import recent_alerts, active_connections, MAX_ALERTS
            
            # 添加更详细的日志
            print(f"准备发送预警: {alert}")
            print(f"当前有 {len(active_connections)} 个活跃连接")
            
            # 添加到最近预警
            recent_alerts.append(alert)
            if len(recent_alerts) > MAX_ALERTS:
                recent_alerts.pop(0)
            
            # 实时发送给所有连接
            disconnected = []
            for i, connection in enumerate(active_connections):
                try:
                    if connection.client_state == WebSocketState.CONNECTED:
                        print(f"发送到连接 {i+1}/{len(active_connections)}")
                        await connection.send_json(alert)
                        print(f"发送成功")
                    else:
                        print(f"连接 {i+1} 状态不是CONNECTED，而是: {connection.client_state}")
                        disconnected.append(connection)
                except Exception as e:
                    print(f"发送到连接 {i+1} 失败: {e}")
                    disconnected.append(connection)
            
            # 清理断开的连接
            for conn in disconnected:
                if conn in active_connections:
                    active_connections.remove(conn)
                    print(f"移除断开的连接，剩余 {len(active_connections)} 个")
        except Exception as e:
            print(f"警报发送过程错误: {e}")
            logging.error(f"警报发送错误: {e}")

    def detect_activity(self, frame: np.ndarray) -> bool:
        """检测画面中的活动"""
        # 简化实现，避免使用未定义的 background_subtractor
        if frame is None:
            return False
        
        # 使用帧差法检测运动
        if not hasattr(self, '_prev_frame'):
            self._prev_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return False
        
        current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(self._prev_frame, current_frame)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        
        # 如果变化像素超过阈值，认为有活动
        motion_ratio = np.count_nonzero(thresh) / thresh.size
        self._prev_frame = current_frame
        
        return motion_ratio > VideoConfig.ACTIVITY_THRESHOLD

    async def generate_activity_record(self, current_time: datetime, frame: np.ndarray) -> Optional[Dict]:
        """生成活动记录"""
        # 简化实现，避免使用未定义的变量
        if not hasattr(self, 'last_activity_time'):
            self.last_activity_time = None
        
        # 避免过于频繁的记录
        if (self.last_activity_time is None or 
            (current_time - self.last_activity_time).total_seconds() > VideoConfig.ANALYSIS_INTERVAL):
            
            self.last_activity_time = current_time
            
            # 这里可以添加更多的分析逻辑，比如目标检测等
            activity_type = "活动"  # 可以根据实际检测结果修改
            
            return {
                'timestamp': current_time.strftime('%Y年%m月%d日%H点%M分'),
                'content': f"监控显示：{current_time.strftime('%Y年%m月%d日%H点%M分')}，检测到{activity_type}",
                'frames': self.analysis_frames[-int(VideoConfig.BUFFER_DURATION):]
            }
        return None

    def clean_buffer(self, current_time: datetime):
        """清理过期的帧"""
        # 简化实现，使用已有的分析帧列表
        max_frames = int(VideoConfig.BUFFER_DURATION)
        if len(self.analysis_frames) > max_frames:
            self.analysis_frames = self.analysis_frames[-max_frames:]
            self.analysis_timestamps = self.analysis_timestamps[-max_frames:] 