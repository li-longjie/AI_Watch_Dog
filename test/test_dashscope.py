#!/usr/bin/env python3
"""
测试DashScope API配置的简单脚本
"""

import os
import asyncio
from openai import AsyncOpenAI
from config import APIConfig

async def test_dashscope_api():
    """测试DashScope API连接"""
    
    print("🔧 测试DashScope API配置...")
    print(f"API URL: {APIConfig.QWEN_API_URL}")
    print(f"模型: {APIConfig.QWEN_MODEL}")
    print(f"API Key: {APIConfig.QWEN_API_KEY[:10]}...{APIConfig.QWEN_API_KEY[-10:]}")
    
    try:
        # 初始化客户端
        client = AsyncOpenAI(
            base_url=APIConfig.QWEN_API_URL,
            api_key=APIConfig.QWEN_API_KEY,
        )
        
        # 测试简单的文本请求
        print("\n📝 发送测试请求...")
        completion = await client.chat.completions.create(
            model=APIConfig.QWEN_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "请简单介绍一下你自己"},
                ]
            }],
            max_tokens=100,
            temperature=0.7,
        )
        
        if completion.choices and len(completion.choices) > 0:
            response = completion.choices[0].message.content
            print("✅ API测试成功!")
            print(f"响应: {response}")
            return True
        else:
            print("❌ API返回格式错误")
            return False
            
    except Exception as e:
        print(f"❌ API测试失败: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_dashscope_api())
    if success:
        print("\n🎉 DashScope API配置正确，可以正常使用!")
    else:
        print("\n⚠️ DashScope API配置有问题，请检查API密钥和网络连接") 