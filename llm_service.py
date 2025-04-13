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
            # 使用 logging 记录错误
            logging.error(f"调用 LLMService.get_response 时出错: {e}")
            # 返回具体的错误信息
            return f"生成回答错误: {str(e)}"

    @staticmethod
    def format_response(response: str) -> str:
        """格式化模型回答"""
        # 可以在这里添加后处理逻辑
        return response.strip()

async def chat_completion(
    prompt: str,
    model: str = "deepseek", # Keep default or change if needed
    temperature: float = None,
    max_tokens: int = 1024
) -> str:
    """调用 Chutes.ai LLM模型进行文本生成"""
    if model.lower() == "deepseek":
        api_key = APIConfig.DEEPSEEK_API_KEY
        model_name = APIConfig.DEEPSEEK_MODEL
    else:  # Default to Qwen if not deepseek
        api_key = APIConfig.QWEN_API_KEY
        model_name = APIConfig.QWEN_MODEL

    api_url = "https://llm.chutes.ai/v1/chat/completions" # Chutes.ai endpoint

    headers = {
        "Authorization": f"Bearer {api_key}", # Correct Bearer token format
        "Content-Type": "application/json"
    }

    data = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature if temperature is not None else APIConfig.TEMPERATURE,
        "max_tokens": max_tokens,
        # Add other parameters if supported by Chutes.ai and needed
        # "top_p": APIConfig.TOP_P,
        # "frequency_penalty": APIConfig.REPETITION_PENALTY,
        "stream": False # Assuming non-streaming for this function
    }

    try:
        async with httpx.AsyncClient(timeout=APIConfig.REQUEST_TIMEOUT) as client:
            response = await client.post(
                api_url,
                headers=headers,
                json=data
            )

        # Check HTTP status code first
        if response.status_code != 200:
            error_message = f"Chutes.ai API 调用失败，状态码: {response.status_code}"
            try:
                # Try to get more details from the response body
                error_details = response.json()
                error_message += f" - {error_details}"
            except Exception:
                error_message += f" - 响应内容: {response.text}" # Fallback to raw text
            logging.error(error_message)
            return error_message # Return error message to caller

        # Parse successful response
        response_data = response.json()
        if "choices" in response_data and len(response_data["choices"]) > 0:
            message = response_data["choices"][0].get("message")
            if message:
                content = message.get("content") # Use .get() for safety
                if isinstance(content, str): # Check if it's a string
                    return content.strip()
                else:
                    # Handle cases where content is None or not a string
                    logging.error(f"API 响应中 content 非字符串或为 None: {content}")
                    return "错误：API响应内容格式不正确" # Return a clear error message
            else:
                logging.error(f"API 响应格式错误 (缺少 message): {response_data}")
                return "错误：API响应格式错误 (message)"
        else:
            logging.error(f"Chutes.ai API 响应格式错误 (缺少 choices): {response_data}")
            return "API 响应格式错误 (choices)"

    except httpx.RequestError as e:
        logging.error(f"请求 Chutes.ai API 时发生网络错误: {e}")
        return f"网络请求错误: {e}"
    except Exception as e:
        logging.error(f"处理 Chutes.ai API 响应时发生未知错误: {e}")
        import traceback
        traceback.print_exc()
        return f"处理响应时发生未知错误: {e}"

# Remove or comment out the specific deepseek_chat and qwen_chat functions
# if chat_completion now handles both.
# async def deepseek_chat(...): ...
# async def qwen_chat(...): ... 