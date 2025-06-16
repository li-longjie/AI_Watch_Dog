import httpx
import requests
from typing import Dict, Any
from datetime import datetime
import traceback
from .base_tool import BaseMCPTool

class SequentialThinkingTool(BaseMCPTool):
    """Sequential Thinking推理工具"""
    
    @property
    def tool_name(self) -> str:
        return "Sequential Thinking推理工具"
    
    @property
    def description(self) -> str:
        return "用于复杂问题的逐步思考和推理，帮助大模型进行结构化分析"
    
    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "sequential_thinking": {
                "description": "对复杂问题进行逐步思考和推理",
                "parameters": {
                    "prompt": {
                        "type": "string", 
                        "description": "需要分析的问题或任务",
                        "required": True
                    },
                    "max_steps": {
                        "type": "integer",
                        "description": "最大思考步骤数，默认5步",
                        "required": False
                    }
                },
                "examples": [
                    "帮我分析这个复杂的数学问题",
                    "逐步思考这个商业决策",
                    "分析这个编程问题的解决方案",
                    "逐步推理这个逻辑问题"
                ]
            }
        }
    
    async def execute_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行Sequential Thinking功能"""
        if function_name == "sequential_thinking":
            return await self._sequential_thinking(parameters)
        else:
            return {
                "status": "error",
                "message": f"未知函数: {function_name}"
            }
    
    async def _sequential_thinking(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行Sequential Thinking推理"""
        try:
            prompt = parameters.get("prompt")
            max_steps = parameters.get("max_steps", 5)
            
            if not prompt:
                return {
                    "status": "error",
                    "message": "缺少必需参数: prompt"
                }
            
            # 调用Sequential Thinking中间件
            result = await self._call_sequential_thinking_with_llm(prompt, max_steps)
            
            if "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }
            
            return {
                "status": "success",
                "thinking_result": result,
                "formatted_response": self._format_middleware_result(result)
            }
            
        except Exception as e:
            self.logger.error(f"Sequential Thinking执行错误: {e}")
            return {
                "status": "error",
                "message": f"Sequential Thinking执行失败: {str(e)}"
            }
    
    async def _call_sequential_thinking_with_llm(self, prompt: str, max_steps: int = 5) -> Dict[str, Any]:
        """使用Sequential Thinking作为中间件协助大模型推理"""
        try:
            self.logger.info(f"启动Sequential Thinking辅助推理: {prompt[:100]}...")
            
            st_endpoint = f"{self.base_url}/sequential-thinking/sequentialthinking"
            thinking_results = []
            
            # 保存完整的原始问题
            original_question = prompt
            
            # 第一阶段：使用Sequential Thinking规划思考步骤
            self.logger.info("=== 阶段1：Sequential Thinking规划思考流程 ===")
            
            planning_prompt = f"""
基于以下完整问题，请规划{max_steps}个逐步思考的步骤：

完整问题：{original_question}

请为每个步骤提供：
1. 步骤标题
2. 该步骤需要思考的具体内容
3. 该步骤的预期输出

格式：
步骤1：[标题] - [思考内容] - [预期输出]
步骤2：[标题] - [思考内容] - [预期输出]
...
"""
            
            # 获取思考规划 (这里需要调用LLM服务)
            planning_result = await self._query_llm_model(planning_prompt)
            self.logger.info(f"思考规划完成: {planning_result[:200]}...")
            
            # 解析规划结果
            steps_plan = self._parse_thinking_plan(planning_result, max_steps)
            
            # 第二阶段：Sequential Thinking状态管理 + 大模型执行
            self.logger.info("=== 阶段2：执行结构化思考 ===")
            
            for step_num in range(1, max_steps + 1):
                # 2.1 向Sequential Thinking注册当前步骤
                st_request = {
                    "thought": f"执行步骤{step_num}：{steps_plan.get(step_num, {}).get('title', f'第{step_num}步思考')}",
                    "nextThoughtNeeded": step_num < max_steps,
                    "thoughtNumber": step_num,
                    "totalThoughts": max_steps,
                    "needsMoreThoughts": step_num < max_steps
                }
                
                try:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        st_response = await client.post(st_endpoint, json=st_request)
                        
                        if st_response.status_code == 200:
                            st_result = st_response.json()
                            self.logger.info(f"Sequential Thinking步骤{step_num}注册成功，历史长度: {st_result.get('thoughtHistoryLength')}")
                            
                            # 2.2 使用大模型执行具体思考
                            step_info = steps_plan.get(step_num, {})
                            
                            # 构建完整的上下文
                            context = f"""
完整原始问题：{original_question}

你正在进行第{step_num}步思考（共{max_steps}步）。

当前步骤：{step_info.get('title', f'第{step_num}步')}
思考重点：{step_info.get('content', '继续分析问题')}
预期输出：{step_info.get('expected', '分析结果')}

{self._format_complete_previous_results(thinking_results) if thinking_results else ''}

请基于完整的原始问题和前面步骤的结果，专注于当前步骤，提供详细的分析和具体的计算：
"""
                            
                            step_result = await self._query_llm_model(context)
                            
                            # 保存步骤结果
                            thinking_results.append({
                                "step_number": step_num,
                                "title": step_info.get('title', f'第{step_num}步'),
                                "content": step_result,
                                "st_state": st_result,
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            self.logger.info(f"步骤{step_num}执行完成")
                            
                        else:
                            self.logger.warning(f"Sequential Thinking步骤{step_num}注册失败: {st_response.text}")
                            # 即使ST失败，也继续用大模型执行
                            step_info = steps_plan.get(step_num, {})
                            context = f"完整问题：{original_question}\n第{step_num}步：{step_info.get('content', '继续分析')}"
                            step_result = await self._query_llm_model(context)
                            
                            thinking_results.append({
                                "step_number": step_num,
                                "title": step_info.get('title', f'第{step_num}步'),
                                "content": step_result,
                                "st_state": None,
                                "timestamp": datetime.now().isoformat()
                            })
                            
                except Exception as e:
                    self.logger.error(f"步骤{step_num}执行异常: {e}")
                    # 失败时也要继续
                    continue
            
            # 第三阶段：综合总结
            self.logger.info("=== 阶段3：综合总结 ===")
            
            summary_prompt = f"""
基于以下逐步思考的结果，请提供一个完整的总结：

原始问题：{original_question}

思考过程：
{self._format_complete_thinking_results(thinking_results)}

请提供：
1. 完整的解答（包含具体数值计算）
2. 关键的推理步骤
3. 最终结论
"""
            
            final_summary = await self._query_llm_model(summary_prompt)
            
            return {
                "original_prompt": original_question,
                "planning": planning_result,
                "steps": thinking_results,
                "summary": final_summary,
                "total_steps": len(thinking_results),
                "method": "sequential_thinking_middleware",
                "completed": True
            }
            
        except Exception as e:
            self.logger.error(f"Sequential Thinking中间件异常: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {"error": f"Sequential Thinking中间件执行异常: {str(e)}"}
    
    async def _query_llm_model(self, prompt: str) -> str:
        """调用LLM模型（这里需要集成到现有的LLM服务）"""
        try:
            # 这里需要调用现有的LLM服务
            # 暂时返回简化响应，稍后会集成到主系统
            from llm_service import chat_completion
            return await chat_completion(prompt)
        except Exception as e:
            self.logger.error(f"LLM调用失败: {e}")
            return f"LLM调用失败: {str(e)}"
    
    def _parse_thinking_plan(self, planning_text: str, max_steps: int) -> Dict[int, Dict[str, str]]:
        """解析思考规划"""
        steps = {}
        lines = planning_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('步骤') and '：' in line:
                try:
                    # 解析：步骤1：[标题] - [内容] - [预期]
                    parts = line.split('：', 1)[1].split(' - ')
                    step_num = int(line.split('：')[0].replace('步骤', ''))
                    
                    if step_num <= max_steps:
                        steps[step_num] = {
                            'title': parts[0].strip() if len(parts) > 0 else f'第{step_num}步',
                            'content': parts[1].strip() if len(parts) > 1 else '继续分析',
                            'expected': parts[2].strip() if len(parts) > 2 else '分析结果'
                        }
                except:
                    continue
        
        # 确保所有步骤都有默认值
        for i in range(1, max_steps + 1):
            if i not in steps:
                steps[i] = {
                    'title': f'第{i}步思考',
                    'content': '继续分析问题',
                    'expected': '分析结果'
                }
        
        return steps
    
    def _format_complete_previous_results(self, results: list) -> str:
        """格式化前面步骤的完整结果"""
        if not results:
            return ""
        
        formatted = "前面步骤的详细结果：\n"
        for result in results:
            formatted += f"\n步骤{result['step_number']}（{result['title']}）：\n{result['content']}\n"
        
        return formatted
    
    def _format_complete_thinking_results(self, results: list) -> str:
        """格式化所有思考结果（完整版）"""
        formatted = ""
        for result in results:
            formatted += f"\n步骤{result['step_number']}：{result['title']}\n{result['content']}\n"
        
        return formatted
    
    def _format_middleware_result(self, result: Dict[str, Any]) -> str:
        """格式化中间件结果"""
        if not isinstance(result, dict):
            return str(result)
        
        formatted_response = "## 🧠 Sequential Thinking 辅助推理\n\n"
        
        # 显示规划
        if "planning" in result:
            formatted_response += "### 📋 思考规划\n"
            formatted_response += f"{result['planning']}\n\n"
        
        # 显示步骤
        if "steps" in result:
            formatted_response += "### 🔄 逐步执行\n\n"
            for step in result["steps"]:
                formatted_response += f"**步骤{step['step_number']}：{step['title']}**\n\n"
                formatted_response += f"{step['content']}\n\n"
                
                # 显示ST状态（可选）
                if step.get('st_state'):
                    st_state = step['st_state']
                    formatted_response += f"*状态：步骤{st_state.get('thoughtNumber')}/{st_state.get('totalThoughts')}，历史长度{st_state.get('thoughtHistoryLength')}*\n\n"
        
        # 显示总结
        if "summary" in result:
            formatted_response += "## 💡 综合总结\n\n"
            formatted_response += f"{result['summary']}\n\n"
        
        # 显示元信息
        formatted_response += "---\n"
        formatted_response += f"*推理方式：Sequential Thinking 中间件 + 大模型API*\n"
        formatted_response += f"*完成步数：{result.get('total_steps', 0)}*\n"
        
        return formatted_response 