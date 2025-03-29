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
            self.cap = cv2.VideoCapture(video_source, cv2.CAP_DSHOW)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, VideoConfig.CAMERA_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VideoConfig.CAMERA_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, VideoConfig.FPS)
        else:
            if not os.path.exists(video_source):
                raise ValueError(f"视频文件不存在: {video_source}")
            self.cap = cv2.VideoCapture(video_source)

        if not self.cap.isOpened():
            raise ValueError(f"无法打开视频源: {video_source}")

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

        # 添加行为检测相关属性
        self.last_behavior_time = 0
        self.behavior_interval = 2.0  # 每2秒检测一次行为，可调整

    async def start_processing(self):
        """启动处理"""
        self.running = True
        self.webcam_thread.start()
        asyncio.create_task(self._process_alerts())
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
        """主摄像头处理循环 - 包含实时行为检测"""
        last_analysis_update = time.time()
        frame_count = 0

        while self.running:
            try:
                ret, frame = self.cap.read()

                if not ret:
                    if not self.is_camera:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.cap.read()
                        if not ret:
                            time.sleep(0.1)
                            continue
                    else:
                        time.sleep(0.1)
                        continue

                current_time = time.time()
                frame_count += 1

                # 更新显示帧
                with self.display_lock:
                    self.display_frame = frame.copy()

                # 收集分析帧
                if current_time - last_analysis_update >= 1.0:
                    self.analysis_frames.append(frame.copy())
                    self.analysis_timestamps.append(datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
                    max_frames = int(VideoConfig.BUFFER_DURATION)
                    if len(self.analysis_frames) > max_frames:
                        self.analysis_frames = self.analysis_frames[-max_frames:]
                        self.analysis_timestamps = self.analysis_timestamps[-max_frames:]
                    last_analysis_update = current_time

                # 实时行为检测
                if current_time - self.last_behavior_time >= self.behavior_interval:
                    behavior_result = self._detect_behavior(frame)
                    if behavior_result:
                        alert = {
                            "type": "behavior",
                            "timestamp": datetime.now().strftime('%Y年%m月%d日%H点%M分'),
                            "content": f"检测到行为: {behavior_result['behavior']}",
                            "level": "info",
                            "details": behavior_result.get("details", ""),
                            "image_url": f"/video_warning/behavior_{int(current_time)}.jpg"
                        }
                        # 保存行为检测帧
                        cv2.imwrite(f"video_warning/behavior_{int(current_time)}.jpg", frame)
                        self.alert_queue.put(alert)
                        self.last_behavior_time = current_time

                # 触发异常分析
                if current_time - self.last_analysis >= VideoConfig.ANALYSIS_INTERVAL and not self.processing:
                    if len(self.analysis_frames) >= 2:
                        analysis_task = threading.Thread(
                            target=self._run_analysis,
                            args=(self.analysis_frames.copy(), self.analysis_timestamps.copy())
                        )
                        analysis_task.daemon = True
                        analysis_task.start()
                        self.last_analysis = current_time

                if not self.is_camera:
                    time.sleep(max(0, self.frame_interval - (time.time() - current_time)))

            except Exception as e:
                logging.error(f"视频处理错误: {e}")
                time.sleep(0.1)

    def _detect_behavior(self, frame: np.ndarray) -> Optional[Dict[str, str]]:
        """
        改进的行为检测逻辑
        返回行为代码：
        1: 专注工作
        2: 吃东西
        3: 喝水
        4: 喝饮料
        5: 玩手机
        6: 睡觉
        7: 其他
        """
        try:
            if not hasattr(self, '_prev_frame'):
                self._prev_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                return None

            current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 计算帧差
            diff = cv2.absdiff(self._prev_frame, current_frame)
            thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
            motion_ratio = np.count_nonzero(thresh) / thresh.size
            
            # 更新前一帧
            self._prev_frame = current_frame

            # 基于运动程度进行行为分类
            if motion_ratio < 0.01:  # 几乎无运动
                return {"behavior": "6", "details": "检测到睡觉行为"}
            elif motion_ratio < 0.03:  # 轻微运动
                return {"behavior": "1", "details": "检测到专注工作"}
            elif motion_ratio < 0.05:  # 中等运动
                return {"behavior": "3", "details": "检测到喝水行为"}
            elif motion_ratio < 0.08:  # 较大运动
                return {"behavior": "2", "details": "检测到吃东西行为"}
            else:  # 剧烈运动
                return {"behavior": "7", "details": "检测到其他行为"}

        except Exception as e:
            logging.error(f"行为检测错误: {e}")
            return {"behavior": "7", "details": "行为检测出错"}

    def _run_analysis(self, frames, timestamps):
        """在单独的线程中运行异常分析"""
        try:
            self.processing = True
            print("开始分析视频片段")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self.analyzer.analyze(frames, self.fps, (timestamps[0], timestamps[-1]))
            )

            if isinstance(result, dict) and result.get("type") in ["important", "warning"]:
                print(f"分析结果: {result}")
                output_filename = f"video_warning/alert_{int(time.time())}.jpg"
                cv2.imwrite(output_filename, frames[-1])

                alert_content = result["alert"] if isinstance(result["alert"], str) else str(result["alert"])
                alert = {
                    "type": "alert",
                    "timestamp": datetime.now().strftime('%Y年%m月%d日%H点%M分'),
                    "content": alert_content,
                    "level": result.get("type", "normal"),
                    "details": result.get("details", ""),
                    "image_url": f"/{output_filename}"
                }
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
                    if frame_delay > 0:
                        await asyncio.sleep(frame_delay)

                    with self.display_lock:
                        if self.display_frame is None:
                            empty_frames_count += 1
                            if empty_frames_count > 10:
                                black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                                _, buffer = cv2.imencode('.jpg', black_frame,
                                                         [cv2.IMWRITE_JPEG_QUALITY, VideoConfig.JPEG_QUALITY])
                                await websocket.send_bytes(buffer.tobytes())
                                await asyncio.sleep(0.1)
                            continue
                        frame = self.display_frame.copy()
                        empty_frames_count = 0

                    timestamp = datetime.now().strftime('%H:%M:%S')
                    cv2.putText(frame, timestamp, (frame.shape[1] - 120, frame.shape[0] - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

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
            from video_server import recent_alerts, active_connections, MAX_ALERTS

            print(f"准备发送预警: {alert}")
            print(f"当前有 {len(active_connections)} 个活跃连接")

            recent_alerts.append(alert)
            if len(recent_alerts) > MAX_ALERTS:
                recent_alerts.pop(0)

            disconnected = []
            for i, connection in enumerate(active_connections):
                try:
                    if connection.client_state == WebSocketState.CONNECTED:
                        print(f"发送到连接 {i + 1}/{len(active_connections)}")
                        await connection.send_json(alert)
                        print(f"发送成功")
                    else:
                        print(f"连接 {i + 1} 状态不是CONNECTED，而是: {connection.client_state}")
                        disconnected.append(connection)
                except Exception as e:
                    print(f"发送到连接 {i + 1} 失败: {e}")
                    disconnected.append(connection)

            for conn in disconnected:
                if conn in active_connections:
                    active_connections.remove(conn)
                    print(f"移除断开的连接，剩余 {len(active_connections)} 个")
        except Exception as e:
            print(f"警报发送过程错误: {e}")
            logging.error(f"警报发送错误: {e}")

    def detect_activity(self, frame: np.ndarray) -> bool:
        """检测画面中的活动"""
        if frame is None:
            return False

        if not hasattr(self, '_prev_frame'):
            self._prev_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return False

        current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(self._prev_frame, current_frame)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]

        motion_ratio = np.count_nonzero(thresh) / thresh.size
        self._prev_frame = current_frame

        return motion_ratio > VideoConfig.ACTIVITY_THRESHOLD

    async def generate_activity_record(self, current_time: datetime, frame: np.ndarray) -> Optional[Dict]:
        """生成活动记录"""
        if not hasattr(self, 'last_activity_time'):
            self.last_activity_time = None

        if (self.last_activity_time is None or
                (current_time - self.last_activity_time).total_seconds() > VideoConfig.ANALYSIS_INTERVAL):
            self.last_activity_time = current_time
            activity_type = "活动"

            return {
                'timestamp': current_time.strftime('%Y年%m月%d日%H点%M分'),
                'content': f"监控显示：{current_time.strftime('%Y年%m月%d日%H点%M分')}，检测到{activity_type}",
                'frames': self.analysis_frames[-int(VideoConfig.BUFFER_DURATION):]
            }
        return None

    def clean_buffer(self, current_time: datetime):
        """清理过期的帧"""
        max_frames = int(VideoConfig.BUFFER_DURATION)
        if len(self.analysis_frames) > max_frames:
            self.analysis_frames = self.analysis_frames[-max_frames:]
            self.analysis_timestamps = self.analysis_timestamps[-max_frames:]

    async def get_frame_and_behavior(self):
        """获取视频帧和行为检测结果"""
        try:
            # 获取当前帧
            with self.display_lock:
                if self.display_frame is None:
                    return None, None
                frame = self.display_frame.copy()

            current_time = time.time()
            
            # 进行行为检测
            behavior_data = None
            if current_time - self.last_behavior_time >= self.behavior_interval:
                behavior_result = self._detect_behavior(frame)
                if behavior_result:
                    behavior_data = {
                        "type": "behavior",
                        "behavior": behavior_result["behavior"],
                        "timestamp": datetime.now().isoformat(),
                        "details": behavior_result.get("details", "")
                    }
                    self.last_behavior_time = current_time

            # 编码视频帧
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, VideoConfig.JPEG_QUALITY])
            
            return buffer.tobytes(), behavior_data

        except Exception as e:
            logging.error(f"获取帧和行为数据时出错: {e}")
            return None, None

