from fastapi import FastAPI, WebSocket
from typing import List, Optional, Dict, Any
import uvicorn
from pydantic import BaseModel
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
import jieba  # 添加中文分词
import httpx
from config import APIConfig, VideoConfig, ServerConfig  # 导入API配置
from llm_service import LLMService, query_siliconflow_model  # 修改导入
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
    table_name: str
    event_timestamps: Optional[List[str]] = None # 添加可选的事件时间戳列表

class SearchRequest(BaseModel):
    query: str
    k: int = 3

class ChatRequest(BaseModel):
    query: str

class WebpageRequest(BaseModel):
    url: str
    


# 在app初始化后添加MCPO服务配置
MCPO_BASE_URL = "http://127.0.0.1:8000"  # MCPO服务地址
MCPO_FETCH_URL = f"{MCPO_BASE_URL}/fetch/fetch"
MCPO_TIME_URL = f"{MCPO_BASE_URL}/time/get_current_time"  # 修改为正确的时间端点

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

请注意提取记录中的具体时间信息，精确回答用户的时间问题，同时回答要更亲切拟人自然。如记录中无相关信息，请明确说明。回答要简洁有效。"""
        else:
            prompt = f"""基于以下监控记录回答问题：

监控记录：
{' '.join(contexts)}

问题：{query}

