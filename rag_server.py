from fastapi import FastAPI, WebSocket
from typing import List, Optional, Dict, Any
import uvicorn
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
import jieba  # 添加中文分词
import httpx
from config import APIConfig, VideoConfig, ServerConfig  # 导入API配置
from llm_service import LLMService, chat_completion  # 修改导入
from video_processor import VideoProcessor
import asyncio
import json
from fastapi.middleware.cors import CORSMiddleware
import datetime  # 导入 datetime 模块
import logging  # 添加日志记录
import re
import requests
import os

app = FastAPI()

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入双数据库支持
from video_database import video_db

# 使用多语言嵌入模型
embeddings = HuggingFaceEmbeddings(
    model_name="Alibaba-NLP/gte-multilingual-base",
    model_kwargs={'device': 'cpu', 'trust_remote_code': True},
    encode_kwargs={'normalize_embeddings': True}
)

# 初始化向量存储 (保持兼容性，主要用于视频活动检索)
vector_store = Chroma(embedding_function=embeddings, persist_directory="./video_chroma_db")

# 初始化视频活动向量管理器
from langchain_community.vectorstores import Chroma
class VideoVectorManager:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name="video_activities",
            embedding_function=embeddings,
            persist_directory="./video_chroma_db"
        )
    
    async def add_activity(self, activity_id, activity_data):
        """添加活动到向量数据库"""
        try:
            # 构建文档内容
            content = activity_data.get('content', '')
            activity_type = activity_data.get('activity_type', '')
            start_time = activity_data.get('start_time', '')
            
            document_text = f"活动类型: {activity_type} 活动描述: {content} 时间: {start_time}"
            
            # 构建元数据
            metadata = {
                "activity_id": activity_id,
                "activity_type": activity_type,
                "start_time": start_time,
                "source_type": activity_data.get('source_type', 'video_analysis')
            }
            
            # 添加到向量数据库
            self.vector_store.add_texts(
                texts=[document_text],
                metadatas=[metadata],
                ids=[f"video_activity_{activity_id}"]
            )
            return True
        except Exception as e:
            logging.error(f"添加活动到向量数据库失败: {e}")
            return False
    
    def search_activities(self, query, k=10, time_filter=None):
        """搜索活动"""
        try:
            # 先进行无过滤的搜索，然后在Python端进行时间过滤
            docs_with_scores = self.vector_store.similarity_search_with_score(query, k=k*2)
            
            # 如果有时间过滤条件，在Python端进行过滤
            if time_filter and "start_time" in time_filter:
                filtered_results = []
                start_time_filter = time_filter["start_time"]
                min_time = start_time_filter.get("$gte")
                max_time = start_time_filter.get("$lte")
                
                for doc, score in docs_with_scores:
                    # 从元数据中获取活动的开始时间
                    activity_id = doc.metadata.get('activity_id')
                    if activity_id:
                        # 这里需要从数据库查询实际的时间信息
                        # 因为向量数据库的元数据可能不包含完整的时间信息
                        try:
                            from video_database import video_db
                            activity = video_db.get_activity_by_id(activity_id)
                            if activity:
                                activity_start = activity.get('start_time', '')
                                if min_time and max_time:
                                    if min_time <= activity_start <= max_time:
                                        filtered_results.append((doc, score))
                                        if len(filtered_results) >= k:
                                            break
                        except Exception as e:
                            logging.warning(f"时间过滤时查询活动失败: {e}")
                            continue
                
                return filtered_results[:k]
            
            return docs_with_scores[:k]
        except Exception as e:
            logging.error(f"向量搜索失败: {e}")
            return []

# 全局向量管理器
video_vector_manager = VideoVectorManager()

# 定义停用词
STOP_WORDS = {"监控", "显示", "在", "了", "吗", "什么", "的", "：", "，", "。", "年", "月", "日"}

