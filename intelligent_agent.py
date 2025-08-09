import json
import re
import logging
from typing import Dict, Any, Optional, List
from mcp_tools import ToolRegistry
from llm_service import LLMService

class IntelligentAgent:
    """智能代理：LLM驱动的意图识别和工具调用"""
    
    def __init__(self, mcp_base_url: str = "http://127.0.0.1:8000"):
        self.tool_registry = ToolRegistry(mcp_base_url)
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def get_system_prompt(self) -> str:
        """构建包含所有工具信息的系统提示词"""
        tools_info = self.tool_registry.format_tools_for_llm()
        
        system_prompt = f"""你是一个智能助手，能够根据用户的自然语言请求，自主判断是否需要使用MCP工具，以及使用哪个工具的哪个函数。

{tools_info}

## 工作流程
1. **意图分析**: 分析用户的请求，判断是否需要使用MCP工具
2. **工具选择**: 如果需要使用工具，选择最合适的工具和函数
3. **参数提取**: 从用户请求中提取函数所需的参数
4. **执行决策**: 决定是否调用工具，或直接回答

## 回复格式
当需要使用MCP工具时，请严格按照以下JSON格式回复：

```json
{{
    "action": "use_tool",
    "tool_name": "工具名称",
    "function_name": "函数名称", 
    "parameters": {{
        "参数名": "参数值"
    }},
    "reasoning": "选择此工具的理由"
}}
```

当不需要使用工具时，请按照以下格式回复：

```json
{{
    "action": "direct_answer",
    "answer": "直接回答用户的问题",
    "reasoning": "不使用工具的理由"
}}
```

## 重要原则
- 优先使用MCP工具来获取实时、准确的信息
- 仔细分析用户请求，准确提取参数
- 如果用户请求涉及多个工具，选择最核心的工具
- 保持回复的JSON格式正确性
- 对于历史监控记录、活动检索等需求，不要使用MCP工具，这类需求会由RAG系统处理
- **对于逻辑推理、复杂分析、步骤性思考问题，优先使用Sequential Thinking推理工具**
- **逻辑推理关键词：推理、逻辑、分析、思考、证明、假设、矛盾、嫌疑人、案件、犯罪、窃贼、侦探、线索、证据、推断、演绎、归纳、步骤、逐步等**

请根据用户的请求进行智能判断和响应。"""

        return system_prompt
    
    async def process_user_request(self, user_query: str) -> Dict[str, Any]:
        """处理用户请求的主入口"""
        try:
            # 构建完整的对话prompt
            system_prompt = self.get_system_prompt()
            full_prompt = f"{system_prompt}\n\n用户请求: {user_query}"
            
            # 调用LLM进行意图识别和工具选择
            llm_response = await LLMService.get_response(full_prompt)
            
            # 检查LLM响应是否包含API错误
            if "API调用失败" in llm_response or "生成回答错误" in llm_response or "网络请求错误" in llm_response:
                # API调用失败，使用本地意图识别
                return await self._handle_api_failure(user_query, llm_response)
            
            # 解析LLM响应
            decision = self._parse_llm_response(llm_response)
            
            if decision["action"] == "use_tool":
                # 执行工具调用
                return await self._execute_tool_call(decision, user_query)
            else:
                # 直接回答
                return {
                    "status": "success",
                    "answer": decision["answer"],
                    "method": "direct_answer",
                    "reasoning": decision.get("reasoning", "")
                }
                
        except Exception as e:
            self.logger.error(f"处理用户请求失败: {e}")
            return await self._handle_api_failure(user_query, str(e))
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM的JSON响应"""
        try:
            # 尝试提取JSON内容
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 如果没有找到markdown格式的JSON，尝试直接解析整个响应
                json_str = response.strip()
            
            # 解析JSON
            decision = json.loads(json_str)
            
            # 验证必需字段
            if "action" not in decision:
                raise ValueError("缺少action字段")
            
            if decision["action"] == "use_tool":
                required_fields = ["tool_name", "function_name", "parameters"]
                for field in required_fields:
                    if field not in decision:
                        raise ValueError(f"缺少必需字段: {field}")
            elif decision["action"] == "direct_answer":
                if "answer" not in decision:
                    raise ValueError("缺少answer字段")
            
            return decision
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON解析失败: {e}，尝试提取关键信息")
            return self._fallback_parse(response)
        except Exception as e:
            self.logger.warning(f"响应解析失败: {e}，使用fallback解析")
            return self._fallback_parse(response)
    
    def _fallback_parse(self, response: str) -> Dict[str, Any]:
        """当JSON解析失败时的回退解析方法"""
        # 简单的关键词匹配来判断意图
        response_lower = response.lower()
        
        # 检查是否提到了工具名
        tool_names = list(self.tool_registry.tools.keys())
        for tool_name in tool_names:
            if tool_name.lower() in response_lower:
                return {
                    "action": "use_tool",
                    "tool_name": tool_name,
                    "function_name": "auto_detect",  # 需要进一步处理
                    "parameters": {},
                    "reasoning": "基于关键词匹配的回退解析"
                }
        
        # 默认作为直接回答处理
        return {
            "action": "direct_answer",
            "answer": response,
            "reasoning": "LLM响应格式不正确，作为直接回答处理"
        }
    
    async def _handle_api_failure(self, user_query: str, error_message: str) -> Dict[str, Any]:
        """处理API调用失败的情况，使用本地意图识别"""
        self.logger.warning(f"API调用失败，使用本地意图识别: {error_message}")
        
        # 使用本地关键词匹配进行简单的意图识别
        query_lower = user_query.lower()
        
        # 优先检查新闻相关查询（避免被时间关键词误匹配）
        news_keywords = ["新闻", "消息", "事件", "发生", "最新", "突发", "政治", "经济", "国际", "国内"]
        if any(keyword in query_lower for keyword in news_keywords):
            # 这是新闻查询，直接跳到搜索处理逻辑
            pass
        # 时间相关查询（纯时间查询，不包含新闻关键词）
        elif any(keyword in query_lower for keyword in ["时间", "几点", "现在", "日期"]) or (
            any(keyword in query_lower for keyword in ["今天", "明天", "昨天"]) and 
            not any(keyword in query_lower for keyword in news_keywords)
        ):
            try:
                # 直接调用时间工具 (使用正确的工具ID "time")
                time_tool = self.tool_registry.get_tool("time")
                if time_tool:
                    result = await time_tool.execute_function("get_current_time", {})
                    if result.get("status") == "success":
                        time_data = result.get("data", {})
                        if isinstance(time_data, dict):
                            # 格式化时间信息为友好的回答
                            datetime_str = time_data.get("datetime_string", "")
                            weekday_zh = time_data.get("weekday_zh", "")
                            source = result.get("source", "unknown")
                            
                            answer = f"现在是 {datetime_str} {weekday_zh}。"
                            if source == "local_system":
                                answer += " (使用本地系统时间)"
                            
                            return {
                                "status": "success", 
                                "answer": answer,
                                "method": "local_tool_call",
                                "reasoning": "API不可用，使用本地时间工具"
                            }
                        else:
                            return {
                                "status": "success",
                                "answer": f"当前时间信息：{time_data}",
                                "method": "local_tool_call", 
                                "reasoning": "API不可用，使用本地时间工具"
                            }
            except Exception as e:
                self.logger.error(f"本地时间工具调用失败: {e}")
        
        # 文件系统相关查询
        file_keywords = ["文件", "文件夹", "桌面", "目录", "列表"]
        if any(keyword in query_lower for keyword in file_keywords):
            try:
                filesystem_tool = self.tool_registry.get_tool("filesystem")
                if filesystem_tool:
                    result = await filesystem_tool.execute_function("list_directory", {"path": "."})
                    if result.get("status") == "success":
                        return {
                            "status": "success",
                            "answer": f"文件列表：{result.get('data', result)}",
                            "method": "local_tool_call",
                            "reasoning": "API不可用，使用本地文件系统工具"
                        }
            except Exception as e:
                self.logger.error(f"本地文件系统工具调用失败: {e}")
        
        # 逻辑推理相关查询（优先级高于搜索）
        reasoning_keywords = ["推理", "逻辑", "分析", "思考", "证明", "假设", "矛盾", "嫌疑人", "案件", "犯罪", "窃贼", "谋杀", "破案", "侦探", "线索", "证据", "推断", "演绎", "归纳", "步骤", "逐步"]
        
        if any(keyword in query_lower for keyword in reasoning_keywords):
            try:
                sequential_thinking_tool = self.tool_registry.get_tool("sequential_thinking")
                if sequential_thinking_tool:
                    result = await sequential_thinking_tool.execute_function("sequential_thinking", {
                        "prompt": user_query,
                        "max_steps": 5
                    })
                    if result.get("status") == "success":
                        formatted_response = result.get("formatted_response", "")
                        return {
                            "status": "success",
                            "answer": formatted_response,
                            "method": "local_tool_call",
                            "reasoning": "API不可用，使用本地Sequential Thinking推理工具"
                        }
            except Exception as e:
                self.logger.error(f"本地推理工具调用失败: {e}")
        
        # 搜索相关查询
        search_keywords = ["搜索", "查找", "查询", "检索", "联网", "网络", "信息", "资料", "桃花"] + news_keywords
        
        if any(keyword in query_lower for keyword in search_keywords):
            try:
                duckduckgo_tool = self.tool_registry.get_tool("duckduckgo")
                if duckduckgo_tool:
                    # 首先检查服务状态
                    status_result = await duckduckgo_tool.execute_function("check_service_status", {})
                    if status_result.get("status") == "success" and status_result.get("service_status") == "可用":
                        # 检查是否是新闻相关查询，如果是则获取详细内容
                        if any(keyword in query_lower for keyword in news_keywords):
                            # 新闻查询：搜索并获取详细内容
                            search_result = await duckduckgo_tool.execute_function("search_and_fetch", {
                                "query": user_query,
                                "max_results": 8,
                                "max_pages": 5
                            })
                        else:
                            # 普通搜索：只获取搜索结果列表
                            search_result = await duckduckgo_tool.execute_function("search", {
                                "query": user_query,
                                "max_results": 3
                            })
                        if search_result.get("status") == "success":
                            # 检查是否有详细内容
                            if "detailed_content" in search_result and search_result["detailed_content"]:
                                # 有详细内容，格式化显示
                                detailed_content = search_result["detailed_content"]
                                answer = f"根据您的查询「{user_query}」，我找到了以下详细信息：\n\n"
                                
                                for i, content_item in enumerate(detailed_content, 1):
                                    answer += f"📰 **第{i}条内容**\n"
                                    answer += f"🔗 来源：{content_item.get('url', '未知')}\n"
                                    answer += f"📝 内容：{content_item.get('content', '无内容')}\n\n"
                                
                                return {
                                    "status": "success",
                                    "answer": answer,
                                    "method": "local_tool_call_with_content",
                                    "reasoning": "API不可用，使用本地DuckDuckGo搜索工具并获取了详细内容"
                                }
                            else:
                                # 只有搜索结果，没有详细内容，但如果是新闻查询，提供更好的格式
                                search_results = search_result.get('search_results', '未找到结果')
                                if any(keyword in query_lower for keyword in news_keywords):
                                    # 新闻查询但没有详细内容，提供改进的格式和说明
                                    answer = f"📰 根据您的查询「{user_query}」，我找到了以下新闻来源：\n\n"
                                    
                                    # 格式化搜索结果
                                    if isinstance(search_results, list) and len(search_results) > 0:
                                        formatted_results = search_results[0] if isinstance(search_results[0], str) else str(search_results[0])
                                    else:
                                        formatted_results = str(search_results)
                                    
                                    # 清理格式
                                    formatted_results = formatted_results.replace("['", "").replace("']", "").replace("\\n", "\n")
                                    answer += f"{formatted_results}\n\n"
                                    answer += "💡 由于网页内容获取服务暂时不可用，我只能提供新闻标题和链接。您可以点击链接查看完整内容，或稍后重试获取详细内容。"
                                    
                                    return {
                                        "status": "success",
                                        "answer": answer,
                                        "method": "local_tool_call_news_fallback",
                                        "reasoning": "API不可用，使用本地DuckDuckGo搜索工具，但内容获取服务不可用"
                                    }
                                else:
                                    # 普通搜索结果
                                    return {
                                        "status": "success",
                                        "answer": f"搜索结果：{search_results}",
                                        "method": "local_tool_call",
                                        "reasoning": "API不可用，使用本地DuckDuckGo搜索工具"
                                    }
                    else:
                        return {
                            "status": "error",
                            "answer": f"抱歉，搜索服务暂时不可用。请检查MCP服务状态。详情：{status_result.get('message', '未知错误')}",
                            "method": "service_unavailable",
                            "reasoning": "DuckDuckGo MCP服务不可用"
                        }
            except Exception as e:
                self.logger.error(f"本地搜索工具调用失败: {e}")
                return {
                    "status": "error",
                    "answer": f"搜索功能暂时不可用，错误：{str(e)}",
                    "method": "local_tool_error",
                    "reasoning": f"本地搜索工具异常: {str(e)}"
                }
        
        # 如果无法匹配到具体工具，返回通用错误信息
        return {
            "status": "error",
            "answer": f"抱歉，AI服务暂时不可用。您询问的是：{user_query}。请稍后重试，或者尝试重新描述您的问题。",
            "method": "fallback_response",
            "reasoning": f"API服务不可用: {error_message}"
        }
    
    async def _execute_tool_call(self, decision: Dict[str, Any], original_query: str) -> Dict[str, Any]:
        """执行工具调用"""
        try:
            tool_name = decision["tool_name"]
            function_name = decision["function_name"]
            parameters = decision["parameters"]
            
            # 工具名称映射：将中文名称映射到英文ID
            tool_name_mapping = {
                "时间工具": "time",
                "文件系统工具": "filesystem", 
                "网页抓取工具": "web",
                "浏览器工具": "browser",
                "搜索工具": "duckduckgo",
                "DuckDuckGo搜索工具": "duckduckgo",
                "思考工具": "sequential_thinking",
                "Sequential Thinking推理工具": "sequential_thinking",
                "推理工具": "sequential_thinking",
                "地图工具": "baidu_map",
                "百度地图工具": "baidu_map"
            }
            
            # 如果是中文名称，转换为英文ID
            if tool_name in tool_name_mapping:
                tool_name = tool_name_mapping[tool_name]
            
            # 特殊处理：如果function_name是auto_detect，需要进一步确定
            if function_name == "auto_detect":
                function_name = self._auto_detect_function(tool_name, original_query)
                if not function_name:
                    return {
                        "status": "error",
                        "message": f"无法确定工具 {tool_name} 的具体函数"
                    }
            
            # 执行工具函数
            tool_result = await self.tool_registry.execute_tool_function(
                tool_name, function_name, parameters
            )
            
            if tool_result["status"] == "success":
                # 使用LLM处理工具结果，生成自然语言回答
                answer = await self._generate_natural_answer(original_query, tool_result)
                
                return {
                    "status": "success",
                    "answer": answer,
                    "method": "tool_call",
                    "tool_used": f"{tool_name}.{function_name}",
                    "tool_result": tool_result,
                    "reasoning": decision.get("reasoning", "")
                }
            else:
                return {
                    "status": "error",
                    "message": tool_result.get("message", "工具执行失败")
                }
                
        except Exception as e:
            self.logger.error(f"执行工具调用失败: {e}")
            return {
                "status": "error",
                "message": f"工具执行错误: {str(e)}"
            }
    
    def _auto_detect_function(self, tool_name: str, query: str) -> Optional[str]:
        """自动检测工具的函数名"""
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return None
        
        functions = tool.get_available_functions()
        if len(functions) == 1:
            # 如果只有一个函数，直接返回
            return list(functions.keys())[0]
        
        # 简单的关键词匹配
        query_lower = query.lower()
        for func_name, func_info in functions.items():
            # 检查函数描述中的关键词
            if any(example.lower() in query_lower for example in func_info.get("examples", [])):
                return func_name
        
        # 返回第一个函数作为默认
        return list(functions.keys())[0] if functions else None
    
    async def _generate_natural_answer(self, original_query: str, tool_result: Dict[str, Any]) -> str:
        """将工具结果转换为自然语言回答"""
        try:
            # 首先检查工具结果的结构
            self.logger.info(f"工具执行结果: {tool_result}")
            
            # 让所有结果都经过LLM处理，以便生成中文回答
            
            # 如果LLM服务可用，尝试生成自然语言
            prompt = f"""
