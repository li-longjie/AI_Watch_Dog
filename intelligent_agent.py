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
            return {
                "status": "error",
                "message": f"处理请求时发生错误: {str(e)}"
            }
    
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
    
    async def _execute_tool_call(self, decision: Dict[str, Any], original_query: str) -> Dict[str, Any]:
        """执行工具调用"""
        try:
            tool_name = decision["tool_name"]
            function_name = decision["function_name"]
            parameters = decision["parameters"]
            
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
            prompt = f"""
用户原始问题: {original_query}

工具执行结果: {json.dumps(tool_result, ensure_ascii=False, indent=2)}

请根据工具执行的结果，生成一个自然、友好、准确的回答来回应用户的问题。
要求：
1. 回答要直接针对用户的问题
2. 保留工具结果中的关键信息
3. 使用友好、自然的语言风格
4. 如果工具结果包含大量数据，请进行适当的总结和组织
"""
            
            natural_answer = await LLMService.get_response(prompt)
            return natural_answer
            
        except Exception as e:
            self.logger.error(f"生成自然语言回答失败: {e}")
            # 返回一个基本的回答
            return f"我已经处理了您的请求，工具执行结果：{tool_result}"
    
    async def get_available_capabilities(self) -> Dict[str, Any]:
        """获取当前可用的能力描述"""
        return {
            "total_tools": len(self.tool_registry.tools),
            "available_tools": list(self.tool_registry.tools.keys()),
            "tool_schemas": self.tool_registry.get_tools_schema(),
            "usage_examples": self.tool_registry.get_tool_usage_examples()
        } 