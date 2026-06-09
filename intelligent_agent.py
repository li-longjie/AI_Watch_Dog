import json
import re
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from abc import ABC, abstractmethod
from mcp_tools import ToolRegistry
from llm_service import LLMService

# ==================== 多智能体基础架构 ====================

class BaseAgent(ABC):
    """基础Agent抽象类"""
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Agent.{name}")

    @abstractmethod
    async def process(self, query: str, mode: str, context: dict) -> Tuple[dict, float]:
        """处理请求并返回结果和置信度"""
        pass

class ForceRouteAgent(BaseAgent):
    """强制路由Agent - 快速关键词匹配"""
    def __init__(self, parent_agent):
        super().__init__("ForceRoute")
        self.parent = parent_agent

    async def process(self, query: str, mode: str, context: dict) -> Tuple[dict, float]:
        query_lower = query.lower()

        # 1. 优先匹配工具操作（Chrome、截图等）
        chrome_keywords = [
            "截图", "截取", "拍照", "网络监控", "网络请求", "监听", "API", "接口",
            "网站", "网页", "浏览", "页面", "导航", "跳转",
            # 浏览历史相关
            "浏览历史", "浏览记录", "访问记录", "历史记录", "分析浏览记录",
            "我浏览了", "都浏览了", "访问了哪些", "浏览了哪些", "去了哪些", "看了哪些",
            "昨天浏览", "昨天访问", "昨天看了", "昨天去了", "最近浏览", "最近访问",
            "一个月", "这个月", "近一个月", "这段时间", "上周", "最近几天",
            "我都去了", "我都看了", "我都访问了", "都访问了哪些"
        ]
        if any(keyword in query_lower for keyword in chrome_keywords):
            self.logger.info(f"🎯 ForceRouteAgent检测到Chrome工具操作: {query}")
            result = await self.parent._handle_api_failure(query, "强制路由到Chrome工具", mode)

            # 检查结果状态，只有成功才返回
            if result.get("status") == "success":
                return result, 0.9  # 高置信度
            else:
                self.logger.warning(f"Chrome工具调用失败: {result.get('status', 'unknown')}")
                return None, 0.0  # 失败时返回None

        # 2. 搜索相关操作
        search_keywords = ["搜索", "查找", "查询", "检索", "联网", "网络信息", "资料", "新闻"]
        if any(keyword in query_lower for keyword in search_keywords):
            self.logger.info(f"🎯 ForceRouteAgent检测到搜索操作: {query}")
            result = await self.parent._handle_api_failure(query, "强制路由到搜索工具", mode)

            # 检查结果状态，只有成功才返回
            if result.get("status") == "success":
                return result, 0.9  # 高置信度
            else:
                self.logger.warning(f"搜索工具调用失败: {result.get('status', 'unknown')}")
                return None, 0.0  # 失败时返回None

        # 3. 原有的数据库路由逻辑
        if mode == "rag":
            video_keywords = ["看手机", "玩手机", "手机", "睡觉", "休息", "睡眠", "喝水", "饮水",
                              "吃东西", "吃饭", "用餐", "工作", "学习", "专注"]
            if any(keyword in query_lower for keyword in video_keywords):
                self.logger.info(f"🎯 ForceRouteAgent检测到视频活动查询: {query}")
                result = await self.parent._handle_api_failure(query, "强制路由到视频数据库", mode)

                # 检查结果状态，只有成功才返回
                if result.get("status") == "success":
                    return result, 0.9  # 高置信度
                else:
                    self.logger.warning(f"视频数据库查询失败: {result.get('status', 'unknown')}")
                    return None, 0.0  # 失败时返回None

        elif mode == "activity":
            activity_keywords = ["访问", "浏览", "网站", "网页", "url", "链接", "页面", "应用", "软件",
                                 "程序", "窗口", "点击", "操作", "使用", "运行", "执行", "打开", "关闭", "视频", "看了", "观看"]
            if any(keyword in query_lower for keyword in activity_keywords):
                self.logger.info(f"🎯 ForceRouteAgent检测到桌面活动查询: {query}")
                result = await self.parent._handle_api_failure(query, "强制路由到活动数据库", mode)

                # 检查结果状态，只有成功才返回
                if result.get("status") == "success":
                    return result, 0.9  # 高置信度
                else:
                    self.logger.warning(f"活动数据库查询失败: {result.get('status', 'unknown')}")
                    return None, 0.0  # 失败时返回None

        return None, 0.0  # 无法处理

