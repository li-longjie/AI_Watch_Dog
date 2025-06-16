# activity_retriever.py

import json
import os
import logging
from datetime import datetime, timedelta
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
# 假设 llm_service.py 和 config.py 在同一项目路径下，并且可以被导入
from llm_service import LLMService # 如果LLMService封装了调用逻辑
from config import APIConfig # 主要用于LLMService初始化，如果它需要的话
import dateparser # 添加导入
from collections import defaultdict # 导入defaultdict
import sqlite3 # <--- 新增：导入sqlite3
from typing import List, Dict, Any, Optional
import re # <--- 新增：导入re模块
from dateparser.search import search_dates # <--- 修改：直接导入 search_dates
import threading

# --- ChromaDB 和 LLM 服务相关导入 ---
# ... (保留您现有的ChromaDB和LLM相关导入)
# 例如:
import chromadb
from chromadb.utils import embedding_functions
from llm_service import get_llm_response 

# --- 配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 文件路径配置
SCREENSHOT_DIR = "screen_recordings" 
# JSONL_FILE = os.path.join(SCREENSHOT_DIR, "screen_activity_log.jsonl") # <--- 注释或删除
DATABASE_FILE = os.path.join(SCREENSHOT_DIR, "activity_log.db") # <--- 新增：SQLite数据库文件名

CHROMA_DB_PATH = "chroma_db_activity" # 统一数据库目录
COLLECTION_NAME = "screen_activity"

# 全局变量，用于跟踪已索引的记录，避免重复索引
# 当从数据库加载时，我们需要一种新的方式来跟踪已索引的ID，例如记录最后索引的ID或时间戳
last_indexed_id = 0 
indexing_lock = threading.Lock()
# 或者，可以考虑在数据库中增加一个 is_indexed 标志，但这会增加写入时的复杂性。
# 简单起见，我们先用 last_indexed_id，并假设ID是自增的。

# --- ChromaDB 初始化 ---
# (保留您现有的ChromaDB初始化逻辑)
# 例如:
try:
    # 使用默认的SentenceTransformer模型
    default_ef = embedding_functions.DefaultEmbeddingFunction()
    
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    
    # 获取或创建集合，并指定嵌入函数
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=default_ef
    )
    logging.info(f"成功连接到ChromaDB并获取/创建集合: {COLLECTION_NAME} at path {CHROMA_DB_PATH}")
except Exception as e:
    logging.error(f"ChromaDB初始化失败: {e}", exc_info=True)
    # 在ChromaDB失败的情况下，核心功能可能无法使用，可以考虑退出或提供降级功能
    collection = None 

# --- 数据库辅助函数 ---
def create_db_connection():
    """ 创建一个数据库连接到SQLite数据库 """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row # 让查询结果可以通过列名访问
    except sqlite3.Error as e:
        logging.error(f"连接SQLite数据库失败 ({DATABASE_FILE}): {e}")
    return conn

# Screenpipe 数据文件
SCREEN_RECORD_DIR = "screen_recordings"
RECORD_DATA_FILE = os.path.join(SCREEN_RECORD_DIR, "screen_activity_log.jsonl")

# ChromaDB 配置
CHROMA_DB_DIR_ACTIVITY = "chroma_db_activity" # 新的数据库目录，避免与rag_server的冲突
CHROMA_COLLECTION_NAME_ACTIVITY = "screen_activity"

# 初始化嵌入模型 (与 rag_server.py 保持一致)
embeddings = None
activity_vector_store = None

try:
    embeddings = HuggingFaceEmbeddings(
        model_name="Alibaba-NLP/gte-multilingual-base",
        model_kwargs={'device': 'cpu', 'trust_remote_code': True},
        encode_kwargs={'normalize_embeddings': True}
    )
    logging.info("嵌入模型加载成功。")
except Exception as e:
    logging.error(f"嵌入模型加载失败: {e}", exc_info=True)
    # embeddings 会保持为 None

# 初始化向量存储
try:
    if embeddings:
        activity_vector_store = Chroma(
            collection_name=CHROMA_COLLECTION_NAME_ACTIVITY,
            embedding_function=embeddings,
            persist_directory=CHROMA_DB_DIR_ACTIVITY
        )
        logging.info(f"[调试点1] 活动向量数据库实例已创建，类型为: {type(activity_vector_store)}, 对象为: {activity_vector_store}")
        
        # 显式检查是否为None，而不是依赖其布尔值
        if activity_vector_store is not None:
            logging.info(f"[调试点2B] activity_vector_store is not None。活动向量数据库已连接/创建于: {CHROMA_DB_DIR_ACTIVITY}")
        else:
            # 这种情况理论上不应该发生，因为上面已经赋值了
            logging.error("[调试点2B] activity_vector_store is None AFTER Chroma() call. 这表明Chroma()可能返回了None或内部有严重错误。")
    else:
        logging.error("由于嵌入模型加载失败，未能初始化活动向量数据库。")
        # activity_vector_store 保持为 None
