from fastapi import FastAPI, WebSocket
from typing import List, Optional, Dict, Any
import uvicorn
from pydantic import BaseModel
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
import jieba
import httpx
from config import APIConfig, VideoConfig, ServerConfig
from llm_service import LLMService, chat_completion
from video_processor import VideoProcessor
import asyncio
import json
from fastapi.middleware.cors import CORSMiddleware
import datetime
import logging
import re
import requests
import os

# 导入新的智能代理
from intelligent_agent import IntelligentAgent

app = FastAPI(title="智能RAG服务器 v2.0", description="集成MCP工具的智能RAG系统")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# 初始化智能代理
intelligent_agent = IntelligentAgent()

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

def preprocess_text(text: str) -> set:
    """预处理文本，进行分词并移除停用词"""
    words = jieba.cut(text)
    return {word for word in words if word not in STOP_WORDS and len(word.strip()) > 0}

# Pydantic模型定义
class TextInput(BaseModel):
    docs: List[str]
    table_name: str
    event_timestamps: Optional[List[str]] = None

class SearchRequest(BaseModel):
    query: str
    k: int = 3

class ChatRequest(BaseModel):
    query: str

class ListDocsRequest(BaseModel):
    table_name: Optional[str] = None
    limit: Optional[int] = 100
    offset: Optional[int] = 0

# 监控关键词集合
MONITORING_KEYWORDS = {
    "监控", "摄像头", "发现", "检测到", "看到", "观察到", "显示", "记录", 
    "camera", "detected", "视频", "画面", "拍到", "出现", "动作", "行为",
    "活动", "状态", "情况", "什么时候"
}

@app.post("/add_text/")
async def add_text(request: TextInput):
    """添加文本到向量数据库"""
    try:
        texts = request.docs
        metadatas = []
        
        timestamps_provided = request.event_timestamps and len(request.event_timestamps) == len(texts)
        
        for i, text in enumerate(texts):
            metadata = {"source": request.table_name}
            if timestamps_provided:
                try:
                    dt_obj = datetime.datetime.strptime(request.event_timestamps[i], '%Y-%m-%d %H:%M:%S')
                    metadata["event_timestamp"] = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    logging.warning(f"Invalid timestamp format received: {request.event_timestamps[i]}. Skipping timestamp metadata.")
                    pass 
            metadatas.append(metadata)
            logging.info(f"Preparing metadata for doc '{text[:20]}...': {metadata}") 
        
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
        logging.error(f"Error in add_text: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/search/")
async def search(request: SearchRequest):
    """原有的RAG搜索功能（保持兼容性）"""
    try:
        query = request.query
        k = request.k
        apply_today_filter = False

        if "今天" in query:
            apply_today_filter = True
            today_str = datetime.datetime.now().strftime('%Y-%m-%d')
            search_k = k * 5
            logging.info(f"Detected 'today' in query. Will retrieve {search_k} docs for post-filtering.")
        else:
            search_k = k

        time_keywords = ["几点", "什么时候", "时间", "多久", "持续"]
        time_query = any(keyword in query for keyword in time_keywords)
        
        docs_with_scores = vector_store.similarity_search_with_score(query, k=search_k)
        logging.info(f"Initial search found {len(docs_with_scores)} documents.")
        if docs_with_scores:
             logging.info(f"First doc metadata preview: {docs_with_scores[0][0].metadata if docs_with_scores else 'N/A'}")

        filtered_docs = []
        if apply_today_filter:
            count = 0
            for doc, score in docs_with_scores:
                if count >= k:
                    break
                timestamp_meta = doc.metadata.get("event_timestamp")
                logging.info(f"Comparing for filter: Metadata timestamp='{timestamp_meta}' (type: {type(timestamp_meta)}), Today string='{today_str}'")
                if timestamp_meta and isinstance(timestamp_meta, str) and timestamp_meta.startswith(today_str):
                    filtered_docs.append((doc, score))
                    count += 1
            logging.info(f"Post-filtering for 'today' resulted in {len(filtered_docs)} documents.")
        else:
            filtered_docs = docs_with_scores[:k]

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

        contexts = [doc.page_content for doc, score in filtered_docs]
        
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

        answer = await LLMService.get_response(prompt)

        if answer.startswith("生成回答错误:") or answer.startswith("网络请求错误:") or "API 调用失败" in answer or "API 响应格式错误" in answer:
            logging.error(f"LLMService 返回错误: {answer}")
            return {
                "status": "error", 
                "message": answer
            }

        return {
            "status": "success",
            "answer": answer,
            "contexts": [
                {
                    "text": doc.page_content,
                    "score": float(score)
                }
                for doc, score in filtered_docs 
            ]
        }

    except Exception as e:
        logging.error(f"Error in search: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/chat/")