class LLMAnalysisAgent(BaseAgent):
    """LLM智能分析Agent"""
    def __init__(self, parent_agent):
        super().__init__("LLMAnalysis")
        self.parent = parent_agent

    async def process(self, query: str, mode: str, context: dict) -> Tuple[dict, float]:
        try:
            # 复用现有的LLM逻辑
            system_prompt = self.parent.get_system_prompt()
            full_prompt = f"{system_prompt}\n\n用户请求: {query}"

            self.logger.info(f"🤖 LLMAnalysisAgent开始分析: {query}")
            llm_response = await LLMService.get_response(full_prompt)

            if "API调用失败" not in llm_response and "生成回答错误" not in llm_response and "网络请求错误" not in llm_response:
                decision = self.parent._parse_llm_response(llm_response)

                if decision["action"] == "use_tool":
                    result = await self.parent._execute_tool_call(decision, query)

                    # 检查工具调用结果
                    if result.get("status") == "success":
                        self.logger.info(f"✅ LLMAnalysisAgent工具调用成功: {decision['tool_name']}")
                        return result, 0.8  # 中高置信度
                    else:
                        self.logger.warning(f"LLMAnalysisAgent工具调用失败: {result.get('status', 'unknown')}")
                        return None, 0.0  # 工具调用失败时返回None
                else:
                    # 检查是否应该查询数据库
                    query_lower = query.lower()
                    if any(keyword in query_lower for keyword in ["什么时候", "几点", "时间", "历史", "记录", "查询"]):
                        self.logger.info(f"🎯 LLMAnalysisAgent检测到查询意图，转为数据库查询")
                        result = await self.parent._handle_api_failure(query, "LLM直接回答但强制路由数据库", mode)

                        # 检查数据库查询结果
                        if result.get("status") == "success":
                            return result, 0.7
                        else:
                            self.logger.warning(f"LLMAnalysisAgent数据库查询失败: {result.get('status', 'unknown')}")
                            return None, 0.0
                    else:
                        result = {
                            "status": "success",
                            "answer": decision["answer"],
                            "method": "direct_answer",
                            "reasoning": decision.get("reasoning", "")
                        }
                        self.logger.info(f"💬 LLMAnalysisAgent直接回答")
                        return result, 0.7  # 中等置信度

        except Exception as e:
            self.logger.error(f"LLMAnalysisAgent处理失败: {e}")

        return None, 0.0  # 处理失败

class LocalFallbackAgent(BaseAgent):
    """本地回退Agent"""
    def __init__(self, parent_agent):
        super().__init__("LocalFallback")
        self.parent = parent_agent

    async def process(self, query: str, mode: str, context: dict) -> Tuple[dict, float]:
        # 复用现有的本地回退逻辑
        self.logger.info(f"🔧 LocalFallbackAgent开始处理: {query}")
        result = await self.parent._handle_api_failure(query, "本地回退处理", mode)

        # 检查处理结果并记录详细日志
        if result.get("status") == "success":
            method = result.get("method", "unknown")
            self.logger.info(f"✅ LocalFallbackAgent处理成功，方法: {method}")
        else:
            self.logger.warning(f"⚠️ LocalFallbackAgent处理未完全成功: {result.get('status')}")

        return result, 0.6  # 中等置信度

# ==================== 主智能代理 ====================