except Exception as e:
    logging.error(f"连接或创建活动向量数据库时发生严重异常: {e}", exc_info=True)
    activity_vector_store = None # 确保在Chroma初始化异常时明确设置为None

# 初始化LLM服务 (如果LLMService的初始化比较简单，可以直接在这里进行)
# 假设LLMService有一个静态方法或在实例化时不需要复杂参数
try:
    # 这里需要根据您的LLMService具体实现来调整
    # 如果LLMService.get_response是静态的，或者类本身处理配置，则可能不需要实例化
    # 或者: llm_service_instance = LLMService(api_config=APIConfig) # 示例
    logging.info("LLM服务准备就绪 (假设其已配置或为静态调用)。")
except Exception as e:
    logging.error(f"初始化LLM服务时发生错误: {e}", exc_info=True)


def batch_iterator(data: list, batch_size: int):
    """一个简单的迭代器，用于将列表分批。"""
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]

def load_and_index_activity_data() -> int:
    """
    从SQLite数据库加载自上次索引以来的新活动记录，并以批处理方式将它们索引到ChromaDB。
    返回新索引的记录数量。
    """
    global last_indexed_id, collection

    if not indexing_lock.acquire(blocking=False):
        logging.info("索引操作已在另一个线程中进行，本次调用跳过。")
        return 0

    try:
        if collection is None:
            logging.error("ChromaDB集合未初始化，无法索引数据。")
            return 0

        conn = create_db_connection()
        if not conn:
            return 0

        total_indexed_count = 0
        try:
            cursor = conn.cursor()
            query = f"""
                SELECT id, timestamp, record_type, triggered_by, event_type, 
                       window_title, process_name, app_name, page_title, url,
                       ocr_text, mouse_x, mouse_y, button
                FROM activity_log 
                WHERE id > ? AND ocr_text IS NOT NULL AND ocr_text != ''
                ORDER BY id ASC 
            """ 
            
            cursor.execute(query, (last_indexed_id,))
            records_to_index = cursor.fetchall()

            if not records_to_index:
                logging.info("没有新的活动记录需要索引。")
                return 0

            logging.info(f"发现 {len(records_to_index)} 条新记录需要索引 (自 ID: {last_indexed_id} 之后)...")

            # --- 分批处理逻辑 ---
            BATCH_SIZE = 4000  # ChromaDB的默认最大批次大小为5461，使用一个安全的值

            max_id_in_run = last_indexed_id

            for batch in batch_iterator(records_to_index, BATCH_SIZE):
                documents_to_add = []
                metadatas_to_add = []
                ids_to_add = []
                max_id_in_batch = max_id_in_run

                for record_row in batch:
                    record_dict = dict(record_row)
                    
                    # 构建文档内容
                    doc_content_parts = []
                    if record_dict.get("app_name") and record_dict["app_name"] != "Unknown":
                        doc_content_parts.append(f"应用: {record_dict['app_name']}")
                    if record_dict.get("window_title") and record_dict["window_title"] != "Unknown":
                        doc_content_parts.append(f"窗口: {record_dict['window_title']}")
                    if record_dict.get("page_title"):
                        doc_content_parts.append(f"页面: {record_dict['page_title']}")
                    if record_dict.get("url"):
                        doc_content_parts.append(f"链接: {record_dict['url']}")
                    
                    ocr_text = record_dict.get("ocr_text", "")
                    if ocr_text:
                         doc_content_parts.append(f"内容: {ocr_text}")
                    
                    document_text = " | ".join(doc_content_parts)
                    
                    if not document_text.strip():
                        logging.warning(f"记录ID {record_dict['id']} 生成的文档内容为空，跳过索引。")
                        if record_dict['id'] > max_id_in_batch:
                            max_id_in_batch = record_dict['id']
                        continue

                    documents_to_add.append(document_text)
                    
                    # 构建元数据
                    original_timestamp_iso = record_dict.get("timestamp")
                    timestamp_unix_float = None
                    if original_timestamp_iso:
                        try:
                            timestamp_unix_float = datetime.fromisoformat(original_timestamp_iso).timestamp()
                        except ValueError:
                            logging.warning(f"无效的ISO时间戳格式 '{original_timestamp_iso}' 对于记录ID {record_dict['id']}. 该记录将无法通过精确时间过滤。")
                    
                    window_title_value = record_dict.get("window_title")

                    temp_metadata = {
                        "timestamp_iso_str": original_timestamp_iso if original_timestamp_iso else "N/A",
                        "record_type": record_dict.get("record_type", "N/A"),
                        "app_name": record_dict.get("app_name", "Unknown"),
                        "window_title_meta": (window_title_value[:200] if isinstance(window_title_value, str) else "N/A"),
                        "url_meta": (record_dict.get("url")[:250] if record_dict.get("url") else "N/A"),
                        "source_db_id": record_dict.get("id")
                    }
                    if timestamp_unix_float is not None:
                        temp_metadata["timestamp_unix_float"] = timestamp_unix_float
                    
                    cleaned_metadata = {}
                    for key, value in temp_metadata.items():
                        if value is None: 
                            cleaned_metadata[key] = "N/A"
                        elif not isinstance(value, (str, int, float, bool)):
                             cleaned_metadata[key] = str(value)
                        else:
                            cleaned_metadata[key] = value

                    metadatas_to_add.append(cleaned_metadata)
                    ids_to_add.append(f"record_{record_dict['id']}")

                    if record_dict['id'] > max_id_in_batch:
                        max_id_in_batch = record_dict['id']
                
                if documents_to_add:
                    try:
                        logging.info(f"正在向ChromaDB添加 {len(documents_to_add)} 条记录的批次...")
                        collection.add(
                            documents=documents_to_add,
                            metadatas=metadatas_to_add,
                            ids=ids_to_add
                        )
                        batch_indexed_count = len(documents_to_add)
                        total_indexed_count += batch_indexed_count
                        last_indexed_id = max_id_in_batch # 每个成功批次后更新
                        max_id_in_run = max_id_in_batch
                        logging.info(f"成功添加批次。当前总共添加 {total_indexed_count} 条记录。Last indexed ID 更新为: {last_indexed_id}")
                    except chromadb.errors.InternalError as e_chroma_internal:
                        if "Batch size" in str(e_chroma_internal):
                            logging.error(f"向ChromaDB添加数据时出现批处理大小错误: {e_chroma_internal}", exc_info=True)
                            logging.error(f"当前批次大小: {len(documents_to_add)}。请考虑减小 BATCH_SIZE。")
                        else:
                            logging.error(f"向ChromaDB添加数据时出现内部错误: {e_chroma_internal}", exc_info=True)
                        return total_indexed_count # 发生错误时停止并返回已成功索引的数量
                    except Exception as e:
                        logging.error(f"向ChromaDB添加数据时出错: {e}", exc_info=True)
                        return total_indexed_count # 发生错误时停止

        except sqlite3.Error as e:
            logging.error(f"从SQLite数据库加载数据用于索引时出错: {e}")
        except Exception as e_global:
            logging.error(f"索引数据过程中发生意外错误: {e_global}", exc_info=True)
        finally:
            if conn:
                conn.close()
                
        return total_indexed_count
    finally:
        indexing_lock.release()

