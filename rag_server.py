from fastapi import FastAPI, WebSocket
from typing import List
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

app = FastAPI()

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
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

class SearchRequest(BaseModel):
    query: str
    k: int = 3

@app.post("/add_text/")
async def add_text(request: dict):
    try:
        texts = request["docs"]
        metadatas = [{"source": request["table_name"]} for _ in texts]
        
        # 添加到向量存储
        vector_store.add_texts(texts, metadatas=metadatas)
        vector_store.persist()
        
        return {
            "status": "success",
            "message": f"Added {len(texts)} documents"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/search/")
async def search(request: SearchRequest):
    try:
        # 搜索相关文档
        docs = vector_store.similarity_search_with_score(request.query, k=request.k)
        
        if not docs:
            return {
                "status": "success",
                "answer": "抱歉，没有找到相关的监控记录。",
                "contexts": []
            }

        # 构建提示词
        contexts = [doc[0].page_content for doc in docs]
        scores = [doc[1] for doc in docs]
        
        prompt = f"""基于以下监控记录回答问题：

监控记录：
{' '.join(contexts)}

问题：{request.query}

请根据监控记录准确回答问题，回答问题时要简洁有效，只保留关键信息。如果记录中没有相关信息，请明确说明。"""

        # 调用大模型生成回答
        answer = await LLMService.get_response(prompt)

        return {
            "status": "success",
            "answer": answer,
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
    video_processor = VideoProcessor()
    
    try:
        # 处理视频流
        async for record in video_processor.process_video_stream(VideoConfig.VIDEO_SOURCE):
            # 添加记录到向量存储
            await add_text(TextInput(
                docs=[record['content']],
                table_name=f"stream_{record['timestamp']}"
            ))
            
            # 发送更新到客户端
            await websocket.send_json({
                "type": "update",
                "content": record['content'],
                "timestamp": record['timestamp']
            })
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8085) 