import os
import json
import glob
from datetime import datetime
from collections import defaultdict

def analyze_test_results(results_dir="test_results"):
    """分析测试结果"""
    
    # 查找所有结果文件
    result_files = glob.glob(os.path.join(results_dir, "result_*.json"))
    
    if not result_files:
        print(f"❌ 在 {results_dir} 目录中未找到测试结果文件")
        return
    
    print(f"📊 分析 {len(result_files)} 个测试结果文件\n")
    
    # 统计数据
    stats = {
        "total_tests": 0,
        "successful_extractions": 0,
        "empty_extractions": 0,
        "total_text_length": 0,
        "response_types": defaultdict(int),
        "avg_response_size": 0,
        "timestamps": []
    }
    
    results_data = []
    
    # 读取所有结果
    for file_path in sorted(result_files):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                results_data.append(data)
                
                # 更新统计
                stats["total_tests"] += 1
                stats["timestamps"].append(data.get("timestamp", ""))
                
                extracted_text = data.get("extracted_text", "")
                if extracted_text:
                    stats["successful_extractions"] += 1
                    stats["total_text_length"] += len(extracted_text)
                else:
                    stats["empty_extractions"] += 1
                
                # 统计响应类型
                response_type = data.get("raw_data_type", "unknown")
                stats["response_types"][response_type] += 1
                
                # 统计响应大小
                response_size = data.get("raw_data_size", 0)
                stats["avg_response_size"] += response_size
                
        except Exception as e:
            print(f"⚠️ 读取文件失败 {file_path}: {e}")
    
    # 计算平均值
    if stats["total_tests"] > 0:
        stats["avg_response_size"] = stats["avg_response_size"] / stats["total_tests"]
        stats["avg_text_length"] = stats["total_text_length"] / stats["successful_extractions"] if stats["successful_extractions"] > 0 else 0
    
    # 打印统计结果
    print("📈 测试统计结果")
    print("=" * 50)
    print(f"总测试次数: {stats['total_tests']}")
    print(f"成功提取文本: {stats['successful_extractions']} ({stats['successful_extractions']/stats['total_tests']*100:.1f}%)")
    print(f"空文本提取: {stats['empty_extractions']} ({stats['empty_extractions']/stats['total_tests']*100:.1f}%)")
    print(f"总文本长度: {stats['total_text_length']:,} 字符")
    print(f"平均文本长度: {stats['avg_text_length']:.1f} 字符")
    print(f"平均响应大小: {stats['avg_response_size']:.1f} 字符")
    
    print(f"\n📋 响应类型分布:")
    for resp_type, count in stats["response_types"].items():
        percentage = count / stats["total_tests"] * 100
        print(f"  {resp_type}: {count} 次 ({percentage:.1f}%)")
    
    # 显示时间范围
    if stats["timestamps"]:
        first_test = min(stats["timestamps"])
        last_test = max(stats["timestamps"])
        print(f"\n⏰ 测试时间范围:")
        print(f"  开始: {first_test}")
        print(f"  结束: {last_test}")
    
    # 显示最近几次结果
    print(f"\n📝 最近 5 次测试结果:")
    print("-" * 80)
    for i, data in enumerate(results_data[-5:], 1):
        timestamp = data.get("timestamp", "unknown")
        extracted_text = data.get("extracted_text", "")
        text_preview = extracted_text[:50] + "..." if len(extracted_text) > 50 else extracted_text
        
        print(f"{i}. [{timestamp}]")
        print(f"   文本长度: {len(extracted_text)} 字符")
        if extracted_text:
            print(f"   预览: {text_preview}")
        else:
            print(f"   预览: (无文本内容)")
        print()

def show_detailed_result(results_dir="test_results", result_index=-1):
    """显示详细的测试结果"""
    
    result_files = sorted(glob.glob(os.path.join(results_dir, "result_*.json")))
    
    if not result_files:
        print(f"❌ 在 {results_dir} 目录中未找到测试结果文件")
        return
    
    if result_index < 0:
        result_index = len(result_files) + result_index  # 支持负索引
    
    if result_index < 0 or result_index >= len(result_files):
        print(f"❌ 无效的索引 {result_index}，有效范围: 0-{len(result_files)-1}")
        return
    
    file_path = result_files[result_index]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📄 详细结果 (文件: {os.path.basename(file_path)})")
        print("=" * 60)
        print(f"时间戳: {data.get('timestamp', 'unknown')}")
        print(f"截图文件: {data.get('image_path', 'unknown')}")
        print(f"原始数据类型: {data.get('raw_data_type', 'unknown')}")
        print(f"原始数据大小: {data.get('raw_data_size', 0):,} 字符")
        print(f"提取文本长度: {data.get('extracted_text_length', 0):,} 字符")
        
        print(f"\n📋 原始API响应数据:")
        print("-" * 40)
        raw_data = data.get('raw_data')
        if isinstance(raw_data, list) and raw_data:
            print(f"列表格式，包含 {len(raw_data)} 个元素:")
            for i, item in enumerate(raw_data[:3]):  # 只显示前3个
                print(f"  元素 {i+1}: {json.dumps(item, ensure_ascii=False, indent=4)[:200]}...")
            if len(raw_data) > 3:
                print(f"  ... 还有 {len(raw_data)-3} 个元素")
        elif isinstance(raw_data, dict):
            print(f"字典格式:")
            print(json.dumps(raw_data, ensure_ascii=False, indent=2)[:500] + "...")
        else:
            print(f"其他格式: {str(raw_data)[:200]}...")
        
        print(f"\n📝 提取的文本内容:")
        print("-" * 40)
        extracted_text = data.get('extracted_text', '')
        if extracted_text:
            print(extracted_text)
        else:
            print("(无文本内容)")
            
    except Exception as e:
        print(f"❌ 读取详细结果失败: {e}")

def main():
    """主函数"""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "detail":
            # 显示详细结果
            index = int(sys.argv[2]) if len(sys.argv) > 2 else -1
            show_detailed_result(result_index=index)
        else:
            print("❌ 未知参数，使用方法:")
            print("  python analyze_test_results.py          # 显示统计分析")
            print("  python analyze_test_results.py detail   # 显示最新结果详情") 
            print("  python analyze_test_results.py detail 0 # 显示第1个结果详情")
    else:
        # 默认显示统计分析
        analyze_test_results()

if __name__ == "__main__":
    main() 