# 全局变量 last_indexed_id 的初始化逻辑：
# 我们需要在程序启动时，从ChromaDB获取已存在的最大 source_db_id，或者从数据库获取最大ID作为起点。
# 一个简单的方法是，如果ChromaDB是空的，last_indexed_id从0开始。
# 如果ChromaDB非空，可以查询ChromaDB中已存在的最大 source_db_id (如果之前存储了这个元数据)。
# 或者，更简单的是，每次启动时都重新索引最近一段时间的数据（比如最近一天），但这可能导致重复。
# 暂时，我们依赖于程序重启后 last_indexed_id 保持（如果脚本不重启），或者从0开始（如果脚本重启）。
# 一个更健壮的方法是持久化 last_indexed_id，或者在启动时查询数据库中的最大ID。

def initialize_last_indexed_id():
    """
    在程序启动时初始化 last_indexed_id。
    从ChromaDB中已存在的记录元数据里恢复。
    """
    global last_indexed_id, collection
    if collection:
        try:
            # 只获取元数据可以更快
            existing_records = collection.get(include=["metadatas"])
            max_db_id = 0
            if existing_records and existing_records['metadatas']:
                for meta in existing_records['metadatas']:
                    if meta and 'source_db_id' in meta and isinstance(meta['source_db_id'], int):
                        if meta['source_db_id'] > max_db_id:
                            max_db_id = meta['source_db_id']
            last_indexed_id = max_db_id
            logging.info(f"从ChromaDB恢复，初始化 last_indexed_id 为: {last_indexed_id}")
            return
        except Exception as e:
            logging.warning(f"从ChromaDB恢复last_indexed_id失败: {e}. 将使用默认值0.")
    
    last_indexed_id = 0
    logging.info(f"未能从ChromaDB恢复 last_indexed_id，初始化为: {last_indexed_id} (将尝试索引所有记录)")

if collection:
    initialize_last_indexed_id()


