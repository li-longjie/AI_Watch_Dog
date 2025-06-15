"""
测试Chutes.ai API的简单脚本
"""

import asyncio
from openai import AsyncOpenAI
from config import APIConfig

async def test_simple_chutes_api():
    """测试基本的文本API调用"""
    
    client = AsyncOpenAI(
        base_url=APIConfig.QWEN_API_URL,
        api_key=APIConfig.QWEN_API_KEY,
    )
    
    try:
        print(f"🔧 测试Chutes.ai API连接...")
        print(f"API URL: {APIConfig.QWEN_API_URL}")
        print(f"模型: {APIConfig.QWEN_MODEL}")
        
        # 简单的文本请求
        completion = await client.chat.completions.create(
            model=APIConfig.QWEN_MODEL,
            messages=[
                {"role": "user", "content": "你好，请简单介绍一下你自己。"}
            ],
            max_tokens=100,
            temperature=0.7,
        )
        
        if completion.choices and len(completion.choices) > 0:
            content = completion.choices[0].message.content
            print(f"✅ API调用成功!")
            print(f"回复: {content}")
            return True
        else:
            print("❌ API响应格式错误")
            return False
            
    except Exception as e:
        print(f"❌ API调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_simple_chutes_api())
    if success:
        print("\n🎉 Chutes.ai API配置正确!")
    else:
        print("\n⚠️ Chutes.ai API配置有问题") 