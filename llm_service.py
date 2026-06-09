import httpx
from config import APIConfig
from typing import List
import json
import asyncio
import logging
from typing import Optional, Dict, Any, Union
import os

# 硅基流动API配置（用于RAG问答）- 从config.py读取
# API密钥从.env文件读取
SILICONFLOW_API_KEY = APIConfig.DEEPSEEK_API_KEY
SILICONFLOW_API_URL = APIConfig.DEEPSEEK_API_URL
SILICONFLOW_MODEL = APIConfig.DEEPSEEK_MODEL

class LLMService:
    @staticmethod
    async def get_response(prompt: str, use_siliconflow: bool = True) -> str:
        """调用大模型生成回答

        Args:
            prompt: 提示词
            use_siliconflow: 是否使用硅流API（默认为True）
        """
        try:
            # 统一使用硅流API
            return await query_siliconflow_model(prompt)
        except Exception as e:
            # 使用 logging 记录错误
            logging.error(f"调用 LLMService.get_response 时出错: {e}")
            # 返回具体的错误信息
            return f"生成回答错误: {str(e)}"

    @staticmethod
    def format_response(response: str) -> str:
        """格式化模型回答"""
        # 可以在这里添加后处理逻辑
        return response.strip()

async def query_siliconflow_model(prompt: str) -> str:
    """调用硅基流动API获取回答（用于智能问答模块）"""
    try:
        logging.info(f"提示词长度: {len(prompt)}")

        # 构建请求数据
        request_data = {
            "model": SILICONFLOW_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "max_tokens": 512,
            "temperature": 0.7,
            "top_p": 0.7,
            "top_k": 50,
            "frequency_penalty": 0.5,
            "n": 1,
            "stop": []
        }

        logging.info(f"正在发送请求到硅基流动API")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                SILICONFLOW_API_URL,
                headers={
                    "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=request_data,
                timeout=60.0
            )

            # 记录响应状态码
            logging.info(f"硅基流动API响应状态码: {response.status_code}")

            # 检查HTTP错误
            if response.status_code != 200:
                error_text = response.text
                logging.error(f"硅基流动API返回HTTP错误: {response.status_code} - {error_text}")
                return f"API调用失败: {response.status_code} - {error_text}"

            # 解析响应
            result = response.json()
            logging.info(f"硅基流动API响应: {result.keys()}")

            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                content = message.get("content", "")
                return content.strip()
            else:
                logging.error(f"硅基流动API响应缺少choices字段: {result}")
                return "API响应格式错误"

    except Exception as e:
        logging.error(f"调用硅基流动模型异常: {str(e)}")
        return f"API调用异常: {str(e)}"

async def chat_completion(prompt: str, model: str = "deepseek", temperature: float = None, max_tokens: int = 1024) -> str:
    """兼容性函数，重定向到硅流API

    Args:
        prompt: 提示词
        model: 模型名称（忽略，统一使用硅流的DeepSeek）
        temperature: 温度参数
        max_tokens: 最大生成token数
    """
    # 为了兼容性，重定向到硅流API
    logging.debug("chat_completion函数已重定向到硅流API")
    return await query_siliconflow_model(prompt)

# Remove or comment out the specific deepseek_chat and qwen_chat functions
# if chat_completion now handles both.
# async def deepseek_chat(...): ...
# async def qwen_chat(...): ...

async def get_llm_response(prompt: str, use_siliconflow: bool = True) -> str:
    """
    Wrapper function to call the LLM service.
    This function is provided for compatibility with modules expecting `get_llm_response`.
    It currently delegates to LLMService.get_response.
    """
    return await LLMService.get_response(prompt, use_siliconflow=use_siliconflow)