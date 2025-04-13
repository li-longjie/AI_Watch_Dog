# -*- coding: utf-8 -*-
"""
Created on Tue Mar  4 10:50:52 2025

@author: 18523
"""
import base64
# Remove 'requests' if no longer needed elsewhere
# import requests
import cv2
import time
import numpy as np
import json
# Remove 'httpx' if no longer needed elsewhere, or keep for chat_request if needed
# import httpx
from config import APIConfig, RAGConfig, VideoConfig, OSSConfig
from typing import List
import logging
# Import the OpenAI library (async version)
from openai import AsyncOpenAI, APIError # Import APIError for specific exception handling
import httpx # Ensure httpx is imported
import oss2
import os


# Initialize the AsyncOpenAI client for OpenRouter
# It's better to initialize it once, perhaps outside the function or globally if appropriate,
# but for simplicity, we'll initialize it inside the function for now.
# Consider moving this initialization if the function is called very frequently.
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=APIConfig.QWEN_API_KEY, # Use the key from config
)


def frames_to_base64(frames,fps,timestamps):
    print(len(frames))
    print(fps)
    width = frames[0].shape[1]
    height = frames[0].shape[0]    
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    
    
    #filename = ":".join(timestamps).replace("-","")
    #video_writer = cv2.VideoWriter(f'./{filename}.mp4', fourcc, fps, (width, height))  
    video_writer = cv2.VideoWriter('./video_warning/output.mp4', fourcc, fps, (width, height))  
    # 遍历所有帧，并将其写入视频文件
    for frame in frames:
        # 确保帧是正确的数据类型和形状
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        if len(frame.shape) == 2:
            # 如果帧是灰度的，转换为BGR
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        video_writer.write(frame)
    
    # 释放VideoWriter对象
    video_writer.release()

    
    with open('./video_warning/output.mp4', 'rb') as video_file:
        video_base64 = base64.b64encode(video_file.read()).decode('utf-8')
    
    return video_base64