# 硅基流动API配置
SILICONFLOW_API_KEY = "sk-xugvbuiyayzzfeoelfytnfioimnwvzouawxlavixynzuloui"
SILICONFLOW_MODEL = "deepseek-ai/DeepSeek-V3"

# 修改监控关键词集合
MONITORING_KEYWORDS = {
    "监控", "摄像头", "发现", "检测到", "看到", "观察到", "显示", "记录", 
    "camera", "detected", "视频", "画面", "拍到", "出现", "动作", "行为",
    "活动", "状态", "情况","什么时候"
}

def preprocess_text(text: str) -> set:
    """预处理文本，进行分词并移除停用词"""
    # 使用结巴分词
    words = jieba.cut(text)
    # 过滤停用词
    return {word for word in words if word not in STOP_WORDS and len(word.strip()) > 0}

class TextInput(BaseModel):
    docs: List[str]
    collection_name: str # 指定要添加到的集合
    metadatas: Optional[List[dict]] = None

class ActivityInput(BaseModel):
    activity_id: int
    activity_data: dict

class SearchRequest(BaseModel):
    query: str
    k: int = 3
    collection_name: str # 指定从哪个集合搜索

class ChatRequest(BaseModel):
    query: str

class WebpageRequest(BaseModel):
    url: str
    
class FilesystemRequest(BaseModel):
    path: str = "C:\\Users\\Jason\\Desktop"  # 默认桌面路径

# 在app初始化后添加MCPO服务配置
MCPO_BASE_URL = "http://127.0.0.1:8000"  # MCPO服务地址
MCPO_FETCH_URL = f"{MCPO_BASE_URL}/fetch/fetch"
MCPO_TIME_URL = f"{MCPO_BASE_URL}/time/get_current_time"  # 修改为正确的时间端点
MCPO_FILESYSTEM_URL = f"{MCPO_BASE_URL}/filesystem/list_directory"
# 添加browser-use服务配置
MCPO_BROWSER_AGENT_URL = f"{MCPO_BASE_URL}/browser-use/run_browser_agent"
MCPO_DEEP_SEARCH_URL = f"{MCPO_BASE_URL}/browser-use/run_deep_search"

# 添加新的请求模型
class ListDocsRequest(BaseModel):
    table_name: Optional[str] = None
    limit: Optional[int] = 100
    offset: Optional[int] = 0

# 添加browser-use的请求模型
class BrowserAgentRequest(BaseModel):
    task: str
    add_infos: Optional[str] = None

class DeepSearchRequest(BaseModel):
    research_task: str
    max_query_per_iteration: Optional[int] = 3
    max_search_iterations: Optional[int] = 10

def batch_iterator(data: list, batch_size: int):
    """一个简单的迭代器，用于将列表分批。"""
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]

