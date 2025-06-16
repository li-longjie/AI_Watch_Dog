"""
统一检索系统 - 整合视频监控和桌面活动的自然语言检索
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import asyncio
import re

# 导入现有的检索模块
from activity_retriever import query_recent_activity, parse_time_range_from_query
from rag_server import search, SearchRequest, LLMService

class UnifiedRetriever:
    """统一检索接口"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 监控关键词 - 用于识别视频监控查询
        self.MONITORING_KEYWORDS = {
            "监控", "摄像头", "发现", "检测到", "看到", "观察到", "显示", "记录", 
            "camera", "detected", "视频", "画面", "拍到", "出现", "动作", "行为",
            "活动", "状态", "情况", "监控录像", "安防"
        }
        
        # 桌面活动关键词 - 用于识别桌面活动查询
        self.DESKTOP_KEYWORDS = {
            "桌面", "屏幕", "软件", "应用", "程序", "窗口", "浏览器", "网页", 
            "打开", "使用", "操作", "点击", "截图", "OCR", "应用程序",
            "Chrome", "Firefox", "VSCode", "Word", "Excel"
        }

    async def unified_query(self, query: str, k: int = 5) -> Dict[str, Any]:
        """
        统一查询接口 - 自动识别查询类型并路由到相应的检索系统
        
        Args:
            query: 用户查询文本
            k: 返回结果数量
            
        Returns:
            统一格式的查询结果
        """
        try:
            # 1. 意图识别
            query_type = self._detect_query_intent(query)
            self.logger.info(f"检测到查询类型: {query_type}, 查询内容: {query}")
            
            # 2. 根据意图路由到相应的检索系统
            if query_type == "monitoring_only":
                return await self._query_monitoring_system(query, k)
            elif query_type == "desktop_only":
                return await self._query_desktop_system(query, k)
            elif query_type == "combined":
                return await self._query_combined_systems(query, k)
            else:
                # 默认使用桌面活动检索（因为使用频率更高）
                return await self._query_desktop_system(query, k)
                
        except Exception as e:
            self.logger.error(f"统一查询处理错误: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"查询处理时发生错误: {str(e)}",
                "source": "unified_retriever"
            }

    def _detect_query_intent(self, query: str) -> str:
        """
        检测查询意图
        
        Returns:
            "monitoring_only": 仅查询视频监控
            "desktop_only": 仅查询桌面活动  
            "combined": 需要查询两个系统
            "unknown": 未知类型
        """
        query_lower = query.lower()
        
        has_monitoring_keywords = any(keyword in query for keyword in self.MONITORING_KEYWORDS)
        has_desktop_keywords = any(keyword in query for keyword in self.DESKTOP_KEYWORDS)
        
        # 检查是否明确要求综合查询
        combined_patterns = [
            r"(视频|监控).*(桌面|软件|应用|程序)",
            r"(桌面|软件|应用|程序).*(视频|监控)",
            r"全部|所有|整体|综合|总的",
            r"都.*(做了什么|在干什么|活动)"
        ]
        
        has_combined_intent = any(re.search(pattern, query) for pattern in combined_patterns)
        
        if has_combined_intent or (has_monitoring_keywords and has_desktop_keywords):
            return "combined"
        elif has_monitoring_keywords and not has_desktop_keywords:
            return "monitoring_only"
        elif has_desktop_keywords and not has_monitoring_keywords:
            return "desktop_only"
        else:
            # 如果没有明确关键词，根据时间词判断更可能是哪种查询
            time_keywords = ["昨天", "今天", "刚才", "最近", "过去"]
            if any(keyword in query for keyword in time_keywords):
                return "desktop_only"  # 桌面活动查询更常用时间范围
            return "unknown"

    async def _query_monitoring_system(self, query: str, k: int) -> Dict[str, Any]:
        """查询视频监控系统"""
        try:
            # 调用 rag_server 的搜索功能
            search_request = SearchRequest(query=query, k=k)
            result = await search(search_request)
            
            # 统一返回格式
            return {
                "status": result.get("status", "success"),
                "answer": result.get("answer", ""),
                "source": "monitoring_system",
                "contexts": result.get("contexts", []),
                "query_type": "monitoring_only"
            }
        except Exception as e:
            self.logger.error(f"监控系统查询错误: {e}")
            return {
                "status": "error",
                "message": f"监控系统查询失败: {str(e)}",
                "source": "monitoring_system"
            }

    async def _query_desktop_system(self, query: str, k: int = None) -> Dict[str, Any]:
        """查询桌面活动系统"""
        try:
            # 调用 activity_retriever 的查询功能
            result = await query_recent_activity(query)
            
            return {
                "status": "success",
                "answer": result,
                "source": "desktop_system", 
                "contexts": [],  # activity_retriever 不直接返回contexts
                "query_type": "desktop_only"
            }
        except Exception as e:
            self.logger.error(f"桌面系统查询错误: {e}")
            return {
                "status": "error",
                "message": f"桌面系统查询失败: {str(e)}",
                "source": "desktop_system"
            }

    async def _query_combined_systems(self, query: str, k: int) -> Dict[str, Any]:
        """同时查询两个系统并合并结果"""
        try:
            # 并行查询两个系统
            monitoring_task = asyncio.create_task(self._query_monitoring_system(query, k//2))
            desktop_task = asyncio.create_task(self._query_desktop_system(query, k//2))
            
            monitoring_result, desktop_result = await asyncio.gather(
                monitoring_task, desktop_task, return_exceptions=True
            )
            
            # 处理异常
            if isinstance(monitoring_result, Exception):
                self.logger.error(f"监控系统查询异常: {monitoring_result}")
                monitoring_result = {"status": "error", "answer": "监控系统查询失败"}
                
            if isinstance(desktop_result, Exception):
                self.logger.error(f"桌面系统查询异常: {desktop_result}")
                desktop_result = {"status": "error", "answer": "桌面系统查询失败"}
            
            # 合并结果
            combined_answer = await self._merge_results(query, monitoring_result, desktop_result)
            
            return {
                "status": "success",
                "answer": combined_answer,
                "source": "combined_systems",
                "monitoring_result": monitoring_result,
                "desktop_result": desktop_result,
                "query_type": "combined"
            }
            
        except Exception as e:
            self.logger.error(f"综合查询错误: {e}")
            return {
                "status": "error",
                "message": f"综合查询失败: {str(e)}",
                "source": "combined_systems"
            }

    async def _merge_results(self, query: str, monitoring_result: Dict, desktop_result: Dict) -> str:
        """使用LLM合并两个系统的查询结果"""
        try:
            # 构建合并提示词
            merge_prompt = f"""请根据以下两个不同系统的查询结果，为用户问题提供一个综合、连贯的回答。

用户问题：{query}

视频监控系统结果：
{monitoring_result.get('answer', '未找到相关监控记录')}

桌面活动系统结果：
{desktop_result.get('answer', '未找到相关桌面活动')}

请综合以上信息，为用户提供一个完整、有逻辑的回答。如果某个系统没有相关信息，请说明。回答要自然流畅，避免简单的信息堆砌。"""

            # 调用LLM生成综合回答
            merged_answer = await LLMService.get_response(merge_prompt)
            return merged_answer
            
        except Exception as e:
            self.logger.error(f"结果合并错误: {e}")
            # 如果LLM合并失败，返回简单的文本合并
            return f"""根据查询结果：

🔍 视频监控方面：
{monitoring_result.get('answer', '未找到相关监控记录')}

💻 桌面活动方面：
{desktop_result.get('answer', '未找到相关桌面活动')}"""

    async def get_activity_summary(self, time_range: str = "今天") -> Dict[str, Any]:
        """获取指定时间范围的活动总结"""
        try:
            # 解析时间范围
            start_time, end_time = parse_time_range_from_query(time_range)
            
            # 并行获取两个系统的数据
            monitoring_query = f"{time_range}的监控记录总结"
            desktop_query = f"{time_range}的桌面活动总结"
            
            monitoring_task = asyncio.create_task(self._query_monitoring_system(monitoring_query, 10))
            desktop_task = asyncio.create_task(self._query_desktop_system(desktop_query))
            
            monitoring_summary, desktop_summary = await asyncio.gather(
                monitoring_task, desktop_task, return_exceptions=True
            )
            
            # 生成综合总结
            summary_prompt = f"""请基于以下信息，生成{time_range}的活动总结报告：

监控系统记录：
{monitoring_summary.get('answer', '无监控记录') if not isinstance(monitoring_summary, Exception) else '监控系统查询失败'}

桌面活动记录：  
{desktop_summary.get('answer', '无桌面活动') if not isinstance(desktop_summary, Exception) else '桌面系统查询失败'}

请生成一个简洁但全面的活动总结，包括主要活动、时间分布等关键信息。"""

            summary = await LLMService.get_response(summary_prompt)
            
            return {
                "status": "success",
                "summary": summary,
                "time_range": f"{start_time.strftime('%Y-%m-%d %H:%M')} 至 {end_time.strftime('%Y-%m-%d %H:%M')}",
                "monitoring_data": monitoring_summary if not isinstance(monitoring_summary, Exception) else None,
                "desktop_data": desktop_summary if not isinstance(desktop_summary, Exception) else None
            }
            
        except Exception as e:
            self.logger.error(f"活动总结生成错误: {e}")
            return {
                "status": "error", 
                "message": f"生成活动总结时出错: {str(e)}"
            }


# 全局实例
unified_retriever = UnifiedRetriever()

# 便捷函数
async def unified_query(query: str, k: int = 5) -> Dict[str, Any]:
    """统一查询入口函数"""
    return await unified_retriever.unified_query(query, k)

async def get_daily_summary(date: str = "今天") -> Dict[str, Any]:
    """获取每日活动总结"""
    return await unified_retriever.get_activity_summary(date)

if __name__ == "__main__":
    # 测试代码
    async def test_unified_retriever():
        # 测试不同类型的查询
        test_queries = [
            "我昨天下午用了什么软件？",  # 桌面活动
            "今天监控到了什么异常？",      # 视频监控  
            "我昨天都在做什么？",          # 综合查询
            "过去一小时的所有活动情况"     # 综合查询
        ]
        
        for query in test_queries:
            print(f"\n测试查询: {query}")
            result = await unified_query(query)
            print(f"查询类型: {result.get('query_type')}")
            print(f"结果: {result.get('answer', result.get('message'))[:200]}...")
            
        # 测试每日总结
        print(f"\n测试每日总结:")
        summary = await get_daily_summary("今天")
        print(summary.get('summary', summary.get('message'))[:300])

    asyncio.run(test_unified_retriever()) 