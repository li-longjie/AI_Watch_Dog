import asyncio
import websockets
import json
from datetime import datetime
from config import ServerConfig

async def test_video_stream():
    uri = f"ws://localhost:{ServerConfig.PORT}/ws"
    async with websockets.connect(uri) as websocket:
        print("连接到视频流服务器...")
        
        while True:
            try:
                response = await websocket.recv()
                data = json.loads(response)
                
                if data["type"] == "update":
                    print(f"\n收到新的监控记录:")
                    print(f"时间: {data['timestamp']}")
                    print(f"内容: {data['content']}")
                    
                    # 测试搜索
                    await test_search("最近发生了什么异常？")
                elif data["type"] == "error":
                    print(f"错误: {data['message']}")
                    break
            except Exception as e:
                print(f"连接错误: {e}")
                break

async def test_search(query: str):
    """测试搜索功能"""
    import requests
    
    url = "http://localhost:8085/search/"
    response = requests.post(url, json={
        "query": query,
        "k": 2
    })
    
    results = response.json()
    if results["status"] == "success":
        print("\n搜索结果:")
        print(f"问题: {query}")
        print(f"回答: {results['answer']}")
        for score_info in results["scores"]:
            print(f"- {score_info['text']}")
            print(f"  相关度: {score_info['similarity_percentage']:.1f}%")

if __name__ == "__main__":
    # 安装必要的包
    try:
        import cv2
        import numpy
    except ImportError:
        print("正在安装必要的包...")
        import subprocess
        subprocess.check_call(["pip", "install", "opencv-python", "numpy", "websockets"])
        print("安装完成，重新运行程序...")
        import sys
        sys.exit(0)
    
    print("启动视频流测试...")
    try:
        asyncio.run(test_video_stream())
    except Exception as e:
        print(f"运行时错误: {e}")
        print("请确保:")
        print("1. 摄像头已正确连接")
        print("2. 摄像头未被其他程序占用")
        print("3. 系统已授予摄像头访问权限") 