@app.post("/add_activity/")
async def add_activity(request: ActivityInput):
    """
    [新] 接收视频活动数据并将其添加到专用的向量数据库集合中。
    这是给 multi_modal_analyzer 调用的中心化接口。
    """
    if video_vector_manager.vector_store is None:
        return {"status": "error", "message": "视频活动向量数据库未初始化"}

    try:
        activity_id = request.activity_id
        activity_data = request.activity_data
        
        # 构建文档和元数据 (逻辑从 multi_modal_analyzer 迁移并优化)
        content = activity_data.get('content', '')
        activity_type = activity_data.get('activity_type', '')
        start_time_str = activity_data.get('start_time', '')

        # 时间格式化
        try:
            time_obj = datetime.datetime.fromisoformat(start_time_str.replace(' ', 'T'))
            natural_time = time_obj.strftime('%Y年%m月%d日 %H时%M分')
            time_period = "早上" if 6 <= time_obj.hour < 12 else "下午" if 12 <= time_obj.hour < 18 else "晚上"
        except (ValueError, TypeError):
            natural_time = start_time_str
            time_period = "未知时段"

        document_text = f"在{natural_time}({time_period})，检测到活动: {activity_type}。具体描述: {content}"
        
        metadata = {
            "activity_id": activity_id,
            "activity_type": activity_type,
            "start_time": start_time_str,
            "source_type": activity_data.get('source_type', 'video_analysis')
        }
        
        # 添加到向量数据库
        video_vector_manager.vector_store.add_texts(
            texts=[document_text],
            metadatas=[metadata],
            ids=[f"video_activity_{activity_id}"]
        )
        
        logging.info(f"活动已通过API添加到向量数据库: ID={activity_id}")
        return {"status": "success", "message": f"Activity {activity_id} added."}
    except Exception as e:
        logging.error(f"通过API添加活动到向量数据库失败: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.post("/add_text/")
async def add_text(request: TextInput):
    """
    [重构] 向指定的文本集合中批量添加文档。
    """
    if video_vector_manager.vector_store is None:
        return {"status": "error", "message": "视频活动向量数据库未初始化"}

    try:
        texts_to_add = request.docs
        metadatas_to_add = request.metadatas or [{}] * len(texts_to_add)

        if not texts_to_add:
            return {"status": "error", "message": "没有提供任何文档"}
        
        total_added = 0
        # 使用分批处理来增加稳定性
        for text_batch, metadata_batch in zip(
            batch_iterator(texts_to_add, 100), 
            batch_iterator(metadatas_to_add, 100)
        ):
            video_vector_manager.vector_store.add_texts(texts=text_batch, metadatas=metadata_batch)
            total_added += len(text_batch)

        return {
            "status": "success",
            "message": f"成功向集合 '{request.collection_name}' 添加了 {total_added} 个文档"
        }
    except Exception as e:
        logging.error(f"添加文本时出错: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.post("/search/")
async def search(request: SearchRequest):
    """
    [重构] 从指定的集合中搜索文档。
    """
    target_store = video_vector_manager.vector_store if request.collection_name == "video_activities" else video_vector_manager.vector_store
    
    if target_store is None:
        return {"status": "error", "message": f"集合 '{request.collection_name}' 对应的向量数据库未初始化"}

    try:
        query = request.query
        k = request.k
        
        # 简化版：直接使用LLM进行问答，上下文来自向量搜索
        docs_with_scores = target_store.similarity_search_with_score(query, k=k)
        
        if not docs_with_scores:
            return {"status": "success", "answer": f"抱歉，在 '{request.collection_name}' 集合中没有找到与您问题相关的信息。", "contexts": []}

        contexts = [doc.page_content for doc, score in docs_with_scores]
        
        # [修复] 注入当前时间以解决相对时间查询问题
        current_time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        prompt = f"""现在是 {current_time_str}。请基于以下背景信息，简洁、直接地回答用户问题。

背景信息:
- {'- '.join(contexts)}

用户问题: {query}

回答要求:
1. 直接回答问题，不要解释你的推理过程。
2. 如果信息不足以回答，就直接说 "根据现有信息无法回答"。
3. 如果问题涉及时间计算（比如"几分钟前"），请根据当前时间进行计算后给出结果。
"""
        
        answer = await LLMService.get_response(prompt)
        
        return {
            "status": "success",
            "answer": answer,
            "contexts": [{"text": doc.page_content, "score": float(score)} for doc, score in docs_with_scores]
        }
    except Exception as e:
        logging.error(f"搜索时出错: {e}", exc_info=True)
        # 增加对特定数据库错误的捕获
        if "Error finding id" in str(e):
            return {"status": "error", "message": "数据库查询失败，索引可能已损坏。请尝试重启服务以自动修复。"}
        return {"status": "error", "message": str(e)}

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

def extract_urls(text):
    """从文本中提取URL"""
    url_pattern = re.compile(r'(https?://[^\s"\'，。？！；：（）、<>\u4e00-\u9fff]+)')
    urls = url_pattern.findall(text)
    cleaned_urls = [re.sub(r'[\u4e00-\u9fff].*$', '', url) for url in urls if re.sub(r'[\u4e00-\u9fff].*$', '', url)]
    return cleaned_urls

@app.post("/extract_webpage/")
async def extract_webpage(request: WebpageRequest):
    try:
        # 确保URL格式正确
        if not request.url.startswith('http'):
            url = 'https://' + request.url
        else:
            url = request.url
            
        # 请求MCPO Fetch服务
        response = requests.post(
            MCPO_FETCH_URL,
            json={"url": url, "max_length": 8000},
            timeout=30
        )
        
        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"无法获取网页内容: HTTP {response.status_code}"
            }
            
        # 获取网页内容
        web_content = response.json()
        
        # 构建提示词
        prompt = f"以下是从URL '{url}' 获取的网页内容。请分析并总结这个网页的主要内容。\n\n"
        
        if isinstance(web_content, list) and len(web_content) > 0:
            content_text = web_content[0]
        elif isinstance(web_content, dict):
            content_text = web_content.get("content", str(web_content))
        else:
            content_text = str(web_content)
            
        prompt += content_text
        
        # 调用LLM生成回答
        summary = await LLMService.get_response(prompt)
        
        return {
            "status": "success",
            "answer": summary,
            "url": url
        }
    except Exception as e:
        logging.error(f"提取网页内容错误: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/get_time/")
async def get_time():
    try:
        # 请求MCPO Time服务
        response = requests.post(
            MCPO_TIME_URL,
            json={"timezone": "Asia/Shanghai"},
            timeout=10
        )
        
        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"无法获取时间信息: HTTP {response.status_code}"
            }
            
        # 获取时间信息
        time_info = response.json()
        
        # 准备提示词给大模型，包含原始时间数据
        prompt = f"以下是从时间服务获取的数据: {json.dumps(time_info, ensure_ascii=False)}\n\n"
        prompt += "请以自然友好的方式向用户展示当前的日期和时间信息。"
       
        
        # 调用大模型生成回答
        time_response = await LLMService.get_response(prompt)
        
        return {
            "status": "success",
            "answer": time_response,
            "raw_time_data": time_info  # 可选：保留原始数据供前端使用
        }
    except Exception as e:
        logging.error(f"获取时间信息错误: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/list_files/")
