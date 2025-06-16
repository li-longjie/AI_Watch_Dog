# 统一检索系统 - 集成视频监控与桌面活动

## 系统概述

本系统将视频监控RAG检索和桌面活动检索整合为一个统一的自然语言查询接口，支持：

- 🎥 **视频监控查询**: 基于监控记录的智能检索
- 💻 **桌面活动查询**: 基于屏幕截图和应用使用的检索  
- 🔍 **综合查询**: 同时查询两个系统并智能合并结果
- 📊 **活动总结**: 生成指定时间范围的综合活动报告

## 架构设计

```
📱 用户查询
    ↓
🧠 统一检索接口 (unified_retriever.py)
    ↓
🔍 意图识别
    ↓
📊 智能路由
    ├── 视频监控系统 (rag_server.py)
    ├── 桌面活动系统 (activity_retriever.py)  
    └── 综合查询 (并行+LLM合并)
    ↓
💬 统一响应格式
```

## 文件结构

```
项目根目录/
├── unified_retriever.py          # 统一检索核心
├── rag_server.py                 # 视频监控RAG服务 (已修改)
├── activity_retriever.py         # 桌面活动检索
├── usage_example.py              # 使用示例和测试
├── README_unified_system.md      # 本文档
├── chroma_db/                    # 视频监控向量数据库
├── chroma_db_activity/           # 桌面活动向量数据库
└── screen_recordings/            # 桌面活动原始数据
    └── activity_log.db          # SQLite数据库
```

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install fastapi uvicorn
pip install langchain-community chromadb 
pip install dateparser aiohttp
pip install requests

# 确保嵌入模型可用
pip install sentence-transformers
```

### 2. 启动服务

```bash
# 启动主服务器
python rag_server.py

# 或使用uvicorn
uvicorn rag_server:app --host 0.0.0.0 --port 8085
```

### 3. 测试系统

```bash
# 运行测试示例
python usage_example.py
```

## API接口

### 统一查询接口

**POST** `/unified_query/`

```json
{
    "query": "我昨天下午用了什么软件？"
}
```

**响应:**
```json
{
    "status": "success",
    "answer": "根据记录，您昨天下午主要使用了...",
    "query_type": "desktop_only",
    "source": "desktop_system"
}
```

### 每日总结接口

**POST** `/daily_summary/`

```json
{}
```

**响应:**
```json
{
    "status": "success", 
    "summary": "今天您的主要活动包括...",
    "time_range": "2024-01-15 00:00 至 2024-01-15 23:59"
}
```

## 查询类型识别

系统会自动识别查询意图并路由到相应系统：

### 桌面活动关键词
- `桌面`, `屏幕`, `软件`, `应用`, `程序`, `窗口`
- `浏览器`, `网页`, `Chrome`, `VSCode`
- `打开`, `使用`, `操作`, `点击`

### 视频监控关键词  
- `监控`, `摄像头`, `发现`, `检测到`
- `视频`, `画面`, `拍到`, `录像`
- `安防`, `异常`, `活动`

### 综合查询模式
- 包含两类关键词: `"我用软件时监控到了什么？"`
- 总结性查询: `"昨天都做了什么？"`
- 明确要求: `"全部活动"`, `"综合情况"`

## 数据存储设计

### 视频监控数据 (rag_server.py)
- **存储**: ChromaDB (`chroma_db/`)
- **格式**: 监控文本记录 + 时间戳元数据
- **特点**: 支持"今天"等时间过滤

### 桌面活动数据 (activity_retriever.py)  
- **存储**: SQLite + ChromaDB (`chroma_db_activity/`)
- **格式**: OCR文本 + 应用元数据 + 精确时间戳
- **特点**: 支持复杂时间解析 ("昨天下午", "过去5分钟")

### 为什么不合并数据库？

1. **数据特性不同**: 监控记录vs屏幕活动有不同的元数据结构
2. **时间处理不同**: 两种系统的时间过滤策略差异较大
3. **扩展性**: 独立数据库便于单独维护和优化
4. **可靠性**: 一个系统故障不影响另一个系统

## 使用示例

### Python代码调用

```python
import asyncio
from unified_retriever import unified_query, get_daily_summary

async def example():
    # 单个查询
    result = await unified_query("我昨天用了什么软件？")
    print(f"查询类型: {result['query_type']}")
    print(f"回答: {result['answer']}")
    
    # 每日总结
    summary = await get_daily_summary("今天")
    print(f"总结: {summary['summary']}")

asyncio.run(example())
```

### HTTP API调用

```bash
# 统一查询
curl -X POST http://localhost:8085/unified_query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "我今天做了什么？"}'

# 每日总结  
curl -X POST http://localhost:8085/daily_summary/
```

## 性能优化

### 并行查询
- 综合查询时并行调用两个系统
- 异步处理避免阻塞
- 异常隔离确保系统可用性

### 缓存策略 (可选扩展)
```python
# 可以为频繁查询添加缓存
from functools import lru_cache

@lru_cache(maxsize=128)
def cached_query(query_hash):
    # 缓存查询结果
    pass
```

### 负载均衡 (生产环境)
```bash
# 使用nginx进行负载均衡
upstream unified_retriever {
    server 127.0.0.1:8085;
    server 127.0.0.1:8086;
}
```

## 故障处理

### 系统降级
- 如果统一检索器不可用，自动回退到原有的 `detect_intent` 逻辑
- 单个系统故障时，仍可提供另一个系统的服务

### 错误监控
```python
# 添加详细的日志记录
import logging
logging.basicConfig(level=logging.INFO)

# 监控关键指标
- 查询响应时间
- 系统可用性
- 错误率统计
```

## 扩展功能

### 1. 添加新的数据源
```python
class UnifiedRetriever:
    def _query_new_system(self, query: str):
        # 添加新的检索系统
        pass
```

### 2. 改进意图识别
```python
# 使用机器学习模型进行意图分类
from sklearn.naive_bayes import MultinomialNB

def ml_intent_detection(query: str):
    # 更精确的意图识别
    pass
```

### 3. 结果后处理
```python
def enhance_results(raw_results: dict):
    # 添加结果增强、去重、排序等
    pass
```

## 监控和维护

### 日志监控
```bash
# 查看服务日志
tail -f rag_server.log

# 检查错误
grep "ERROR" rag_server.log
```

### 数据库维护
```bash
# 清理过期数据 (可选)
# ChromaDB会自动管理存储

# 备份SQLite数据库
cp screen_recordings/activity_log.db backup/
```

### 性能监控
```python
# 添加性能指标收集
import time
from collections import defaultdict

query_metrics = defaultdict(list)

def track_performance(query_type, response_time):
    query_metrics[query_type].append(response_time)
```

## 常见问题

### Q: 统一检索器初始化失败？
A: 检查依赖模块是否正确安装，确保 `activity_retriever.py` 和相关数据库文件存在。

### Q: 查询结果不准确？
A: 检查意图识别逻辑，可能需要调整关键词或增加新的识别规则。

### Q: 性能较慢？  
A: 考虑减少检索的文档数量(k值)，或增加缓存机制。

### Q: 数据库错误？
A: 检查ChromaDB和SQLite文件权限，确保向量数据库初始化正常。

## 总结

这个统一检索系统成功将两个独立的检索系统整合为一个智能的查询接口，既保持了各自系统的优势，又提供了更好的用户体验。通过智能意图识别和并行查询，用户可以用自然语言同时检索视频监控和桌面活动数据。 