def index_single_activity_record(record_data: Dict[str, Any]) -> bool:
    """
    索引单条活动记录到ChromaDB。
    record_data: 一个包含活动记录的字典，应包含 'id' 和 'ocr_text' 以及其他元数据字段。
    返回 True 表示成功，False 表示失败。
    """
    global collection, last_indexed_id
    if collection is None:
        logging.error("index_single_activity_record: ChromaDB集合未初始化，无法索引数据。")
        return False

    if not record_data or not isinstance(record_data, dict):
        logging.error("index_single_activity_record: 提供的记录数据无效。")
        return False

    record_id = record_data.get("id")
    
    # 关键检查：确保 record_id 是有效的整数
    if record_id is None or not isinstance(record_id, int):
        logging.error(f"index_single_activity_record: 无效或缺失的记录ID ('{record_id}')。无法索引。数据: {record_data}")
        return False # 不进行索引

    ocr_text_content = record_data.get("ocr_text", "")

    # 通常我们只索引包含有效OCR文本的记录
    # 对于 app_switch 事件，其 ocr_text 是生成的描述，也可以被索引
    if not ocr_text_content and record_data.get("record_type") != "app_switch": # 如果不是app_switch且ocr为空则跳过
        # 或者根据您的策略决定是否索引ocr_text为空的记录
        logging.debug(f"记录ID {record_id} (类型: {record_data.get('record_type')}) OCR文本为空，跳过单条索引。")
        return True # 认为处理完成，但不索引

    # 构建文档内容
    doc_content_parts = []
    if record_data.get("app_name") and record_data["app_name"] != "Unknown":
        doc_content_parts.append(f"应用: {record_data['app_name']}")
    if record_data.get("window_title") and record_data["window_title"] != "Unknown":
        doc_content_parts.append(f"窗口: {record_data['window_title']}")
    if record_data.get("page_title"):
        doc_content_parts.append(f"页面: {record_data['page_title']}")
    if record_data.get("url"):
        doc_content_parts.append(f"链接: {record_data['url']}")
    
    if ocr_text_content:
         doc_content_parts.append(f"内容: {ocr_text_content}")
    
    document_text = " | ".join(doc_content_parts)

    if not document_text.strip():
        logging.warning(f"记录ID {record_id} 生成的文档内容为空（单条索引），跳过。")
        return True 

    # 构建元数据
    original_timestamp_iso = record_data.get("timestamp")
    timestamp_unix_float = None
    if original_timestamp_iso:
        try:
            timestamp_unix_float = datetime.fromisoformat(original_timestamp_iso).timestamp()
        except ValueError:
            logging.warning(f"index_single_activity_record: 无效的ISO时间戳格式 '{original_timestamp_iso}' 对于记录ID {record_id}.")

    window_title_value = record_data.get("window_title")
    
    temp_metadata = {
        "timestamp_iso_str": original_timestamp_iso if original_timestamp_iso else "N/A",
        "record_type": record_data.get("record_type", "N/A"),
        "app_name": record_data.get("app_name", "Unknown"),
        "window_title_meta": (window_title_value[:200] if isinstance(window_title_value, str) else "N/A"),
        "url_meta": (record_data.get("url")[:250] if record_data.get("url") else "N/A"),
        "source_db_id": record_id 
    }
    if timestamp_unix_float is not None:
        temp_metadata["timestamp_unix_float"] = timestamp_unix_float

    cleaned_metadata = {}
    for key, value in temp_metadata.items():
        if value is None:
            cleaned_metadata[key] = "N/A"
        elif not isinstance(value, (str, int, float, bool)):
             cleaned_metadata[key] = str(value)
        else:
            cleaned_metadata[key] = value
    
    chroma_id = f"record_{record_id}" # 确保ID是字符串

    try:
        # 使用 upsert=True 可以安全地覆盖已存在的记录，避免因重复ID导致错误
        collection.add(
            documents=[document_text],
            metadatas=[cleaned_metadata],
            ids=[chroma_id]
        )
        logging.info(f"成功将记录ID {record_id} (Chroma ID: {chroma_id}) 单独索引到ChromaDB。")
        return True
    except Exception as e:
        error_message = str(e)
        # 检查是否是ChromaDB损坏相关的错误
        if "Error in compaction" in error_message or "hnsw segment reader" in error_message:
            logging.error(f"ChromaDB数据库损坏错误，记录ID {record_id} 索引失败: {error_message}")
            logging.info("建议重启系统以重置损坏的向量数据库")
        elif "already exists" in error_message:
            logging.warning(f"记录ID {record_id} (Chroma ID: {chroma_id}) 已存在于ChromaDB中，跳过索引")
            return True  # 视为成功，因为数据已存在
        else:
            logging.error(f"单独索引记录ID {record_id} (Chroma ID: {chroma_id}) 到ChromaDB时出错: {e}", exc_info=True)
        return False

# --- 其他函数将在这里逐个修改 --- 

