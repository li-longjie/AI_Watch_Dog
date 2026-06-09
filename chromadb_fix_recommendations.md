# ChromaDB损坏问题解决方案

## 问题分析总结

经过深入分析，ChromaDB经常损坏的主要原因包括：

1. **并发访问冲突**：多个服务同时访问同一个ChromaDB实例
2. **缺乏连接管理**：没有适当的连接池或单例模式
3. **不正确的关闭流程**：服务异常退出时没有正确清理
4. **导入时初始化**：模块导入时就创建连接，导致共享问题

## 立即解决方案

### 1. 建立ChromaDB连接管理器

```python
import threading
import atexit
from contextlib import contextmanager

class ChromaDBManager:
    _instance = None
    _lock = threading.Lock()
    _connections = {}

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @contextmanager
    def get_connection(self, db_path, collection_name):
        conn_key = f"{db_path}_{collection_name}"

        with self._lock:
            if conn_key not in self._connections:
                client = chromadb.PersistentClient(path=db_path)
                collection = client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=embedding_function
                )
                self._connections[conn_key] = {
                    'client': client,
                    'collection': collection
                }

        try:
            yield self._connections[conn_key]['collection']
        finally:
            # 这里可以添加连接清理逻辑
            pass

    def cleanup_all(self):
        with self._lock:
            for conn_info in self._connections.values():
                try:
                    # ChromaDB没有显式关闭方法，但我们可以清除引用
                    del conn_info['client']
                    del conn_info['collection']
                except:
                    pass
            self._connections.clear()

# 注册程序退出时的清理函数
def cleanup_chromadb():
    manager = ChromaDBManager()
    manager.cleanup_all()

atexit.register(cleanup_chromadb)
```

### 2. 修改activity_retriever.py

```python
# 移除导入时的初始化，改为懒加载
class ActivityVectorStore:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def get_store(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._init_store()
                    self._initialized = True
        return self._store

    def _init_store(self):
        # 原来的初始化逻辑
        embeddings = HuggingFaceEmbeddings(...)
        self._store = Chroma(
            collection_name=CHROMA_COLLECTION_NAME_ACTIVITY,
            embedding_function=embeddings,
            persist_directory=CHROMA_DB_DIR_ACTIVITY
        )

# 使用方式
def get_activity_vector_store():
    return ActivityVectorStore().get_store()
```

### 3. 添加信号处理和清理机制

```python
import signal
import sys

def signal_handler(sig, frame):
    print("正在安全关闭ChromaDB连接...")
    cleanup_chromadb()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

### 4. 分离不同服务的数据库路径

建议为每个服务使用独立的ChromaDB目录：
- `activity_retriever.py` → `chroma_db_activity`
- `rag_server.py` → `chroma_db_video_v1`
- `rag_server_v2.py` → `chroma_db_video_v2`
- `view_chroma_db.py` → 只读访问模式

### 5. 添加数据库健康检查

```python
def check_chromadb_health(db_path):
    """检查ChromaDB数据库健康状态"""
    try:
        client = chromadb.PersistentClient(path=db_path)
        collections = client.list_collections()
        # 尝试访问第一个集合
        if collections:
            collection = client.get_collection(collections[0].name)
            collection.count()  # 简单的健康检查
        return True
    except Exception as e:
        logging.error(f"ChromaDB健康检查失败: {e}")
        return False
```

### 6. 实现自动修复机制

```python
def auto_repair_chromadb(db_path):
    """自动修复损坏的ChromaDB"""
    if not check_chromadb_health(db_path):
        logging.warning(f"检测到ChromaDB损坏，开始自动修复: {db_path}")

        # 备份损坏的数据库
        backup_path = f"{db_path}_backup_{int(time.time())}"
        if os.path.exists(db_path):
            shutil.move(db_path, backup_path)

        # 重新创建数据库
        logging.info(f"ChromaDB已重置，损坏文件已备份到: {backup_path}")
        return True
    return False
```

## 预防措施

1. **定期备份**：建立定期备份ChromaDB的机制
2. **监控磁盘空间**：确保有足够的磁盘空间
3. **优雅关闭**：确保所有服务都有适当的关闭流程
4. **日志记录**：增加详细的ChromaDB操作日志
5. **健康检查**：定期检查数据库健康状态

## 紧急恢复

如果ChromaDB再次损坏：

1. **立即停止所有相关服务**
2. **运行重置脚本**：`python reset_vector_db.py --force`
3. **检查磁盘空间和权限**
4. **重新启动服务**
5. **监控日志确保正常运行**

## 长期解决方案

考虑迁移到更稳定的向量数据库解决方案：
- Weaviate
- Pinecone
- Qdrant
- 或者使用PostgreSQL + pgvector

这些解决方案通常有更好的并发处理和稳定性。