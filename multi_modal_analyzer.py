# -*- coding: utf-8 -*-
"""
Created on Mon Feb 17 12:03:32 2025

@author: 18523
"""

import base64
import requests
import cv2 
import time 
import numpy as np
import time
import json
import httpx
import os
import datetime
import asyncio
from typing import List, Tuple, Dict
import logging

from utility import video_chat_async,chat_request,insert_txt,video_chat_async_limit_frame
from config import RAGConfig

# 导入双数据库组件 (仅SQLite部分)
from video_database import video_db

# --------------------------------------------------------------------------------
# [重构] 移除所有ChromaDB相关的代码，该模块不再直接与向量数据库交互。
# 移除 VideoVectorManager 类，因为它现在由 rag_server.py 统一管理。
# --------------------------------------------------------------------------------

async def add_activity_to_vector_db_via_api(activity_id: int, activity_data: Dict) -> bool:
    """
    [新] 通过调用rag_server的API将活动添加到向量数据库。
    """
    try:
        # 从配置中获取RAG服务器的地址
        # 假设RAG服务器运行在 http://localhost:8085
        # 你可能需要将此URL移动到config.py中
        rag_server_url = "http://localhost:8085/add_activity/"

        payload = {
            "activity_id": activity_id,
            "activity_data": activity_data
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(rag_server_url, json=payload)
        
        if response.status_code == 200:
            logging.info(f"活动 {activity_id} 已成功通过API发送到向量数据库。")
            return True
        else:
            logging.error(
                f"通过API发送活动到向量数据库失败: "
                f"状态码 {response.status_code}, 响应: {response.text}"
            )
            return False
            
    except Exception as e:
        logging.error(f"调用向量数据库API时发生网络或未知错误: {e}", exc_info=True)
        return False

# 全局向量管理器实例 (移除)
# video_vector_manager = VideoVectorManager()

from prompt import prompt_detect, prompt_vieo
from llm_service import chat_completion

class MultiModalAnalyzer:
    def __init__(self, alert_queue=None):
        self.message_queue = []
        self.time_step_story = []
        self.alert_queue = alert_queue
        
        # 智能活动跟踪器配置
        self.current_activities = {}  # {activity_type: {activity_id, start_time, last_update}}
        self.activity_configs = {
            "睡觉": {"max_gap": 999999, "min_duration": 0},      # 无时间间隔限制
            "专注工作学习": {"max_gap": 999999, "min_duration": 0},   # 无时间间隔限制
            "玩手机": {"max_gap": 999999, "min_duration": 0},       # 无时间间隔限制
            "吃东西": {"max_gap": 999999, "min_duration": 0},      # 无时间间隔限制
            "喝水": {"max_gap": 999999, "min_duration": 0},      # 无时间间隔限制
            "喝饮料": {"max_gap": 999999, "min_duration": 0}       # 无时间间隔限制
        }

    def trans_date(self,date_str):
        # Split the input string into components
        year, month, day, hour, minute, second = date_str.split('-')
        
        # Determine AM or PM
        am_pm = "上午" if int(hour) < 12 else "下午"
        
        # Convert 24-hour format to 12-hour format
        hour_12 = hour if hour == '12' else str(int(hour) % 12)
        
        # Return the formatted date and time string
        return f"{year}年{int(month)}月{int(day)}日{am_pm}{hour_12}点（{hour}时）{int(minute)}分{int(second)}秒"
    
    async def analyze(self, frames, fps=None, timestamps=None):
        """分析视频内容并返回结果"""
        start_time = time.time()
        
        # 获取当前视频片段的分析结果
        result = await self.analyze_video(frames, fps, timestamps)
        
        # 直接返回分析结果
        return result

    def generate_description(self, activity_type: str, timestamp: str) -> str:
        """生成活动描述"""
        return f"监控显示：{timestamp}，{activity_type}"

    def detect_activity(self, frames: List[np.ndarray]) -> bool:
        """检测画面中是否有活动"""
        if len(frames) < 2:
            return False
            
        # 使用帧差法检测运动
        frame1 = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
        frame2 = cv2.cvtColor(frames[-1], cv2.COLOR_BGR2GRAY)
        
        # 计算帧差
        diff = cv2.absdiff(frame1, frame2)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        
        # 如果变化像素超过阈值，认为有活动
        change_ratio = np.count_nonzero(thresh) / thresh.size
        return change_ratio > 0.01

    async def analyze_activity(self, frames: List[np.ndarray]) -> str:
        """分析活动类型，调用大模型进行视频描述"""
        try:
            # 调用原有的视频分析方法获取描述
            description = await self.analyze_video(frames)
            return description
        except Exception as e:
            logging.error(f"活动分析失败: {str(e)}")
            return "未知活动"

    async def process_activity_detection(self, activity_type: str, timestamp: str, image_path: str = None, custom_level: str = None):
        """处理活动检测结果，实现智能活动跟踪"""
        try:
            # 解析检测结果 - 已通过参数传入，不再需要解析
            activity_type = activity_type.strip()
            
            # 修复时间格式不匹配的问题
            # 将连字符格式的时间戳转换为标准格式
            if '-' in timestamp and ':' not in timestamp:
                # 从 '2025-06-10-20-15-45' 转换为 '2025-06-10 20:15:45'
                timestamp_parts = timestamp.split('-')
                if len(timestamp_parts) == 6:
                    date_part = f"{timestamp_parts[0]}-{timestamp_parts[1]}-{timestamp_parts[2]}"
                    time_part = f"{timestamp_parts[3]}:{timestamp_parts[4]}:{timestamp_parts[5]}"
                    timestamp = f"{date_part} {time_part}"
                    logging.info(f"时间戳格式已转换: {timestamp}")
            
            # 检查活动类型是否在配置中
            if activity_type not in self.activity_configs:
                # 如果是新的活动类型，直接记录
                activity_data = {
                    'activity_type': activity_type,
                    'content': f"检测到{activity_type}",
                    'start_time': timestamp,
                    'end_time': None,
                    'duration_minutes': 0,
                    'confidence_score': 0.8,
                    'image_path': image_path,
                    'metadata': {
                        'detection_method': 'video_analysis',
                        'source': 'multi_modal_analyzer'
                    },
                    'source_type': 'activity_detection'
                }
                
                activity_id = video_db.insert_activity(activity_data)
                if activity_id:
                    # [修改] 调用新的API函数
                    await add_activity_to_vector_db_via_api(activity_id, activity_data)
                    logging.info(f"新活动已记录: {activity_type}")
                return activity_id
            
            # 智能活动跟踪逻辑
            config = self.activity_configs[activity_type]
            current_time = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            
            # 检查是否存在正在进行的同类活动
            if activity_type in self.current_activities:
                last_activity = self.current_activities[activity_type]
                last_time = datetime.datetime.strptime(last_activity['last_update'], '%Y-%m-%d %H:%M:%S')
                time_gap = (current_time - last_time).total_seconds()
                
                if time_gap <= config['max_gap']:
                    # 延续现有活动，不发送新预警
                    self.current_activities[activity_type]['last_update'] = timestamp
                    logging.info(f"活动延续: {activity_type}, 间隔{time_gap}秒")
                    return last_activity['activity_id']
                else:
                    # 结束旧活动，开始新活动
                    await self._finish_activity(activity_type, last_time, config)
            
            # 检查并结束其他正在进行的活动（一次只能有一个活动）
            for other_activity_type in list(self.current_activities.keys()):
                if other_activity_type != activity_type:
                    await self._finish_activity(other_activity_type, current_time, self.activity_configs[other_activity_type])
            
            # 确定预警级别
            alert_level = custom_level or self._get_activity_level(activity_type)
            
            # 开始新的活动
            activity_data = {
                'activity_type': activity_type,
                'content': f"开始{activity_type}",
                'start_time': timestamp,
                'end_time': None,
                'duration_minutes': 0,
                'confidence_score': 0.9,
                'image_path': image_path,
                'metadata': {
                    'detection_method': 'intelligent_tracking',
                    'source': 'multi_modal_analyzer'
                },
                'source_type': 'activity_tracking'
            }
            
            activity_id = video_db.insert_activity(activity_data)
            if activity_id:
                self.current_activities[activity_type] = {
                    'activity_id': activity_id,
                    'start_time': timestamp,
                    'last_update': timestamp,
                    'level': alert_level  # 保存级别信息
                }
                # [修改] 调用新的API函数
                await add_activity_to_vector_db_via_api(activity_id, activity_data)
                
                # 发送活动开始预警
                await self._send_activity_start_alert(activity_type, timestamp, alert_level, activity_id, image_path)
                
                logging.info(f"新活动开始: {activity_type}, ID={activity_id}, 级别={alert_level}")
            
            return activity_id
            
        except Exception as e:
            logging.error(f"处理活动检测结果失败: {e}")
            return None
    
    async def _finish_activity(self, activity_type: str, end_time: datetime.datetime, config: dict):
        """结束一个活动并更新持续时间"""
        if activity_type not in self.current_activities:
            return
            
        activity_info = self.current_activities[activity_type]
        start_time = datetime.datetime.strptime(activity_info['start_time'], '%Y-%m-%d %H:%M:%S')
        duration_minutes = (end_time - start_time).total_seconds() / 60
        
        # 无论持续时间长短，都更新数据库中的结束时间和持续时长
        video_db.update_activity_end_time(
            activity_info['activity_id'],
            end_time.strftime('%Y-%m-%d %H:%M:%S'),
            duration_minutes
        )
        
        # 确定预警级别 - 从活动信息中获取或使用默认值
        alert_level = activity_info.get('level', self._get_activity_level(activity_type))
        
        # 检查是否是自定义规则
        system_activities = {"睡觉", "专注工作学习", "玩手机", "吃东西", "喝水", "喝饮料"}
        is_custom = activity_type not in system_activities
        
        # 生成活动结束预警，显示持续时间
        try:
            end_alert = {
                "type": "custom_activity_end" if is_custom else "activity_end",
                "timestamp": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                "content": f"{activity_type}结束",
                "start_time": activity_info['start_time'],
                "end_time": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                "duration_minutes": duration_minutes,
                "level": alert_level,
                "activity_id": activity_info['activity_id'],
                "alert_key": f"{activity_type}_结束_{end_time.strftime('%Y-%m-%d %H:%M:%S')}",
                "is_custom": is_custom  # 添加标识字段
            }
            
            # 这里需要将结束预警发送到预警队列
            # 由于架构限制，可以尝试通过导入获取alert_queue
            try:
                if self.alert_queue:
                    self.alert_queue.put(end_alert)
                    logging.info(f"活动结束预警已发送: {activity_type}, 持续{duration_minutes:.1f}分钟")
                else:
                    logging.warning("Alert queue is not available, a活动结束预警未发送")
            except Exception as e:
                logging.warning(f"发送结束预警失败: {e}")
                
        except Exception as e:
            logging.error(f"生成结束预警失败: {e}")
        
        logging.info(f"活动结束: {activity_type}, 持续{duration_minutes:.1f}分钟")
        
        # 从当前活动中移除
        del self.current_activities[activity_type]
    
    def _get_activity_level(self, activity_type: str) -> str:
        """获取活动的预警级别"""
        # 系统预设活动的级别映射
        level_mapping = {
            "睡觉": "high",
            "专注工作学习": "low", 
            "玩手机": "high",
            "吃东西": "high",
            "喝水": "high",
            "喝饮料": "high"
        }
        
        # 返回对应级别，自定义活动默认为 medium
        return level_mapping.get(activity_type, "medium")
    
    async def _send_activity_start_alert(self, activity_type: str, timestamp: str, level: str, activity_id: int, image_path: str = None):
        """发送活动开始预警"""
        try:
            print(f"\n📤 准备发送活动开始预警: {activity_type}, 级别={level}, ID={activity_id}")
            
            # 检查是否是自定义规则（不在系统预设活动中）
            system_activities = {"睡觉", "专注工作学习", "玩手机", "吃东西", "喝水", "喝饮料"}
            is_custom = activity_type not in system_activities
            
            start_alert = {
                "type": "custom_activity_start" if is_custom else "activity_start",
                "timestamp": timestamp,
                "content": f"{activity_type}",  # 开始时不显示"开始"字样
                "level": level,
                "activity_id": activity_id,
                "start_time": timestamp,
                "end_time": None,
                "duration_minutes": 0,
                "image_url": f"/video_warning/{os.path.basename(image_path)}" if image_path else None,
                "video_url": None,  # 开始预警通常没有视频
                "alert_key": f"{activity_type}_{timestamp}",
                "is_custom": is_custom  # 添加标识字段
            }
            
            print(f"📋 构造的预警消息: {start_alert}")
            
            # 发送到预警队列
            try:
                print(f"🔄 尝试发送到预警队列...")
                if self.alert_queue:
                    self.alert_queue.put(start_alert)
                    print(f"✅ 活动开始预警已成功发送到队列: {activity_type}, 级别={level}")
                    logging.info(f"活动开始预警已发送: {activity_type}, 级别={level}")
                else:
                    print(f"❌ Alert queue is not available, a开始预警未发送")
                    logging.warning("Alert queue is not available, 开始预警未发送")
            except Exception as e:
                print(f"❌ 发送开始预警失败: {e}")
                logging.warning(f"发送开始预警失败: {e}")
                
        except Exception as e:
            print(f"❌ 生成开始预警失败: {e}")
            logging.error(f"生成开始预警失败: {e}")

    # 添加DeepSeek关键信息提取函数
    async def extract_key_points(self, text, context="视频监控预警"):
        """使用DeepSeek提取关键信息"""
        try:
            # 使用DeepSeek提取关键信息
            prompt = f"""
            请从以下视频监控描述中提取关键信息，保留最重要的行为、人物和环境细节，以简洁的形式呈现:
            ```
            {text}
            ```
            只需返回提取后的简洁要点，不要多余解释。
            """
            
            # 调用DeepSeek模型
            # 注意：这里假设llm_service中已有适当的函数，如果没有需要添加
            key_points = await chat_completion(prompt, model="deepseek")
            
            # 如果提取结果太长，进一步截断
            if len(key_points) > 100:
                key_points = key_points[:100] + "..."
            
            return key_points
        except Exception as e:
            print(f"关键信息提取错误: {e}")
            return text[:100] + "..." if len(text) > 100 else text

    async def analyze_video(self, frames, fps=20, timestamps=None):
        """分析视频片段内容"""
        start_time = time.time()
        
        try:
            # 获取视频描述
            description = await video_chat_async_limit_frame(prompt_vieo, frames, timestamps, fps=fps, use_oss=True)
            print(f"\n📹 视频描述原文：{description}")
            
            # 如果时间戳有效，将描述存入双数据库
            if timestamps is not None:
                await self.store_video_summary(description, timestamps)
            
            if timestamps is None:
                return description
            
            # 应用用户自定义预警规则检测（仅处理用户创建的规则，不包括系统预设规则）
            custom_alerts = await self.apply_custom_alert_rules(description, timestamps[0])
            
            # 标志位，表示是否已处理一个预警
            alert_processed_in_cycle = False

            # 优先处理自定义预警
            if custom_alerts:
                print(f"\n🔔 用户自定义规则触发，优先处理: {len(custom_alerts)}个规则")
                for custom_alert in custom_alerts:
                    print(f"   - {custom_alert['rule_name']}: {custom_alert['condition']}")
                    await self.process_custom_alert(custom_alert, timestamps[0], frames)
                alert_processed_in_cycle = True # 标记已处理

            # 如果没有处理自定义预警，再处理标准检测
            if not alert_processed_in_cycle:
                # 首先进行标准的异常检测
                detect_prompt = prompt_detect.format(
                    description=description,
                    time=timestamps[0]
                )
                
                # 调用DeepSeek进行标准检测
                detection_result_raw = await chat_completion(detect_prompt, model="deepseek")
                
                # 检查返回结果是否表示错误
                if isinstance(detection_result_raw, str) and detection_result_raw.startswith("错误："):
                    print(f"\n❌ 异常检测失败：{detection_result_raw}")
                    return "分析失败" 
                elif detection_result_raw is None:
                    print(f"\n❌ 异常检测失败：返回结果为 None")
                    return "分析失败"
                
                # 标准检测结果处理
                detection_result = detection_result_raw.strip()
                print(f"\n🎯 标准异常检测结果：{detection_result}")

                # 使用智能活动跟踪处理标准检测结果
                if detection_result != "分析失败" and detection_result != "未检测到特定活动":
                    # 解析活动类型和时间戳
                    parts = detection_result.split(' ', 1)
                    if len(parts) == 2:
                        activity_type = parts[1]
                        
                        try:
                            # 保存关键帧
                            image_path = None
                            if frames:
                                image_path = f"video_warning/activity_{int(time.time())}.jpg"
                                os.makedirs("video_warning", exist_ok=True)
                                cv2.imwrite(image_path, frames[-1])
                            
                            # 使用智能活动跟踪
                            activity_id = await self.process_activity_detection(
                                activity_type, timestamps[0], image_path
                            )
                            
                            if activity_id:
                                print(f"📊 标准检测活动已记录到双数据库: ID={activity_id}")
                            
                        except Exception as e:
                            logging.error(f"活动跟踪处理失败: {e}")
                    else:
                        logging.warning(f"无法从结果中解析活动类型: {detection_result}")
                
                return detection_result
            else:
                # 如果处理了自定义预警，则返回自定义预警的结果作为本次分析的主要结果
                return f"自定义预警: {', '.join([a['rule_name'] for a in custom_alerts])}"
            
        except Exception as e:
            print(f"❌ 视频分析错误: {e}")
            import traceback
            traceback.print_exc()
            return f"分析出错: {str(e)}"

    async def apply_custom_alert_rules(self, description, timestamp):
        """应用自定义预警规则进行检测"""
        try:
            # 获取当前激活的自定义规则（这里需要从video_server获取）
            # 由于架构限制，我们先创建一个简化的实现
            all_rules = await self.get_active_custom_rules()
            
            # 过滤掉系统预设规则，只处理真正的用户自定义规则
            custom_rules = [rule for rule in all_rules if not rule.get('is_system_rule', False)]
            
            if not custom_rules:
                logging.debug("没有启用的用户自定义规则")
                return []
            
            triggered_alerts = []
            
            for rule in custom_rules:
                if not rule.get('enabled', False):
                    continue
                
                # 使用生成的提示词进行检测
                custom_prompt = rule.get('generated_prompt', '')
                if not custom_prompt:
                    continue
                
                # 将当前视频描述和时间戳插入到自定义提示词中
                detection_prompt = f"""
                {custom_prompt}
                
                当前视频描述：{description}
                当前时间：{timestamp}
                
                请根据规则检测是否触发预警，如果触发请返回："{timestamp} {rule['name']}"
                如果未触发请返回："未检测到"
                """
                
                try:
                    logging.info(f"🔍 检测自定义规则: {rule['name']}")
                    custom_result = await chat_completion(detection_prompt, model="deepseek")
                    logging.info(f"🤖 LLM检测结果: '{custom_result}'")
                    
                    if custom_result and custom_result.strip() != "未检测到" and rule['name'] in custom_result:
                        triggered_alerts.append({
                            'rule_id': rule['id'],
                            'rule_name': rule['name'],
                            'condition': rule['condition'],
                            'level': rule['level'],
                            'detection_result': custom_result.strip(),
                            'timestamp': timestamp
                        })
                        logging.info(f"✅ 用户自定义规则触发: {rule['name']}")
                    else:
                        logging.info(f"❌ 自定义规则未触发: {rule['name']} (结果: '{custom_result}')")
                        
                except Exception as e:
                    logging.error(f"执行自定义规则检测失败 [{rule['name']}]: {e}")
            
            if triggered_alerts:
                logging.info(f"本次共触发{len(triggered_alerts)}个用户自定义规则")
            
            return triggered_alerts
            
        except Exception as e:
            logging.error(f"应用自定义预警规则失败: {e}")
            return []

    async def get_active_custom_rules(self):
        """获取当前激活的自定义规则（简化实现）"""
        try:
            # 这是一个简化的实现，实际应用中应该从global变量或数据库获取
            # 由于模块间的耦合问题，这里使用一个简化的方法
            import httpx
            
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get("http://localhost:16532/api/custom-alert-rules", timeout=5.0)
                    if response.status_code == 200:
                        data = response.json()
                        return data.get('rules', [])
                except:
                    pass
            
            # 如果无法获取，返回空列表
            return []
            
        except Exception as e:
            logging.warning(f"获取自定义规则失败: {e}")
            return []

    async def process_custom_alert(self, custom_alert, timestamp, frames):
        """处理自定义预警 - 使用智能活动跟踪系统"""
        try:
            print(f"\n🔧 开始处理自定义预警: {custom_alert}")
            
            # 修复时间戳格式，将连字符格式转换为标准格式
            formatted_timestamp = timestamp
            if '-' in timestamp and ':' not in timestamp:
                # 从 '2025-06-12-14-08-48' 转换为 '2025-06-12 14:08:48'
                timestamp_parts = timestamp.split('-')
                if len(timestamp_parts) == 6:
                    date_part = f"{timestamp_parts[0]}-{timestamp_parts[1]}-{timestamp_parts[2]}"
                    time_part = f"{timestamp_parts[3]}:{timestamp_parts[4]}:{timestamp_parts[5]}"
                    formatted_timestamp = f"{date_part} {time_part}"
                    print(f"🕒 自定义预警时间戳格式已转换: {formatted_timestamp}")
                    logging.info(f"自定义预警时间戳格式已转换: {formatted_timestamp}")
            
            # 保存预警相关的图像
            image_path = None
            if frames:
                timestamp_str = formatted_timestamp.replace(':', '-').replace(' ', '-')
                alert_id = f"custom_{custom_alert['rule_id']}_{timestamp_str}"
                image_path = f"video_warning/{alert_id}.jpg"
                os.makedirs("video_warning", exist_ok=True)
                cv2.imwrite(image_path, frames[-1])
                print(f"📸 自定义预警图片已保存: {image_path}")
                logging.info(f"自定义预警图片已保存: {image_path}")
            
            # 📌 关键：使用智能活动跟踪系统处理自定义预警
            activity_type = custom_alert['rule_name']
            print(f"🎯 准备处理自定义活动: {activity_type}, 级别: {custom_alert['level']}")
            
            # 将自定义规则添加到活动配置中（如果不存在）
            if activity_type not in self.activity_configs:
                self.activity_configs[activity_type] = {
                    "max_gap": 999999,  # 与系统预设规则保持一致
                    "min_duration": 0
                }
                print(f"➕ 为自定义规则添加活动配置: {activity_type}")
                logging.info(f"为自定义规则添加活动配置: {activity_type}")
            
            # 构造检测结果格式，使其兼容智能活动跟踪
            detection_result = f"{formatted_timestamp} {activity_type}"
            print(f"🔄 构造的检测结果: '{detection_result}'")
            
            # 使用现有的智能活动跟踪系统处理，传递自定义级别
            print(f"🔄 调用智能活动跟踪...")
            activity_id = await self.process_activity_detection(
                activity_type, formatted_timestamp, image_path, custom_alert['level']
            )
            
            if activity_id:
                print(f"✅ 自定义规则活动已通过智能跟踪处理: {activity_type}, ID={activity_id}")
                logging.info(f"✅ 自定义规则活动已通过智能跟踪处理: {activity_type}, ID={activity_id}")
            else:
                print(f"⚠️ 自定义规则活动跟踪处理失败: {activity_type}")
                logging.warning(f"⚠️ 自定义规则活动跟踪处理失败: {activity_type}")
            
            return activity_id
            
        except Exception as e:
            print(f"❌ 处理自定义预警失败: {e}")
            logging.error(f"处理自定义预警失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def send_custom_alert(self, alert_message):
        """发送自定义预警到系统"""
        try:
            print(f"🚨 正在发送自定义预警: {alert_message.get('content', 'Unknown')}")
            
            # 直接访问全局的video_processor实例来发送预警
            import video_server
            
            print(f"🔍 检查video_server模块: hasattr(video_server, 'video_processor') = {hasattr(video_server, 'video_processor')}")
            
            if hasattr(video_server, 'video_processor'):
                print(f"🔍 video_processor实例: {video_server.video_processor}")
                if video_server.video_processor:
                    print(f"🔍 alert_queue是否存在: {hasattr(video_server.video_processor, 'alert_queue')}")
                    if hasattr(video_server.video_processor, 'alert_queue'):
                        # 直接将预警放入队列
                        video_server.video_processor.alert_queue.put(alert_message)
                        print(f"✅ 自定义预警已成功发送到队列: {alert_message.get('content', 'Unknown')}")
                        logging.info(f"自定义预警已发送到队列: {alert_message.get('content', 'Unknown')}")
                        return True
                    else:
                        print(f"❌ video_processor没有alert_queue属性")
                        logging.error("video_processor没有alert_queue属性")
                        return False
                else:
                    print(f"❌ video_processor实例为None")
                    logging.error("video_processor实例为None")
                    return False
            else:
                print(f"❌ video_server模块没有video_processor属性")
                logging.error("video_server模块没有video_processor属性")
                return False
                    
        except Exception as e:
            print(f"❌ 发送自定义预警异常: {e}")
            logging.error(f"发送自定义预警失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def store_video_summary(self, description, timestamp):
        """将视频描述存入双数据库系统 - 简化版本，不再生成周期性总结"""
        try:
            # 添加时间信息
            formatted_time = timestamp[0]
            
            # 1. 存入SQLite主数据库
            activity_data = {
                'activity_type': '视频描述',
                'content': description,
                'start_time': formatted_time,
                'end_time': None,
                'duration_minutes': 0,
                'confidence_score': 1.0,
                'image_path': None,
                'metadata': {
                    'source': 'video_analysis',
                    'analysis_type': 'description',
                    'content_length': len(description)
                },
                'source_type': 'video_summary'
            }
            
            # 插入SQLite
            activity_id = video_db.insert_activity(activity_data)
            
            # 2. 添加到向量数据库（使用优化的文档构建）
            if activity_id:
                # [修改] 调用新的API函数
                await add_activity_to_vector_db_via_api(activity_id, activity_data)
                logging.info(f"视频描述已存入双数据库: ID={activity_id}")
            
            # 3. 保留原有的RAG服务器兼容性（仅为视频描述）
            try:
                import httpx
                from config import RAGConfig
                
                summary = f"{formatted_time} - {description}"
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        RAGConfig.VECTOR_API_URL,
                        json={
                            "docs": [summary],
                            "collection_name": "text_summaries",
                            "metadatas": [{"source": f"video_summary_{int(time.time())}"}]
                        },
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        logging.info(f"视频描述同时发送到RAG服务器成功")
                    else:
                        logging.warning(f"RAG服务器存储失败，但双数据库存储成功")
            except Exception as rag_error:
                logging.warning(f"RAG服务器不可用，仅使用双数据库: {rag_error}")
                    
            return True
        except Exception as e:
            logging.error(f"存储视频描述到双数据库出错: {e}")
            return False
        