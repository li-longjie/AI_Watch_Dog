from fastapi import FastAPI, WebSocket
from typing import List, Optional
import uvicorn
from pydantic import BaseModel
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
import jieba  # 添加中文分词
import httpx
from config import APIConfig, VideoConfig, ServerConfig  # 导入API配置
from llm_service import LLMService  # 添加导入
from video_processor import VideoProcessor
import asyncio
import json
from fastapi.middleware.cors import CORSMiddleware
import datetime  # 导入 datetime 模块
import logging  # 添加日志记录

app = FastAPI()

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 使用多语言嵌入模型
embeddings = HuggingFaceEmbeddings(
    model_name="Alibaba-NLP/gte-multilingual-base",
    model_kwargs={'device': 'cpu', 'trust_remote_code': True},
    encode_kwargs={'normalize_embeddings': True}
)

# 初始化向量存储
vector_store = Chroma(embedding_function=embeddings, persist_directory="./chroma_db")

# 定义停用词
STOP_WORDS = {"监控", "显示", "在", "了", "吗", "什么", "的", "：", "，", "。", "年", "月", "日"}

def preprocess_text(text: str) -> set:
    """预处理文本，进行分词并移除停用词"""
    # 使用结巴分词
    words = jieba.cut(text)
    # 过滤停用词
    return {word for word in words if word not in STOP_WORDS and len(word.strip()) > 0}

class TextInput(BaseModel):
    docs: List[str]
    table_name: str
    event_timestamps: Optional[List[str]] = None # 添加可选的事件时间戳列表

class SearchRequest(BaseModel):
    query: str
    k: int = 3