用户原始问题: {original_query}

工具执行结果: {json.dumps(tool_result, ensure_ascii=False, indent=2)}

请根据工具执行的结果，生成一个自然、友好、准确的中文回答来回应用户的问题。
要求：
1. 必须使用中文回答
2. 回答要直接针对用户的问题
3. 保留工具结果中的关键信息
4. 使用友好、自然的中文语言风格
5. 如果是新闻搜索结果，请严格按照以下格式展示，并尽可能显示7-10条新闻：

今天的热点新闻
以下是今天的热点新闻摘要，按重要性排序：

[序号]. [中文标题]
   时间：今天
   事件概述：[用中文详细描述新闻内容，包含关键信息和背景]
   详细报道：[完整URL链接]

6. 每条新闻都必须包含完整的URL链接
7. 请尽量显示所有可用的新闻，目标是至少7条新闻
8. 如果工具结果包含大量数据，请进行适当的总结和组织
9. 对于英文内容，请提供中文说明或翻译关键信息
10. 确保所有URL链接都完整显示，不要省略
"""
            
            natural_answer = await LLMService.get_response(prompt)
            
            # 检查LLM响应是否有错误
            if "API调用失败" in natural_answer or "生成回答错误" in natural_answer:
                # LLM服务不可用，使用上面的直接处理结果
                return f"我已经处理了您的请求：{json.dumps(tool_result, ensure_ascii=False, indent=2)}"
            
            return natural_answer
            
        except Exception as e:
            self.logger.error(f"生成自然语言回答失败: {e}")
            # 返回一个基本的回答，确保包含工具结果的关键信息
            if tool_result.get("status") == "success" and "search_results" in tool_result:
                return f"搜索完成，结果：{tool_result['search_results']}"
            else:
                return f"我已经处理了您的请求，工具执行结果：{json.dumps(tool_result, ensure_ascii=False, indent=2)}"
    
    def _format_search_results(self, search_results, query: str) -> str:
        """格式化搜索结果为更清晰的显示"""
        try:
            formatted_text = f"📰 根据您的搜索「{query}」，为您找到以下新闻资讯：\n\n"
            
            # 处理不同类型的搜索结果
            if isinstance(search_results, str):
                # 解析字符串格式的搜索结果
                if "Found" in search_results and "search results:" in search_results:
                    # 处理标准格式的搜索结果
                    lines = search_results.split('\n')
                    news_items = []
                    current_item = {}
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # 检测新闻条目开始（数字开头）
                        if line.startswith(('1.', '2.', '3.', '4.', '5.')):
                            if current_item:
                                news_items.append(current_item)
                                current_item = {}
                            current_item['title'] = line[2:].strip()
                        elif line.startswith('URL:'):
                            current_item['url'] = line[4:].strip()
                        elif line.startswith('Summary:'):
                            current_item['summary'] = line[8:].strip()
                    
                    # 添加最后一个条目
                    if current_item:
                        news_items.append(current_item)
                    
                    # 格式化输出
                    if news_items:
                        for i, item in enumerate(news_items, 1):
                            formatted_text += f"🔸 **第{i}条新闻**\n"
                            formatted_text += f"   📄 标题：{item.get('title', '未知标题')}\n"
                            if 'summary' in item:
                                summary = item['summary'][:150] + "..." if len(item['summary']) > 150 else item['summary']
                                formatted_text += f"   📝 摘要：{summary}\n"
                            if 'url' in item:
                                formatted_text += f"   🔗 链接：{item['url']}\n"
                            formatted_text += "\n"
                    else:
                        # 如果解析失败，直接显示原始结果
                        formatted_text += self._clean_search_text(search_results)
                else:
                    # 其他字符串格式，进行清理
                    formatted_text += self._clean_search_text(search_results)
                    
            elif isinstance(search_results, list):
                # 处理列表格式 - 特别针对DuckDuckGo的返回格式
                for i, item in enumerate(search_results, 1):
                    if isinstance(item, str):
                        # 尝试解析字符串中的结构化内容
                        if "Found" in item and "search results:" in item:
                            parsed_items = self._parse_search_string(item)
                            if parsed_items:
                                for j, parsed_item in enumerate(parsed_items, 1):
                                    formatted_text += f"🔸 **第{j}条新闻**\n"
                                    formatted_text += f"   📄 标题：{parsed_item.get('title', '未知标题')}\n"
                                    if 'summary' in parsed_item and parsed_item['summary']:
                                        summary = parsed_item['summary'][:200] + "..." if len(parsed_item['summary']) > 200 else parsed_item['summary']
                                        formatted_text += f"   📝 摘要：{summary}\n"
                                    if 'url' in parsed_item and parsed_item['url']:
                                        formatted_text += f"   🔗 链接：{parsed_item['url']}\n"
                                    formatted_text += "\n"
                            else:
                                formatted_text += f"🔸 **搜索结果**\n"
                                formatted_text += self._clean_search_text(item) + "\n\n"
                        else:
                            formatted_text += f"🔸 **第{i}条信息**\n"
                            formatted_text += self._clean_search_text(item) + "\n\n"
                    elif isinstance(item, dict):
                        formatted_text += f"🔸 **第{i}条新闻**\n"
                        formatted_text += f"   📄 标题：{item.get('title', '未知标题')}\n"
                        if 'summary' in item:
                            formatted_text += f"   📝 摘要：{item['summary']}\n"
                        if 'url' in item:
                            formatted_text += f"   🔗 链接：{item['url']}\n"
                        formatted_text += "\n"
                        
            elif isinstance(search_results, dict):
                # 处理字典格式
                formatted_text += "📊 搜索结果详情：\n\n"
                for key, value in search_results.items():
                    formatted_text += f"🔹 {key}：{value}\n"
                    
            else:
                # 其他格式，转换为字符串
                formatted_text += self._clean_search_text(str(search_results))
            
            # 添加友好的结尾
            formatted_text += "\n💡 如果您需要查看具体某条新闻的详细内容，请告诉我您感兴趣的新闻标题。"
            
            return formatted_text
            
        except Exception as e:
            self.logger.error(f"格式化搜索结果失败: {e}")
            return f"根据您的搜索「{query}」，我找到了以下信息：\n\n{str(search_results)}"
    
    def _clean_search_text(self, text: str) -> str:
        """清理搜索文本，使其更易读"""
        # 移除多余的换行符和空格
        cleaned = text.replace('\n\n\n', '\n\n').strip()
        return cleaned
    
    def _parse_search_string(self, search_text: str) -> List[Dict[str, str]]:
        """从搜索结果字符串中解析出结构化的新闻条目"""
        try:
            news_items = []
            lines = search_text.split('\n')
            current_item = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 检测新闻条目开始（数字开头）
                if line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                    if current_item:
                        news_items.append(current_item)
                        current_item = {}
                    # 提取标题（去掉数字前缀）
                    title = line[2:].strip()
                    current_item['title'] = title
                elif line.startswith('URL:'):
                    current_item['url'] = line[4:].strip()
                elif line.startswith('Summary:'):
                    current_item['summary'] = line[8:].strip()
                elif current_item and 'summary' in current_item and not line.startswith(('URL:', 'Summary:')):
                    # 继续拼接摘要内容（多行摘要）
                    current_item['summary'] += ' ' + line
            
            # 添加最后一个条目
            if current_item:
                news_items.append(current_item)
            
            return news_items
            
        except Exception as e:
            self.logger.error(f"解析搜索字符串失败: {e}")
            return []
    

    
    async def get_available_capabilities(self) -> Dict[str, Any]:
        """获取当前可用的能力描述"""
        return {
            "total_tools": len(self.tool_registry.tools),
            "available_tools": list(self.tool_registry.tools.keys()),
            "tool_schemas": self.tool_registry.get_tools_schema(),
            "usage_examples": self.tool_registry.get_tool_usage_examples()
        } 