async def intelligent_chat(request: ChatRequest):
    """新的智能聊天接口 - 集成MCP工具和RAG"""
    try:
        query = request.query
        
        # 首先检查是否是视频活动相关问题
        activity_keywords = ["睡觉", "玩手机", "喝水", "喝饮料", "吃东西", "专注工作", "学习", "活动", "行为", "多长时间", "持续", "时长"]
        if any(keyword in query for keyword in activity_keywords):
            try:
                result = await search_video_activities(query)
                if result:
                    return result
            except Exception as e:
                logging.error(f"视频活动检索失败: {e}")
        
        # 检查是否是监控相关问题
        if any(keyword in query for keyword in MONITORING_KEYWORDS):
            search_result = await search(SearchRequest(query=query, k=3))
            if search_result.get("status") == "success":
                return search_result
        
        # 使用智能代理处理其他请求
        result = await intelligent_agent.process_user_request(query)
        return result
        
    except Exception as e:
        logging.error(f"智能聊天处理失败: {e}")
        return {
            "status": "error",
            "message": f"处理请求时发生错误: {str(e)}"
        }

async def search_video_activities(query: str):
    """智能搜索视频活动（复用原有逻辑）"""
    try:
        import re
        from datetime import datetime, timedelta
        
        time_info = None
        now = datetime.now()
        
        if "昨天" in query or "昨日" in query:
            yesterday = now - timedelta(days=1)
            time_info = {
                'start_time': yesterday.strftime('%Y-%m-%d 00:00:00'),
                'end_time': yesterday.strftime('%Y-%m-%d 23:59:59'),
                'date': yesterday.strftime('%Y-%m-%d')
            }
        elif "今天" in query or "今日" in query or "当天" in query:
            time_info = {
                'start_time': now.strftime('%Y-%m-%d 00:00:00'),
                'end_time': now.strftime('%Y-%m-%d 23:59:59'),
                'date': now.strftime('%Y-%m-%d')
            }
        elif "前天" in query:
            day_before_yesterday = now - timedelta(days=2)
            time_info = {
                'start_time': day_before_yesterday.strftime('%Y-%m-%d 00:00:00'),
                'end_time': day_before_yesterday.strftime('%Y-%m-%d 23:59:59'),
                'date': day_before_yesterday.strftime('%Y-%m-%d')
            }
        
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
        
        is_duration_query = any(pattern in query for pattern in ["多长时间", "多久", "时长", "持续"])
        is_stats_query = any(pattern in query for pattern in ["总共", "一共", "平均", "最多", "最少", "次数"])
        
        if time_info or activity_type:
            activities = []
            
            if time_info and activity_type:
                activities = video_db.get_activities_by_time_range(
                    time_info['start_time'], time_info['end_time'], activity_type
                )
            elif time_info:
                activities = video_db.get_activities_by_time_range(
                    time_info['start_time'], time_info['end_time']
                )
            elif activity_type:
                recent_activities = video_db.get_recent_activities(50)
                activities = [a for a in recent_activities if a['activity_type'] == activity_type][:10]
            
            stats = {}
            if time_info and (is_duration_query or is_stats_query):
                stats = video_db.get_activity_statistics(time_info['date'], activity_type)
            
            if len(activities) < 3:
                try:
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
                                if time_info:
                                    activity_start = activity.get('start_time', '')
                                    if not (time_info['start_time'] <= activity_start <= time_info['end_time']):
                                        continue
                                activities.append(activity)
                except Exception as e:
                    logging.warning(f"语义搜索补充失败: {e}")
        else:
            activities = []
            try:
                implicit_time_filter = None
                recent_keywords = ["最近", "近期", "刚才", "刚刚", "现在"]
                if any(keyword in query for keyword in recent_keywords):
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
        
        if activities:
            context_parts = []
            
            if stats:
                context_parts.append("=== 统计信息 ===")
                for act_type, stat in stats.items():
                    context_parts.append(
                        f"{act_type}: {stat['event_count']}次, "
                        f"总时长{stat['total_duration']:.1f}分钟"
                    )
            
            context_parts.append("\n=== 相关活动记录 ===")
            for i, activity in enumerate(activities[:6]):
                duration = activity.get('duration_minutes', 0)
                context_parts.append(
                    f"{i+1}. [{activity['start_time']}] {activity['activity_type']}: "
                    f"{activity['content']} (持续{duration:.1f}分钟)"
                )
            
            context = "\n".join(context_parts)
            
            from prompt import prompt_activity_search
            prompt = prompt_activity_search.format(
                context=context,
                query=query
            )
            
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

@app.post("/delete/")
async def delete(table_name: str):
    """删除向量数据库中的文档"""
    try:
        vector_store.delete(filter={"source": table_name})
        return {"status": "success", "message": f"Deleted documents from {table_name}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/list_docs/")
async def list_docs(request: ListDocsRequest):
    """列出向量数据库中的文档"""
    try:
        filter_dict = {}
        if request.table_name:
            filter_dict["source"] = request.table_name
            
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

@app.get("/capabilities/")
async def get_capabilities():
    """获取系统能力信息"""
    try:
        capabilities = await intelligent_agent.get_available_capabilities()
        return {
            "status": "success",
            "capabilities": capabilities,
            "version": "2.0",
            "features": [
                "智能MCP工具调用",
                "视频活动检索",
                "监控记录检索", 
                "自然语言意图识别",
                "实时信息获取"
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/health/")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "version": "2.0",
        "timestamp": datetime.datetime.now().isoformat(),
        "tools_available": len(intelligent_agent.tool_registry.tools)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8086)  # 使用新的端口号 