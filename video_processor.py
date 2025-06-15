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
from config import VideoConfig, OSSConfig, RAGConfig
import oss2
from utility import frames_to_video_oss


class VideoProcessor:
    def __init__(self, video_source: Union[int, str]):
        self.video_source = video_source
        self.is_camera = isinstance(video_source, int)

        # 添加frame_queue属性
        self.frame_queue = queue.Queue()

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

        # 消息队列
        self.alert_queue = queue.Queue()

        # 分析器 (注入预警队列)
        self.analyzer = MultiModalAnalyzer(alert_queue=self.alert_queue)

        # 创建摄像头线程
        self.webcam_thread = threading.Thread(target=self._process_webcam)
        self.webcam_thread.daemon = True

        self.start_push_queue = 0

        # 添加活动追踪相关属性
        self.current_activity = None  # 当前正在进行的活动
        self.activity_start_time = None  # 活动开始时间
        self.activity_start_image_url = None  # 活动开始时的图片URL
        self.activity_start_video_url = None  # 活动开始时的视频URL
        self.last_activity_time = None  # 最后一次检测到活动的时间
        self.activity_threshold = 10  # 活动结束判定阈值（秒）
        
        # 添加已发送预警的跟踪集合，用于去重
        self.sent_alerts = set()

    async def start_processing(self):
        """启动处理"""
        try:
            # 增加日志输出
            self.init_video_capture()
            
            self.running = True
            self.webcam_thread.start()
            asyncio.create_task(self._process_alerts())
            while self.running:
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"视频处理错误: {e}")
            time.sleep(0.1)

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

                # 添加到帧队列，用于WebSocket传输
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, VideoConfig.JPEG_QUALITY])
                try:
                    # 如果队列满，清空旧帧
                    if self.frame_queue.qsize() > 10:  # 保持帧队列不过长
                        while not self.frame_queue.empty():
                            try:
                                self.frame_queue.get_nowait()
                            except queue.Empty:
                                break
                    self.frame_queue.put_nowait(buffer.tobytes())
                except Exception as e:
                    logging.error(f"添加帧到队列出错: {e}")

            except Exception as e:
                logging.error(f"视频处理错误: {e}")
                time.sleep(0.1)

    def _run_analysis(self, frames, timestamps):
        """在单独的线程中运行异常分析"""
        try:
            self.processing = True
            print("开始分析视频片段")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self.analyzer.analyze(frames, self.fps, timestamps)
            )
            
            # --- 旧的预警系统逻辑已由 multi_modal_analyzer 接管 ---
            # --- 下方的代码块将被注释掉或移除 ---
            
            # current_time = datetime.now()
            
            # # 定义允许触发预警的活动类型
            # allowed_activities = {
            #     "睡觉", "玩手机", "喝饮料", "喝水", "吃东西", "专注工作学习",
            #     "发现明火", "人员聚集", "打架斗殴"
            # }

            # # 如果结果是字符串且不是"正常"
            # if isinstance(result, str) and result and result != "正常":
            #     # 尝试从结果中提取行为 (假设格式为 "时间 情况")
            #     parts = result.split()
            #     behavior = parts[-1] if len(parts) > 1 else result # 获取最后一个词作为行为
                
            #     # 检查提取的行为是否在允许列表中
            #     if behavior in allowed_activities:
            #         logging.info(f"检测到允许的活动: {behavior}")
            #         # 此处原有的活动持续时间判断和 alert_queue.put(alert) 逻辑
            #         # 已全部转移到 multi_modal_analyzer.py 中实现
            #     else:
            #         # 如果检测到的行为不在允许列表中，记录日志但不生成预警
            #         logging.info(f"检测到非预警活动: {behavior} (原始结果: {result})，不生成预警。")

            # elif self.current_activity is not None:
            #     # 检查是否需要结束当前活动 (即使当前检测为'正常'或非允许活动)
            #     # 此部分逻辑也已转移
            #     pass

            loop.close()

        except Exception as e:
            logging.error(f"分析错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.processing = False

    def _run_async_task(self, coro):
        """在合适的事件循环中运行异步任务"""
        try:
            # 如果有活动的事件循环，则使用它
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(coro)
            else:
                # 否则直接运行协程
                loop.run_until_complete(coro)
        except RuntimeError:
            # 如果没有事件循环，创建一个新的
            logging.info("创建新的事件循环处理异步任务")
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
                
    def _end_current_activity(self, frames, timestamps):
        """结束当前活动并发送持续时间预警"""
        # --- 旧的预警系统逻辑已由 multi_modal_analyzer 接管 ---
        # --- 此方法不再需要，其功能已合并到 multi_modal_analyzer ---
        pass
        
        # if self.current_activity and self.activity_start_time:
        #     end_time = self.last_activity_time or datetime.now()
        #     duration = (end_time - self.activity_start_time).total_seconds()
        #     duration_minutes = round(duration / 60, 1) # 保留一位小数

        #     # 定义允许触发预警的活动类型 (与 _run_analysis 一致)
        #     allowed_activities = {
        #         "睡觉", "玩手机", "喝饮料", "喝水", "吃东西", "专注工作学习",
        #         "发现明火", "人员聚集", "打架斗殴"
        #     }

        #     # 只有当活动类型在允许列表内，且持续时间超过阈值(例如0.1分钟)才发送结束预警
        #     if self.current_activity in allowed_activities and duration_minutes >= 0.1:
        #         alert_key = f"{self.current_activity}_{self.activity_start_time.strftime('%Y-%m-%d %H:%M:%S')}_{end_time.strftime('%Y-%m-%d %H:%M:%S')}"
        #         logging.info(f"尝试生成结束预警，Key: {alert_key}, 当前 sent_alerts 数量: {len(self.sent_alerts)}")

        #         if alert_key not in self.sent_alerts:
        #             self.sent_alerts.add(alert_key)
        #             logging.info(f"添加 Key 到 sent_alerts: {alert_key}")

        #             # 使用活动开始时保存的图片和视频，确保预警信息与图片匹配
        #             image_url = self.activity_start_image_url
        #             video_url = self.activity_start_video_url


        #             alert = {
        #                 "type": "alert",
        #                 "timestamp": end_time.strftime('%Y-%m-%d %H:%M:%S'),
        #                 "content": f"{self.current_activity}结束", # 更简洁的内容
        #                 "start_time": self.activity_start_time.strftime('%Y-%m-%d %H:%M:%S'),
        #                 "end_time": end_time.strftime('%Y-%m-%d %H:%M:%S'),
        #                 "duration_minutes": duration_minutes,
        #                 "level": "normal", # 结束预警通常为 normal
        #                 "image_url": image_url,
        #                 "video_url": video_url,
        #                 "alert_key": alert_key,
        #                 "activity_id": f"{self.current_activity}_{int(self.activity_start_time.timestamp())}" # 活动唯一ID
        #             }
        #             self.alert_queue.put(alert)
        #             # 结束预警通常不需要存入向量数据库，因为它只是对开始预警的补充
        #             # self._run_async_task(self._add_to_vector_db(alert, alert["timestamp"]))
        #         else:
        #             logging.info(f"预警已存在，不重复发送: {alert_key}")
        #     else:
        #          logging.info(f"活动 '{self.current_activity}' 不在允许列表或持续时间 ({duration_minutes} 分钟) 过短，不发送结束预警。")


        #     # 重置活动追踪状态
        #     logging.info(f"重置活动追踪状态，原活动: {self.current_activity}")
        #     self.current_activity = None
        #     self.activity_start_time = None
        #     self.activity_start_image_url = None
        #     self.activity_start_video_url = None
        #     self.last_activity_time = None

    async def video_streamer(self, websocket):
        while True:
            try:
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    logging.info("WebSocket已断开连接")
                    break
                
                if self.frame_queue.empty():
                    await asyncio.sleep(0.1)
                    continue
                
                frame = self.frame_queue.get_nowait()
                await websocket.send_bytes(frame)
            except Exception as e:
                logging.error(f"视频流发送错误: {e}")
                break

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
        """获取视频帧"""
        try:
            # 获取当前帧
            with self.display_lock:
                if self.display_frame is None:
                    return None
                frame = self.display_frame.copy()

            # 编码视频帧
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, VideoConfig.JPEG_QUALITY])
            
            return buffer.tobytes()

        except Exception as e:
            logging.error(f"获取帧数据时出错: {e}")
            return None

    def init_video_capture(self):
        """初始化或重新初始化视频捕获"""
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
        
        if self.is_camera:
            self.cap = cv2.VideoCapture(self.video_source, cv2.CAP_DSHOW)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, VideoConfig.CAMERA_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VideoConfig.CAMERA_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, VideoConfig.FPS)
        else:
            self.cap = cv2.VideoCapture(self.video_source)
        
        if not self.cap.isOpened():
            raise ValueError(f"无法打开视频源: {self.video_source}")
        logging.info(f"视频捕获已初始化: {self.video_source}")

    def upload_to_oss(self, image, object_key=None):
        """上传图像到阿里云OSS并返回URL"""
        if object_key is None:
            object_key = f"{OSSConfig.ALERT_PREFIX}alert_{int(time.time())}.jpg"
        
        try:
            # 创建OSS连接
            auth = oss2.Auth(OSSConfig.ACCESS_KEY_ID, OSSConfig.ACCESS_KEY_SECRET)
            bucket = oss2.Bucket(auth, OSSConfig.ENDPOINT, OSSConfig.BUCKET)
            
            # 编码图像并上传
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, VideoConfig.JPEG_QUALITY])
            bucket.put_object(object_key, buffer.tobytes())
            
            # 生成URL
            url = f"https://{OSSConfig.BUCKET}.{OSSConfig.ENDPOINT}/{object_key}"
            return url
        except Exception as e:
            # 不再回退到本地存储，直接抛出异常
            logging.error(f"上传到OSS失败: {e}")
            raise Exception(f"上传到OSS失败: {e}")

    async def _add_to_vector_db(self, alert, event_timestamp: str):
        """将预警信息添加到向量数据库"""
        try:
            import httpx
            
            # 检查alert内容是否为系统错误等，避免存入数据库
            # （在 _run_analysis 中已过滤，这里可作为双重保险，但暂时省略）
            allowed_activities = {
                "睡觉", "玩手机", "喝饮料", "喝水", "吃东西", "专注工作学习",
                "发现明火", "人员聚集", "打架斗殴"
            }
            activity_content = alert['content'].replace('开始', '').replace('结束', '').split('，')[0] # 提取核心活动内容
            
            if activity_content not in allowed_activities:
                 logging.info(f"预警内容 '{activity_content}' 不属于定义活动，跳过添加到向量数据库。")
                 return

            # 提取预警文本内容
            alert_text = f"{alert['timestamp']} - {alert['content']}"
            if 'start_time' in alert and 'end_time' in alert:
                alert_text += f"，从{alert['start_time']}持续到{alert['end_time']}，共{alert.get('duration_minutes', 0)}分钟"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    RAGConfig.VECTOR_API_URL,
                    json={
                        "docs": [alert_text],
                        "table_name": f"alert_{int(time.time())}",
                        "event_timestamps": [event_timestamp]
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logging.info(f"预警信息已添加到向量数据库: {alert_text}")
                else:
                    logging.error(f"添加到向量数据库失败: {response.text}")
        except Exception as e:
            logging.error(f"添加预警到向量数据库出错: {e}")

