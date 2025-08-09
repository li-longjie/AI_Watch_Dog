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
                "description": "使用DuckDuckGo搜索引擎搜索信息，只返回搜索结果列表（标题和链接）。适用于快速查找相关链接",
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
                    "搜索Python编程教程",
                    "查找某个网站的链接",
                    "搜索产品官网",
                    "查找学习资源"
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
                "description": "执行搜索并自动获取前几个搜索结果的详细内容。适用于需要具体内容的查询，如新闻详情、文章内容等",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询关键词",
                        "required": True
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大搜索结果数量，默认8个",
                        "required": False
                    },
                    "max_pages": {
                        "type": "integer", 
                        "description": "最多获取多少个页面的详细内容，默认5个",
                        "required": False
                    }
                },
                "examples": [
                    "今天有哪些新闻？需要具体内容",
                    "最近发生了什么重要事件？",
                    "查找并获取AI发展趋势的详细报告内容",
                    "获取最新科技新闻的详细内容",
                    "搜索政治新闻并获取具体内容"
                ]
            },
            "check_service_status": {
                "description": "检查DuckDuckGo MCP服务状态",
                "parameters": {},
                "examples": [
                    "检查搜索服务是否正常",
                    "测试DuckDuckGo连接"
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
        elif function_name == "check_service_status":
            return await self._check_service_status(parameters)
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
            max_results = parameters.get("max_results", 8)
            max_pages = parameters.get("max_pages", 5)
            
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
            
            # 尝试多个可能的端点，包括直接DuckDuckGo搜索API模拟
            potential_endpoints = [
                f"{self.base_url}/duckduckgo-search/search",  # 主要端点
                f"{self.base_url}/search",  # 简化端点
            ]
            
            for endpoint in potential_endpoints:
                try:
                    self.logger.info(f"尝试端点: {endpoint}")
                    
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.post(endpoint, json=request_body)
                        
                        self.logger.info(f"端点 {endpoint} 响应状态码: {response.status_code}")
                        
                        if response.status_code == 200:
                            result = response.json()
                            self.logger.info(f"搜索成功，返回结果: {str(result)[:300]}...")
                            return result
                        elif response.status_code == 404:
                            # 端点不存在，尝试下一个
                            self.logger.warning(f"端点 {endpoint} 不存在，尝试下一个")
                            continue
                        else:
                            # 其他错误，也尝试下一个端点
                            self.logger.warning(f"端点 {endpoint} 返回错误: {response.status_code}")
                            continue
                            
                except httpx.ConnectError:
                    self.logger.warning(f"无法连接到端点: {endpoint}")
                    continue
                except Exception as e:
                    self.logger.warning(f"端点 {endpoint} 异常: {str(e)}")
                    continue
            
            # 如果所有端点都失败，尝试简化查询再重试一次主端点
            self.logger.warning("所有端点失败，尝试简化查询")
            simple_query = ' '.join(search_query.split()[:3])  # 只保留前3个词
            simple_request = {
                "query": simple_query,
                "max_results": max_results
            }
            
            main_endpoint = f"{self.base_url}/duckduckgo-search/search"
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(main_endpoint, json=simple_request)
                    if response.status_code == 200:
                        result = response.json()
                        self.logger.info(f"简化查询成功: {str(result)[:300]}...")
                        return result
            except Exception as e:
                self.logger.error(f"简化查询也失败: {str(e)}")
            
            # 如果MCP服务不可用，尝试直接DuckDuckGo搜索
            self.logger.warning("MCP服务不可用，尝试直接DuckDuckGo搜索")
            return await self._direct_duckduckgo_search(search_query, max_results)
            
        except Exception as e:
            self.logger.error(f"DuckDuckGo搜索异常: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {"error": f"DuckDuckGo搜索异常: {str(e)}"}
    
    async def _fetch_page_content(self, url: str) -> Any:
        """获取网页具体内容，增加更好的错误处理"""
        try:
            self.logger.info(f"尝试获取页面内容: {url}")
            
            # 尝试多个可能的端点
            potential_endpoints = [
                f"{self.base_url}/duckduckgo-search/fetch_content",  # 主要端点
                f"{self.base_url}/fetch_content",  # 简化端点
            ]
            
            request_body = {"url": url}
            
            # 尝试所有端点
            for endpoint in potential_endpoints:
                try:
                    self.logger.info(f"尝试获取页面内容端点: {endpoint}")
                    
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.post(endpoint, json=request_body)
                        
                        self.logger.info(f"端点 {endpoint} 响应状态码: {response.status_code}")
                        
                        if response.status_code == 200:
                            result = response.json()
                            # 检查返回的内容是否有效
                            if isinstance(result, str) and len(result.strip()) > 100:
                                self.logger.info(f"成功获取页面内容，长度: {len(str(result))}")
                                return result
                            else:
                                self.logger.warning(f"页面内容为空或过短: {len(str(result))}")
                                continue  # 尝试下一个端点
                        elif response.status_code == 404:
                            # 端点不存在，尝试下一个
                            self.logger.warning(f"端点 {endpoint} 不存在，尝试下一个")
                            continue
                        elif response.status_code == 500 and "httpx" in response.text:
                            # 特定的httpx错误，尝试下一个端点
                            self.logger.warning(f"端点 {endpoint} 内部错误，尝试下一个")
                            continue
                        else:
                            # 其他错误，也尝试下一个端点
                            self.logger.warning(f"端点 {endpoint} 返回错误: {response.status_code}")
                            continue
                            
                except httpx.ConnectError:
                    self.logger.warning(f"无法连接到端点: {endpoint}")
                    continue
                except httpx.TimeoutException:
                    self.logger.warning(f"端点 {endpoint} 请求超时")
                    continue
                except Exception as e:
                    self.logger.warning(f"端点 {endpoint} 异常: {str(e)}")
                    continue
            
            return {"error": "无法获取页面内容，所有端点都不可用"}
                        
        except Exception as e:
            self.logger.error(f"获取页面内容异常: {str(e)}")
            return {"error": f"请求异常: {str(e)}"}
    
    async def _direct_duckduckgo_search(self, query: str, max_results: int = 5) -> Any:
        """直接DuckDuckGo搜索（备用方案）"""
        try:
            self.logger.info(f"执行直接DuckDuckGo搜索: {query}")
            
            # 使用DuckDuckGo的即时回答API
            search_url = "https://api.duckduckgo.com/"
            params = {
                'q': query,
                'format': 'json',
                'no_redirect': '1',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(search_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # 构建搜索结果
                    results = []
                    
                    # 即时回答
                    if data.get('Answer'):
                        results.append(f"即时回答: {data['Answer']}")
                    
                    if data.get('AbstractText'):
                        results.append(f"摘要: {data['AbstractText']}")
                        if data.get('AbstractURL'):
                            results.append(f"来源: {data['AbstractURL']}")
                    
                    # 相关主题
                    if data.get('RelatedTopics'):
                        for i, topic in enumerate(data['RelatedTopics'][:3]):
                            if isinstance(topic, dict) and topic.get('Text'):
                                results.append(f"相关{i+1}: {topic['Text']}")
                                if topic.get('FirstURL'):
                                    results.append(f"URL: {topic['FirstURL']}")
                    
                    if results:
                        return '\n'.join(results)
                    else:
                        return f"关于'{query}'的搜索没有找到直接结果。建议: 1) 检查拼写 2) 使用更具体的关键词 3) 尝试英文搜索"
                else:
                    return {"error": f"DuckDuckGo API请求失败: {response.status_code}"}
                    
        except Exception as e:
            self.logger.error(f"直接DuckDuckGo搜索失败: {e}")
            return {"error": f"搜索失败: {str(e)}"}
    
    async def _check_service_status(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """检查DuckDuckGo MCP服务状态"""
        try:
            self.logger.info("检查DuckDuckGo MCP服务状态")
            
            # 测试端点列表
            test_endpoints = [
                f"{self.base_url}/duckduckgo-search/search",
                f"{self.base_url}/search",
            ]
            
            # 简单的测试查询
            test_request = {
                "query": "test",
                "max_results": 1
            }
            
            status_results = []
            
            for endpoint in test_endpoints:
                try:
                    self.logger.info(f"测试端点: {endpoint}")
                    
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.post(endpoint, json=test_request)
                        
                        status_results.append({
                            "endpoint": endpoint,
                            "status": "可用" if response.status_code == 200 else f"错误({response.status_code})",
                            "status_code": response.status_code,
                            "response_time": "正常"
                        })
                        
                        if response.status_code == 200:
                            self.logger.info(f"✅ 端点 {endpoint} 可用")
                        else:
                            self.logger.warning(f"❌ 端点 {endpoint} 不可用: {response.status_code}")
                            
                except httpx.ConnectError:
                    status_results.append({
                        "endpoint": endpoint,
                        "status": "连接失败",
                        "status_code": "无法连接",
                        "response_time": "超时"
                    })
                    self.logger.warning(f"❌ 无法连接到端点: {endpoint}")
                except Exception as e:
                    status_results.append({
                        "endpoint": endpoint,
                        "status": f"异常: {str(e)}",
                        "status_code": "异常",
                        "response_time": "异常"
                    })
                    self.logger.warning(f"❌ 端点 {endpoint} 异常: {str(e)}")
            
            # 统计结果
            available_count = sum(1 for result in status_results if result["status"] == "可用")
            total_count = len(status_results)
            
            return {
                "status": "success",
                "service_status": "可用" if available_count > 0 else "不可用",
                "available_endpoints": available_count,
                "total_endpoints": total_count,
                "endpoints_detail": status_results,
                "recommendation": "正常" if available_count > 0 else "请检查MCP服务是否正确启动"
            }
            
        except Exception as e:
            self.logger.error(f"服务状态检查失败: {e}")
            return {
                "status": "error",
                "message": f"服务状态检查失败: {str(e)}"
            }
    
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