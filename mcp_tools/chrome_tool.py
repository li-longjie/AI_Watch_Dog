import httpx
import asyncio
from typing import Dict, Any, Optional
from .base_tool import BaseMCPTool

class ChromeTool(BaseMCPTool):
    """Chrome浏览器直接控制工具 - 基于streamable-mcp-server"""

    def __init__(self, base_url: str = "http://127.0.0.1:12306"):
        """初始化Chrome工具，默认使用12306端口"""
        super().__init__(base_url)
        self._session_initialized = False
        self._client: Optional[httpx.AsyncClient] = None
        self._session_id: Optional[str] = None

    @property
    def tool_name(self) -> str:
        return "Chrome浏览器控制工具"

    @property
    def description(self) -> str:
        return "直接控制用户当前的Chrome浏览器，支持页面导航、元素交互、内容获取、网络监控等22种核心功能"

    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        return {
            # 浏览器管理
            "get_windows_and_tabs": {
                "description": "获取所有打开的浏览器窗口和标签页",
                "parameters": {},
                "examples": ["查看所有打开的标签页", "显示浏览器窗口列表"]
            },
            "chrome_navigate": {
                "description": "导航到指定URL或刷新当前页面",
                "parameters": {
                    "url": {"type": "string", "description": "要访问的网址", "required": False},
                    "refresh": {"type": "boolean", "description": "是否刷新当前页面", "required": False},
                    "newWindow": {"type": "boolean", "description": "是否在新窗口打开", "required": False}
                },
                "examples": ["打开百度", "刷新当前页面", "在新窗口打开GitHub"]
            },
            "chrome_close_tabs": {
                "description": "关闭指定的浏览器标签页",
                "parameters": {
                    "tabIds": {"type": "array", "description": "要关闭的标签页ID列表", "required": False},
                    "url": {"type": "string", "description": "关闭匹配此URL的标签页", "required": False}
                },
                "examples": ["关闭当前标签页", "关闭百度相关的标签页"]
            },
            "chrome_go_back_or_forward": {
                "description": "浏览器历史记录导航",
                "parameters": {
                    "isForward": {"type": "boolean", "description": "true为前进，false为后退", "required": False}
                },
                "examples": ["后退到上一页", "前进到下一页"]
            },

            # 页面截图
            "chrome_screenshot": {
                "description": "对当前页面或指定元素进行截图",
                "parameters": {
                    "selector": {"type": "string", "description": "要截图的元素CSS选择器", "required": False},
                    "fullPage": {"type": "boolean", "description": "是否截取整个页面", "required": False},
                    "name": {"type": "string", "description": "截图文件名", "required": False}
                },
                "examples": ["截取当前页面", "截取登录按钮", "截取整个网页"]
            },

            # 内容获取
            "chrome_get_web_content": {
                "description": "获取网页的文本或HTML内容",
                "parameters": {
                    "url": {"type": "string", "description": "要获取内容的URL", "required": False},
                    "textContent": {"type": "boolean", "description": "获取文本内容", "required": False},
                    "htmlContent": {"type": "boolean", "description": "获取HTML内容", "required": False},
                    "selector": {"type": "string", "description": "指定元素的CSS选择器", "required": False}
                },
                "examples": ["获取当前页面文本", "获取页面HTML源码", "提取特定元素内容"]
            },

            # 页面交互
            "chrome_click_element": {
                "description": "点击页面中的元素或指定坐标",
                "parameters": {
                    "selector": {"type": "string", "description": "要点击的元素CSS选择器", "required": False},
                    "coordinates": {"type": "object", "description": "点击坐标{x, y}", "required": False},
                    "waitForNavigation": {"type": "boolean", "description": "是否等待页面导航完成", "required": False}
                },
                "examples": ["点击登录按钮", "点击搜索框", "点击坐标(100, 200)"]
            },
            "chrome_fill_or_select": {
                "description": "填写表单字段或选择下拉选项",
                "parameters": {
                    "selector": {"type": "string", "description": "输入框或选择框的CSS选择器", "required": True},
                    "value": {"type": "string", "description": "要填入或选择的值", "required": True}
                },
                "examples": ["在搜索框输入'人工智能'", "选择下拉菜单选项", "填写用户名"]
            },
            "chrome_get_interactive_elements": {
                "description": "获取页面中可交互的元素列表",
                "parameters": {
                    "selector": {"type": "string", "description": "过滤元素的CSS选择器", "required": False},
                    "textQuery": {"type": "string", "description": "按文本内容搜索元素", "required": False}
                },
                "examples": ["获取所有按钮", "查找包含'登录'的元素", "获取所有链接"]
            },
            "chrome_keyboard": {
                "description": "模拟键盘输入和快捷键操作",
                "parameters": {
                    "keys": {"type": "string", "description": "要按的键，如'Enter'、'Ctrl+C'等", "required": True},
                    "selector": {"type": "string", "description": "目标元素选择器", "required": False},
                    "delay": {"type": "number", "description": "按键间延迟(毫秒)", "required": False}
                },
                "examples": ["按Enter键", "复制内容Ctrl+C", "刷新页面F5"]
            },

            # 网络请求
            "chrome_network_request": {
                "description": "通过浏览器发送HTTP请求",
                "parameters": {
                    "url": {"type": "string", "description": "请求URL", "required": True},
                    "method": {"type": "string", "description": "HTTP方法", "required": False},
                    "headers": {"type": "object", "description": "请求头", "required": False},
                    "body": {"type": "string", "description": "请求体", "required": False}
                },
                "examples": ["发送GET请求", "POST提交数据", "带认证头的请求"]
            },
            "chrome_network_debugger_start": {
                "description": "开始捕获网络请求(包含响应体)",
                "parameters": {
                    "url": {"type": "string", "description": "要监控的页面URL", "required": False}
                },
                "examples": ["开始监听网络请求", "监控当前页面的网络活动"]
            },
            "chrome_network_debugger_stop": {
                "description": "停止网络请求捕获并返回数据",
                "parameters": {},
                "examples": ["停止网络监听并获取数据", "结束网络监控"]
            },

            # 浏览器数据
            "chrome_history": {
                "description": "检索和搜索Chrome浏览历史",
                "parameters": {
                    "text": {"type": "string", "description": "搜索关键词", "required": False},
                    "startTime": {"type": "string", "description": "开始时间", "required": False},
                    "endTime": {"type": "string", "description": "结束时间", "required": False},
                    "maxResults": {"type": "number", "description": "最大结果数", "required": False}
                },
                "examples": ["搜索浏览历史", "查找昨天访问的网站", "搜索包含'AI'的历史记录"]
            },
            "chrome_bookmark_search": {
                "description": "搜索Chrome书签",
                "parameters": {
                    "query": {"type": "string", "description": "搜索关键词", "required": False},
                    "folderPath": {"type": "string", "description": "搜索特定文件夹", "required": False},
                    "maxResults": {"type": "number", "description": "最大结果数", "required": False}
                },
                "examples": ["搜索所有书签", "查找技术相关书签", "搜索工作文件夹的书签"]
            },
            "chrome_bookmark_add": {
                "description": "添加新书签到Chrome",
                "parameters": {
                    "url": {"type": "string", "description": "书签URL", "required": False},
                    "title": {"type": "string", "description": "书签标题", "required": False},
                    "parentId": {"type": "string", "description": "父文件夹路径", "required": False}
                },
                "examples": ["收藏当前页面", "添加GitHub到书签", "保存到工作文件夹"]
            },
            "chrome_bookmark_delete": {
                "description": "删除Chrome书签",
                "parameters": {
                    "bookmarkId": {"type": "string", "description": "书签ID", "required": False},
                    "url": {"type": "string", "description": "要删除的书签URL", "required": False}
                },
                "examples": ["删除指定书签", "移除当前页面的书签"]
            },

            # 高级功能
            "search_tabs_content": {
                "description": "在当前打开的标签页中搜索相关内容",
                "parameters": {
                    "query": {"type": "string", "description": "搜索查询", "required": True}
                },
                "examples": ["搜索所有标签页中的'人工智能'", "查找相关技术文档"]
            },
            "chrome_inject_script": {
                "description": "向网页注入JavaScript代码",
                "parameters": {
                    "jsScript": {"type": "string", "description": "要注入的JavaScript代码", "required": True},
                    "type": {"type": "string", "description": "执行环境：ISOLATED或MAIN", "required": True},
                    "url": {"type": "string", "description": "目标页面URL", "required": False}
                },
                "examples": ["注入页面修改脚本", "执行数据提取代码", "添加页面功能"]
            },
            "chrome_console": {
                "description": "获取浏览器控制台输出",
                "parameters": {
                    "url": {"type": "string", "description": "目标页面URL", "required": False},
                    "maxMessages": {"type": "number", "description": "最大消息数", "required": False},
                    "includeExceptions": {"type": "boolean", "description": "包含异常信息", "required": False}
                },
                "examples": ["获取控制台日志", "查看页面错误", "监控调试信息"]
            }
        }

    async def _initialize_session(self) -> bool:
        """初始化MCP会话"""
        if self._session_initialized:
            return True

        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }

            # 初始化请求
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ai-watch-dog",
                        "version": "1.0.0"
                    }
                }
            }

            if not self._client:
                self._client = httpx.AsyncClient(timeout=60.0)

            response = await self._client.post(
                f"{self.base_url}/mcp",
                json=init_request,
                headers=headers
            )

            if response.status_code == 200:
                # 提取会话ID
                self._session_id = response.headers.get('mcp-session-id')
                self.logger.debug(f"获取会话ID: {self._session_id}")

                # 解析SSE格式的响应
                response_text = response.text
                self.logger.debug(f"初始化响应: {response_text}")

                # 提取SSE数据部分
                if "data: " in response_text:
                    import json
                    data_line = None
                    for line in response_text.split('\n'):
                        if line.startswith('data: '):
                            data_line = line[6:]  # 去掉"data: "前缀
                            break

                    if data_line:
                        try:
                            result = json.loads(data_line)
                            if "result" in result:
                                self._session_initialized = True
                                self.logger.info(f"Chrome MCP会话初始化成功，会话ID: {self._session_id}")
                                return True
                        except json.JSONDecodeError as e:
                            self.logger.error(f"解析SSE数据失败: {e}")
                            return False

            self.logger.error(f"MCP会话初始化失败: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            self.logger.error(f"MCP会话初始化异常: {e}")
            return False

    def _parse_response(self, response: httpx.Response) -> Optional[Dict[str, Any]]:
        """解析HTTP响应，支持JSON和SSE格式"""
        try:
            content_type = response.headers.get('content-type', '')

            if 'text/event-stream' in content_type:
                # 解析SSE格式
                response_text = response.text
                for line in response_text.split('\n'):
                    if line.startswith('data: '):
                        data_line = line[6:]  # 去掉"data: "前缀
                        try:
                            import json
                            return json.loads(data_line)
                        except json.JSONDecodeError:
                            continue
                return None
            else:
                # 解析普通JSON
                return response.json()

        except Exception as e:
            self.logger.error(f"响应解析失败: {e}")
            return None

    async def execute_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行Chrome浏览器操作"""
        try:
            # 确保会话已初始化
            if not await self._initialize_session():
                return {
                    "status": "error",
                    "message": "无法初始化Chrome MCP会话"
                }

            # 构建MCP协议请求
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 2,  # 使用id=2，因为id=1用于初始化
                "method": "tools/call",
                "params": {
                    "name": function_name,
                    "arguments": parameters
                }
            }

            # 设置正确的HTTP头，包含会话ID
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }

            if self._session_id:
                headers["mcp-session-id"] = self._session_id

            response = await self._client.post(
                f"{self.base_url}/mcp",
                json=mcp_request,
                headers=headers
            )

            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Chrome操作失败: HTTP {response.status_code}",
                    "details": response.text
                }

            # 解析响应（可能是SSE格式）
            result = self._parse_response(response)
            if result is None:
                return {
                    "status": "error",
                    "message": "无法解析Chrome MCP响应"
                }

            # 处理MCP协议响应
            if "error" in result:
                return {
                    "status": "error",
                    "message": f"Chrome MCP错误: {result['error'].get('message', '未知错误')}",
                    "details": result["error"]
                }

            if "result" in result:
                return {
                    "status": "success",
                    "function": function_name,
                    "result": result["result"]
                }

            return {
                "status": "success",
                "function": function_name,
                "result": result
            }

        except httpx.TimeoutException:
            return {
                "status": "error",
                "message": f"Chrome操作超时: {function_name}"
            }
        except Exception as e:
            self.logger.error(f"Chrome工具错误: {function_name} - {e}")
            return {
                "status": "error",
                "message": f"Chrome操作失败: {str(e)}"
            }

    async def cleanup(self):
        """清理资源"""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._session_initialized = False
        self._session_id = None