async def list_files(request: FilesystemRequest):
    try:
        # 请求MCPO Filesystem服务
        response = requests.post(
            MCPO_FILESYSTEM_URL,
            json={"path": request.path},
            timeout=10
        )
        
        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"无法获取文件列表: HTTP {response.status_code}"
            }
            
        # 获取文件列表
        file_list = response.json()
        
        if isinstance(file_list, dict) and "error" in file_list:
            return {
                "status": "error",
                "message": file_list["error"]
            }
            
        # 构建提示词
        filesystem_prompt = f"用户请求查看目录 '{request.path}' 中的文件和文件夹。\n\n"
        filesystem_prompt += f"以下是从文件系统获取的原始列表:\n{json.dumps(file_list, ensure_ascii=False)}\n\n"
        filesystem_prompt += "请以友好、有条理的方式向用户展示这些文件和文件夹。可以对内容进行分类（如分为文件夹和文件两类，或按文件类型分类），并简洁说明文件总数。"
        
        # 调用LLM生成回答
        files_summary = await LLMService.get_response(filesystem_prompt)
        
        return {
            "status": "success",
            "answer": files_summary,
            "raw_files": file_list  # 可选：保留原始数据供前端使用
        }
    except Exception as e:
        logging.error(f"获取文件列表错误: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/detect_intent/")
