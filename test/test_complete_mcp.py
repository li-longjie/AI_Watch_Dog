#!/usr/bin/env python3
"""
完整的MCP工具系统测试脚本
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def main():
    """主函数"""
    try:
        from mcp_tools.tool_registry import tool_registry
        
        print("🤖 MCP工具系统完整测试")
        print("=" * 60)
        print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 获取所有工具
        all_tools = tool_registry.get_all_tools()
        print(f"🔧 已注册工具数量: {len(all_tools)}")
        
        # 显示工具列表
        print("\n📋 **注册的工具列表:**")
        for tool_id, tool in all_tools.items():
            print(f"  - {tool_id}: {tool.tool_name}")
        
        # 测试智能工具发现
        print("\n🔍 **智能工具发现测试:**")
        test_queries = [
            "查看桌面文件",
            "搜索地图路线", 
            "现在几点了",
            "搜索新闻",
            "分析问题",
            "获取网页"
        ]
        
        for query in test_queries:
            discovered = tool_registry.discover_relevant_tools(query)
            print(f"  '{query}' → {discovered}")
        
        print("\n✅ MCP工具系统基础测试完成!")
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 