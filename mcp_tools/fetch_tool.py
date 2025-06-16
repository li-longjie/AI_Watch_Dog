import httpx
from typing import Dict, Any
from .base_tool import BaseMCPTool

class FetchTool(BaseMCPTool):
    """网页内容抓取工具"""
    
    @property
    def tool_name(self) -> str:
        return "网页抓取工具"
    
    @property
    def description(self) -> str:
        return "用于获取指定URL的网页内容，支持网页内容提取和分析"
    
    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "fetch_webpage": {
                "description": "获取指定URL的网页内容",
                "parameters": {
                    "url": {
                        "type": "string",
                        "description": "要获取内容的网页URL",
                        "required": True
                    },
                    "max_length": {
                        "type": "integer", 
                        "description": "内容最大长度限制",
                        "required": False
                    }
                },
                "examples": [
                    "获取https://www.baidu.com的网页内容",
                    "抓取新闻网站的最新文章",
                    "分析某个产品页面的信息"
                ]
            }
        }
    
    async def execute_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行网页抓取功能"""
        if function_name == "fetch_webpage":
            return await self._fetch_webpage(parameters)
        else:
            return {
                "status": "error",
                "message": f"未知函数: {function_name}"
            }
    
    async def _fetch_webpage(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """获取网页内容"""
        try:
            url = parameters.get("url")
            max_length = parameters.get("max_length", 8000)
            
            if not url:
                return {
                    "status": "error",
                    "message": "缺少必需参数: url"
                }
            
            # 确保URL格式正确
            if not url.startswith('http'):
                url = 'https://' + url
            
            # 请求MCPO Fetch服务
            fetch_url = f"{self.base_url}/fetch/fetch"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    fetch_url,
                    json={"url": url, "max_length": max_length}
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"无法获取网页内容: HTTP {response.status_code}"
                    }
                
                web_content = response.json()
                
                # 处理返回内容
                if isinstance(web_content, list) and len(web_content) > 0:
                    content_text = web_content[0]
                elif isinstance(web_content, dict):
                    content_text = web_content.get("content", str(web_content))
                else:
                    content_text = str(web_content)
                
                return {
                    "status": "success",
                    "content": content_text,
                    "url": url,
                    "length": len(content_text)
                }
                
        except httpx.TimeoutException:
            return {
                "status": "error",
                "message": "网页请求超时"
            }
        except Exception as e:
            self.logger.error(f"网页抓取错误: {e}")
            return {
                "status": "error",
                "message": f"抓取失败: {str(e)}"
            } 