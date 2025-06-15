import httpx
from typing import Dict, Any
from .base_tool import BaseMCPTool

class BrowserTool(BaseMCPTool):
    """浏览器自动化工具"""
    
    @property
    def tool_name(self) -> str:
        return "浏览器工具"
    
    @property
    def description(self) -> str:
        return "用于浏览器自动化操作和深度网络搜索，可以执行复杂的网页操作任务"
    
    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "run_browser_agent": {
                "description": "执行浏览器自动化任务，如打开网站、点击按钮、填写表单等",
                "parameters": {
                    "task": {
                        "type": "string",
                        "description": "要执行的浏览器任务描述",
                        "required": True
                    },
                    "add_infos": {
                        "type": "string",
                        "description": "额外的信息或URL",
                        "required": False
                    }
                },
                "examples": [
                    "打开百度搜索Python教程",
                    "访问GitHub并查看最新的仓库",
                    "浏览新闻网站获取今日头条",
                    "打开购物网站搜索商品"
                ]
            },
            "run_deep_search": {
                "description": "执行深度网络搜索和研究任务，自动搜索多个来源并整合信息",
                "parameters": {
                    "research_task": {
                        "type": "string",
                        "description": "研究任务或主题",
                        "required": True
                    },
                    "max_query_per_iteration": {
                        "type": "integer",
                        "description": "每次迭代的最大查询数量，默认3",
                        "required": False
                    },
                    "max_search_iterations": {
                        "type": "integer",
                        "description": "最大搜索迭代次数，默认10",
                        "required": False
                    }
                },
                "examples": [
                    "研究人工智能最新发展趋势",
                    "调研2024年电动汽车市场情况",
                    "深度搜索区块链技术应用案例",
                    "查找关于气候变化的最新科研成果"
                ]
            }
        }
    
    async def execute_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行浏览器操作"""
        if function_name == "run_browser_agent":
            return await self._run_browser_agent(parameters)
        elif function_name == "run_deep_search":
            return await self._run_deep_search(parameters)
        else:
            return {
                "status": "error",
                "message": f"未知函数: {function_name}"
            }
    
    async def _run_browser_agent(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行浏览器代理任务"""
        try:
            task = parameters.get("task")
            add_infos = parameters.get("add_infos")
            
            if not task:
                return {
                    "status": "error",
                    "message": "缺少必需参数: task"
                }
            
            # 准备请求数据
            request_data = {"task": task}
            if add_infos:
                request_data["add_infos"] = add_infos
            
            # 请求MCPO Browser Agent服务
            browser_url = f"{self.base_url}/browser-use/run_browser_agent"
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    browser_url,
                    json=request_data
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"浏览器任务执行失败: HTTP {response.status_code}"
                    }
                
                result = response.json()
                
                return {
                    "status": "success",
                    "task": task,
                    "result": result
                }
                
        except httpx.TimeoutException:
            return {
                "status": "error",
                "message": "浏览器任务执行超时，任务可能较复杂"
            }
        except Exception as e:
            self.logger.error(f"浏览器代理错误: {e}")
            return {
                "status": "error",
                "message": f"浏览器任务失败: {str(e)}"
            }
    
    async def _run_deep_search(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行深度搜索任务"""
        try:
            research_task = parameters.get("research_task")
            max_query_per_iteration = parameters.get("max_query_per_iteration", 3)
            max_search_iterations = parameters.get("max_search_iterations", 10)
            
            if not research_task:
                return {
                    "status": "error",
                    "message": "缺少必需参数: research_task"
                }
            
            # 准备请求数据
            request_data = {
                "research_task": research_task,
                "max_query_per_iteration": max_query_per_iteration,
                "max_search_iterations": max_search_iterations
            }
            
            # 请求MCPO Deep Search服务
            search_url = f"{self.base_url}/browser-use/run_deep_search"
            
            async with httpx.AsyncClient(timeout=360.0) as client:
                response = await client.post(
                    search_url,
                    json=request_data
                )
                
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"深度搜索失败: HTTP {response.status_code}"
                    }
                
                result = response.json()
                
                return {
                    "status": "success",
                    "research_task": research_task,
                    "result": result
                }
                
        except httpx.TimeoutException:
            return {
                "status": "error",
                "message": "深度搜索超时，研究任务可能较复杂"
            }
        except Exception as e:
            self.logger.error(f"深度搜索错误: {e}")
            return {
                "status": "error",
                "message": f"深度搜索失败: {str(e)}"
            } 