async def detect_intent(request: ChatRequest):
    """[待重构] 检测用户查询意图并调用相应服务"""
    query = request.query
    
    try:
        # 1. 检查是否是视频活动相关问题 (现在应调用新的搜索)
        activity_keywords = ["睡觉", "玩手机", "喝水", "吃东西", "工作", "学习", "活动", "行为"]
        if any(keyword in query for keyword in activity_keywords):
            logging.info("意图检测: 视频活动查询")
            # 调用新的搜索函数，并指定正确的集合
            search_req = SearchRequest(query=query, k=5, collection_name="video_activities")
            return await search(search_req)

        # 2. 检查是否是监控相关问题 (搜索文本摘要集合)
        monitoring_keywords = ["监控", "总结", "摄像头", "发现", "看到", "记录"]
        if any(keyword in query for keyword in monitoring_keywords):
            logging.info("意图检测: 监控摘要查询")
            search_req = SearchRequest(query=query, k=3, collection_name="text_summaries")
            return await search(search_req)

        # ... (保留其他意图检测逻辑：浏览器、搜索、URL、时间、文件等) ...
        # [示例]
        time_keywords = ["时间", "几点", "日期"]
        if any(keyword in query.lower() for keyword in time_keywords):
            # (此部分逻辑保持不变)
            pass

        # 默认使用LLM直接回答
        logging.info("意图检测: 通用问答")
        prompt = f"用户问题: {query}\n\n请以友好的方式回答用户的问题。"
        model_response = await chat_completion(prompt)
        
        return {"status": "success", "answer": model_response}

    except Exception as e:
        logging.error(f"意图检测或处理过程出错: {e}", exc_info=True)
        return {"status": "error", "message": f"处理您的请求时出错: {str(e)}"}

@app.post("/list_docs/")
async def list_docs(request: ListDocsRequest):
    """列出向量数据库中的文档"""
    try:
        # 构建过滤条件
        filter_dict = {}
        if request.table_name:
            filter_dict["source"] = request.table_name
            
        # 获取所有匹配的文档
        results = vector_store.get(
            where=filter_dict if filter_dict else None,
            limit=request.limit,
            offset=request.offset
        )
        
        if not results['ids']:
            return {
                "status": "success",
                "message": "没有找到文档",
                "total": 0,
                "documents": []
            }
            
        # 整理文档信息
        documents = []
        for i in range(len(results['ids'])):
            doc_info = {
                "id": results['ids'][i],
                "content": results['documents'][i],
                "metadata": results['metadatas'][i] if results['metadatas'] else {},
            }
            documents.append(doc_info)
            
        return {
            "status": "success",
            "total": len(documents),
            "documents": documents
        }
        
    except Exception as e:
        logging.error(f"获取文档列表错误: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/run_browser_agent/")
async def run_browser_agent(request: BrowserAgentRequest):
    """调用MCP browser-use服务执行浏览器任务"""
    try:
        # 准备请求参数
        request_data = {
            "task": request.task
        }
        
        if request.add_infos:
            request_data["add_infos"] = request.add_infos
            
        # 发送请求到MCP browser-use服务，增加超时时间并使用异步请求
        logging.info(f"调用browser-agent执行任务: {request.task}")
        
        # 创建异步HTTP客户端
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                response = await client.post(
                    MCPO_BROWSER_AGENT_URL,
                    json=request_data
                )
                
                if response.status_code != 200:
                    logging.error(f"调用browser-agent失败: {response.status_code}")
                    return {
                        "status": "success",  # 仍返回success以避免前端显示错误
                        "answer": f"我尝试执行浏览器任务'{request.task}'，但服务返回了错误。可能是网络问题或任务复杂度超出了能力范围。您可以尝试简化任务或稍后再试。",
                    }
                
                # 获取结果
                result = response.json()
                
                # 将结果通过大模型处理
                prompt = f"以下是我通过浏览器执行任务 '{request.task}' 的结果:\n\n"
                if isinstance(result, list) and len(result) > 0:
                    prompt += f"{result[0]}\n\n"
                else:
                    prompt += f"{result}\n\n"
                prompt += "请以友好且有条理的方式总结这些结果，保留关键信息，并向用户展示最重要的发现。"
                
                # 调用大模型生成回答
                browser_response = await LLMService.get_response(prompt)
                
                return {
                    "status": "success",
                    "answer": browser_response,
                    "raw_result": result
                }
            except httpx.TimeoutException:
                logging.error(f"调用browser-agent超时，任务可能仍在执行")
                return {
                    "status": "success",  # 返回success避免前端错误
                    "answer": f"我开始执行浏览器任务'{request.task}'，但任务执行时间超过了等待时间。这可能是因为网页加载缓慢或任务较复杂。您可以尝试简化任务或指定具体网址。"
                }
    except Exception as e:
        logging.error(f"调用browser-agent时出错: {e}")
        return {
            "status": "success",  # 更改为success以避免前端显示错误
            "answer": f"我尝试执行浏览器任务'{request.task}'，但遇到了一些问题: {str(e)}。请稍后再试或尝试不同的任务。"
        }

