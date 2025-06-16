import requests
import json

def test_activity_server():
    """测试activity_ui.py服务器是否正常工作"""
    url = "http://localhost:5001/api/query"
    
    test_data = {
        "message": "测试连接"
    }
    
    try:
        print("正在测试activity_ui.py服务器...")
        print(f"URL: {url}")
        print(f"请求数据: {test_data}")
        
        response = requests.post(
            url, 
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ 服务器响应正常")
            try:
                data = response.json()
                print(f"响应数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
            except:
                print(f"响应文本: {response.text}")
        else:
            print(f"❌ 服务器返回错误状态码: {response.status_code}")
            print(f"错误响应: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器 - 请确保activity_ui.py正在运行")
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    test_activity_server() 