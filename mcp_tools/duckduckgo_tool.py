import httpx
import requests
import traceback
import re
from typing import Dict, Any, List
from .base_tool import BaseMCPTool

class DuckDuckGoTool(BaseMCPTool):
    """DuckDuckGo搜索工具"""
    
    @property
    def tool_name(self) -> str:
        return "DuckDuckGo搜索工具"
    
    @property
    def description(self) -> str:
        return "使用DuckDuckGo搜索引擎进行网络搜索，获取实时信息和网页内容"
    
    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "search": {
                "description": "使用DuckDuckGo搜索引擎搜索信息",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询关键词",
                        "required": True
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大搜索结果数量，默认5个",
                        "required": False
                    }
                },
                "examples": [
                    "搜索今天的天气",
                    "查找人工智能最新新闻",
                    "搜索Python编程教程",
                    "查询股票市场行情",
                    "搜索北京今天温度"
                ]
            },
            "fetch_content": {
                "description": "获取指定网页的详细内容",
                "parameters": {
                    "url": {
                        "type": "string",
                        "description": "要获取内容的网页URL",
                        "required": True
                    }
                },
                "examples": [
                    "获取https://example.com的页面内容",
                    "抓取新闻网站文章内容"
                ]
            },
            "search_and_fetch": {
                "description": "执行搜索并自动获取前几个搜索结果的详细内容",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询关键词",
                        "required": True
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大搜索结果数量，默认3个",
                        "required": False
                    },
                    "max_pages": {
                        "type": "integer", 
                        "description": "最多获取多少个页面的详细内容，默认2个",
                        "required": False
                    }
                },
                "examples": [
                    "搜索并获取今天的新闻详情",
                    "查找AI发展趋势的详细报告",
                    "获取最新技术资讯的详细内容"
                ]
            }
        }
    
    async def execute_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行DuckDuckGo搜索功能"""
        if function_name == "search":
            return await self._search(parameters)
        elif function_name == "fetch_content":
            return await self._fetch_content(parameters)
        elif function_name == "search_and_fetch":
            return await self._search_and_fetch(parameters)
        else:
            return {
                "status": "error",
                "message": f"未知函数: {function_name}"
            }
    
    async def _search(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行DuckDuckGo搜索"""
        try:
            query = parameters.get("query")
            max_results = parameters.get("max_results", 5)
            
            if not query:
                return {
                    "status": "error",
                    "message": "缺少必需参数: query"
                }
            
            result = await self._run_duckduckgo_search(query, max_results)
            
            if isinstance(result, dict) and "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }
            
            return {
                "status": "success",
                "search_results": result,
                "query": query,
                "max_results": max_results
            }
            
        except Exception as e:
            self.logger.error(f"DuckDuckGo搜索执行错误: {e}")
            return {
                "status": "error",
                "message": f"搜索执行失败: {str(e)}"
            }
    
    async def _fetch_content(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """获取网页内容"""
        try:
            url = parameters.get("url")
            
            if not url:
                return {
                    "status": "error",
                    "message": "缺少必需参数: url"
                }
            
            content = await self._fetch_page_content(url)
            
            if isinstance(content, dict) and "error" in content:
                return {
                    "status": "error",
                    "message": content["error"]
                }
            
            return {
                "status": "success",
                "content": content,
                "url": url,
                "content_length": len(str(content))
            }
            
        except Exception as e:
            self.logger.error(f"网页内容获取错误: {e}")
            return {
                "status": "error",
                "message": f"内容获取失败: {str(e)}"
            }
    
    async def _search_and_fetch(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """搜索并获取详细内容"""
        try:
            query = parameters.get("query")
            max_results = parameters.get("max_results", 3)
            max_pages = parameters.get("max_pages", 2)
            
            if not query:
                return {
                    "status": "error",
                    "message": "缺少必需参数: query"
                }
            
            # 执行搜索
            search_result = await self._run_duckduckgo_search(query, max_results)
            
            if isinstance(search_result, dict) and "error" in search_result:
                return {
                    "status": "error",
                    "message": search_result["error"]
                }
            
            # 提取URL并获取详细内容
            detailed_content = []
            urls = []
            
            # 从搜索结果中提取URL
            if isinstance(search_result, str) and "URL:" in search_result:
                urls = re.findall(r'URL: (https?://[^\s\n]+)', search_result)
                self.logger.info(f"找到 {len(urls)} 个URL，尝试获取页面详细内容")
                
                # 获取前max_pages个URL的内容
                actual_pages = min(len(urls), max_pages)
                for i, url in enumerate(urls[:actual_pages]):
                    self.logger.info(f"获取第 {i+1}/{actual_pages} 个URL内容: {url}")
                    content = await self._fetch_page_content(url)
                    
                    if isinstance(content, str) and len(content.strip()) > 100:
                        detailed_content.append({
                            "index": i+1,
                            "url": url,
                            "content": content[:2000],  # 限制内容长度
                            "content_length": len(content)
                        })
                        self.logger.info(f"成功获取第 {i+1} 个URL的有效内容")
                    else:
                        self.logger.warning(f"第 {i+1} 个URL内容获取失败或无效")
            
            return {
                "status": "success",
                "search_results": search_result,
                "detailed_content": detailed_content,
                "query": query,
                "urls_found": len(urls),
                "pages_fetched": len(detailed_content),
                "summary": f"搜索到{len(urls)}个结果，成功获取{len(detailed_content)}个页面的详细内容"
            }
            
        except Exception as e:
            self.logger.error(f"搜索并获取内容错误: {e}")
            return {
                "status": "error", 
                "message": f"搜索并获取内容失败: {str(e)}"
            }
    
    async def _run_duckduckgo_search(self, query: str, max_results: int = 5) -> Any:
        """使用DuckDuckGo MCP服务进行搜索，增加错误处理和重试机制"""
        try:
            self.logger.info(f"执行DuckDuckGo搜索: {query}")
            
            # 清理查询字符串，移除可能导致问题的字符
            cleaned_query = query.strip().replace('"', '').replace("'", '').replace('\n', ' ')
            
            # 如果是中文查询，先尝试翻译成英文
            if any('\u4e00' <= char <= '\u9fff' for char in cleaned_query):
                # 包含中文字符，尝试翻译（简化处理）
                english_query = await self._translate_query_to_english(cleaned_query)
                self.logger.info(f"中文查询简化为: {cleaned_query} -> {english_query}")
                search_query = english_query
            else:
                search_query = cleaned_query
            
            # 进一步简化查询，避免复杂的短语
            search_query = ' '.join(search_query.split()[:5])  # 限制为最多5个词
            
            # 根据API文档使用正确的参数格式
            request_body = {
                "query": search_query,
                "max_results": max_results
            }
            
            # 使用正确的端点路径 - 带服务前缀
            endpoint = f"{self.base_url}/duckduckgo-search/search"
            
            self.logger.info(f"调用端点: {endpoint}")
            self.logger.info(f"请求参数: {request_body}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=request_body)
                
                self.logger.info(f"DuckDuckGo搜索响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    self.logger.info(f"搜索成功，返回结果: {str(result)[:300]}...")
                    return result
                else:
                    # 如果第一次失败，尝试更简单的查询
                    self.logger.warning(f"第一次搜索失败，尝试简化查询")
                    
                    # 提取关键词
                    simple_query = ' '.join(search_query.split()[:3])  # 只保留前3个词
                    
                    simple_request = {
                        "query": simple_query,
                        "max_results": max_results
                    }
                    
                    self.logger.info(f"尝试简化查询: {simple_request}")
                    
                    retry_response = await client.post(endpoint, json=simple_request)
                    
                    if retry_response.status_code == 200:
                        result = retry_response.json()
                        self.logger.info(f"简化查询成功: {str(result)[:300]}...")
                        return result
                    else:
                        error_text = retry_response.text
                        self.logger.error(f"DuckDuckGo搜索失败，状态码: {retry_response.status_code}, 错误: {error_text}")
                        return {"error": f"DuckDuckGo搜索失败: HTTP {retry_response.status_code} - {error_text}"}
            
        except Exception as e:
            self.logger.error(f"DuckDuckGo搜索异常: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {"error": f"DuckDuckGo搜索异常: {str(e)}"}
    
    async def _fetch_page_content(self, url: str) -> Any:
        """获取网页具体内容，增加更好的错误处理"""
        try:
            self.logger.info(f"尝试获取页面内容: {url}")
            endpoint = f"{self.base_url}/duckduckgo-search/fetch_content"
            request_body = {"url": url}
            
            # 增加重试机制，但减少重试次数避免长时间等待
            max_retries = 1  # 减少到1次重试
            for attempt in range(max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=20.0) as client:  # 减少超时时间
                        response = await client.post(endpoint, json=request_body)
                        
                        self.logger.info(f"页面内容获取响应状态码: {response.status_code} (尝试 {attempt + 1}/{max_retries + 1})")
                        
                        if response.status_code == 200:
                            result = response.json()
                            # 检查返回的内容是否有效
                            if isinstance(result, str) and len(result.strip()) > 100:
                                self.logger.info(f"成功获取页面内容，长度: {len(str(result))}")
                                return result
                            else:
                                self.logger.warning(f"页面内容为空或过短: {len(str(result))}")
                                return {"error": "页面内容为空或无效"}
                        elif response.status_code == 500 and "httpx" in response.text:
                            # 特定的httpx错误，不重试
                            self.logger.warning(f"DuckDuckGo服务内部错误（httpx问题），跳过此页面")
                            return {"error": "DuckDuckGo服务内部错误"}
                        elif attempt < max_retries:
                            self.logger.warning(f"第 {attempt + 1} 次尝试失败，重试中...")
                            continue
                        else:
                            error_text = response.text[:200]  # 限制错误信息长度
                            self.logger.warning(f"获取页面内容失败: {response.status_code} - {error_text}")
                            return {"error": f"HTTP {response.status_code}"}
                            
                except httpx.TimeoutException:
                    if attempt < max_retries:
                        self.logger.warning(f"第 {attempt + 1} 次请求超时，重试中...")
                        continue
                    else:
                        return {"error": "请求超时"}
                except Exception as e:
                    if attempt < max_retries:
                        self.logger.warning(f"第 {attempt + 1} 次请求异常: {str(e)}，重试中...")
                        continue
                    else:
                        raise e
                        
        except Exception as e:
            self.logger.error(f"获取页面内容异常: {str(e)}")
            return {"error": f"请求异常: {str(e)}"}
    
    async def _translate_query_to_english(self, chinese_query: str) -> str:
        """将中文查询翻译为英文关键词（简化版本）"""
        try:
            # 这里可以集成翻译API或使用本地LLM
            # 暂时使用简单的关键词映射
            keyword_mapping = {
                "天气": "weather",
                "新闻": "news",
                "股票": "stock",
                "人工智能": "artificial intelligence AI",
                "编程": "programming",
                "技术": "technology",
                "今天": "today",
                "最新": "latest",
                "市场": "market",
                "价格": "price"
            }
            
            english_words = []
            for chinese_word, english_word in keyword_mapping.items():
                if chinese_word in chinese_query:
                    english_words.append(english_word)
            
            if english_words:
                return ' '.join(english_words)
            else:
                # 如果没有匹配的关键词，返回原始查询
                return chinese_query
                
        except Exception as e:
            self.logger.warning(f"翻译查询失败: {e}")
            return chinese_query 