async def search_video_activities(query: str):
    """智能搜索视频活动 (双数据库检索)"""
    try:
        import re
        from datetime import datetime, timedelta
        
        # 时间解析
        time_info = None
        now = datetime.now()
        
        if "昨天" in query or "昨日" in query:
            yesterday = now - timedelta(days=1)
            time_info = {
                'start_time': yesterday.strftime('%Y-%m-%d 00:00:00'),
                'end_time': yesterday.strftime('%Y-%m-%d 23:59:59'),
                'date': yesterday.strftime('%Y-%m-%d')
            }
            logging.info(f"检测到'昨天'查询，时间范围: {time_info['start_time']} - {time_info['end_time']}")
        elif "今天" in query or "今日" in query or "当天" in query:
            time_info = {
                'start_time': now.strftime('%Y-%m-%d 00:00:00'),
                'end_time': now.strftime('%Y-%m-%d 23:59:59'),
                'date': now.strftime('%Y-%m-%d')
            }
            logging.info(f"检测到'今天'查询，时间范围: {time_info['start_time']} - {time_info['end_time']}")
        elif "前天" in query:
            day_before_yesterday = now - timedelta(days=2)
            time_info = {
                'start_time': day_before_yesterday.strftime('%Y-%m-%d 00:00:00'),
                'end_time': day_before_yesterday.strftime('%Y-%m-%d 23:59:59'),
                'date': day_before_yesterday.strftime('%Y-%m-%d')
            }
            logging.info(f"检测到'前天'查询，时间范围: {time_info['start_time']} - {time_info['end_time']}")
        elif "这周" in query or "本周" in query:
            # 获取本周的开始和结束时间
            weekday = now.weekday()  # 0=Monday, 6=Sunday
            week_start = now - timedelta(days=weekday)
            week_end = week_start + timedelta(days=6)
            time_info = {
                'start_time': week_start.strftime('%Y-%m-%d 00:00:00'),
                'end_time': week_end.strftime('%Y-%m-%d 23:59:59'),
                'date': week_start.strftime('%Y-%m-%d')
            }
            logging.info(f"检测到'本周'查询，时间范围: {time_info['start_time']} - {time_info['end_time']}")
        
        # 活动类型检测
        activity_type = None
        activity_mapping = {
            "睡觉": "睡觉", "休息": "睡觉", "睡眠": "睡觉",
            "玩手机": "玩手机", "看手机": "玩手机", "手机": "玩手机",
            "喝水": "喝水", "饮水": "喝水",
            "喝饮料": "喝饮料", "饮料": "喝饮料",
            "吃东西": "吃东西", "吃饭": "吃东西", "用餐": "吃东西",
            "工作": "专注工作学习", "学习": "专注工作学习", "专注": "专注工作学习"
        }
        
        for keyword, mapped_type in activity_mapping.items():
            if keyword in query:
                activity_type = mapped_type
                break
        
        # 判断查询类型
        is_duration_query = any(pattern in query for pattern in ["多长时间", "多久", "时长", "持续"])
        is_stats_query = any(pattern in query for pattern in ["总共", "一共", "平均", "最多", "最少", "次数"])
        
        # 使用SQLite进行结构化查询
        if time_info or activity_type:
            activities = []
            
            if time_info and activity_type:
                # 时间+类型查询
                logging.info(f"执行时间+类型查询: {activity_type}, 时间范围: {time_info['start_time']} - {time_info['end_time']}")
                activities = video_db.get_activities_by_time_range(
                    time_info['start_time'], time_info['end_time'], activity_type
                )
                logging.info(f"结构化查询找到 {len(activities)} 条记录")
            elif time_info:
                # 仅时间查询
                logging.info(f"执行仅时间查询: {time_info['start_time']} - {time_info['end_time']}")
                activities = video_db.get_activities_by_time_range(
                    time_info['start_time'], time_info['end_time']
                )
                logging.info(f"结构化查询找到 {len(activities)} 条记录")
            elif activity_type:
                # 仅类型查询 (最近记录)
                logging.info(f"执行仅类型查询: {activity_type}")
                recent_activities = video_db.get_recent_activities(50)
                activities = [a for a in recent_activities if a['activity_type'] == activity_type][:10]
                logging.info(f"结构化查询找到 {len(activities)} 条记录")
            
            # 生成统计信息
            stats = {}
            if time_info and (is_duration_query or is_stats_query):
                stats = video_db.get_activity_statistics(time_info['date'], activity_type)
            
            # 如果结构化查询结果不够，补充语义搜索
            if len(activities) < 3:
                try:
                    # 构建时间过滤条件用于向量搜索
                    vector_time_filter = None
                    if time_info:
                        vector_time_filter = {
                            "start_time": {"$gte": time_info['start_time'], "$lte": time_info['end_time']}
                        }
                    
                    vector_results = video_vector_manager.search_activities(query, k=5, time_filter=vector_time_filter)
                    for doc, score in vector_results:
                        activity_id = doc.metadata.get('activity_id')
                        if activity_id:
                            activity = video_db.get_activity_by_id(activity_id)
                            if activity and activity not in activities:
                                # 额外验证时间范围（双重保险）
                                if time_info:
                                    activity_start = activity.get('start_time', '')
                                    if not (time_info['start_time'] <= activity_start <= time_info['end_time']):
                                        continue
                                activities.append(activity)
                except Exception as e:
                    logging.warning(f"语义搜索补充失败: {e}")
        
        else:
            # 纯语义搜索
            activities = []
            try:
                # 检查是否有隐含的时间限制（比如"最近"、"近期"等）
                implicit_time_filter = None
                recent_keywords = ["最近", "近期", "刚才", "刚刚", "现在"]
                if any(keyword in query for keyword in recent_keywords):
                    # 限制为最近24小时
                    recent_start = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
                    recent_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    implicit_time_filter = {
                        "start_time": {"$gte": recent_start, "$lte": recent_end}
                    }
                
                vector_results = video_vector_manager.search_activities(query, k=8, time_filter=implicit_time_filter)
                for doc, score in vector_results:
                    activity_id = doc.metadata.get('activity_id')
                    if activity_id:
                        activity = video_db.get_activity_by_id(activity_id)
                        if activity:
                            # 如果有隐含时间过滤，额外验证
                            if implicit_time_filter:
                                activity_start = activity.get('start_time', '')
                                recent_start = implicit_time_filter["start_time"]["$gte"]
                                recent_end = implicit_time_filter["start_time"]["$lte"]
                                if not (recent_start <= activity_start <= recent_end):
                                    continue
                            activities.append(activity)
            except Exception as e:
                logging.error(f"语义搜索失败: {e}")
                return None
        
        # 生成回答
        if activities:
            # 构建上下文
            context_parts = []
            
            # 添加统计信息
            if stats:
                context_parts.append("=== 统计信息 ===")
                for act_type, stat in stats.items():
                    context_parts.append(
                        f"{act_type}: {stat['event_count']}次, "
                        f"总时长{stat['total_duration']:.1f}分钟"
                    )
            
            # 添加活动记录
            context_parts.append("\n=== 相关活动记录 ===")
            for i, activity in enumerate(activities[:6]):
                duration = activity.get('duration_minutes', 0)
                context_parts.append(
                    f"{i+1}. [{activity['start_time']}] {activity['activity_type']}: "
                    f"{activity['content']} (持续{duration:.1f}分钟)"
                )
            
            context = "\n".join(context_parts)
            
            # 使用优化的活动检索提示词
            from prompt import prompt_activity_search
            prompt = prompt_activity_search.format(
                context=context,
                query=query
            )
            
            # 调用LLM生成回答
            answer = await chat_completion(prompt)
            
            return {
                "status": "success",
                "answer": answer,
                "activities_found": len(activities),
                "query_type": "video_activity_search",
                "search_method": "双数据库混合检索"
            }
        else:
            return {
                "status": "success", 
                "answer": f"抱歉，没有找到与'{query}'相关的视频活动记录。",
                "query_type": "video_activity_search"
            }
    
    except Exception as e:
        logging.error(f"视频活动搜索失败: {e}")
        return None