class IntelligentAgent:
    """智能代理：LLM驱动的意图识别和工具调用"""

    def __init__(self, mcp_base_url: str = "http://127.0.0.1:8000"):
        self.tool_registry = ToolRegistry(mcp_base_url)
        self.logger = logging.getLogger(self.__class__.__name__)

        # 🚀 多智能体架构 - 懒加载Agent实例
        self._agents = None
        self._multi_agent_enabled = True  # 可通过配置开关控制
        self._fast_response_mode = True   # 启用快速响应优化

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

    async def process_user_request(self, user_query: str, mode: str = "rag") -> Dict[str, Any]:
        """处理用户请求的主入口 - 多智能体协作版本"""
        try:
            # 🚀 多智能体模式启用检查
            if self._multi_agent_enabled:
                return await self._multi_agent_process(user_query, mode)
            else:
                return await self._original_process_logic(user_query, mode)

        except Exception as e:
            self.logger.error(f"多智能体处理失败: {e}")
            # 回退到原有逻辑
            return await self._original_process_logic(user_query, mode)

    async def _multi_agent_process(self, user_query: str, mode: str) -> Dict[str, Any]:
        """多智能体协作处理"""
        # 初始化Agent（懒加载）
        if self._agents is None:
            self._agents = [
                ForceRouteAgent(self),
                LLMAnalysisAgent(self),
                LocalFallbackAgent(self)
            ]
            self.logger.info("🚀 多智能体系统已初始化")

        # 并行调用所有Agent
        self.logger.info(f"🎯 开始多智能体协作处理: {user_query}")
        tasks = []
        for agent in self._agents:
            task = asyncio.create_task(
                self._safe_agent_call(agent, user_query, mode)
            )
            tasks.append(task)

        # 🚀 智能早停机制：快速Agent优先，LLM后台运行
        results = [None] * len(self._agents)
        best_result = None
        fast_agents_done = 0  # 快速Agent完成计数

        try:
            # 使用 asyncio.as_completed 实现真正的并行
            for completed_task in asyncio.as_completed(tasks, timeout=15.0):
                try:
                    result, confidence = await completed_task
                    agent_idx = tasks.index(completed_task)
                    results[agent_idx] = (result, confidence)
                    agent_name = self._agents[agent_idx].__class__.__name__

                    # 🎯 早停策略1：ForceRoute高置信度立即返回
                    if agent_name == "ForceRouteAgent" and result and confidence >= 0.8:
                        self.logger.info(f"⚡ 强制路由早停：{agent_name}高置信度({confidence})")
                        best_result = result
                        break

                    # 🎯 早停策略2：快速Agent达到阈值后等待一小段时间
                    if agent_name in ["ForceRouteAgent", "LocalFallbackAgent"]:
                        fast_agents_done += 1
                        if result and confidence >= 0.6:
                            if not best_result or confidence > getattr(best_result, 'confidence', 0):
                                best_result = result
                                self.logger.info(f"⚡ 快速Agent响应：{agent_name}({confidence})")

                        # 如果两个快速Agent都完成了，等待0.5秒看LLM是否也完成
                        if fast_agents_done >= 2 and best_result:
                            self.logger.info("⚡ 快速Agent完成，短暂等待LLM...")
                            try:
                                # 等待0.5秒，看LLM是否能快速完成
                                remaining_tasks = [t for t in tasks if not t.done()]
                                if remaining_tasks:
                                    llm_results = await asyncio.wait_for(
                                        asyncio.gather(*remaining_tasks, return_exceptions=True),
                                        timeout=0.5
                                    )
                                    # 检查LLM结果是否更好
                                    for i, llm_result in enumerate(llm_results):
                                        if isinstance(llm_result, tuple) and len(llm_result) == 2:
                                            llm_res, llm_conf = llm_result
                                            if llm_res and llm_conf > confidence:
                                                self.logger.info(f"⚡ LLM提供更好结果({llm_conf})")
                                                best_result = llm_res
                                                break
                            except asyncio.TimeoutError:
                                self.logger.info("⚡ LLM未在0.5秒内完成，使用快速结果")
                            break

                    # LLM Agent完成
                    elif agent_name == "LLMAnalysisAgent" and result:
                        self.logger.info(f"🧠 LLM分析完成：{agent_name}({confidence})")
                        if not best_result or confidence > 0.75:
                            best_result = result

                except Exception as e:
                    self.logger.error(f"Agent任务异常: {e}")
                    continue

        except asyncio.TimeoutError:
            self.logger.warning("多智能体处理整体超时")

        # 如果没有获得结果，使用传统选择逻辑
        if not best_result:
            best_result = self._select_best_result(results, user_query)

        if best_result:
            self.logger.info(f"✅ 多智能体处理成功，选择了最佳结果")
            return best_result
        else:
            # 完全回退到原有逻辑
            self.logger.warning("所有Agent都无法处理，回退到原有逻辑")
            return await self._original_process_logic(user_query, mode)

    async def _original_process_logic(self, user_query: str, mode: str) -> Dict[str, Any]:
        """原有的处理逻辑（保持向后兼容）"""
        try:
            # 🔥 强制数据库路由检查 - 优先于LLM调用
            query_lower = user_query.lower()

            # 检查是否包含数据库查询关键词
            if mode == "rag":
                video_activity_keywords = ["看手机", "玩手机", "手机", "睡觉", "休息", "睡眠", "喝水", "饮水",
                                           "吃东西", "吃饭", "用餐", "工作", "学习", "专注"]
                if any(keyword in query_lower for keyword in video_activity_keywords):
                    self.logger.info(f"🎯 检测到视频活动查询关键词，直接路由到数据库: {user_query}")
                    return await self._handle_api_failure(user_query, "强制路由到视频活动数据库", mode)

            elif mode == "activity":
                desktop_activity_keywords = ["访问", "浏览", "网站", "网页", "url", "链接", "页面", "应用", "软件",
                                             "程序", "窗口", "点击", "操作", "使用", "运行", "执行", "打开", "关闭", "视频", "看了", "观看"]
                if any(keyword in query_lower for keyword in desktop_activity_keywords):
                    self.logger.info(f"🎯 检测到桌面活动查询关键词，直接路由到数据库: {user_query}")
                    return await self._handle_api_failure(user_query, "强制路由到桌面活动数据库", mode)

            # 构建完整的对话prompt
            system_prompt = self.get_system_prompt()
            full_prompt = f"{system_prompt}\n\n用户请求: {user_query}"

            # 调用LLM进行意图识别和工具选择
            llm_response = await LLMService.get_response(full_prompt)

            # 检查LLM响应是否包含API错误
            if "API调用失败" in llm_response or "生成回答错误" in llm_response or "网络请求错误" in llm_response:
                # API调用失败，使用本地意图识别
                return await self._handle_api_failure(user_query, llm_response, mode)

            # 解析LLM响应
            decision = self._parse_llm_response(llm_response)

            if decision["action"] == "use_tool":
                # 执行工具调用
                return await self._execute_tool_call(decision, user_query)
            else:
                # 🔥 即使LLM返回direct_answer，也要检查是否应该查询数据库
                if any(keyword in query_lower for keyword in ["什么时候", "几点", "时间", "历史", "记录", "查询"]):
                    self.logger.info(f"🎯 LLM返回直接回答，但检测到查询意图，强制路由到数据库: {user_query}")
                    return await self._handle_api_failure(user_query, "LLM直接回答但强制路由数据库", mode)

                # 直接回答
                return {
                    "status": "success",
                    "answer": decision["answer"],
                    "method": "direct_answer",
                    "reasoning": decision.get("reasoning", "")
                }

        except Exception as e:
            self.logger.error(f"处理用户请求失败: {e}")
            return await self._handle_api_failure(user_query, str(e), mode)

    # ==================== 多智能体辅助方法 ====================

    async def _safe_agent_call(self, agent: BaseAgent, query: str, mode: str) -> Tuple[dict, float]:
        """安全的Agent调用，带异常处理和超时保护"""
        try:
            # 为每个Agent设置独立的超时，LLM Agent需要更多时间
            timeout = 20.0 if agent.name == "LLMAnalysis" else 10.0
            result = await asyncio.wait_for(
                agent.process(query, mode, {}),
                timeout=timeout  # LLM Agent 20秒，其他Agent 10秒超时
            )
            return result
        except asyncio.TimeoutError:
            self.logger.warning(f"Agent {agent.name} 处理超时")
            return None, 0.0
        except Exception as e:
            self.logger.warning(f"Agent {agent.name} 处理失败: {e}")
            return None, 0.0

    def _select_best_result(self, results: List[Tuple[dict, float]], query: str) -> dict:
        """选择置信度最高的结果，带智能筛选"""
        valid_results = []

        # 过滤有效结果
        for i, agent_result in enumerate(results):
            # 检查结果是否为None或异常
            if agent_result is None or isinstance(agent_result, Exception):
                agent_name = self._agents[i].name if i < len(self._agents) else "Unknown"
                self.logger.warning(f"⚠️ Agent {agent_name} 返回了无效结果: {agent_result}")
                continue

            try:
                result, confidence = agent_result
                if result is not None and confidence > 0:
                    agent_name = self._agents[i].name if i < len(self._agents) else "Unknown"
                    valid_results.append((result, confidence, agent_name))
                    self.logger.info(f"🎯 Agent {agent_name} 返回结果，置信度: {confidence}")
            except (TypeError, ValueError) as e:
                agent_name = self._agents[i].name if i < len(self._agents) else "Unknown"
                self.logger.error(f"❌ Agent {agent_name} 返回格式错误: {e}")

        if not valid_results:
            self.logger.warning("没有Agent返回有效结果")
            return None

        # 按置信度排序
        valid_results.sort(key=lambda x: x[1], reverse=True)

        # 选择最佳结果
        best_result, best_confidence, best_agent = valid_results[0]
        self.logger.info(f"✅ 选择Agent {best_agent} 的结果，置信度: {best_confidence}")

        # 在结果中添加多智能体元数据
        if isinstance(best_result, dict):
            best_result["multi_agent_info"] = {
                "selected_agent": best_agent,
                "confidence": best_confidence,
                "total_agents": len(self._agents),
                "valid_responses": len(valid_results)
            }

        return best_result

    def set_multi_agent_mode(self, enabled: bool):
        """动态开启/关闭多智能体模式"""
        self._multi_agent_enabled = enabled
        if enabled:
            self.logger.info("🚀 多智能体模式已启用")
        else:
            self.logger.info("🔄 多智能体模式已禁用，使用传统模式")

    def get_agent_status(self) -> Dict[str, Any]:
        """获取多智能体系统状态"""
        if self._agents is None:
            return {
                "multi_agent_enabled": self._multi_agent_enabled,
                "agents_initialized": False,
                "agent_count": 0
            }

        return {
            "multi_agent_enabled": self._multi_agent_enabled,
            "agents_initialized": True,
            "agent_count": len(self._agents),
            "agents": [agent.name for agent in self._agents]
        }

    # ==================== 原有方法保持不变 ====================

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

        # 优先检查Chrome网络监控相关命令
        network_keywords = ["网络请求", "监听", "API", "接口", "网络监控", "网络活动"]
        network_phrases = ["停止并获取", "获取捕获", "获取数据", "停止监控", "结束监控"]

        if (any(keyword in response_lower for keyword in network_keywords) or
            any(phrase in response_lower for phrase in network_phrases)):
            # 判断是开始还是停止
            stop_phrases = ["停止并获取", "获取捕获", "获取数据", "停止监控", "结束监控", "获取网络"]
            stop_keywords = ["停止", "结束", "获取", "数据", "结果"]
            is_stop_command = (any(phrase in response_lower for phrase in stop_phrases) or
                             any(stop_word in response_lower for stop_word in stop_keywords))

            if is_stop_command:
                function_name = "chrome_network_debugger_stop"
            else:
                function_name = "chrome_network_debugger_start"

            return {
                "action": "use_tool",
                "tool_name": "chrome",
                "function_name": function_name,
                "parameters": {},
                "reasoning": "回退解析识别为网络监控命令"
            }

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

    async def _handle_api_failure(self, user_query: str, error_message: str, mode: str = "rag") -> Dict[str, Any]:
        """处理API调用失败的情况，使用本地意图识别"""
        self.logger.info(f"🔄 LLM API不可用，启用本地智能回退处理: {error_message}, 模式: {mode}")

        # 使用本地关键词匹配进行简单的意图识别
        query_lower = user_query.lower()

        # 根据模式确定数据源优先级
        if mode == "activity":
            # 活动检索模式：优先处理桌面行为相关查询
            activity_keywords = [
                "访问", "浏览", "网站", "网页", "url", "链接", "页面", "应用", "软件",
                "程序", "窗口", "点击", "操作", "使用", "运行", "执行", "打开", "关闭", "视频", "看了", "观看"
            ]
            if any(keyword in query_lower for keyword in activity_keywords):
                # 这是桌面活动查询，直接返回提示用户使用活动检索服务
                return {
                    "status": "success",
                    "answer": "请稍候，正在查询您的桌面活动记录...",
                    "method": "activity_redirect",
                    "reasoning": f"检测到活动相关查询，模式：{mode}"
                }
        elif mode == "rag":
            # AI问答模式：优先处理视频监控相关查询
            video_activity_keywords = [
                "看手机", "玩手机", "手机", "睡觉", "休息", "睡眠", "喝水", "饮水",
                "吃东西", "吃饭", "用餐", "工作", "学习", "专注"
            ]
            if any(keyword in query_lower for keyword in video_activity_keywords):
                # 这是视频活动查询，提示查询视频监控记录
                return {
                    "status": "success",
                    "answer": "请稍候，正在查询您的视频监控活动记录...",
                    "method": "video_activity_redirect",
                    "reasoning": f"检测到视频活动相关查询，模式：{mode}"
                }

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

        # Chrome浏览器相关查询（优先级高于搜索）
        chrome_keywords = [
            # 浏览器管理
            "当前浏览器", "这个页面", "当前标签页", "打开标签页", "关闭标签页",
            "浏览器窗口", "标签页管理", "导航", "前进", "后退", "刷新", "截图",

            # 页面交互
            "点击", "点击按钮", "点击链接", "填写", "填写表单", "输入", "选择",
            "下拉选择", "键盘操作", "按键", "快捷键",

            # 内容获取
            "获取页面内容", "页面文本", "页面截图", "元素截图",
            "提取内容", "当前页面", "这个网站", "翻译网页", "总结网页",

            # 浏览器数据 - 增强的历史记录查询关键词
            "浏览历史", "搜索历史", "浏览记录", "访问记录", "历史记录",
            "书签", "添加书签", "删除书签", "收藏",

            # 时间相关的浏览历史查询
            "分析浏览记录", "分析我的浏览", "我的浏览", "我浏览了", "都浏览了",
            "访问了哪些", "浏览了哪些", "去了哪些", "看了哪些",
            "近一个月", "最近访问", "最近浏览", "这个月", "一个月", "这段时间",
            "昨天", "前天", "上周", "最近几天", "今天", "今天浏览",
            "昨天浏览", "昨天访问", "昨天看了", "昨天去了",
            "这周", "上个月", "最近一周", "最近的", "最近看的",
            "我都去了", "我都看了", "我都访问了", "都访问了哪些",
            "网页浏览", "网站访问", "浏览了什么", "访问了什么",

            # 网络监控
            "网络请求", "监听请求", "网络监控", "HTTP请求", "网络数据", "监听网络",
            "API接口", "响应体", "捕获网络", "抓取接口", "监控网络", "网络活动",
            "停止网络", "结束网络", "获取网络", "网络监控数据", "捕获的网络",
            "停止监控", "结束监控", "获取数据", "停止监听", "结束监听",
            "监控并获取", "监听并获取", "停止并获取", "网络监控结果",

            # 高级功能
            "注入脚本", "JavaScript", "控制台", "调试", "搜索标签页内容",

            # 直接操作指令
            "在当前", "直接", "立即", "马上", "现在就", "帮我",

            # 具体网站操作
            "huggingface", "github", "百度", "谷歌", "微博", "知乎",
            "小红书", "shadcn", "打开网站", "访问网站"
        ]

        if any(keyword in query_lower for keyword in chrome_keywords):
            try:
                chrome_tool = self.tool_registry.get_tool("chrome")
                if chrome_tool:
                    navigation_result = False  # 初始化导航结果标志

                    # 检查是否是分析网站API的综合请求
                    api_analysis_keywords = ["搜索接口", "API接口", "响应体", "接口结构"]
                    website_names = ["小红书", "知乎", "微博", "百度", "github"]

                    if (any(api_kw in query_lower for api_kw in api_analysis_keywords) and
                        any(site in query_lower for site in website_names)):
                        # 这是一个完整的API分析请求，需要自动化流程
                        return await self._handle_comprehensive_api_analysis(user_query, chrome_tool)

                    # Chrome工具的基本功能调用
                    if any(word in query_lower for word in ["截图", "截取"]):
                        # 检查是否需要先导航到特定网站
                        navigation_result = await self._handle_navigation_before_action(query_lower, chrome_tool)
                        if navigation_result:
                            # 导航成功，然后截图
                            result = await chrome_tool.execute_function("chrome_screenshot", {
                                "fullPage": True,
                                "storeBase64": True
                            })
                        else:
                            # 直接截图当前页面
                            result = await chrome_tool.execute_function("chrome_screenshot", {"storeBase64": True})
                    elif any(word in query_lower for word in ["标签页", "窗口"]):
                        result = await chrome_tool.execute_function("get_windows_and_tabs", {})
                    elif any(word in query_lower for word in [
                        "浏览记录", "浏览历史", "访问记录", "历史记录", "分析浏览记录",
                        "我浏览了", "都浏览了", "访问了哪些", "浏览了哪些", "去了哪些", "看了哪些",
                        "昨天浏览", "昨天访问", "昨天看了", "昨天去了", "最近浏览", "最近访问",
                        "一个月", "这个月", "近一个月", "这段时间", "我都去了", "我都看了",
                        "我都访问了", "都访问了哪些", "网页浏览", "网站访问"
                    ]):
                        # 增强的浏览历史查询，支持时间范围参数
                        max_results = 100

                        # 根据查询内容调整结果数量
                        if any(time_word in query_lower for time_word in ["一个月", "这个月", "近一个月", "这段时间"]):
                            max_results = 500  # 一个月的记录可能较多
                        elif any(time_word in query_lower for time_word in ["昨天", "前天", "今天"]):
                            max_results = 50   # 单天的记录相对较少

                        result = await chrome_tool.execute_function("chrome_history", {"maxResults": max_results})
                    elif (any(keyword in query_lower for keyword in ["网络请求", "监听", "API", "接口", "网络监控", "网络活动"]) or
                          any(phrase in query_lower for phrase in ["停止并获取", "获取捕获", "获取数据", "停止监控", "结束监控"])):
                        # 增强版网络监控处理
                        stop_keywords = ["停止", "结束", "获取", "数据", "结果"]
                        # 检查是否是停止相关的命令
                        stop_phrases = ["停止并获取", "获取捕获", "获取数据", "停止监控", "结束监控", "获取网络"]
                        is_stop_command = (any(phrase in query_lower for phrase in stop_phrases) or
                                         any(stop_word in query_lower for stop_word in stop_keywords))

                        if is_stop_command:
                            # 停止监控并获取数据
                            result = await chrome_tool.execute_function("chrome_network_debugger_stop", {})
                        else:
                            # 开始监控
                            result = await chrome_tool.execute_function("chrome_network_debugger_start", {})
                    elif any(word in query_lower for word in ["页面内容", "提取内容"]):
                        result = await chrome_tool.execute_function("chrome_get_web_content", {"textContent": True})
                    else:
                        # 默认获取页面信息
                        result = await chrome_tool.execute_function("get_windows_and_tabs", {})

                    if result.get("status") == "success":
                        # 构建更友好的回答
                        if any(word in query_lower for word in ["截图", "截取"]):
                            if navigation_result:
                                answer = f"已导航到指定网站并成功截图！截图操作完成。"
                                self.logger.info("✅ 本地Chrome工具成功完成：导航+截图")
                            else:
                                answer = f"当前页面截图完成！"
                                self.logger.info("✅ 本地Chrome工具成功完成：页面截图")
                        elif (any(keyword in query_lower for keyword in ["网络请求", "监听", "API", "接口", "网络监控", "网络活动"]) or
                              any(phrase in query_lower for phrase in ["停止并获取", "获取捕获", "获取数据", "停止监控", "结束监控"])):
                            # 检查是否是停止相关的命令
                            stop_phrases = ["停止并获取", "获取捕获", "获取数据", "停止监控", "结束监控", "获取网络"]
                            stop_keywords = ["停止", "结束", "获取", "数据", "结果"]
                            is_stop_command = (any(phrase in query_lower for phrase in stop_phrases) or
                                             any(stop_word in query_lower for stop_word in stop_keywords))

                            if is_stop_command:
                                # 格式化网络数据分析
                                answer = self._format_network_data(result, user_query)
                            else:
                                answer = f"网络监控已开始，请在浏览器中进行操作，然后说'停止网络监控并获取数据'来查看结果"
                        else:
                            answer = f"Chrome操作完成：{result.get('data', result)}"

                        return {
                            "status": "success",
                            "answer": answer,
                            "method": "local_tool_call",
                            "reasoning": "API不可用，使用本地Chrome工具"
                        }
            except Exception as e:
                self.logger.error(f"本地Chrome工具调用失败: {e}")

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
                "Chrome浏览器控制工具": "chrome",
                "Chrome工具": "chrome",
                "浏览器控制工具": "chrome",
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

            # 特殊处理Chrome截图：检查是否需要先导航
            if tool_name == "chrome" and function_name == "chrome_screenshot":
                chrome_tool = self.tool_registry.get_tool("chrome")
                if chrome_tool:
                    navigation_result = await self._handle_navigation_before_action(original_query.lower(), chrome_tool)
                    if navigation_result:
                        self.logger.info("已导航到目标网站，准备截图")

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

    async def _handle_navigation_before_action(self, query_lower: str, chrome_tool) -> bool:
        """检查查询中是否包含网站名称或URL，如有则先导航到该网站。
        返回是否已执行导航（True/False）。"""
        try:
            # 网站名称到URL的映射
            website_mapping = {
                # 常用网站
                "百度": "https://www.baidu.com",
                "谷歌": "https://www.google.com",
                "github": "https://github.com",
                "huggingface": "https://huggingface.co",
                "抖音": "https://www.douyin.com",
                "微博": "https://weibo.com",
                "知乎": "https://www.zhihu.com",
                "小红书": "https://www.xiaohongshu.com",
                "bilibili": "https://www.bilibili.com",
                "b站": "https://www.bilibili.com",
                "淘宝": "https://www.taobao.com",
                "京东": "https://www.jd.com",
                "豆瓣": "https://www.douban.com",
                "csdn": "https://www.csdn.net",
                "stackoverflow": "https://stackoverflow.com",
                "youtube": "https://www.youtube.com",
                "twitter": "https://twitter.com",
                "facebook": "https://www.facebook.com",
                "linkedin": "https://www.linkedin.com",
                "reddit": "https://www.reddit.com",
                "wikipedia": "https://www.wikipedia.org",
                "维基百科": "https://zh.wikipedia.org",
                "openai": "https://openai.com",
                "claude": "https://claude.ai",
                "chatgpt": "https://chat.openai.com",
                "notion": "https://www.notion.so",
                "figma": "https://www.figma.com",
                "canva": "https://www.canva.com",
            }

            # 如果包含常见网站名称，先导航
            for site_name, url in website_mapping.items():
                if site_name in query_lower:
                    await chrome_tool.execute_function("chrome_navigate", {"url": url})
                    return True

            # 检查是否有直接URL或域名
            import re
            url_patterns = [
                r"https?://[a-zA-Z0-9\-\./_~:?#[\]@!$&'()*+,;=%]+",
                r"https?://[^\s\u4e00-\u9fff，。！？、]+",
            ]
            urls_found = []
            for pattern in url_patterns:
                urls_found.extend(re.findall(pattern, query_lower))
            if urls_found:
                target_url = max(set(urls_found), key=len)
                await chrome_tool.execute_function("chrome_navigate", {"url": target_url})
                return True

            # 如果没有http/https但像域名，也尝试拼接https导航
            domain_pattern = r"(?:www\.)?[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:/[a-zA-Z0-9\-\./_~:?#[\]@!$&'()*+,;=%]*)?"
            domains = re.findall(domain_pattern, query_lower)
            if domains:
                # 选择最长的作为最可能的目标
                domain = max(set(domains), key=len)
                if not domain.startswith("http"):
                    domain = f"https://{domain}"
                await chrome_tool.execute_function("chrome_navigate", {"url": domain})
                return True

            return False
        except Exception as e:
            self.logger.error(f"导航前处理失败: {e}")
            return False

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

    async def _handle_comprehensive_api_analysis(self, user_query: str, chrome_tool) -> Dict[str, Any]:
        """处理综合API分析请求，包括导航、监控、操作和分析"""
        try:
            query_lower = user_query.lower()

            # 确定目标网站
            website_mapping = {
                "小红书": "https://www.xiaohongshu.com",
                "知乎": "https://www.zhihu.com",
                "微博": "https://weibo.com",
                "百度": "https://www.baidu.com",
                "github": "https://github.com"
            }

            target_site = None
            target_url = None
            for site_name, url in website_mapping.items():
                if site_name in query_lower:
                    target_site = site_name
                    target_url = url
                    break

            if not target_site:
                return {
                    "status": "error",
                    "answer": "未能识别目标网站，请明确指定要分析的网站（如小红书、知乎等）。",
                    "method": "comprehensive_analysis_error"
                }

            # 开始综合分析流程
            analysis_steps = []

            # 第一步：导航到目标网站
            self.logger.info(f"开始综合API分析：导航到{target_site}")
            analysis_steps.append(f"🌐 正在导航到{target_site}...")

            nav_result = await chrome_tool.execute_function("chrome_navigate", {
                "url": target_url,
                "timeout": 10000
            })

            if nav_result.get("status") != "success":
                return {
                    "status": "error",
                    "answer": f"无法导航到{target_site}，请检查网络连接或网站是否可访问。错误：{nav_result.get('message', '未知错误')}",
                    "method": "comprehensive_analysis_nav_error"
                }

            analysis_steps.append(f"✅ 成功导航到{target_site}")

            # 等待页面加载
            import asyncio
            await asyncio.sleep(3)

            # 第二步：开始网络监控
            analysis_steps.append("🔍 开始网络请求监控...")
            monitor_result = await chrome_tool.execute_function("chrome_network_debugger_start", {})

            if monitor_result.get("status") != "success":
                return {
                    "status": "error",
                    "answer": f"无法启动网络监控。错误：{monitor_result.get('message', '未知错误')}",
                    "method": "comprehensive_analysis_monitor_error"
                }

            analysis_steps.append("✅ 网络监控已启动")

            # 第三步：提示用户进行操作
            instructions = f"""
🎯 **{target_site}接口分析已准备就绪**

📋 **已完成的步骤**:
{chr(10).join(f"   {step}" for step in analysis_steps)}

🔧 **接下来请您**:
1. 在{target_site}网站上进行搜索操作
2. 点击搜索按钮或相关功能
3. 等待页面加载完成
4. 然后对我说："停止监控并分析{target_site}的搜索接口"

💡 **说明**:
- 网络监控正在后台运行，会捕获所有网络请求
- 建议进行多种操作（搜索、点击、滚动等）以获取更全面的接口信息
- 操作完成后，我会为您分析捕获的API接口结构和响应体格式

⏱️ **监控状态**: 🟢 正在运行中...
"""

            return {
                "status": "success",
                "answer": instructions,
                "method": "comprehensive_analysis_ready",
                "reasoning": f"已为{target_site}准备好API分析环境，等待用户操作"
            }

        except Exception as e:
            self.logger.error(f"综合API分析失败: {e}")
            return {
                "status": "error",
                "answer": f"综合API分析过程中出错：{str(e)}",
                "method": "comprehensive_analysis_exception"
            }

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

    def _format_network_data(self, result: Dict[str, Any], query: str = "") -> str:
        """格式化网络请求数据，特别针对API分析"""
        try:
            if result.get("status") != "success":
                return f"网络监控出错：{result.get('message', '未知错误')}"

            # 处理不同格式的result数据
            network_data = result.get("result", {})

            # 如果result是字符串，尝试解析
            if isinstance(network_data, str):
                try:
                    import json
                    network_data = json.loads(network_data)
                except:
                    return f"网络数据格式异常：无法解析字符串数据"

            # 如果result包含content字段，尝试提取
            if isinstance(network_data, dict) and "content" in network_data:
                content = network_data["content"]
                if isinstance(content, list) and len(content) > 0:
                    # 尝试从content中提取text数据
                    text_content = content[0].get("text", "")
                    if text_content:
                        try:
                            import json
                            network_data = json.loads(text_content)
                        except:
                            return f"网络数据格式异常：无法解析content中的text数据"

            # 检查是否包含requests字段
            if not isinstance(network_data, dict):
                return f"网络数据格式异常：数据不是字典格式 - {type(network_data)}"

            if "requests" not in network_data:
                # 如果没有requests字段，可能是刚开始监控的响应
                if "message" in network_data:
                    return f"📊 {network_data['message']}"
                else:
                    return f"网络数据格式异常：缺少requests字段 - {list(network_data.keys())}"

            requests = network_data["requests"]
            if not requests:
                return "📊 网络监控完成，但没有捕获到任何网络请求。\n💡 请确保在监控期间有进行页面操作（如搜索、点击等）。"

            # 分析请求
            api_requests = []
            static_requests = []
            error_requests = []

            for req in requests:
                url = req.get("url", "")
                method = req.get("method", "GET")
                status = req.get("statusCode", 0)

                # 分类请求
                if status >= 400:
                    error_requests.append(req)
                elif any(keyword in url.lower() for keyword in ["api", "search", "query", "login", "user", "fe_api"]):
                    api_requests.append(req)
                else:
                    static_requests.append(req)

            # 格式化输出
            formatted_text = f"🌐 **网络请求分析报告** (共捕获 {len(requests)} 个请求)\n\n"

            # API请求分析
            if api_requests:
                formatted_text += f"🎯 **API接口请求** ({len(api_requests)} 个):\n"
                for i, req in enumerate(api_requests[:10], 1):  # 只显示前10个
                    url = req.get("url", "")
                    method = req.get("method", "GET")
                    status = req.get("statusCode", 0)

                    formatted_text += f"   {i}. **{method}** {url}\n"
                    formatted_text += f"      📊 状态: {status}\n"

                    # 显示响应体（如果有且是API）
                    if "responseBody" in req and req["responseBody"]:
                        response_body = req["responseBody"]
                        if isinstance(response_body, str):
                            try:
                                import json
                                response_json = json.loads(response_body)
                                # 只显示关键字段
                                if isinstance(response_json, dict):
                                    if "data" in response_json:
                                        formatted_text += f"      📄 响应数据: 包含data字段\n"
                                    if "code" in response_json:
                                        formatted_text += f"      🔢 响应码: {response_json['code']}\n"
                                    if "msg" in response_json or "message" in response_json:
                                        msg = response_json.get("msg") or response_json.get("message")
                                        formatted_text += f"      💬 消息: {msg}\n"
                            except:
                                formatted_text += f"      📄 响应: {response_body[:100]}...\n"

                    formatted_text += "\n"

                if len(api_requests) > 10:
                    formatted_text += f"   ... 还有 {len(api_requests) - 10} 个API请求\n\n"

            # 错误请求
            if error_requests:
                formatted_text += f"❌ **失败请求** ({len(error_requests)} 个):\n"
                for req in error_requests[:5]:
                    url = req.get("url", "")
                    status = req.get("statusCode", 0)
                    formatted_text += f"   • {status} - {url}\n"
                formatted_text += "\n"

            # 统计信息
            formatted_text += f"📈 **请求统计**:\n"
            formatted_text += f"   • API接口: {len(api_requests)} 个\n"
            formatted_text += f"   • 静态资源: {len(static_requests)} 个\n"
            formatted_text += f"   • 失败请求: {len(error_requests)} 个\n"
            formatted_text += f"   • 总计: {len(requests)} 个\n\n"

            # 针对小红书的特殊分析
            if "xiaohongshu" in str(requests) or "小红书" in query:
                xhs_apis = [req for req in api_requests if "xiaohongshu" in req.get("url", "")]
                if xhs_apis:
                    formatted_text += f"🔍 **小红书API分析**:\n"
                    for req in xhs_apis:
                        url = req.get("url", "")
                        if "search" in url:
                            formatted_text += f"   🔎 搜索接口: {url}\n"
                        elif "login" in url:
                            formatted_text += f"   🔐 登录接口: {url}\n"
                        elif "user" in url:
                            formatted_text += f"   👤 用户接口: {url}\n"
                        else:
                            formatted_text += f"   📡 其他接口: {url}\n"
                    formatted_text += "\n"

            formatted_text += "💡 **提示**: 如需查看具体接口的响应内容，请告诉我您感兴趣的API URL。"

            return formatted_text

        except Exception as e:
            self.logger.error(f"格式化网络数据失败: {e}")
            return f"网络监控完成，但格式化数据时出错：{str(e)}\n原始数据：{result}"

    async def get_available_capabilities(self) -> Dict[str, Any]:
        """获取当前可用的能力描述"""
        return {
            "total_tools": len(self.tool_registry.tools),
            "available_tools": list(self.tool_registry.tools.keys()),
            "tool_schemas": self.tool_registry.get_tools_schema(),
            "usage_examples": self.tool_registry.get_tool_usage_examples()
        }