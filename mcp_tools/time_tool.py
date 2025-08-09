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
            
            # 首先尝试请求MCP Time服务
            try:
                time_url = f"{self.base_url}/time/get_current_time"
                
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        time_url,
                        headers={"Content-Type": "application/json"},
                        json={"timezone": timezone}
                    )
                    
                    if response.status_code == 200:
                        time_info = response.json()
                        return {
                            "status": "success",
                            "data": time_info,
                            "source": "mcp_proxy",
                            "timezone": timezone
                        }
                    else:
                        self.logger.warning(f"MCP时间服务返回错误状态码: {response.status_code}")
            except Exception as e:
                self.logger.warning(f"MCP时间服务不可用，使用本地时间: {e}")
            
            # 如果MCP服务不可用，使用本地时间
            import datetime
            import pytz
            
            # 设置时区
            if timezone == "Asia/Shanghai":
                tz = pytz.timezone("Asia/Shanghai")
            else:
                try:
                    tz = pytz.timezone(timezone)
                except pytz.exceptions.UnknownTimeZoneError:
                    tz = pytz.timezone("Asia/Shanghai")
            
            # 获取当前时间
            now = datetime.datetime.now(tz)
            
            time_data = {
                "year": now.year,
                "month": now.month,
                "day": now.day,
                "hour": now.hour,
                "minute": now.minute,
                "second": now.second,
                "weekday": now.strftime("%A"),
                "weekday_zh": ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()],
                "date_string": now.strftime("%Y年%m月%d日"),
                "time_string": now.strftime("%H:%M:%S"),
                "datetime_string": now.strftime("%Y年%m月%d日 %H:%M:%S"),
                "iso_string": now.isoformat(),
                "timezone": str(tz)
            }
            
            return {
                "status": "success",
                "data": time_data,
                "source": "local_system",
                "timezone": timezone
            }
                
        except Exception as e:
            self.logger.error(f"获取时间错误: {e}")
            return {
                "status": "error",
                "message": f"获取时间失败: {str(e)}"
            } 