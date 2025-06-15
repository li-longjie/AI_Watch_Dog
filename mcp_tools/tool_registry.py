from typing import Dict, List, Any, Optional
import logging
from .base_tool import BaseMCPTool
from .fetch_tool import FetchTool
from .time_tool import TimeTool
from .filesystem_tool import FilesystemTool
from .browser_tool import BrowserTool
from .sequential_thinking_tool import SequentialThinkingTool
from .duckduckgo_tool import DuckDuckGoTool
from .baidu_map_tool import BaiduMapTool

logger = logging.getLogger(__name__)

class ToolRegistry:
    """工具注册表类"""
    
    def __init__(self):
        self.tools: Dict[str, BaseMCPTool] = {}
        self._initialize_tools()
    
    def _initialize_tools(self):
        """初始化所有工具"""
        try:
            # 注册所有工具
            self.tools = {
                "web": FetchTool(),
                "time": TimeTool(),
                "filesystem": FilesystemTool(),
                "browser": BrowserTool(),
                "sequential_thinking": SequentialThinkingTool(),
                "duckduckgo": DuckDuckGoTool(),
                "baidu_map": BaiduMapTool()
            }
            
            logger.info(f"已注册 {len(self.tools)} 个MCP工具")
            for tool_id, tool in self.tools.items():
                logger.info(f"- {tool_id}: {tool.tool_name}")
                
        except Exception as e:
            logger.error(f"初始化工具失败: {e}")
    
    def get_tool(self, tool_id: str) -> Optional[BaseMCPTool]:
        """根据工具ID获取工具实例"""
        return self.tools.get(tool_id)
    
    def get_all_tools(self) -> Dict[str, BaseMCPTool]:
        """获取所有注册的工具"""
        return self.tools.copy()
    
    def discover_relevant_tools(self, user_query: str) -> List[str]:
        """
        基于用户查询智能发现相关工具
        返回匹配的工具ID列表，按相关度排序
        """
        query_lower = user_query.lower()
        tool_scores = {}
        
        # 工具关键词映射（增强版）
        tool_keywords = {
            "web": [
                "网页", "网站", "链接", "url", "http", "https", "抓取", "爬虫", 
                "网络", "下载", "fetch", "web", "site", "page", "html", "内容获取"
            ],
            "time": [
                "时间", "日期", "现在", "当前", "几点", "今天", "明天", "昨天",
                "time", "date", "now", "today", "tomorrow", "yesterday", "clock",
                "年", "月", "日", "小时", "分钟", "秒", "时区", "timezone"
            ],
            "filesystem": [
                "文件", "文件夹", "目录", "桌面", "读取", "写入", "创建", "删除", 
                "移动", "复制", "重命名", "搜索", "查看", "保存", "打开",
                "file", "folder", "directory", "desktop", "read", "write", 
                "create", "delete", "move", "copy", "rename", "search", "save", "open",
                "txt", "文档", "记事本", "列表", "内容", "信息", "属性",
                "新建", "建立", "编辑", "修改", "浏览", "查找", "定位"
            ],
            "browser": [
                "浏览器", "网页操作", "点击", "输入", "表单", "自动化", "selenium",
                "browser", "click", "input", "form", "automation", "navigate",
                "页面", "元素", "按钮", "链接", "滚动", "截图", "等待"
            ],
            "sequential_thinking": [
                "思考", "分析", "推理", "逻辑", "步骤", "计划", "策略", "解决",
                "thinking", "analysis", "reasoning", "logic", "step", "plan", 
                "strategy", "solve", "问题", "方案", "建议", "决策", "评估"
            ],
            "duckduckgo": [
                "搜索", "查找", "查询", "检索", "信息", "资料", "新闻", "知识",
                "search", "find", "query", "lookup", "information", "data", 
                "news", "knowledge", "百科", "答案", "结果", "内容"
            ],
            "baidu_map": [
                "地图", "导航", "路线", "位置", "地址", "交通", "出行", "驾车",
                "步行", "公交", "骑行", "景点", "餐厅", "POI", "旅游", "规划",
                "map", "navigation", "route", "location", "address", "traffic",
                "travel", "driving", "walking", "bus", "cycling", "restaurant",
                "attraction", "tourism", "planning", "坐标", "距离", "时间",
                "费用", "推荐", "搜索地点", "查找位置", "路径规划", "行程安排"
            ]
        }
        
        # 计算每个工具的相关度得分
        for tool_id, keywords in tool_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in query_lower:
                    # 完全匹配得更高分
                    if keyword == query_lower.strip():
                        score += 10
                    # 包含关键词得基础分
                    else:
                        score += 1
            
            if score > 0:
                tool_scores[tool_id] = score
        
        # 按得分排序，返回工具ID列表
        sorted_tools = sorted(tool_scores.items(), key=lambda x: x[1], reverse=True)
        return [tool_id for tool_id, score in sorted_tools]
    
    def get_tool_info(self, tool_id: str) -> Dict[str, Any]:
        """获取工具的详细信息"""
        tool = self.get_tool(tool_id)
        if not tool:
            return {}
        
        return {
            "id": tool_id,
            "name": tool.tool_name,
            "description": tool.description,
            "functions": tool.get_available_functions()
        }
    
    def list_all_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具的信息"""
        return [self.get_tool_info(tool_id) for tool_id in self.tools.keys()]

# 全局工具注册表实例
tool_registry = ToolRegistry() 