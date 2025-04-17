import chromadb
from chromadb.config import Settings
import pandas as pd
from tabulate import tabulate
import datetime
import os

class ChromaDBViewer:
    def __init__(self, persist_directory="./chroma_db"):
        # 直接使用ChromaDB客户端
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # 获取默认集合
        try:
            # 先获取所有集合名称
            collection_names = self.client.list_collections()
            if collection_names:
                # 尝试获取第一个集合
                self.collection = self.client.get_collection(name=collection_names[0])
            else:
                print("数据库中没有集合")
                self.collection = None
        except Exception as e:
            print(f"初始化集合时出错: {e}")
            self.collection = None

    def list_collections(self):
        """列出所有集合"""
        try:
            # 获取所有集合名称（字符串列表）
            collection_names = self.client.list_collections()
            if not collection_names:
                print("数据库中没有集合")
                return
            
            print("\n=== 数据库集合列表 ===")
            for idx, name in enumerate(collection_names, 1):
                # 直接用字符串name获取集合对象
                collection = self.client.get_collection(name=name)
                count = collection.count()
                print(f"{idx}. {name} (文档数: {count})")
        except Exception as e:
            print(f"获取集合列表时出错: {e}")

    def view_documents(self, collection_name=None, limit=100, offset=0):
        """查看文档内容"""
        try:
            # 获取指定集合或使用默认集合
            collection = None
            if collection_name:
                try:
                    collection = self.client.get_collection(name=collection_name)
                except:
                    print(f"未找到集合 {collection_name}")
                    return
            elif self.collection:
                collection = self.collection
            else:
                print("没有可用的集合")
                return

            # 获取文档
            results = collection.get(
                limit=limit,
                offset=offset
            )
            
            if not results['ids']:
                print("没有找到文档")
                return
            
            # 将结果转换为DataFrame以便更好地显示
            docs_data = []
            for i in range(len(results['ids'])):
                doc_info = {
                    'ID': results['ids'][i],
                    '内容': results['documents'][i],
                    '元数据': results['metadatas'][i] if results['metadatas'] else 'N/A'
                }
                docs_data.append(doc_info)
            
            df = pd.DataFrame(docs_data)
            
            # 使用tabulate美化输出
            print(f"\n=== 文档列表 (总数: {len(docs_data)}) ===")
            print(tabulate(df, headers='keys', tablefmt='pretty', showindex=True))
        except Exception as e:
            print(f"查看文档时出错: {e}")
            print(f"错误详情: {str(e)}")

    def search_documents(self, query_text, k=5):
        """搜索文档"""
        try:
            if not self.collection:
                print("没有可用的集合")
                return
                
            # 使用ChromaDB的原生搜索
            results = self.collection.query(
                query_texts=[query_text],
                n_results=k
            )
            
            if not results['ids'][0]:
                print("没有找到相关文档")
                return
            
            print(f"\n=== 搜索结果 (查询: {query_text}) ===")
            for i in range(len(results['ids'][0])):
                print(f"\n文档 {i+1}")
                print(f"ID: {results['ids'][0][i]}")
                print(f"内容: {results['documents'][0][i]}")
                print(f"元数据: {results['metadatas'][0][i] if results['metadatas'] else 'N/A'}")
                if 'distances' in results:
                    print(f"相似度距离: {results['distances'][0][i]:.4f}")
                print("-" * 80)
        except Exception as e:
            print(f"搜索文档时出错: {e}")

    def get_statistics(self):
        """获取数据库统计信息"""
        try:
            collection_names = self.client.list_collections()
            total_docs = 0
            
            print("\n=== 数据库统计信息 ===")
            print(f"总集合数: {len(collection_names)}")
            print("\n按集合统计:")
            
            for coll_name in collection_names:
                collection = self.client.get_collection(name=coll_name)
                count = collection.count()
                total_docs += count
                print(f"- {coll_name}: {count} 文档")
                
            print(f"\n总文档数: {total_docs}")
        except Exception as e:
            print(f"获取统计信息时出错: {e}")

def main():
    viewer = ChromaDBViewer()
    
    while True:
        print("\n=== Chroma向量数据库查看器 ===")
        print("1. 查看所有集合")
        print("2. 查看文档内容")
        print("3. 搜索文档")
        print("4. 查看数据库统计")
        print("0. 退出")
        
        try:
            choice = input("\n请选择操作 (0-4): ")
            
            if choice == '0':
                break
            elif choice == '1':
                viewer.list_collections()
            elif choice == '2':
                collection_name = input("请输入集合名称(直接回车使用默认集合): ").strip()
                limit = int(input("请输入显示数量(默认100): ") or "100")
                viewer.view_documents(collection_name if collection_name else None, limit=limit)
            elif choice == '3':
                query = input("请输入搜索关键词: ")
                k = int(input("请输入返回结果数量(默认5): ") or "5")
                viewer.search_documents(query, k)
            elif choice == '4':
                viewer.get_statistics()
            else:
                print("无效的选择，请重试")
        except Exception as e:
            print(f"操作出错: {e}")
            print(f"错误详情: {str(e)}")
            continue

if __name__ == "__main__":
    main() 