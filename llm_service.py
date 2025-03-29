import httpx
from config import APIConfig
from typing import List
import json
import asyncio
import logging
from typing import Optional, Dict, Any, Union

class LLMService:
    @staticmethod
    async def get_response(prompt: str) -> str:
        """调用大模型生成回答"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    APIConfig.DEEPSEEK_API_URL,
                    headers={
                        "Authorization": f"Bearer {APIConfig.DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": APIConfig.DEEPSEEK_MODEL,
                        "messages": [
                            {"role": "system", "content": "你是一个智能监控助手，负责回答关于监控记录的问题。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 500
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"调用大模型出错: {e}")
            return "抱歉，生成回答时出现错误。"

    @staticmethod
    def format_response(response: str) -> str:
        """格式化模型回答"""
        # 可以在这里添加后处理逻辑
        return response.strip()

async def chat_completion(
    prompt: str, 
    model: str = "deepseek", 
    temperature: float = None,
    max_tokens: int = 1024
) -> str:
    """调用LLM模型进行文本生成
    
    Args:
        prompt: 提示词
        model: 模型名称，支持"deepseek"或"qwen"
        temperature: 温度参数，控制随机性
        max_tokens: 最大生成token数
        
    Returns:
        生成的文本
    """
    if model.lower() == "deepseek":
        return await deepseek_chat(prompt, temperature, max_tokens)
    else:  # 默认使用qwen
        return await qwen_chat(prompt, temperature, max_tokens)

async def deepseek_chat(
    prompt: str, 
    temperature: float = None, 
    max_tokens: int = 1024
) -> str:
    """调用DeepSeek模型API"""
    try:
        headers = {
            "Authorization": f"Bearer {APIConfig.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": APIConfig.DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature or APIConfig.TEMPERATURE,
            "max_tokens": max_tokens,
        }
        
        async with httpx.AsyncClient(timeout=APIConfig.REQUEST_TIMEOUT) as client:
            response = await client.post(
                APIConfig.DEEPSEEK_API_URL,
                headers=headers,
                json=data
            )
            
        response_data = response.json()
        if "choices" in response_data and len(response_data["choices"]) > 0:
            return response_data["choices"][0]["message"]["content"].strip()
        else:
            logging.error(f"DeepSeek API返回格式错误: {response_data}")
            return "API返回格式错误"
            
    except Exception as e:
        logging.error(f"DeepSeek API调用失败: {e}")
        return f"API调用错误: {str(e)}"

async def qwen_chat(
    prompt: str, 
    temperature: float = None, 
    max_tokens: int = 1024
) -> str:
    """调用通义千问模型API"""
    # 已有的函数实现，保留不变
    # ...
    pass  # 这里应该有现有的实现代码 