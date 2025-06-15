#!/usr/bin/env python3
"""
增强文件系统工具测试脚本
测试从flie.py整合的所有文件操作功能
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp_tools.filesystem_tool import FilesystemTool

async def test_filesystem_operations():
    """测试所有文件系统操作"""
    
    print("🚀 启动增强文件系统工具测试")
    print("=" * 60)
    
    # 初始化工具
    fs_tool = FilesystemTool()
    
    # 测试用例列表
    test_cases = [
        {
            "name": "📂 列出桌面目录",
            "function": "list_directory",
            "parameters": {"path": "C:\\Users\\Jason\\Desktop"}
        },
        {
            "name": "📝 创建测试文件",
            "function": "create_file", 
            "parameters": {
                "file_name": "test_file",
                "content": "这是一个测试文件\n第二行内容",
                "file_type": "txt",
                "location": "desktop"
            }
        },
        {
            "name": "📖 读取测试文件",
            "function": "read_file",
            "parameters": {"file_path": "桌面上的test_file.txt"}
        },
        {
            "name": "✏️ 追加内容到文件",
            "function": "write_file",
            "parameters": {
                "file_path": "test_file.txt",
                "content": "\n追加的新内容",
                "mode": "append"
            }
        },
        {
            "name": "📁 创建测试文件夹",
            "function": "create_directory",
            "parameters": {
                "folder_name": "test_folder",
                "location": "desktop"
            }
        },
        {
            "name": "🔍 搜索txt文件",
            "function": "search_files",
            "parameters": {
                "pattern": "*.txt",
                "search_path": "C:\\Users\\Jason\\Desktop"
            }
        },
        {
            "name": "📋 获取文件信息",
            "function": "get_file_info", 
            "parameters": {"file_path": "test_file.txt"}
        },
        {
            "name": "📦 移动文件到文件夹",
            "function": "move_file",
            "parameters": {
                "file_name": "test_file.txt",
                "source_location": "desktop", 
                "destination_location": "desktop/test_folder"
            }
        },
        {
            "name": "🏷️ 重命名文件",
            "function": "rename_file",
            "parameters": {
                "old_name": "test_file.txt",
                "new_name": "renamed_test.txt",
                "location": "desktop/test_folder"
            }
        },
        {
            "name": "📂 查看文件夹内容",
            "function": "list_directory", 
            "parameters": {"path": "C:\\Users\\Jason\\Desktop\\test_folder"}
        }
    ]
    
    # 执行测试用例
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print("-" * 40)
        
        try:
            result = await fs_tool.execute_function(
                test_case["function"],
                test_case["parameters"]
            )
            
            print(f"状态: {result.get('status', 'unknown')}")
            
            if result.get("status") == "success":
                # 根据不同功能显示相应信息
                if test_case["function"] == "list_directory":
                    directories = result.get("directories", [])
                    files = result.get("files", [])
                    print(f"目录数量: {len(directories)}")
                    print(f"文件数量: {len(files)}")
                    
                    if directories:
                        print("📁 文件夹:")
                        for d in directories[:5]:  # 只显示前5个
                            print(f"  - {d}")
                        if len(directories) > 5:
                            print(f"  ... 还有 {len(directories) - 5} 个文件夹")
                    
                    if files:
                        print("📄 文件:")
                        for f in files[:5]:  # 只显示前5个
                            print(f"  - {f}")
                        if len(files) > 5:
                            print(f"  ... 还有 {len(files) - 5} 个文件")
                
                elif test_case["function"] == "read_file":
                    content = result.get("content", "")
                    size = result.get("size", 0)
                    print(f"文件大小: {size} 字符")
                    print(f"文件内容:\n{content}")
                
                elif test_case["function"] == "write_file":
                    print(f"写入模式: {result.get('mode', 'unknown')}")
                    print(f"内容长度: {result.get('content_length', 0)} 字符")
                
                elif test_case["function"] == "create_file":
                    print(f"创建文件: {result.get('file_path', 'unknown')}")
                
                elif test_case["function"] == "create_directory":
                    print(f"创建文件夹: {result.get('folder_path', 'unknown')}")
                
                elif test_case["function"] == "move_file":
                    print(f"源路径: {result.get('source_path', 'unknown')}")
                    print(f"目标路径: {result.get('destination_path', 'unknown')}")
                
                elif test_case["function"] == "rename_file":
                    print(f"原名称: {result.get('old_name', 'unknown')}")
                    print(f"新名称: {result.get('new_name', 'unknown')}")
                
                elif test_case["function"] == "search_files":
                    results = result.get("results", [])
                    print(f"找到 {len(results)} 个匹配项")
                    for r in results[:3]:  # 只显示前3个结果
                        print(f"  - {r}")
                
                elif test_case["function"] == "get_file_info":
                    info = result.get("info", {})
                    for key, value in info.items():
                        print(f"{key}: {value}")
                
            else:
                print(f"❌ 错误: {result.get('message', '未知错误')}")
                
        except Exception as e:
            print(f"❌ 异常: {str(e)}")
    
    print("\n" + "=" * 60)
    print("🎉 文件系统工具测试完成!")

def test_path_parsing():
    """测试智能路径解析功能"""
    print("\n🔍 测试智能路径解析功能")
    print("-" * 40)
    
    fs_tool = FilesystemTool()
    
    test_paths = [
        "桌面上的test.txt",
        "桌面/文件夹1",
        "desktop\\document.pdf", 
        "名为项目的文件夹",
        "文件夹 新建项目",
        "C:\\Users\\Jason\\Desktop\\existing_file.txt",
        "simple_file.txt"
    ]
    
    for path in test_paths:
        parsed = fs_tool._parse_path(path)
        print(f"'{path}' -> '{parsed}'")

async def main():
    """主函数"""
    try:
        # 测试路径解析
        test_path_parsing()
        
        # 测试文件系统操作
        await test_filesystem_operations()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 