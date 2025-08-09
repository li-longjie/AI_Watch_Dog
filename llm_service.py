import httpx
from config import APIConfig
from typing import List
import json
import asyncio
import logging
from typing import Optional, Dict, Any, Union
import os

# 硅基流动API配置（用于RAG问答）- 已废弃，统一使用Chutes.ai
# SILICONFLOW_API_KEY = "sk-xugvbuiyayzzfeoelfytnfioimnwvzouawxlavixynzuloui"
# SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
# SILICONFLOW_MODEL = "deepseek-ai/DeepSeek-V3"

class LLMService:
    @staticmethod
    async def get_response(prompt: str, use_chutes: bool = True) -> str:
        """调用大模型生成回答
        
        Args:
            prompt: 提示词
            use_chutes: 是否使用Chutes.ai的模型（为了保持接口兼容性，默认为True）
        """
        try:
            # 统一使用Chutes.ai的API
            return await chat_completion(prompt)
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

# 注释掉硅基流动相关函数，不再使用
# async def query_siliconflow_model(prompt: str) -> str:
#     """调用硅基流动API获取回答（用于智能问答模块）"""
#     try:
#         logging.info(f"提示词长度: {len(prompt)}")
#         
#         # 构建请求数据
#         request_data = {
#             "model": SILICONFLOW_MODEL,
#             "messages": [
#                 {"role": "user", "content": prompt}
#             ],
#             "stream": False,
#             "max_tokens": 512,
#             "temperature": 0.7,
#             "top_p": 0.7,
#             "top_k": 50,
#             "frequency_penalty": 0.5,
#             "n": 1,
#             "stop": []
#         }
#         
#         logging.info(f"正在发送请求到硅基流动API")
#         
#         async with httpx.AsyncClient() as client:
#             response = await client.post(
#                 SILICONFLOW_API_URL,
#                 headers={
#                     "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
#                     "Content-Type": "application/json"
#                 },
#                 json=request_data,
#                 timeout=60.0
#             )
#             
#             # 记录响应状态码
#             logging.info(f"硅基流动API响应状态码: {response.status_code}")
#             
#             # 检查HTTP错误
#             if response.status_code != 200:
#                 error_text = response.text
#                 logging.error(f"硅基流动API返回HTTP错误: {response.status_code} - {error_text}")
#                 
#                 # 如果硅基流动API失败，尝试回退到Chutes.ai
#                 logging.info("硅基流动API失败，尝试使用Chutes.ai作为回退")
#                 return await chat_completion(prompt)
#             
#             # 解析响应
#             result = response.json()
#             logging.info(f"硅基流动API响应: {result.keys()}")
#             
#             if "choices" in result and len(result["choices"]) > 0:
#                 message = result["choices"][0].get("message", {})
#                 content = message.get("content", "")
#                 return content
#             else:
#                 logging.error(f"硅基流动API响应缺少choices字段: {result}")
#                 
#                 # 如果响应格式异常，回退到Chutes.ai
#                 logging.info("硅基流动API响应格式异常，尝试使用Chutes.ai作为回退")
#                 return await chat_completion(prompt)
#             
#     except Exception as e:
#         logging.error(f"调用硅基流动模型异常: {str(e)}")
#         
#         # 如果发生异常，回退到Chutes.ai
#         logging.info(f"硅基流动API异常，尝试使用Chutes.ai作为回退: {e}")
#         return await chat_completion(prompt)

async def chat_completion(prompt: str, model: str = "deepseek", temperature: float = None, max_tokens: int = 1024) -> str:
    """使用Chutes.ai LLM模型（用于视频画面描述和活动提取）
    
    Args:
        prompt: 提示词
        model: 模型名称，可选值为 'deepseek' 或 'qwen'
        temperature: 温度参数，决定输出的随机性
        max_tokens: 最大生成token数
    """
    # 根据model参数选择不同的API配置
    if model == "qwen":
        api_key = APIConfig.QWEN_API_KEY
        model_name = APIConfig.QWEN_MODEL
        api_url = APIConfig.QWEN_API_URL
    else:  # 默认使用deepseek
        api_key = APIConfig.DEEPSEEK_API_KEY
        model_name = APIConfig.DEEPSEEK_MODEL
        api_url = APIConfig.DEEPSEEK_API_URL

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": model_name,
        "messages": [{
            "role": "user", 
            "content": prompt
        }],
        "max_tokens": max_tokens,
        "stream": False
        # 完全不发送stop参数，避免触发默认停止令牌
    }
    
    # 添加可选参数
    if temperature is not None:
        data["temperature"] = temperature

    logging.debug(f"🚀 准备调用API: {api_url}")
    logging.debug(f"📋 使用模型: {model_name}")
    logging.debug(f"📝 提示词长度: {len(prompt)} 字符")
    logging.debug(f"⚙️ 参数: max_tokens={max_tokens}, temperature={temperature}")
    
    # 检查提示词中是否包含可能导致问题的字符（注释掉以减少日志噪音）
    # if '#' in prompt:
    #     logging.warning(f"⚠️ 警告：提示词包含#字符，可能导致API停止令牌问题")
    #     logging.debug(f"📄 提示词预览: {prompt[:200]}...")

    try:
        async with httpx.AsyncClient(timeout=APIConfig.REQUEST_TIMEOUT) as client:
            response = await client.post(
                api_url,
                headers=headers,
                json=data
            )

        # 检查HTTP状态码
        if response.status_code != 200:
            error_message = f"Chutes.ai API调用失败，状态码: {response.status_code}"
            try:
                error_details = response.json()
                error_message += f" - {error_details}"
            except Exception:
                error_message += f" - 响应内容: {response.text}"
            logging.error(error_message)
            return error_message

        # 解析成功响应
        response_data = response.json()
        logging.debug(f"Chutes.ai API 完整响应: {response_data}")
        
        if "choices" in response_data and len(response_data["choices"]) > 0:
            message = response_data["choices"][0].get("message")
            if message:
                content = message.get("content")
                if isinstance(content, str):
                    logging.debug(f"成功获取API响应内容，长度: {len(content)}")
                    return content.strip()
                else:
                    logging.error(f"API响应中content非字符串或为None: {content}")
                    logging.error(f"完整message对象: {message}")
                    # 检查是否有usage信息显示API确实被调用了
                    usage_info = response_data.get("usage", {})
                    logging.error(f"API使用情况: {usage_info}")
                    return f"API返回的content类型错误: {type(content)}, 值: {content}"
            else:
                logging.error(f"API响应格式错误(缺少message): {response_data}")
                return "错误：API响应格式错误(message)"
        else:
            logging.error(f"Chutes.ai API响应格式错误(缺少choices): {response_data}")
            return "API响应格式错误(choices)"

    except httpx.RequestError as e:
        logging.error(f"请求Chutes.ai API时发生网络错误: {e}")
        return f"网络请求错误: {e}"
    except Exception as e:
        logging.error(f"处理Chutes.ai API响应时发生未知错误: {e}")
        import traceback
        traceback.print_exc()
        return f"处理响应时发生未知错误: {e}"

# Remove or comment out the specific deepseek_chat and qwen_chat functions
# if chat_completion now handles both.
# async def deepseek_chat(...): ...
# async def qwen_chat(...): ... 

async def get_llm_response(prompt: str, use_chutes: bool = True) -> str:
    """
    Wrapper function to call the LLM service.
    This function is provided for compatibility with modules expecting `get_llm_response`.
    It currently delegates to LLMService.get_response.
    """
    return await LLMService.get_response(prompt, use_chutes=use_chutes) 