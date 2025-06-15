from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging

class BaseMCPTool(ABC):
    """MCP工具基础抽象类"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def tool_name(self) -> str:
        """工具名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @abstractmethod
    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        """
        获取可用函数列表及其描述
        返回格式: {
            "function_name": {
                "description": "函数描述",
                "parameters": {
                    "param1": {"type": "string", "description": "参数描述", "required": True},
                    ...
                },
                "examples": ["使用示例1", "使用示例2"]
            }
        }
        """
        pass
    
    @abstractmethod
    async def execute_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行指定函数
        Args:
            function_name: 函数名
            parameters: 参数字典
        Returns:
            执行结果
        """
        pass
    
    def get_tool_schema(self) -> Dict[str, Any]:
        """获取工具的完整schema信息"""
        functions = self.get_available_functions()
        return {
            "tool_name": self.tool_name,
            "description": self.description,
            "functions": functions,
            "base_url": self.base_url
        }
    
    def format_for_llm(self) -> str:
        """格式化工具信息供LLM理解"""
        schema = self.get_tool_schema()
        
        formatted = f"""
## {schema['tool_name']}
**描述**: {schema['description']}

**可用函数**:
"""
        
        for func_name, func_info in schema['functions'].items():
            formatted += f"\n### {func_name}\n"
            formatted += f"- **描述**: {func_info['description']}\n"
            
            if 'parameters' in func_info:
                formatted += "- **参数**:\n"
                for param_name, param_info in func_info['parameters'].items():
                    required = " (必需)" if param_info.get('required', False) else " (可选)"
                    formatted += f"  - `{param_name}` ({param_info['type']}){required}: {param_info['description']}\n"
            
            if 'examples' in func_info and func_info['examples']:
                formatted += "- **使用示例**:\n"
                for example in func_info['examples']:
                    formatted += f"  - {example}\n"
        
        return formatted 