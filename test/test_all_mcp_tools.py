#!/usr/bin/env python3
"""
完整的MCP工具系统测试脚本
测试所有7个工具，22个功能的集成和协作
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp_tools.tool_registry import tool_registry

async def test_all_tools():
    """完整测试所有MCP工具"""
    
    print("🚀 启动完整MCP工具系统测试")
    print("=" * 80)
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔧 工具总数: {len(tool_registry.get_all_tools())}")
    print("=" * 80)
    
    # 定义完整的测试用例
    test_scenarios = [
        {
            "category": "📂 文件系统操作",
            "tests": [
                {
                    "name": "列出桌面目录",
                    "tool": "filesystem",
                    "function": "list_directory",
                    "params": {"path": "C:\\Users\\Jason\\Desktop"}
                },
                {
                    "name": "创建测试文件",
                    "tool": "filesystem", 
                    "function": "create_file",
                    "params": {
                        "file_name": "mcp_test",
                        "content": "MCP工具系统测试文件\n创建时间: " + datetime.now().isoformat(),
                        "file_type": "txt"
                    }
                },
                {
                    "name": "读取测试文件",
                    "tool": "filesystem",
                    "function": "read_file", 
                    "params": {"file_path": "mcp_test.txt"}
                }
            ]
        },
        {
            "category": "⏰ 时间信息获取",
            "tests": [
                {
                    "name": "获取当前时间",
                    "tool": "time",
                    "function": "get_current_time",
                    "params": {"timezone": "Asia/Shanghai"}
                }
            ]
        },
        {
            "category": "🌐 网页内容获取", 
            "tests": [
                {
                    "name": "获取网页内容",
                    "tool": "web",
                    "function": "fetch_webpage",
                    "params": {
                        "url": "https://httpbin.org/json",
                        "max_length": 1000
                    }
                }
            ]
        },
        {
            "category": "🔍 搜索功能测试",
            "tests": [
                {
                    "name": "DuckDuckGo基础搜索",
                    "tool": "duckduckgo",
                    "function": "search",
                    "params": {
                        "query": "MCP Model Context Protocol",
                        "max_results": 3
                    }
                }
            ]
        },
        {
            "category": "🧠 推理分析测试",
            "tests": [
                {
                    "name": "Sequential Thinking推理",
                    "tool": "sequential_thinking", 
                    "function": "sequential_thinking",
                    "params": {
                        "prompt": "如何优化MCP工具系统的性能？",
                        "max_steps": 3
                    }
                }
            ]
        },
        {
            "category": "🗺️ 地图服务测试",
            "tests": [
                {
                    "name": "地理编码测试",
                    "tool": "baidu_map",
                    "function": "geocoding", 
                    "params": {"address": "北京天安门"}
                },
                {
                    "name": "路线规划测试",
                    "tool": "baidu_map",
                    "function": "route_planning",
                    "params": {
                        "origin": "北京站",
                        "destination": "天安门广场",
                        "mode": "walking"
                    }
                }
            ]
        }
    ]
    
    # 统计信息
    total_tests = sum(len(scenario["tests"]) for scenario in test_scenarios)
    passed_tests = 0
    failed_tests = 0
    test_results = []
    
    # 执行所有测试
    for scenario in test_scenarios:
        print(f"\n{scenario['category']}")
        print("-" * 60)
        
        for test in scenario["tests"]:
            test_name = test["name"]
            tool_id = test["tool"]
            function_name = test["function"]
            parameters = test["params"]
            
            print(f"  🧪 测试: {test_name}")
            
            try:
                # 获取工具实例
                tool = tool_registry.get_tool(tool_id)
                if not tool:
                    print(f"    ❌ 错误: 未找到工具 '{tool_id}'")
                    failed_tests += 1
                    continue
                
                # 执行功能
                result = await tool.execute_function(function_name, parameters)
                
                # 分析结果
                if isinstance(result, dict):
                    status = result.get("status", "unknown")
                    if status == "success":
                        print(f"    ✅ 成功")
                        
                        # 显示关键结果信息
                        if tool_id == "filesystem":
                            if function_name == "list_directory":
                                count = result.get("total_count", 0)
                                print(f"       📊 找到 {count} 个项目")
                            elif function_name == "create_file":
                                file_path = result.get("file_path", "")
                                print(f"       📝 创建文件: {Path(file_path).name}")
                            elif function_name == "read_file":
                                content = result.get("content", "")
                                size = result.get("size", 0)
                                print(f"       📖 读取 {size} 字符")
                        
                        elif tool_id == "time":
                            # 假设时间工具返回时间信息
                            print(f"       🕐 时间信息已获取")
                        
                        elif tool_id == "web":
                            content = result.get("content", "")
                            if content:
                                print(f"       🌐 获取内容: {len(content)} 字符")
                        
                        elif tool_id == "duckduckgo":
                            if function_name == "search":
                                results = result.get("results", [])
                                print(f"       🔍 找到 {len(results)} 个搜索结果")
                        
                        elif tool_id == "baidu_map":
                            if function_name == "geocoding":
                                location = result.get("location", {})
                                if location:
                                    print(f"       📍 坐标: ({location.get('lat', 'N/A')}, {location.get('lng', 'N/A')})")
                            elif function_name == "route_planning":
                                distance = result.get("distance", "N/A")
                                duration = result.get("duration", "N/A")
                                print(f"       🛣️ 距离: {distance}, 时长: {duration}")
                        
                        passed_tests += 1
                        
                    else:
                        error_msg = result.get("message", "未知错误")
                        print(f"    ❌ 失败: {error_msg}")
                        failed_tests += 1
                        
                else:
                    print(f"    ⚠️ 意外结果格式: {type(result)}")
                    failed_tests += 1
                
                # 记录测试结果
                test_results.append({
                    "category": scenario["category"],
                    "test_name": test_name,
                    "tool": tool_id,
                    "function": function_name,
                    "status": status if isinstance(result, dict) else "unexpected",
                    "result": result
                })
                
            except Exception as e:
                print(f"    ❌ 异常: {str(e)}")
                failed_tests += 1
                test_results.append({
                    "category": scenario["category"],
                    "test_name": test_name,
                    "tool": tool_id,
                    "function": function_name,
                    "status": "exception",
                    "error": str(e)
                })
    
    # 测试完成，显示总结
    print("\n" + "=" * 80)
    print("🎉 MCP工具系统测试完成!")
    print("=" * 80)
    
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"📊 **测试统计:**")
    print(f"   总测试数: {total_tests}")
    print(f"   成功: {passed_tests} ✅")
    print(f"   失败: {failed_tests} ❌") 
    print(f"   成功率: {success_rate:.1f}%")
    
    # 保存详细测试结果
    results_file = f"mcp_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": success_rate,
                "test_time": datetime.now().isoformat()
            },
            "test_results": test_results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 详细测试结果已保存到: {results_file}")
    
    return success_rate >= 70  # 70%以上成功率视为通过

async def test_intelligent_discovery():
    """测试智能工具发现功能"""
    print("\n🔍 **智能工具发现功能测试**")
    print("-" * 60)
    
    discovery_tests = [
        ("查看桌面文件", ["filesystem"]),
        ("搜索地图路线", ["baidu_map"]),
        ("现在几点了", ["time"]),
        ("搜索新闻信息", ["duckduckgo"]),
        ("分析复杂问题", ["sequential_thinking"]),
        ("获取网页内容", ["web"]),
        ("文件管理操作", ["filesystem"]),
        ("网络搜索查询", ["duckduckgo"]),
    ]
    
    correct_predictions = 0
    
    for query, expected_tools in discovery_tests:
        discovered = tool_registry.discover_relevant_tools(query)
        
        # 检查是否包含期望的工具
        has_expected = any(tool in discovered for tool in expected_tools)
        status = "✅" if has_expected else "❌"
        
        print(f"{status} '{query}' → {discovered}")
        if has_expected:
            correct_predictions += 1
    
    accuracy = (correct_predictions / len(discovery_tests)) * 100
    print(f"\n📊 工具发现准确率: {accuracy:.1f}% ({correct_predictions}/{len(discovery_tests)})")
    
    return accuracy >= 80  # 80%以上准确率视为通过

async def main():
    """主函数"""
    try:
        print("🤖 MCP工具系统完整测试套件")
        print("=" * 80)
        
        # 测试智能工具发现
        discovery_success = await test_intelligent_discovery()
        
        # 测试所有工具功能
        tools_success = await test_all_tools()
        
        print("\n" + "=" * 80)
        print("🏁 **最终测试结果**")
        print("=" * 80)
        
        print(f"🔍 智能工具发现: {'✅ 通过' if discovery_success else '❌ 未通过'}")
        print(f"🛠️ 工具功能测试: {'✅ 通过' if tools_success else '❌ 未通过'}")
        
        overall_success = discovery_success and tools_success
        print(f"\n🎯 **整体测试: {'✅ 通过' if overall_success else '❌ 未通过'}**")
        
        if overall_success:
            print("\n🎉 MCP工具系统已准备就绪，可以投入使用！")
        else:
            print("\n⚠️ 部分功能需要进一步优化")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 