async def query_recent_activity(query_text: str, custom_prompt: Optional[str] = None, minutes_ago: Optional[int] = None) -> str:
    """
    根据用户查询（可能包含自然语言时间描述）和自定义提示，
    查询ChromaDB中的活动记录，并使用LLM生成回答。
    """
    global collection
    if collection is None:
        return "抱歉，向量数据库未初始化，无法执行语义查询。\n\n💡 提示：您可以通过Web界面的'活动记录'页面查看最近的活动数据，或者联系管理员重新启用向量索引功能。"

    try:
        # 1. 确保数据已索引
        new_indexed_count = load_and_index_activity_data()
        if new_indexed_count > 0:
            logging.info(f"查询前，新索引了 {new_indexed_count} 条记录到ChromaDB。")
        else:
            logging.info("查询前，没有新的记录被索引到ChromaDB。")

        # 2. 从用户查询中解析时间范围
        if minutes_ago is not None and isinstance(minutes_ago, int) and minutes_ago > 0 :
            end_time_dt = datetime.now()
            start_time_dt = end_time_dt - timedelta(minutes=minutes_ago)
            logging.info(f"使用前端传递的固定时间范围: {minutes_ago} 分钟前. 从 {start_time_dt.isoformat()} 到 {end_time_dt.isoformat()}")
        else:
            start_time_dt, end_time_dt = parse_time_range_from_query(query_text)
        
        logging.info(f"用于ChromaDB查询的最终时间范围: 从 {start_time_dt.isoformat()} 到 {end_time_dt.isoformat()}")

        # 3. 构建ChromaDB的 'where' 过滤器
        where_filter = {
            "$and": [
                {"timestamp_unix_float": {"$gte": start_time_dt.timestamp()}},
                {"timestamp_unix_float": {"$lte": end_time_dt.timestamp()}}
            ]
        }
        
        logging.info(f"构建的ChromaDB 'where' 过滤器: {where_filter}")
        
        # 4. 从ChromaDB检索相关文档
        results = collection.query(
            query_texts=[query_text],
            n_results=30,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        retrieved_count = len(results['documents'][0]) if results and results['documents'] and results['documents'][0] else 0
        logging.info(f"ChromaDB查询在应用时间过滤器后返回了 {retrieved_count} 条文档。")
        
        retrieved_docs = []
        if retrieved_count > 0:
            for i, doc_text in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] and results['metadatas'][0] else {}
                distance = results['distances'][0][i] if results['distances'] and results['distances'][0] else float('inf')
                
                doc_info_parts = [
                    f"活动记录 (时间: {metadata.get('timestamp_iso_str', '未知')}",
                    f"应用: {metadata.get('app_name', '未知')}",
                    f"类型: {metadata.get('record_type','未知')}"
                ]
                url_from_meta = metadata.get('url_meta')
                if url_from_meta and url_from_meta != "N/A":
                    doc_info_parts.append(f"URL: {url_from_meta}")

                doc_info_parts.append(f"相关度: {1-distance:.2f})")
                
                doc_info_header = ", ".join(doc_info_parts)
                doc_info = f"{doc_info_header}:\n{doc_text}\n---"
                retrieved_docs.append(doc_info)
        
        if not retrieved_docs:
            return f"根据您的问题并在指定的时间范围（从 {start_time_dt.strftime('%Y-%m-%d %H:%M:%S')} 到 {end_time_dt.strftime('%Y-%m-%d %H:%M:%S')}）内，我没有找到相关的活动记录。"

        context_for_llm = "\n".join(retrieved_docs)
        
        # 5. 构建最终的提示词并调用LLM
        if custom_prompt:
            final_prompt = custom_prompt + f"\n\n以下是相关的屏幕活动摘要 (已按时间范围筛选)，请基于这些信息回答问题:\n{context_for_llm}\n\n用户的问题是: {query_text}"
        else:
            final_prompt = f"""请根据以下在指定时间范围内筛选的屏幕活动记录摘要来回答用户的问题。
这些记录可能包含网页URL和页面标题。当被问及浏览过的网页时，请优先使用并提供具体的URL链接。
活动记录摘要 (时间范围: {start_time_dt.strftime('%Y-%m-%d %H:%M:%S')} 到 {end_time_dt.strftime('%Y-%m-%d %H:%M:%S')}):
{context_for_llm}

用户的问题是: "{query_text}"
请直接回答问题。如果信息包含URL，请清晰地列出URL链接。如果信息不足，可以说信息不足。请严格基于提供的摘要内容。
"""
        
        logging.debug(f"LLM Final Prompt (部分):\n{final_prompt[:1000]}...")

        llm_response = await get_llm_response(final_prompt)
        return llm_response

    except chromadb.errors.InternalError as e:
        error_message = str(e)
        logging.error(f"查询活动记录时发生ChromaDB内部错误: {error_message}", exc_info=True)
        if "Error finding id" in error_message:
            return "抱歉，处理您的请求时发生了数据库错误 (Error finding id)。这通常是由于向量数据库索引损坏导致的。请尝试重启程序，系统在启动时会自动尝试修复索引。如果问题仍然存在，您可能需要手动删除 'chroma_db_activity' 目录来强制重建数据库。"
        return f"抱歉，处理您的请求时发生了数据库内部错误: {e}"
    except Exception as e:
        logging.error(f"查询活动记录或调用LLM时出错: {e}", exc_info=True)
        return f"抱歉，处理您的请求时发生了错误: {e}"


# --- 其他可能需要修改的函数，例如与特定文件格式相关的辅助函数，现在可以移除了 ---
# 例如，如果您有类似 load_jsonl_data 的函数，现在不再需要。

