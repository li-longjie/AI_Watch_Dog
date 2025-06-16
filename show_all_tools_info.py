#!/usr/bin/env python3
"""
显示所有MCP工具的完整描述信息
验证前端大模型能获取到的工具Schema
"""

import sys
from pathlib import Path
import json

# 添加项目根目录到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """主函数"""
    try:
        from mcp_tools.tool_registry import tool_registry
        
        print("🤖 MCP工具系统 - 前端大模型可用的完整工具描述")
        print("=" * 80)
        
        all_tools = tool_registry.list_all_tools()
        
        print(f"📊 **工具总数：{len(all_tools)}个**\n")
        
        for i, tool_info in enumerate(all_tools, 1):
            tool_id = tool_info["id"]
            
            print(f"{i}. 🛠️ **{tool_info['name']}** (`{tool_id}`)")
            print(f"   📝 {tool_info['description']}")
            print(f"   🔧 功能数量: {len(tool_info['functions'])}")
            
            # 显示每个功能的详细信息
            for func_name, func_info in tool_info["functions"].items():
                print(f"   └── 📌 **{func_name}**: {func_info['description']}")
                
                # 参数信息
                if "parameters" in func_info:
                    params = func_info["parameters"]
                    print(f"       📋 参数:")
                    for param_name, param_info in params.items():
                        required = "✅" if param_info.get("required", False) else "🔹"
                        print(f"         {required} {param_name}: {param_info.get('description', 'N/A')}")
                
                # 使用示例
                if "examples" in func_info:
                    examples = func_info["examples"]
                    print(f"       💡 示例: {', '.join(examples[:2])}")
                    if len(examples) > 2:
                        print(f"              等{len(examples)}个示例...")
            
            print()
        
        # 显示智能工具发现测试
        print("\n🔍 **智能工具发现测试**")
        print("-" * 50)
        
        test_queries = [
            "查看桌面上有什么文件",
            "创建一个新的记事本文件", 
            "搜索北京到上海的路线",
            "帮我分析这个问题",
            "搜索今天的新闻",
            "现在几点了",
            "打开百度网页",
            "在浏览器中点击登录按钮"
        ]
        
        for query in test_queries:
            relevant_tools = tool_registry.discover_relevant_tools(query)
            print(f"'{query}' → {relevant_tools}")
        
        print("\n📤 **前端大模型调用方式:**")
        print("""
1. 获取工具列表: tool_registry.list_all_tools()
2. 智能工具发现: tool_registry.discover_relevant_tools(user_query)  
3. 执行工具功能: tool.execute_function(function_name, parameters)
4. 返回结构化结果给用户
        """)
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 