@app.post("/run_deep_search/")
async def run_deep_search(request: DeepSearchRequest):
    """调用MCP browser-use服务执行深度搜索任务"""
    try:
        # 准备请求参数
        request_data = {
            "research_task": request.research_task
        }
        
        if request.max_query_per_iteration:
            request_data["max_query_per_iteration"] = request.max_query_per_iteration
            
        if request.max_search_iterations:
            request_data["max_search_iterations"] = request.max_search_iterations
            
        # 发送请求到MCP browser-use服务，使用异步HTTP客户端
        logging.info(f"调用deep-search执行研究任务: {request.research_task}")
        
        # 创建异步HTTP客户端
        async with httpx.AsyncClient(timeout=360.0) as client:
            try:
                response = await client.post(
                    MCPO_DEEP_SEARCH_URL,
                    json=request_data
                )
                
                if response.status_code != 200:
                    logging.error(f"调用deep-search失败: {response.status_code}")
                    return {
                        "status": "success",
                        "answer": f"我尝试执行深度搜索任务'{request.research_task}'，但服务返回了错误。可能是网络问题或查询过于复杂。您可以尝试简化研究主题或提供更具体的问题。"
                    }
                
                # 获取结果
                result = response.json()
                
                # 将结果通过大模型处理
                prompt = f"以下是我对 '{request.research_task}' 进行深度搜索的结果:\n\n"
                if isinstance(result, list) and len(result) > 0:
                    prompt += f"{result[0]}\n\n"
                else:
                    prompt += f"{result}\n\n"
                prompt += "请以友好且专业的方式总结这些研究结果，保留重要信息，并向用户展示最关键的发现和见解。"
                
                # 调用大模型生成回答
                search_response = await LLMService.get_response(prompt)
                
                return {
                    "status": "success",
                    "answer": search_response,
                    "raw_result": result
                }
            except httpx.TimeoutException:
                logging.error(f"调用deep-search超时，任务可能仍在执行")
                return {
                    "status": "success",
                    "answer": f"我开始执行深度搜索任务'{request.research_task}'，但由于任务复杂度或网络原因，搜索时间超过了等待时间。深度搜索通常需要更长时间，您可以尝试使用更具体的问题或稍后再试。"
                }
    except Exception as e:
        logging.error(f"调用deep-search时出错: {e}")
        return {
            "status": "success",
            "answer": f"我尝试进行深度搜索'{request.research_task}'，但遇到了一些问题: {str(e)}。请稍后再试或尝试不同的研究主题。"
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8085) 