@app.post("/add_text/")
async def add_text(request: TextInput): # 使用更新后的 TextInput 模型
    try:
        texts = request.docs
        metadatas = []
        
        # 检查是否提供了 event_timestamps 并且长度匹配
        timestamps_provided = request.event_timestamps and len(request.event_timestamps) == len(texts)
        
        for i, text in enumerate(texts):
            metadata = {"source": request.table_name}
            if timestamps_provided:
                try:
                    # 尝试解析时间戳以验证格式，并存储 YYYY-MM-DD HH:MM:SS 格式
                    # 这里假设传入的时间戳已经是 'YYYY-MM-DD HH:MM:SS' 格式
                    # 如果格式不确定，需要更复杂的解析逻辑
                    dt_obj = datetime.datetime.strptime(request.event_timestamps[i], '%Y-%m-%d %H:%M:%S')
                    metadata["event_timestamp"] = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # 如果格式不匹配或无效，则不添加时间戳元数据
                    logging.warning(f"Invalid timestamp format received: {request.event_timestamps[i]}. Skipping timestamp metadata.")
                    pass 
            metadatas.append(metadata)
            # 添加日志：记录准备添加到该文档的元数据
            logging.info(f"Preparing metadata for doc '{text[:20]}...': {metadata}") 
        
        # 添加到向量存储
        if texts and metadatas:
            vector_store.add_texts(texts, metadatas=metadatas)
            return {
                "status": "success",
                "message": f"Added {len(texts)} documents"
            }
        else:
             return {
                "status": "error",
                "message": "No valid documents or metadata to add."
            }
            
    except Exception as e:
        logging.error(f"Error in add_text: {e}") # 添加日志记录
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/search/")
async def search(request: SearchRequest):
    try:
        query = request.query
        k = request.k
        # filters = None # 不再使用 Chroma 的 filter 功能进行日期过滤
        apply_today_filter = False # 标记是否需要应用"今天"的过滤

        # 检查查询是否包含 "今天"
        if "今天" in query:
            apply_today_filter = True
            today_str = datetime.datetime.now().strftime('%Y-%m-%d')
            # 当需要日期过滤时，获取更多的结果以供后续筛选
            search_k = k * 5 # 或者一个合理的固定值，比如 20
            logging.info(f"Detected 'today' in query. Will retrieve {search_k} docs for post-filtering.")
        else:
            search_k = k

        # 提取可能的时间查询词 (保留，用于后续提示词构建)
        time_keywords = ["几点", "什么时候", "时间", "多久", "持续"]
        time_query = any(keyword in query for keyword in time_keywords)
        
        # 从向量数据库搜索文档 (不使用 filter 进行日期过滤)
        docs_with_scores = vector_store.similarity_search_with_score(query, k=search_k)
        # 添加日志：记录初始检索到的文档数量和元数据概览
        logging.info(f"Initial search found {len(docs_with_scores)} documents.")
        if docs_with_scores:
             logging.info(f"First doc metadata preview: {docs_with_scores[0][0].metadata if docs_with_scores else 'N/A'}")

        # 在 Python 端进行"今天"的日期过滤
        filtered_docs = []
        if apply_today_filter:
            count = 0
            for doc, score in docs_with_scores:
                if count >= k: # 只保留最多 k 个结果
                    break
                # 检查元数据中是否有 event_timestamp 且以今天日期开头
                timestamp_meta = doc.metadata.get("event_timestamp")
                # 添加日志，查看实际比较的字符串
                logging.info(f"Comparing for filter: Metadata timestamp='{timestamp_meta}' (type: {type(timestamp_meta)}), Today string='{today_str}'")
                if timestamp_meta and isinstance(timestamp_meta, str) and timestamp_meta.startswith(today_str):
                    filtered_docs.append((doc, score))
                    count += 1
            logging.info(f"Post-filtering for 'today' resulted in {len(filtered_docs)} documents.")
        else:
            # 如果不过滤，直接取前 k 个
            filtered_docs = docs_with_scores[:k]

        # 处理没有找到文档的情况
        if not filtered_docs:
            if apply_today_filter:
                 answer = f'抱歉，根据今天的监控记录，没有找到与"{query}"相关的信息。'
            else:
                 answer = f'抱歉，没有找到与"{query}"相关的监控记录。'
            return {
                "status": "success",
                "answer": answer,
                "contexts": []
            }

        # 构建提示词
        contexts = [doc.page_content for doc, score in filtered_docs]
        
        # 如果是时间相关查询，增加时间理解提示
        if time_query:
            prompt = f"""基于以下监控记录回答关于时间的问题：

监控记录：
{' '.join(contexts)}

问题：{query}

请注意提取记录中的具体时间信息，精确回答用户的时间问题。如记录中无相关信息，请明确说明。回答要简洁有效。"""
        else:
            prompt = f"""基于以下监控记录回答问题：

监控记录：
{' '.join(contexts)}

问题：{query}

请根据监控记录准确回答问题，回答问题时要简洁有效，只保留关键信息。如果记录中没有相关信息，请明确说明。"""

        # 调用大模型生成回答
        answer = await LLMService.get_response(prompt)

        # 检查 LLM 返回的是否是错误信息
        if answer.startswith("生成回答错误:") or answer.startswith("网络请求错误:") or "API 调用失败" in answer or "API 响应格式错误" in answer:
            logging.error(f"LLMService 返回错误: {answer}")
            # 将错误信息直接返回给前端，或者返回一个通用的错误提示
            return {
                "status": "error", 
                "message": answer # 或者 "抱歉，处理您的请求时发生内部错误。"
            }

        return {
            "status": "success",
            "answer": answer,
            "contexts": [
                {
                    "text": doc.page_content,
                    "score": float(score)
                }
                # 使用 filtered_docs 循环
                for doc, score in filtered_docs 
            ]
        }

    except Exception as e:
        logging.error(f"Error in search: {e}") # 添加日志记录
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/delete/")
async def delete(table_name: str):
    try:
        vector_store.delete(filter={"source": table_name})
        return {"status": "success", "message": f"Deleted documents from {table_name}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 添加 WebSocket 支持
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # 假设 VideoProcessor 或其流产生带有时间戳的记录
    # video_processor = VideoProcessor() # 实例化可能不应在此处进行
    
    try:
        # 这里的实现需要调整，以获取带有时间戳的记录
        # 假设我们从某个地方获取 record = {'content': '...', 'timestamp': 'YYYY-MM-DD HH:MM:SS'}
        # 以下为示例逻辑，具体取决于 process_video_stream 的实现
        # async for record in video_processor.process_video_stream(VideoConfig.VIDEO_SOURCE):
        #     # 添加记录到向量存储，并传递时间戳
        #     await add_text(TextInput(
        #         docs=[record['content']],
        #         table_name=f"stream_{record['timestamp']}", # table_name 可以简化
        #         event_timestamps=[record['timestamp']] # 传递时间戳
        #     ))
            
        #     # 发送更新到客户端
        #     await websocket.send_json({
        #         "type": "update",
        #         "content": record['content'],
        #         "timestamp": record['timestamp']
        #     })
        # 模拟等待消息
        while True:
            message = await websocket.receive_text() # 简单示例，实际可能不需要接收
            logging.info(f"Received message on /ws: {message}") # 日志记录
            await asyncio.sleep(1) 

    except WebSocketDisconnect:
         logging.info("WebSocket /ws disconnected.")
    except Exception as e:
        logging.error(f"Error in /ws endpoint: {e}")
        # await websocket.send_json({ # 避免在异常处理中再次发送
        #     "type": "error",
        #     "message": str(e)
        # })
    finally:
        # 关闭连接的逻辑
        # await websocket.close() # FastAPI 会自动处理
        logging.info("Closing /ws WebSocket connection.")
        pass # 确保 finally 块存在

@app.post("/summary/")
async def get_summaries(request: SearchRequest):
    try:
        # 特别搜索带有"总结"字样的文档
        modified_query = f"监控总结 {request.query}"
        docs = vector_store.similarity_search_with_score(modified_query, k=request.k, 
                                                       filter={"source": {"$regex": "summary_.*"}})
        
        if not docs:
            return {
                "status": "success",
                "answer": "抱歉，没有找到相关时间段的监控总结。",
                "contexts": []
            }

        # 直接返回总结内容
        summaries = [doc[0].page_content for doc in docs]
        
        return {
            "status": "success",
            "answer": "\n\n".join(summaries),
            "contexts": [
                {
                    "text": doc[0].page_content,
                    "score": float(doc[1])
                }
                for doc in docs
            ]
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8085) 