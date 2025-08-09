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
你是一个专业的逻辑推理专家，需要对以下复杂问题进行结构化分析。请设计{max_steps}个逐步推理的步骤，体现严密的逻辑思维：

完整问题：{original_question}

请按照以下原则设计推理步骤：
1. **假设分析法**：对每个可能性进行系统性假设和验证
2. **矛盾排除法**：寻找逻辑矛盾，排除不可能的选项
3. **条件梳理**：明确所有约束条件和已知信息
4. **逐步推进**：每个步骤都基于前一步的结论
5. **反证验证**：用反证法验证最终结论

格式要求：
步骤1：[明确信息梳理] - [列出所有已知条件、约束和陈述，建立逻辑框架] - [完整的条件清单和逻辑关系图]
步骤2：[假设A的情况] - [假设某个关键条件为真，推导所有后果] - [该假设下的完整推理链和结论]
步骤3：[假设B的情况] - [假设另一个关键条件为真，推导所有后果] - [该假设下的完整推理链和结论]
步骤4：[矛盾检验与排除] - [检查各假设是否产生逻辑矛盾，排除不可能情况] - [有效假设列表和排除理由]
步骤5：[最终推论与验证] - [基于排除法确定唯一解，并进行反证验证] - [最终答案和完整证明过程]
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
🧠 **逻辑推理专家模式** - 第{step_num}步推理

【原始问题】
{original_question}

【当前任务】
步骤{step_num}：{step_info.get('title', f'第{step_num}步')}
推理要求：{step_info.get('content', '继续分析问题')}
预期成果：{step_info.get('expected', '分析结果')}

【前置推理链】
{self._format_complete_previous_results(thinking_results) if thinking_results else ''}

【推理指导原则】
1. **严格逻辑**：每个推论都要有明确的逻辑依据
2. **假设验证**：明确区分假设和已知事实
3. **矛盾检测**：主动寻找和识别逻辑矛盾
4. **完整性检查**：确保考虑所有可能的情况
5. **推理可视化**：用符号化表示复杂的逻辑关系

请以专业逻辑推理专家的身份，进行严密的分析。

**重要要求：本步骤需要有清晰的推理过程，但保持简洁（100-150字）**

在推理过程中：
- 明确标出【假设】、【已知】、【推论】、【矛盾】
- 使用逻辑符号（→, ∧, ∨, ¬）表示关键关系
- 提供核心推理依据，不跳过关键步骤
- 简明扼要地说明推理逻辑
- 识别矛盾和关键转折点

请确保这一步有清晰的推理链条，但避免冗长描述。
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
🎯 **逻辑推理总结与验证**

【原始问题】
{original_question}

【完整推理过程】
{self._format_complete_thinking_results(thinking_results)}

作为逻辑推理专家，请提供专业的总结报告：

## 📋 推理过程回顾
- 总结每个推理步骤的核心逻辑
- 展示假设→推论→验证的完整链条
- 突出关键的矛盾排除过程

## 🔍 逻辑验证检查
- 验证推理链的完整性和严密性
- 检查是否存在逻辑漏洞或遗漏
- 确认排除法的彻底性

## 💡 最终结论
- 明确的答案和推理依据
- 为什么这是唯一正确的解
- 反证：为什么其他可能性被排除

## 🎓 推理方法总结
- 使用了哪些逻辑推理技巧
- 体现了Sequential Thinking的哪些优势
- 这种方法相比直觉判断的优势

请确保总结体现出专业逻辑推理工具的价值和严谨性。
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
        
        formatted_response = "# 🧠 Sequential Thinking 专业逻辑推理分析\n\n"
        
        # 显示规划
        if "planning" in result:
            formatted_response += "### 📋 思考规划\n"
            formatted_response += f"{result['planning']}\n\n"
        
        # 显示步骤
        if "steps" in result and len(result["steps"]) > 0:
            formatted_response += "## 🔬 严密逻辑推理过程\n\n"
            formatted_response += "以下是完整的5步推理分析，每步简洁但清晰地展现推理逻辑：\n\n"
            
            for step in result["steps"]:
                step_content = step.get('content', '').strip()
                if step_content:  # 只显示有内容的步骤
                    formatted_response += f"### 步骤 {step['step_number']}: {step['title']}\n\n"
                    formatted_response += f"{step_content}\n\n"
                    
                    # 显示ST状态
                    if step.get('st_state'):
                        st_state = step['st_state']
                        formatted_response += f"---\n*🔗 推理状态：第{st_state.get('thoughtNumber')}/{st_state.get('totalThoughts')}步 | 推理历史长度：{st_state.get('thoughtHistoryLength')}*\n\n"
                else:
                    # 如果步骤内容为空，显示警告
                    formatted_response += f"### 步骤 {step['step_number']}: {step['title']}\n\n"
                    formatted_response += f"⚠️ 此步骤内容生成异常，请重新尝试推理。\n\n"
        else:
            # 如果没有步骤，显示错误信息
            formatted_response += "⚠️ **推理步骤生成失败**\n\n"
            formatted_response += "Sequential Thinking工具未能生成详细的推理步骤。这可能是由于：\n"
            formatted_response += "1. LLM服务异常\n2. 网络连接问题\n3. 推理复杂度过高\n\n"
        
        # 显示总结
        if "summary" in result:
            formatted_response += "## 💡 综合总结\n\n"
            formatted_response += f"{result['summary']}\n\n"
        
        # 显示元信息
        formatted_response += "---\n"
        formatted_response += f"**🎯 推理技术说明**\n"
        formatted_response += f"- **方法**：Sequential Thinking 结构化推理框架\n"
        formatted_response += f"- **特点**：状态管理 + 逻辑验证 + 假设排除\n"
        formatted_response += f"- **步数**：完成 {result.get('total_steps', 0)} 步严密推理\n"
        formatted_response += f"- **优势**：相比直觉判断，提供可验证的推理链条\n"
        
        return formatted_response 