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

# 从配置文件加载提示词
# with open('prompts.json', 'r', encoding='utf-8') as f:
#     prompts = json.load(f)

# prompt_detect = prompts['prompt_detect']
# prompt_summary = prompts['prompt_summary']
# prompt_vieo = prompts['prompt_video']

from prompt import prompt_detect,prompt_summary,prompt_vieo
from llm_service import chat_completion


class MultiModalAnalyzer:
    def __init__(self):
        self.message_queue = []
        self.time_step_story = []
        # 添加历史描述记录和最后汇总时间
        self.recent_descriptions = []
        self.last_summary_time = time.time()
        self.summary_interval = 600  # 每10分钟生成一次总结

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
            print("\n视频描述原文：", description)
            
            # 如果时间戳有效，将描述存入向量数据库
            if timestamps is not None:
                await self.store_video_summary(description, timestamps)
            
            if timestamps is None:
                return description
            
            # 使用DeepSeek进行异常检测
            detect_prompt = prompt_detect.format(
                description=description,
                time=timestamps[0]
            )
            
            # 调用DeepSeek
            detection_result_raw = await chat_completion(detect_prompt, model="deepseek")
            
            # 检查返回结果是否表示错误
            if isinstance(detection_result_raw, str) and detection_result_raw.startswith("错误："):
                print(f"\n异常检测失败：{detection_result_raw}")
                # 可以选择返回一个特定的值表示失败，或者重新抛出异常
                # 这里我们返回一个特定的字符串
                return "分析失败" 
            elif detection_result_raw is None: # 以防 chat_completion 可能返回 None
                print("\n异常检测失败：返回结果为 None")
                return "分析失败"
            else:
                # 只有在结果看起来正常时才打印和返回
                detection_result = detection_result_raw.strip() # 现在 strip 是安全的
                print(f"\n异常检测结果：{detection_result}")
                return detection_result
            
        except Exception as e:
            print(f"视频分析错误: {e}")
            import traceback
            traceback.print_exc()
            return f"分析出错: {str(e)}"

    async def maybe_generate_summary(self):
        """检查是否需要生成历史描述总结"""
        current_time = time.time()
        
        # 如果有足够的描述且间隔时间已到或描述过多
        if ((len(self.recent_descriptions) >= 3 and 
             current_time - self.last_summary_time > self.summary_interval) or
            len(self.recent_descriptions) >= 10):
            
            await self.generate_and_store_summary()
            self.last_summary_time = current_time
    
    async def generate_and_store_summary(self):
        """生成并存储历史描述总结"""
        if not self.recent_descriptions:
            return
        
        try:
            # 准备历史描述文本
            history_text = "\n".join(self.recent_descriptions)
            
            # 使用prompt_summary模板生成总结提示词
            summary_prompt = prompt_summary.format(histroy=history_text)
            
            # 调用DeepSeek生成总结
            summary_result = await chat_completion(summary_prompt, model="deepseek")
            print(f"\n历史总结结果：{summary_result}")
            
            # 添加时间范围信息
            first_time = self.recent_descriptions[0].split(" - ")[0] if " - " in self.recent_descriptions[0] else "未知时间"
            last_time = self.recent_descriptions[-1].split(" - ")[0] if " - " in self.recent_descriptions[-1] else "未知时间"
            
            summary_with_time = f"{first_time}至{last_time}的监控总结: {summary_result}"
            
            # 存入向量数据库
            import httpx
            from config import RAGConfig
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    RAGConfig.VECTOR_API_URL,
                    json={
                        "docs": [summary_with_time],
                        "table_name": f"summary_{int(time.time())}"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logging.info(f"监控总结已添加到向量数据库: {summary_with_time[:50]}...")
                else:
                    logging.error(f"添加监控总结到向量数据库失败: {response.text}")
            
            # 清空历史描述列表，为下一轮收集做准备
            self.recent_descriptions = []
            
            return summary_result
        except Exception as e:
            logging.error(f"生成监控总结出错: {e}")
            return None

    async def store_video_summary(self, description, timestamp):
        """将视频描述存入向量数据库"""
        try:
            import httpx
            from config import RAGConfig
            
            # 添加时间信息
            formatted_time = timestamp[0]  # 使用视频片段的开始时间
            summary = f"{formatted_time} - {description}"
            
            # 添加到最近描述列表
            self.recent_descriptions.append(summary)
            
            # 发送到向量数据库
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    RAGConfig.VECTOR_API_URL,
                    json={
                        "docs": [summary],
                        "table_name": f"video_summary_{int(time.time())}"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logging.info(f"视频描述已添加到向量数据库: {summary[:50]}...")
                else:
                    logging.error(f"添加视频描述到向量数据库失败: {response.text}")
            
            # 检查是否需要生成总结
            await self.maybe_generate_summary()
                    
            return True
        except Exception as e:
            logging.error(f"存储视频描述到向量数据库出错: {e}")
            return False
        