#强制抽取关键帧帧，限制数量
async def video_chat_async_limit_frame(text, frames, timestamps, fps=20, use_oss=True):
    # --- 新增：限制最大图片数量 ---
    MAX_IMAGES_ALLOWED = 8 # Chutes.ai 限制
    # --- 结束新增 ---

    # 原始打算发送的帧数
    desired_frame_count = min(MAX_IMAGES_ALLOWED, int(VideoConfig.BUFFER_DURATION), len(frames))

    if desired_frame_count <= 0:
        logging.error(f"没有足够的帧可供发送 (需要至少1帧, 共有 {len(frames)} 帧).")
        return "Error: No frames available to send."
    
    # 从可用帧中均匀选取帧
    indices = np.linspace(0, len(frames) - 1, num=desired_frame_count, dtype=int)
    selected_frames = [frames[i] for i in indices]
    
    # 强制使用OSS存储和URL
    image_urls = upload_frames_to_oss(selected_frames)
    if not image_urls:
        logging.error("无法上传图像到OSS")
        return "Error: Failed to upload images to OSS."

    # Chutes.ai API details from config
    api_url = APIConfig.QWEN_API_URL
    api_key = APIConfig.QWEN_API_KEY
    model = APIConfig.QWEN_MODEL

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 构建请求内容
    content = [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": url}} for url in image_urls]
    messages = [{"role": "user", "content": content}]

    # 构建请求数据
    data = {
        "model": model,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": APIConfig.TEMPERATURE,
        "stream": False
    }

    try:
        async with httpx.AsyncClient(timeout=APIConfig.REQUEST_TIMEOUT) as client:
            response = await client.post(
                api_url,
                headers=headers,
                json=data
            )

        # Check HTTP status code
        if response.status_code != 200:
            error_message = f"Chutes.ai Qwen API 调用失败，状态码: {response.status_code}"
            try:
                error_details = response.json()
                error_message += f" - {error_details}"
            except Exception:
                 error_message += f" - 响应内容: {response.text}"
            logging.error(error_message)
            return error_message

        # Parse successful response
        response_data = response.json()
        if "choices" in response_data and len(response_data["choices"]) > 0:
            message = response_data["choices"][0].get("message")
            if message and "content" in message:
                return message["content"].strip()
            else:
                 logging.error(f"Chutes.ai Qwen API 响应格式错误 (缺少 message/content): {response_data}")
                 return "API 响应格式错误 (message/content)"
        elif "object" in response_data and response_data.get("object") == "error":
             error_message = f"Chutes.ai Qwen API 返回错误对象: {response_data}"
             logging.error(error_message)
             # Extract the message from the error object if possible
             api_error_msg = response_data.get('message', '未知 API 错误')
             return f"API 返回错误: {api_error_msg}"
        else:
            logging.error(f"Chutes.ai Qwen API 响应格式错误 (缺少 choices): {response_data}")
            return "API 响应格式错误 (choices)"

    except httpx.RequestError as e:
        logging.error(f"请求 Chutes.ai Qwen API 时发生网络错误: {e}")
        return f"网络请求错误: {e}"
    except Exception as e:
        logging.error(f"处理 Chutes.ai Qwen API 响应时发生未知错误: {e}")
        import traceback
        traceback.print_exc()
        return f"处理响应时发生未知错误: {e}"


# Note: video_chat_async function might need similar refactoring if you intend to use it
# with a model that supports direct video URL input via OpenRouter (check their docs).
# The current Qwen-VL example uses image_url list.
async def video_chat_async(text, frames, timestamps, fps=20):
    # ... (Keep original or refactor similar to above if needed) ...
    # This function might not work as intended with the image-based Qwen model via OpenAI lib
    # unless OpenRouter specifically supports the 'video_url' type for it.
    # For now, using video_chat_async_limit_frame is safer.
    logging.warning("video_chat_async might not work correctly with the current setup. Use video_chat_async_limit_frame.")
    # Fallback or raise an error might be better here.
    # For now, just return an error message.
    return "Error: video_chat_async function is likely incompatible with the current model/library setup."


# Update chat_request to use Chutes.ai if it's still needed for DeepSeek
# (Note: chat_completion in llm_service.py now handles this)
async def chat_request(message, stream=False):
     logging.warning("chat_request in utility.py might be redundant. Use chat_completion from llm_service.")
     # If you absolutely need this function, refactor it similar to chat_completion
     # using APIConfig.DEEPSEEK_API_KEY, APIConfig.DEEPSEEK_MODEL, and the Chutes.ai URL.
     # Example call to the unified function:
     return await llm_service.chat_completion(message, model="deepseek", stream=stream) # Requires importing llm_service


# Keep insert_txt as is, assuming it talks to a different service
async def insert_txt(docs: List[str], table_name: str) -> bool:
    # ... (Keep using httpx for RAG service) ...
    # Ensure httpx is imported
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                RAGConfig.VECTOR_API_URL,
                json={
                    "docs": docs,
                    "table_name": table_name
                },
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return result.get("status") == "success"
    except Exception as e:
        print(f"向 RAG 系统添加文本失败: {e}")
        return False

# Make sure to import llm_service if chat_request uses it
import llm_service

def upload_frames_to_oss(frames, max_retries=3):
    """上传多个帧到OSS并返回URL列表"""
    urls = []
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            auth = oss2.Auth(OSSConfig.ACCESS_KEY_ID, OSSConfig.ACCESS_KEY_SECRET)
            bucket = oss2.Bucket(auth, OSSConfig.ENDPOINT, OSSConfig.BUCKET)
            
            for i, frame in enumerate(frames):
                object_key = f"{OSSConfig.ANALYSIS_PREFIX}{int(time.time())}_{i}.jpg"
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, VideoConfig.JPEG_QUALITY])
                bucket.put_object(object_key, buffer.tobytes())
                urls.append(f"https://{OSSConfig.BUCKET}.{OSSConfig.ENDPOINT}/{object_key}")
            
            return urls
        except Exception as e:
            logging.error(f"上传多帧到OSS失败 (尝试 {retry_count+1}/{max_retries}): {e}")
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)  # 等待1秒再重试
    
    # 不再返回None进行回退，直接抛出异常
    raise Exception(f"上传到OSS失败，已重试{max_retries}次")

def frames_to_video_oss(frames, fps, timestamps, alert_id=None):
    """将帧序列转换为视频并上传到OSS"""
    width = frames[0].shape[1]
    height = frames[0].shape[0]    
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    
    # 生成唯一标识符
    timestamp = int(time.time())
    unique_id = alert_id or timestamp
    
    temp_path = f'./video_warning/temp_video_{unique_id}.mp4'
    video_writer = cv2.VideoWriter(temp_path, fourcc, fps, (width, height))  
    
    # 遍历所有帧，并将其写入视频文件
    for frame in frames:
        # 确保帧是正确的数据类型和形状
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        if len(frame.shape) == 2:
            # 如果帧是灰度的，转换为BGR
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        video_writer.write(frame)
    
    # 释放VideoWriter对象
    video_writer.release()
    
    # 上传到OSS
    try:
        auth = oss2.Auth(OSSConfig.ACCESS_KEY_ID, OSSConfig.ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, OSSConfig.ENDPOINT, OSSConfig.BUCKET)
        
        # 使用唯一标识符创建对象键
        object_key = f"{OSSConfig.ALERT_PREFIX}video_{unique_id}.mp4"
        
        with open(temp_path, 'rb') as video_file:
            bucket.put_object(object_key, video_file)
        
        # 生成URL
        url = f"https://{OSSConfig.BUCKET}.{OSSConfig.ENDPOINT}/{object_key}"
        
        # 删除临时文件
        os.remove(temp_path)
        
        return url
    except Exception as e:
        # 不再返回本地路径，直接抛出异常
        logging.error(f"上传视频到OSS失败: {e}")
        raise Exception(f"上传视频到OSS失败: {e}")