# --- 时间解析辅助函数 (如果之前没有，可以保留或添加) ---
def parse_time_range_from_query(query_text: str, default_minutes_ago: int = 1440) -> tuple[datetime, datetime]:
    now = datetime.now()
    start_time, end_time = None, now  # Default end_time is now

    # 优先使用正则表达式处理 "最近X分钟/小时/天" 或 "过去X分钟/小时/天"
    # 支持数字和部分中文数字（一至十）
    num_map_chinese_to_int = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    # 匹配例如: "过去5分钟", "最近一小时", "过去十天"
    match_duration = re.search(r"(?:最近|过去)([\d一二三四五六七八九十]+)\s*(分钟|小时|天|周|月)", query_text)

    if match_duration:
        value_str = match_duration.group(1)
        unit = match_duration.group(2)
        value = 0

        if value_str in num_map_chinese_to_int:
            value = num_map_chinese_to_int[value_str]
        else:
            try:
                value = int(value_str)
            except ValueError:
                logging.warning(f"无法从 '{value_str}' 解析数字用于时间范围查询。")
                value = 0 
        
        if value > 0:
            if unit == "分钟":
                start_time = now - timedelta(minutes=value)
            elif unit == "小时":
                start_time = now - timedelta(hours=value)
            elif unit == "天":
                start_time = now - timedelta(days=value)
            elif unit == "周":
                start_time = now - timedelta(weeks=value)
            elif unit == "月": # 近似月份
                start_time = now - timedelta(days=value * 30)
            logging.info(f"通过正则表达式解析时间: 值={value}, 单位='{unit}'. 计算开始时间: {start_time.isoformat() if start_time else 'N/A'}")

    # 如果正则表达式没有匹配成功，尝试使用 dateparser
    if start_time is None:
        parsed_dates = search_dates(
            query_text,
            languages=['zh'],
            settings={'PREFER_DATES_FROM': 'past', 'RETURN_AS_TIMEZONE_AWARE': False, 'RELATIVE_BASE': now}
        )
        logging.info(f"Dateparser 为查询 '{query_text}' 返回的结果: {parsed_dates}")

        if parsed_dates:
            # 先检查是否包含特定的日期关键词
            query_lower = query_text.lower()
            
            # 处理"前天"
            if "前天" in query_text:
                day_before_yesterday = now.date() - timedelta(days=2)
                
                # 检查是否有时间段限定
                if "上午" in query_text:
                    start_time = datetime.combine(day_before_yesterday, datetime.min.time().replace(hour=6))  # 6:00
                    end_time = datetime.combine(day_before_yesterday, datetime.min.time().replace(hour=12))   # 12:00
                    logging.info(f"检测到 '前天上午'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
                elif "下午" in query_text:
                    start_time = datetime.combine(day_before_yesterday, datetime.min.time().replace(hour=12)) # 12:00
                    end_time = datetime.combine(day_before_yesterday, datetime.min.time().replace(hour=18))   # 18:00
                    logging.info(f"检测到 '前天下午'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
                elif "晚上" in query_text or "夜里" in query_text:
                    start_time = datetime.combine(day_before_yesterday, datetime.min.time().replace(hour=18)) # 18:00
                    end_time = datetime.combine(day_before_yesterday, datetime.max.time())                    # 23:59:59
                    logging.info(f"检测到 '前天晚上'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
                else:
                    # 整个前天
                    start_time = datetime.combine(day_before_yesterday, datetime.min.time())
                    end_time = datetime.combine(day_before_yesterday, datetime.max.time())
                    logging.info(f"检测到 '前天'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
            
            # 处理"昨天"
            elif any(pd[0] == "昨天" for pd in parsed_dates) or "昨天" in query_text:
                yesterday_date = now.date() - timedelta(days=1)
                
                # 检查是否有时间段限定
                if "上午" in query_text:
                    start_time = datetime.combine(yesterday_date, datetime.min.time().replace(hour=6))
                    end_time = datetime.combine(yesterday_date, datetime.min.time().replace(hour=12))
                    logging.info(f"检测到 '昨天上午'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
                elif "下午" in query_text:
                    start_time = datetime.combine(yesterday_date, datetime.min.time().replace(hour=12))
                    end_time = datetime.combine(yesterday_date, datetime.min.time().replace(hour=18))
                    logging.info(f"检测到 '昨天下午'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
                elif "晚上" in query_text or "夜里" in query_text:
                    start_time = datetime.combine(yesterday_date, datetime.min.time().replace(hour=18))
                    end_time = datetime.combine(yesterday_date, datetime.max.time())
                    logging.info(f"检测到 '昨天晚上'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
                else:
                    # 整个昨天
                    start_time = datetime.combine(yesterday_date, datetime.min.time())
                    end_time = datetime.combine(yesterday_date, datetime.max.time())
                    logging.info(f"检测到 '昨天'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
            
            # 处理"今天"
            elif any(pd[0] == "今天" for pd in parsed_dates) or "今天" in query_text:
                today_date = now.date()
                
                # 检查是否有时间段限定
                if "上午" in query_text:
                    start_time = datetime.combine(today_date, datetime.min.time().replace(hour=6))
                    end_time = min(datetime.combine(today_date, datetime.min.time().replace(hour=12)), now)
                    logging.info(f"检测到 '今天上午'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
                elif "下午" in query_text:
                    start_time = datetime.combine(today_date, datetime.min.time().replace(hour=12))
                    end_time = min(datetime.combine(today_date, datetime.min.time().replace(hour=18)), now)
                    logging.info(f"检测到 '今天下午'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
                elif "晚上" in query_text or "夜里" in query_text:
                    start_time = datetime.combine(today_date, datetime.min.time().replace(hour=18))
                    end_time = now  # 到现在为止
                    logging.info(f"检测到 '今天晚上'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
                else:
                    # 今天从开始到现在
                    start_time = datetime.combine(today_date, datetime.min.time())
                    end_time = now
                    logging.info(f"检测到 '今天'. 时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}")
            
            else:
                # 对于其他 dateparser 的结果，取最早的过去时间点作为开始时间
                # 这可能不完全符合用户的意图，但作为一种回退机制
                potential_start_times = sorted([pd[1] for pd in parsed_dates if pd[1] < now])
                if potential_start_times:
                    start_time = potential_start_times[0]
                    logging.info(f"Dateparser 通用回退机制. 使用最早的解析时间点作为开始时间: {start_time.isoformat()}")
    
    # 如果以上所有方法都未能确定 start_time，则使用默认时间窗口
    if start_time is None:
        start_time = now - timedelta(minutes=default_minutes_ago)
        logging.info(f"未能从查询中解析特定时间，使用默认时间窗口: {default_minutes_ago} 分钟前. 开始时间: {start_time.isoformat()}")

    # 确保 start_time 不晚于 end_time
    if start_time > end_time:
        logging.warning(f"解析后的开始时间 ({start_time.isoformat()}) 晚于结束时间 ({end_time.isoformat()}). 将调整开始时间。")
        start_time = end_time - timedelta(seconds=1) # 创建一个极小但有效的时间范围

    return start_time, end_time


def get_all_activity_records(limit: int = 50) -> list:
    """
    从SQLite数据库中检索活动记录。
    默认按时间戳降序排序，返回最新的记录。
    """
    conn = create_db_connection()
    if not conn:
        logging.error("get_all_activity_records: 无法连接到数据库。")
        return []

    records = []
    try:
        cursor = conn.cursor()
        # 获取最新的记录
        cursor.execute("SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        for row in rows:
            records.append(dict(row))  # 将 sqlite3.Row 对象转换为字典
        logging.info(f"成功从数据库检索到 {len(records)} 条活动记录 (限制: {limit}).")
    except sqlite3.Error as e:
        logging.error(f"从数据库检索活动记录失败: {e}")
        records = [] # 确保出错时返回空列表
    finally:
        if conn:
            conn.close()
    return records

async def get_application_usage_summary(start_time_dt: datetime, end_time_dt: datetime) -> dict:
    """
    计算在给定时间范围内每个应用程序的使用时长。
    """
    conn = create_db_connection()
    if not conn:
        return {"error": "无法连接到数据库以计算应用使用时长。"}

    usage_summary = defaultdict(timedelta)
    # 用于调试的原始事件样本
    raw_events_for_period = [] 

    try:
        cursor = conn.cursor()
        
        # 将 datetime 对象转换为 ISO 格式的字符串以进行 SQL 查询
        start_time_iso = start_time_dt.isoformat()
        end_time_iso = end_time_dt.isoformat()

        # 查询此时间段内所有的 'app_switch' 和 'screen_content' 事件，按时间戳排序
        # 我们需要app_name和timestamp
        # 'mouse_interaction' 通常也发生在某个应用内，但如果只关心应用切换和主要内容，可以先关注前两者
        # 为了更准确，我们应该考虑所有带有 app_name 的记录类型
        query = """
            SELECT timestamp, app_name, record_type, url
            FROM activity_log
            WHERE timestamp >= ? AND timestamp <= ? AND app_name IS NOT NULL AND app_name != 'Unknown'
            ORDER BY timestamp ASC
        """
        cursor.execute(query, (start_time_iso, end_time_iso))
        events = cursor.fetchall()
        
        # logging.debug(f"获取到 {len(events)} 条事件用于计算 {start_time_iso} 到 {end_time_iso} 之间的应用时长。")
        # for event_row in events[:5]: # 打印一些样本事件
        #     logging.debug(f"  事件样本: {dict(event_row)}")


        if not events:
            return {"usage": {}, "raw_events": [], "message": "指定时间段内无相关活动记录。"}

        # 将原始事件添加到调试输出
        for event_row in events:
            raw_events_for_period.append(dict(event_row))


        # 计算逻辑:
        # 遍历排序后的事件。对于每个事件，它代表了从该事件时间点到下一个不同应用事件时间点之间，
        # 当前应用是活动状态的。
        # 如果是最后一个事件，则它代表从该事件时间点到查询范围的结束时间点。

        for i in range(len(events)):
            current_event_dict = dict(events[i])
            current_app = current_event_dict['app_name']
            
            try:
                # sqlite3.Row['timestamp'] 返回的是字符串，需要解析
                current_event_time = datetime.fromisoformat(current_event_dict['timestamp'])
            except ValueError:
                logging.warning(f"无法解析事件时间戳: {current_event_dict['timestamp']} for app {current_app}. 跳过此事件对。")
                continue

            if not current_app or current_app == "Unknown": # 再次确认，虽然查询时已过滤
                continue
            
            next_event_time = end_time_dt # 默认到查询范围的结束

            if i + 1 < len(events):
                next_event_dict = dict(events[i+1])
                try:
                    next_event_time_candidate = datetime.fromisoformat(next_event_dict['timestamp'])
                    # 如果下一个事件的时间超出了查询范围的结束时间，则截断到查询结束时间
                    next_event_time = min(next_event_time_candidate, end_time_dt)
                except ValueError:
                    logging.warning(f"无法解析下一个事件时间戳: {next_event_dict['timestamp']}. 将使用范围结束时间。")
                    # next_event_time 保持为 end_time_dt
            
            # 确保 current_event_time 不晚于 next_event_time (例如，如果数据有误或都在同一秒)
            if current_event_time < next_event_time:
                duration = next_event_time - current_event_time
                usage_summary[current_app] += duration
            elif current_event_time == next_event_time and i == len(events) -1 :
                # 如果是最后一个事件且时间与end_time_dt相同，给一个象征性的短时间（例如1秒）
                # 或者基于它是最后一个事件的上下文来决定。
                # 这里简化，如果时间相同，认为持续时间为0，除非有特殊处理需求。
                pass


        # logging.debug(f"计算后的应用时长 (原始): {dict(usage_summary)}")
        
        # 返回结果，包含总时长和原始事件样本（用于调试）
        return {
            "usage": dict(usage_summary), # 将defaultdict转为普通dict
            "raw_events": raw_events_for_period # 返回在此期间处理的所有事件
        }

    except sqlite3.Error as e:
        logging.error(f"计算应用使用时长时数据库查询出错: {e}")
        return {"error": f"数据库错误: {e}", "usage": {}, "raw_events": []}
    except Exception as e_global:
        logging.error(f"计算应用使用时长时发生未知错误: {e_global}", exc_info=True)
        return {"error": f"未知错误: {e_global}", "usage": {}, "raw_events": []}
    finally:
        if conn:
            conn.close()

# 注释掉整个 __main__ 块以避免导入时执行
# if __name__ == "__main__":
#     # 为了运行异步的 main_test_query
#     # asyncio.run(main_test_query())

#     # 首先，确保数据被加载和索引
#     # 这一步只需要做一次，或者在数据更新时定期做
#     # 对于测试，我们可以在每次运行时都加载最新的数据
#     print("正在加载和索引屏幕活动数据...")
#     count = load_and_index_activity_data()
#     print(f"加载了 {count} 条新记录。")

#     if activity_vector_store is not None: # 确保数据库对象不是None才尝试查询
#         # 并且最好也检查一下数据库中是否有数据被加载进去
#         # 这个检查可以放在 main_test_query 内部或这里
#         db_is_empty = True
#         try:
#             # 尝试获取集合中的条目数量，如果为0，则认为空
#             # 注意: .count() 是新版chromadb的方法，langchain的Chroma可能没有直接的 .count()
#             # 我们通过 .get() 来间接判断
#             retrieved_items = activity_vector_store.get(limit=1) 
#             if retrieved_items and retrieved_items.get('ids') and len(retrieved_items.get('ids')) > 0:
#                 db_is_empty = False
#             elif count > 0 and (not retrieved_items or not retrieved_items.get('ids')):
#                 logging.warning("数据已尝试加载到Chroma，但 .get(limit=1) 未返回有效ID，可能持久化或集合内部有问题。")
#         except Exception as e:
#             logging.error(f"检查数据库是否为空时出错: {e}")

#         if count > 0 and not db_is_empty:
#             import asyncio
#             # 测试应用时长计算
#             async def test_usage_calculation():
#                 # await main_test_query()  # 注释掉未定义的函数调用
#                 print("\n--- 测试应用时长计算 (过去60分钟) ---")
#                 now = datetime.now()
#                 start_calc_time = now - timedelta(minutes=60)
#                 usage_summary = await get_application_usage_summary(start_calc_time, now)
#                 if usage_summary.get("error"):
#                     print(f"计算出错: {usage_summary['error']}")
#                 else:
#                     print("应用使用时长:")
#                     for app, duration in usage_summary["usage"].items():
#                         print(f"  {app}: {duration}")
#                 # print("\n原始事件:")
#                 # for evt in usage_summary["raw_events"][:10]: # 打印前10条事件调试
#                 #     print(evt)
#             asyncio.run(test_usage_calculation())
#         elif count == 0 and db_is_empty:
#             print(f"没有新的活动记录被加载，且数据库 ({CHROMA_COLLECTION_NAME_ACTIVITY}) 为空。请确保 screen_capture.py 已运行并生成数据。")
#         elif count > 0 and db_is_empty:
#             print(f"{count} 条记录尝试加载，但数据库 ({CHROMA_COLLECTION_NAME_ACTIVITY}) 似乎仍为空或无法正确读取。请检查ChromaDB的持久化和查询。")
#         else: # activity_vector_store is None 的情况
#             print(f"向量数据库未能成功初始化。无法进行查询。")
#     else:
#         print(f"向量数据库未能成功初始化 (activity_vector_store is None)。无法进行查询。")