请根据监控记录准确回答问题，回答问题时要简洁有效但是要更亲切拟人自然，只保留关键信息。如果记录中没有相关信息，请明确说明。"""

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

def extract_urls(text):
    """从文本中提取URL"""
    # 修改正则表达式，匹配URL直到空格、引号或中文字符
    url_pattern = re.compile(r'(https?://[^\s"\'，。？！；：（）、<>\u4e00-\u9fff]+)')
    urls = url_pattern.findall(text)
    
    # 清理URL，移除可能附加的非URL字符
    cleaned_urls = []
    for url in urls:
        # 确保URL中不包含中文字符
        valid_url = re.sub(r'[\u4e00-\u9fff].*$', '', url)
        if valid_url:
            cleaned_urls.append(valid_url)
    
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



@app.post("/detect_intent/")
async def detect_intent(request: ChatRequest):
    """检测用户查询意图并调用相应服务"""
    query = request.query
    
    try:
        # 1. 优先检查是否是监控相关问题 (RAG搜索)
        if any(keyword in query for keyword in MONITORING_KEYWORDS):
            # 直接使用现有的search函数进行RAG搜索
            search_result = await search(SearchRequest(query=query, k=3))
            if search_result.get("status") == "success":
                return search_result
            else:
                raise Exception("RAG搜索失败")
                
        # 2. 检查是否含有URL (MCP网页提取服务) - 优先处理
        urls = extract_urls(query)
        if urls:
            # 调用网页提取服务
            webpage_request = WebpageRequest(url=urls[0])
            return await extract_webpage(webpage_request)
        
        # 3. 检查是否是搜索相关请求 (包括图片搜索、资料搜索等)
        search_keywords = [
            "搜索", "查找", "联网搜索", "网上搜索", "搜一下", "查一查", 
            "图片", "照片", "图像", "picture", "image", "photo",
            "资料", "信息", "新闻", "最新", "了解", "查询",
            "search", "find", "lookup", "google", "百度"
        ]
        if any(keyword in query.lower() for keyword in search_keywords):
            try:
                logging.info(f"检测到搜索请求，调用DuckDuckGo: {query}")
                
                # 可以先返回一个"正在搜索"的状态
                # 或者直接进行搜索（当前做法）
                result = await call_duckduckgo_search_api(query)
                return {
                    "status": "success",
                    "answer": result
                }
            except Exception as e:
                logging.error(f"调用DuckDuckGo搜索功能失败: {e}")
                return {
                    "status": "success",
                    "answer": f"我尝试为您搜索'{query}'，但遇到了技术问题。请稍后再试，或尝试使用更具体的搜索关键词。"
                }
        
        # 4. 检查是否是逻辑推理请求
        reasoning_keywords = [
            "分析", "推理", "思考", "解决", "计算", "求解", "逐步",
            "reasoning", "analyze", "solve", "calculate", "step by step",
            "为什么", "怎么样", "如何", "原理", "机制", "逻辑"
        ]
        if any(keyword in query.lower() for keyword in reasoning_keywords):
            try:
                logging.info(f"检测到推理请求，调用Sequential Thinking: {query}")
                result = await call_sequential_thinking_api(query)
                return {
                    "status": "success",
                    "answer": result
                }
            except Exception as e:
                logging.error(f"调用Sequential Thinking功能失败: {e}")
                return {
                    "status": "success",
                    "answer": f"我尝试进行逻辑推理'{query}'，但遇到了技术问题。请稍后再试，或尝试简化问题。"
                }
        
        # 5. 检查是否是地图相关请求
        map_keywords = [
            "地图", "导航", "路线", "地址", "位置", "附近", "天气",
            "从", "到", "怎么去", "如何到达", "交通", "距离",
            "map", "navigation", "route", "location", "address", "nearby"
        ]
        if any(keyword in query.lower() for keyword in map_keywords):
            try:
                logging.info(f"检测到地图请求，调用百度地图: {query}")
                result = await call_baidu_map_api(query)
                return {
                    "status": "success",
                    "answer": result
                }
            except Exception as e:
                logging.error(f"调用百度地图功能失败: {e}")
                return {
                    "status": "success",
                    "answer": f"我尝试处理地图查询'{query}'，但遇到了技术问题。请稍后再试，或提供更具体的地址信息。"
                }
            
        # 6. 检查是否是浏览器任务请求（只有明确的交互式浏览任务才调用browser-agent）
        browser_keywords = ["浏览", "打开网站", "访问网站", "browse", "visit", "打开浏览器"]
        if any(keyword in query.lower() for keyword in browser_keywords):
            try:
                # 调用browser-agent服务
                logging.info(f"检测到浏览器任务请求: {query}")
                browser_request = BrowserAgentRequest(task=query, add_infos=None)
                return await run_browser_agent(browser_request)
            except Exception as e:
                logging.error(f"处理浏览器任务时出错: {e}")
                # 返回友好的错误消息
                return {
                    "status": "success",
                    "answer": f"我尝试执行浏览器任务'{query}'，但遇到了技术问题。请稍后再试，或者使用更明确的指令。"
                }
        
        # 7. 检查是否是深度搜索请求
        deep_search_keywords = ["深度搜索", "研究", "调研", "deep search", "research"]
        if any(keyword in query.lower() for keyword in deep_search_keywords):
            try:
                # 调用deep-search服务
                logging.info(f"检测到深度搜索请求: {query}")
                search_request = DeepSearchRequest(research_task=query)
                return await run_deep_search(search_request)
            except Exception as e:
                logging.error(f"处理深度搜索请求时出错: {e}")
                # 返回友好的错误消息
                return {
                    "status": "success",
                    "answer": f"我尝试执行深度搜索任务'{query}'，但遇到了技术问题。请稍后再试，或者尝试使用更具体的研究主题。"
                }
            
        # 8. 检查是否是时间查询 (MCP时间服务)
        time_keywords = ["时间", "几点", "日期", "today", "time", "date", "clock", "现在"]
        if any(keyword in query.lower() for keyword in time_keywords):
            return await get_time()
            
        # 9. 检查是否是文件系统查询 (调用app.py服务)
        filesystem_keywords = ["文件", "目录", "桌面", "文件夹", "Desktop", "desktop", "files", "folders", "桌面上", "文件列表", "查看文件", "创建文件", "删除文件", "重命名", "移动文件"]
        if any(keyword in query for keyword in filesystem_keywords):
            # 调用app.py的统一聊天API
            try:
                logging.info(f"检测到文件系统查询，转发到app.py: {query}")
                result = await call_app_py_api(query)
                return {
                    "status": "success",
                    "answer": result
                }
            except Exception as e:
                logging.error(f"调用app.py文件系统功能失败: {e}")
                return {
                    "status": "success",
                    "answer": f"我尝试处理文件操作请求'{query}'，但遇到了技术问题。请确保所有服务正常运行，或稍后再试。"
                }

        
        # 10. 如果不属于以上类型，视为日常交流，直接调用大模型回答
        prompt = f"用户问题: {query}\n\n请以友好的方式回答用户的问题。"
        model_response = await query_siliconflow_model(prompt)
        
        return {
            "status": "success",
            "answer": model_response
        }
        
    except Exception as e:
        logging.error(f"意图检测或处理过程出错: {e}")
        return {
            "status": "error",
            "message": f"处理您的请求时出错: {str(e)}"
        }

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

async def call_app_py_api(query: str) -> str:
    """调用app.py的统一聊天API处理文件系统请求"""
    try:
        app_py_url = "http://127.0.0.1:8086/api/unified-chat"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                app_py_url,
                json={"message": query},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("answer", "处理完成，但未收到有效回答")
            else:
                logging.error(f"app.py API返回错误: {response.status_code} - {response.text}")
                return f"文件系统服务暂时不可用，请稍后重试。"
                
    except Exception as e:
        logging.error(f"调用app.py API异常: {e}")
        return f"连接文件系统服务时出错: {str(e)}"

async def call_specialized_services(query: str, service_type: str) -> str:
    """调用专门的服务处理特定类型的请求"""
    try:
        app_py_url = "http://127.0.0.1:8086/api/unified-chat"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            # 根据服务类型构建请求消息
            if service_type == "duckduckgo_search":
                # 对于搜索请求，确保包含搜索关键词
                message = f"搜索: {query}"
            elif service_type == "sequential_thinking":
                # 对于逻辑推理请求，确保包含推理关键词
                message = f"分析推理: {query}"
            elif service_type == "baidu_map":
                # 对于地图请求，确保包含地图关键词
                message = f"地图查询: {query}"
            else:
                # 默认直接使用原始查询
                message = query
            
            logging.info(f"调用{service_type}服务处理: {message}")
            
            response = await client.post(
                app_py_url,
                json={"message": message},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get("answer", "处理完成，但未收到有效回答")
                
                # 记录成功调用
                logging.info(f"{service_type}服务调用成功，返回内容长度: {len(answer)}")
                return answer
            else:
                error_msg = f"{service_type}服务返回错误: {response.status_code}"
                logging.error(f"{error_msg} - {response.text}")
                
                # 根据不同服务类型返回友好的错误信息
                if service_type == "duckduckgo_search":
                    return f"抱歉，搜索服务暂时不可用。您可以稍后重试，或尝试使用更具体的搜索关键词。"
                elif service_type == "sequential_thinking":
                    return f"抱歉，逻辑推理服务暂时不可用。您可以稍后重试，或尝试简化问题。"
                elif service_type == "baidu_map":
                    return f"抱歉，地图服务暂时不可用。您可以稍后重试，或提供更具体的地址信息。"
                else:
                    return f"抱歉，{service_type}服务暂时不可用，请稍后重试。"
                
    except httpx.TimeoutException:
        timeout_msg = f"{service_type}服务请求超时"
        logging.error(timeout_msg)
        
        if service_type == "duckduckgo_search":
            return f"搜索请求处理时间较长，可能是网络问题。请稍后重试或使用更简单的搜索词。"
        elif service_type == "sequential_thinking":
            return f"逻辑推理任务较复杂，处理时间超时。请尝试简化问题或稍后重试。"
        elif service_type == "baidu_map":
            return f"地图查询超时，可能是网络问题。请稍后重试或检查地址格式。"
        else:
            return f"{service_type}服务处理超时，请稍后重试。"
    
    except Exception as e:
        error_msg = f"调用{service_type}服务异常: {str(e)}"
        logging.error(error_msg)
        
        if service_type == "duckduckgo_search":
            return f"搜索功能遇到技术问题: {str(e)}。请稍后重试。"
        elif service_type == "sequential_thinking":
            return f"逻辑推理功能遇到技术问题: {str(e)}。请稍后重试。"
        elif service_type == "baidu_map":
            return f"地图功能遇到技术问题: {str(e)}。请稍后重试。"
        else:
            return f"连接{service_type}服务时出错: {str(e)}"

async def call_duckduckgo_search_api(query: str) -> str:
    """调用app.py的DuckDuckGo搜索功能"""
    try:
        app_py_url = "http://127.0.0.1:8086/api/unified-chat"
        
        # 增加超时时间到150秒
        async with httpx.AsyncClient(timeout=150.0) as client:
            # 构建搜索请求消息，确保触发搜索意图
            search_message = f"搜索: {query}"
            
            logging.info(f"开始搜索请求: {search_message}")
            
            response = await client.post(
                app_py_url,
                json={"message": search_message},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get("answer", "搜索完成，但未收到有效结果")
                logging.info(f"搜索完成，返回内容长度: {len(answer)}")
                return answer
            else:
                logging.error(f"搜索服务API返回错误: {response.status_code} - {response.text}")
                return f"搜索服务暂时不可用，请稍后重试。"
                
    except httpx.TimeoutException:
        logging.error(f"搜索请求超时: {query}")
        return f"搜索'{query}'的时间较长，请稍后重试或使用更具体的关键词。"
    except Exception as e:
        logging.error(f"调用搜索服务API异常: {e}")
        return f"连接搜索服务时出错: {str(e)}"

async def call_sequential_thinking_api(query: str) -> str:
    """调用app.py的Sequential Thinking逻辑推理功能"""
    try:
        app_py_url = "http://127.0.0.1:8086/api/unified-chat"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            # 构建推理请求消息，确保触发推理意图
            thinking_message = f"逐步分析推理: {query}"
            
            response = await client.post(
                app_py_url,
                json={"message": thinking_message},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("answer", "推理完成，但未收到有效回答")
            else:
                logging.error(f"推理服务API返回错误: {response.status_code} - {response.text}")
                return f"逻辑推理服务暂时不可用，请稍后重试。"
                
    except Exception as e:
        logging.error(f"调用推理服务API异常: {e}")
        return f"连接逻辑推理服务时出错: {str(e)}"

async def call_baidu_map_api(query: str) -> str:
    """调用app.py的百度地图功能"""
    try:
        app_py_url = "http://127.0.0.1:8086/api/unified-chat"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 构建地图请求消息，确保触发地图意图
            map_message = f"地图查询: {query}"
            
            response = await client.post(
                app_py_url,
                json={"message": map_message},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("answer", "地图查询完成，但未收到有效结果")
            else:
                logging.error(f"地图服务API返回错误: {response.status_code} - {response.text}")
                return f"地图服务暂时不可用，请稍后重试。"
                
    except Exception as e:
        logging.error(f"调用地图服务API异常: {e}")
        return f"连接地图服务时出错: {str(e)}"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8085) 