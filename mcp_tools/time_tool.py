import httpx
from typing import Dict, Any
from .base_tool import BaseMCPTool

class TimeTool(BaseMCPTool):
    """时间获取工具"""
    
    @property
    def tool_name(self) -> str:
        return "时间工具"
    
    @property
    def description(self) -> str:
        return "用于获取当前时间、日期等时间相关信息"
    
    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "get_current_time": {
                "description": "获取当前的日期和时间信息",
                "parameters": {
                    "timezone": {
                        "type": "string",
                        "description": "时区设置，默认为Asia/Shanghai",
                        "required": False
                    }
                },
                "examples": [
                    "现在几点了？",
                    "今天是几号？",
                    "获取当前时间",
                    "查看日期和时间"
                ]
            }
        }
    
    async def execute_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行时间相关功能"""
        if function_name == "get_current_time":
            return await self._get_current_time(parameters)
        else:
            return {
                "status": "error",
                "message": f"未知函数: {function_name}"
            }
    
    async def _get_current_time(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """获取当前时间"""
        try:
            timezone = parameters.get("timezone", "Asia/Shanghai")
            
            # 请求MCPO Time服务
            time_url = f"{self.base_url}/time/get_current_time"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    time_url,
                    json={"timezone": timezone}
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"无法获取时间信息: HTTP {response.status_code}"
                    }
                
                time_info = response.json()
                
                return {
                    "status": "success",
                    "time_data": time_info,
                    "timezone": timezone
                }
                
        except httpx.TimeoutException:
            return {
                "status": "error",
                "message": "时间服务请求超时"
            }
        except Exception as e:
            self.logger.error(f"获取时间错误: {e}")
            return {
                "status": "error",
                "message": f"获取时间失败: {str(e)}"
            } 