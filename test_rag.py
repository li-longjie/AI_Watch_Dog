import requests
import json
import time

def test_rag():
    # 测试添加文本
    url = "http://localhost:8085/add_text/"
    test_data = {
        "docs": [
            "监控显示：2025年3月23日下午2点，一只橘猫在客厅门口徘徊",
            "监控显示：2025年3月23日下午3点，发现一个人在走廊摔倒",
            "监控显示：2025年3月23日晚上8点，有人在门口徘徊"
        ],
        "table_name": "test_table"
    }
    
    print("测试添加文本...")
    response = requests.post(url, json=test_data)
    print("添加响应:", response.json())
    
    # 等待一下确保数据已经保存
    time.sleep(1)

def test_multiple_queries():
    queries = [
        "猫在做什么",
        "有人摔倒了吗",
        "晚上发生了什么",
        "有什么异常行为",
        "下午2点发生了什么",
        "谁在门口徘徊",
        "走廊里发生了什么"
    ]
    
    url = "http://localhost:8085/search/"
    for query in queries:
        print(f"\n搜索查询: {query}")
        response = requests.post(url, json={
            "query": query,
            "k": 2
        })
        results = response.json()
        if results["status"] == "success":
            if "message" in results:
                print(results["message"])
            elif results["scores"]:
                print("\n相关记录:")
                for score_info in results["scores"]:
                    print(f"- {score_info['text']}")
                    print(f"  相关度: {score_info['similarity_percentage']:.1f}%")
                    print(f"  关键词匹配度: {score_info['keyword_match_ratio']:.1f}%")
                    if score_info['matching_keywords']:
                        print(f"  匹配关键词: {', '.join(score_info['matching_keywords'])}")
                
                print("\n大模型回答:")
                print(results["answer"])
            else:
                print("没有找到相关记录")
        else:
            print("搜索失败:", results.get("message", "未知错误"))

if __name__ == "__main__":
    # 先添加测试数据
    test_rag()
    print("\n开始多查询测试...")
    # 然后进行多查询测试
    test_multiple_queries() 