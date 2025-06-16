#!/usr/bin/env python3
"""
向量数据库重置工具
用于解决ChromaDB损坏问题，重新索引所有数据
"""

import os
import shutil
import sys
from datetime import datetime

def reset_vector_database():
    """删除所有向量数据库目录"""
    chroma_dirs = ["chroma_db_activity", "chroma_db"]
    deleted_any = False
    
    print("=== 向量数据库重置工具 ===")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    for chroma_dir in chroma_dirs:
        if os.path.exists(chroma_dir):
            try:
                print(f"正在删除: {chroma_dir}")
                shutil.rmtree(chroma_dir)
                print(f"✅ 成功删除: {chroma_dir}")
                deleted_any = True
            except Exception as e:
                print(f"❌ 删除失败 ({chroma_dir}): {e}")
        else:
            print(f"⚠️  目录不存在: {chroma_dir}")
    
    if deleted_any:
        print("\n🔄 向量数据库已重置")
        print("📝 系统下次启动时将重新创建向量数据库并重新索引所有历史数据")
        print("⚠️  注意：重新索引可能需要一些时间，具体取决于历史数据量")
    else:
        print("\n✅ 没有发现需要删除的向量数据库目录")
    
    return deleted_any

def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print("向量数据库重置工具")
        print("用途：解决ChromaDB损坏问题")
        print("使用：python reset_vector_db.py")
        print("     python reset_vector_db.py --force (跳过确认)")
        return
    
    # 检查是否跳过确认
    force_reset = len(sys.argv) > 1 and sys.argv[1] == '--force'
    
    if not force_reset:
        print("⚠️  此操作将删除所有向量数据库文件")
        print("📊 SQLite主数据库不会受到影响")
        print("🔄 系统将在下次启动时重新索引所有数据")
        
        response = input("\n是否继续？(y/N): ").strip().lower()
        if response not in ['y', 'yes', '是']:
            print("❌ 操作已取消")
            return
    
    reset_vector_database()
    
    print("\n=== 重置完成 ===")
    print("💡 现在可以重新启动 screen_capture.py 或 activity_ui.py")

if __name__ == "__main__":
    main() 