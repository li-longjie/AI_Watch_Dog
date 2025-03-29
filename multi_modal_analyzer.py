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
        
        # 1. 获取当前视频片段的分析结果
        result = await self.analyze_video(frames, fps, timestamps)
        
        # 2. 直接返回分析结果 - 确保所有类型的活动都有输出
        # 而不是只返回预警类活动
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
            # 1. 获取视频描述
            description = await video_chat_async_limit_frame(prompt_vieo, frames, timestamps, fps=fps)
            print("\n视频描述原文：", description)
            
            if timestamps is None:
                return description
            
            # 2. 使用DeepSeek和prompt_detect进行异常检测
            detect_prompt = prompt_detect.format(
                description=description,
                time=timestamps[0]
            )
            
            # 调用DeepSeek进行异常检测
            detection_result = await chat_completion(detect_prompt, model="deepseek")
            print(f"\n异常检测结果：{detection_result}")
            
            try:
                # 解析检测结果
                # 期望的返回格式是JSON字符串：
                # {
                #    "type": "important/warning/normal",
                #    "reason": "检测到的具体原因",
                #    "confidence": 0.95
                # }
                result = json.loads(detection_result)
                
                # 如果检测到重要或异常情况
                if result["type"] in ["important", "warning"]:
                    # 提取关键信息
                    key_points = await self.extract_key_points(description)
                    print(f"提取的关键信息: {key_points}")
                    
                    # 生成预警消息
                    if result["type"] == "important":
                        alert_msg = f"{timestamps[0]}，{result['reason']}"
                    else:  # warning
                        alert_msg = f"请注意，{result['reason']}"
                    
                    return {
                        "alert": alert_msg,
                        "details": key_points,  # 使用提取的关键信息
                        "type": result["type"],
                        "confidence": result.get("confidence", 0.9)
                    }
                
                # 如果是正常情况，返回空结果
                return {
                    "alert": "",
                    "details": "",
                    "type": "normal",
                    "confidence": 0.0
                }
                
            except json.JSONDecodeError:
                print("异常检测结果解析失败，尝试直接处理文本结果")
                # 如果JSON解析失败，检查文本中是否包含关键信息
                detection_lower = detection_result.lower()
                
                if "重要" in detection_lower or "严重" in detection_lower:
                    return {
                        "alert": f"{timestamps[0]}，检测到重要情况：{detection_result}",
                        "details": await self.extract_key_points(description),
                        "type": "important",
                        "confidence": 0.9
                    }
                elif "警告" in detection_lower or "异常" in detection_lower:
                    return {
                        "alert": f"请注意，{detection_result}",
                        "details": await self.extract_key_points(description),
                        "type": "warning",
                        "confidence": 0.8
                    }
                
                # 如果没有检测到异常，返回空结果
                return {
                    "alert": "",
                    "details": "",
                    "type": "normal",
                    "confidence": 0.0
                }
                
        except Exception as e:
            print(f"视频分析错误: {e}")
            import traceback
            traceback.print_exc()
            return {
                "alert": "分析出错: " + str(e),
                "details": str(e),
                "type": "error",
                "confidence": 0.0
            }
        