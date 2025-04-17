import requests

def fetch_webpage(url, max_length=10000, start_index=0, raw=False):
    """
    使用 MCP Fetch 服务器从指定 URL 获取内容。
    
    参数:
        url (str): 要获取的 URL
        max_length (int): 返回内容的最大字符数
        start_index (int): 从该字符索引位置开始获取内容
        raw (bool): 是否获取原始 HTML 内容（不进行 Markdown 转换）
    
    返回:
        dict: 服务器返回的响应，包含获取的内容
    """
    try:
        # Make a POST request to the fetch endpoint
        response = requests.post(
            url="http://localhost:8000/fetch/fetch",
            json={
                "url": url,
                "max_length": max_length,
                "start_index": start_index,
                "raw": raw
            }
        )
        
        # Ensure the request was successful
        response.raise_for_status()
        
        # Parse the response
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# Example usage
if __name__ == "__main__":
    # Fetch the specific URL you requested
    target_url = "https://www.aivi.fyi/aiagents/RooCode-Gemini2.5Pro-OpenAIAgentsSDK"
    result = fetch_webpage(target_url)
    print(result) 