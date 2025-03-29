import requests
import json

def search_history(query: str):
    url = "http://localhost:8085/search/"
    response = requests.post(url, json={
        "query": query,
        "k": 5
    })
    
    results = response.json()
    if results["status"] == "success":
        print("\n搜索结果:")
        for i, result in enumerate(results["results"], 1):
            print(f"{i}. {result}")
    else:
        print("搜索失败:", results.get("message", "未知错误"))

if __name__ == "__main__":
    # 示例查询
    search_history("有什么异常行为") 