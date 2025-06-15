import time
import os
from PIL import Image
import mss
import pytesseract
import pygetwindow as gw
import logging
from datetime import datetime
import json
import psutil
import threading
import requests  # 新增：导入requests库用于API调用
import base64    # 新增：导入base64用于图像编码
from io import BytesIO  # 新增：导入BytesIO用于图像处理
import queue
import sqlite3
import re
from typing import Optional

# 尝试导入 pynput，用于鼠标事件监听和控制
try:
    from pynput import mouse
    PYNPUT_AVAILABLE = True
    logging.info("pynput库 (mouse) 加载成功。")
except ImportError:
    PYNPUT_AVAILABLE = False
    logging.warning("pynput库加载失败。鼠标点击监听功能将不可用。请尝试 `pip install pynput`")
    # 创建一个dummy mouse类以避免错误
    class DummyMouse:
        class Controller:
            @property
            def position(self):
                return (0, 0)
        class Listener:
            def __init__(self, on_click=None):
                pass
            def start(self):
                pass
            def join(self):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
    mouse = DummyMouse()

# 尝试导入 pywin32，如果失败则记录错误，并在后续逻辑中回退
try:
    import win32process
    import win32gui
    import win32api
    PYWIN32_AVAILABLE = True
    logging.info("pywin32库 (win32process, win32gui, win32api) 加载成功。")
except ImportError:
    PYWIN32_AVAILABLE = False
    logging.warning("pywin32库加载失败。在Windows上获取精确的应用名称、PID和窗口截图可能会受限。请尝试 `pip install pywin32`")

# 尝试设置DPI感知 (仅Windows)
if os.name == 'nt' and PYWIN32_AVAILABLE: # 检查是否为Windows且pywin32可用
    try:
        import ctypes
        # Per-Monitor DPI Aware V2: 对于现代应用最理想
        # 1 表示 System DPI Aware, 0 表示 Unaware
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logging.info("成功将进程DPI感知设置为 Per-Monitor Aware V2。")
    except AttributeError:
        # shcore.dll 可能在非常旧的Windows版本上不可用，或者 SetProcessDpiAwareness 不存在
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            logging.info("成功将进程DPI感知设置为 System DPI Aware (回退方案)。")
        except Exception as e_dpi_fallback:
            logging.warning(f"设置DPI感知失败: {e_dpi_fallback}")
    except Exception as e_dpi:
        logging.warning(f"设置DPI感知时发生未知错误: {e_dpi}")

# 导入活动索引功能
try:
    from activity_retriever import index_single_activity_record
    logging.info("成功导入index_single_activity_record函数")
except ImportError as e:
    logging.error(f"导入index_single_activity_record函数失败: {e}")
    # 定义一个替代函数，在真正的函数不可用时使用
    def index_single_activity_record(record):
        logging.error("无法使用实际的index_single_activity_record函数，只记录数据到文件")
        return False

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s') # 将日志级别改为DEBUG

# --- Tesseract OCR 配置 ---
# 根据您的Tesseract安装路径进行配置
# Windows示例:
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe' # 注意路径中的反斜杠
# Linux/macOS 通常不需要特别指定，如果已添加到PATH

# --- 全局变量 ---
SCREENSHOT_DIR = "screen_recordings"
DATABASE_FILE = os.path.join(SCREENSHOT_DIR, "activity_log.db")
CAPTURE_INTERVAL_SECONDS = 20
MOUSE_CLICK_CAPTURE_INTERVAL_SECONDS = 5
# 新增：Omniparser API配置
OMNIPARSER_API_URL = "http://localhost:5111/parse"  # 根据实际部署情况修改
USE_OMNIPARSER = True  # 控制是否使用Omniparser替代OCR
ENABLE_VECTOR_INDEXING = True # 是否启用向量数据库索引（临时禁用以避免ChromaDB问题）

# 特殊应用名称的大小写映射
KNOWN_APP_CASINGS = {
    "qq": "QQ",        # 修正：键应该是全小写 "qq"
    "vscode": "VSCode",
    "code": "VSCode",    # VS Code 的进程名通常是 Code.exe
    # 在这里可以添加更多自定义的大小写规则
    # "wechat": "WeChat", # 如果您希望微信显示为 WeChat 而不是 Wechat
}

# 用于检测应用切换的全局变量
last_active_app_name = None
last_window_title = None # 可选：也跟踪窗口标题变化，以记录更细微的切换

# 用于鼠标点击截图的全局变量
last_mouse_click_screenshot_time = 0
record_file_lock = threading.Lock() # 用于同步对记录文件的写入
mouse_controller = None # pynput鼠标控制器实例
click_task_queue = queue.Queue() # 用于处理鼠标点击任务的队列

# 用于解析器统计的全局变量
omniparser_request_count = 0  # Omniparser请求计数器
tesseract_request_count = 0   # Tesseract请求计数器
last_stats_time = time.time() # 上次统计时间

# 用于服务健康监控的全局变量
omniparser_consecutive_failures = 0  # 连续失败次数
omniparser_max_failures = 3         # 最大连续失败次数
omniparser_temporary_disabled = False # 临时禁用标志

# 尝试导入 uiautomation，如果失败则记录错误，并在后续逻辑中回退
try:
    import uiautomation as auto
    UIAUTOMATION_AVAILABLE = True
    logging.info("uiautomation库加载成功。可以尝试获取浏览器URL。")
except ImportError:
    UIAUTOMATION_AVAILABLE = False
    logging.warning("uiautomation库加载失败。无法获取浏览器URL。请尝试 `pip install uiautomation`")

# --- 确保截图目录存在 ---
if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

def create_connection(db_file):
    """ 创建一个数据库连接到SQLite数据库 """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        # logging.debug(f"成功连接到SQLite数据库: {db_file}")
    except sqlite3.Error as e:
        logging.error(f"连接SQLite数据库失败 ({db_file}): {e}")
    return conn

def init_db():
    """ 初始化数据库，创建表（如果不存在），并自动迁移旧的表结构。 """
    conn = create_connection(DATABASE_FILE)
    if conn is not None:
        try:
            cursor = conn.cursor()

            # 1. 确保表存在 (使用最新的 schema 定义)
            # 这样新创建的数据库就直接是正确的结构。
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                record_type TEXT NOT NULL,
                triggered_by TEXT,
                event_type TEXT,
                window_title TEXT,
                process_name TEXT,
                app_name TEXT,
                page_title TEXT,
                url TEXT,
                pid INTEGER,
                from_app TEXT,
                to_app TEXT,
                to_app_title TEXT,
                screenshot_path TEXT,
                ocr_text TEXT,
                visual_elements TEXT,  -- 新增：存储Omniparser返回的结构化视觉元素JSON
                parser_type TEXT,      -- 新增：标记使用的解析器类型 (omniparser/tesseract)
                mouse_x INTEGER,
                mouse_y INTEGER,
                button TEXT,
                pressed INTEGER 
            );
            """
            cursor.execute(create_table_sql)
            conn.commit() # 提交创表操作

            # 2. 检查旧的表结构并进行迁移 (如果需要)
            cursor.execute("PRAGMA table_info(activity_log);")
            columns = [row[1] for row in cursor.fetchall()]
            
            # 检查并添加新列
            if 'visual_elements' not in columns:
                logging.info("检测到旧版数据库表，缺少 'visual_elements' 列。正在进行迁移...")
                try:
                    cursor.execute("ALTER TABLE activity_log ADD COLUMN visual_elements TEXT;")
                    conn.commit()
                    logging.info("数据库迁移成功：已成功添加 'visual_elements' 列。")
                except sqlite3.Error as e_alter:
                    logging.error(f"数据库迁移失败：添加 'visual_elements' 列时出错: {e_alter}")
            
            if 'parser_type' not in columns:
                logging.info("检测到旧版数据库表，缺少 'parser_type' 列。正在进行迁移...")
                try:
                    cursor.execute("ALTER TABLE activity_log ADD COLUMN parser_type TEXT;")
                    conn.commit()
                    logging.info("数据库迁移成功：已成功添加 'parser_type' 列。")
                except sqlite3.Error as e_alter:
                    logging.error(f"数据库迁移失败：添加 'parser_type' 列时出错: {e_alter}")
            
            # 检查url列（保留原有的迁移逻辑）
            if 'url' not in columns:
                logging.info("检测到旧版数据库表，缺少 'url' 列。正在进行迁移...")
                try:
                    cursor.execute("ALTER TABLE activity_log ADD COLUMN url TEXT;")
                    conn.commit()
                    logging.info("数据库迁移成功：已成功添加 'url' 列。")
                except sqlite3.Error as e_alter:
                    logging.error(f"数据库迁移失败：添加 'url' 列时出错: {e_alter}")
            
            # 3. 创建索引（如果不存在）
            create_index_timestamp_sql = "CREATE INDEX IF NOT EXISTS idx_timestamp ON activity_log (timestamp);"
            cursor.execute(create_index_timestamp_sql)
            create_index_app_name_sql = "CREATE INDEX IF NOT EXISTS idx_app_name ON activity_log (app_name);"
            cursor.execute(create_index_app_name_sql)
            create_index_record_type_sql = "CREATE INDEX IF NOT EXISTS idx_record_type ON activity_log (record_type);"
            cursor.execute(create_index_record_type_sql)
            
            conn.commit() # 提交索引创建操作
            logging.info(f"数据库表 'activity_log' 已在 {DATABASE_FILE} 中初始化/验证完毕。")
        except sqlite3.Error as e:
            logging.error(f"创建/验证数据库表失败: {e}")
        finally:
            conn.close()
    else:
        logging.error("未能创建数据库连接，无法初始化数据库。")

def get_mouse_position():
    """获取当前鼠标指针的全局位置"""
    global mouse_controller
    if not PYNPUT_AVAILABLE:
        logging.debug("pynput不可用，无法获取鼠标位置")
        return None
        
    if not mouse_controller: # 确保控制器已初始化
        try:
            mouse_controller = mouse.Controller()
        except Exception as e:
            logging.error(f"初始化鼠标控制器失败: {e}")
            return None
    try:
        return mouse_controller.position
    except Exception as e:
        # 处理 Wayland 等环境下 pynput 可能无法获取位置的问题
        if "DISPLAY environment variable not set" in str(e) or "Wayland" in str(e):
             logging.warning(f"无法获取鼠标位置 (可能在Wayland环境下或无显示服务): {e}")
        else:
            logging.error(f"获取鼠标位置失败: {e}")
        return None

def handle_omniparser_failure():
    """处理Omniparser服务失败，实现临时禁用机制"""
    global omniparser_consecutive_failures, omniparser_temporary_disabled
    
    omniparser_consecutive_failures += 1
    logging.warning(f"⚠️  Omniparser服务失败，连续失败次数: {omniparser_consecutive_failures}")
    
    if omniparser_consecutive_failures >= omniparser_max_failures:
        omniparser_temporary_disabled = True
        logging.warning(f"🚫 Omniparser服务连续失败{omniparser_consecutive_failures}次，临时禁用服务")
        logging.info(f"💡 将在接下来的请求中使用Tesseract OCR，服务恢复后会自动重新启用")

def extract_text_from_image(image_path):
    """
    从图像提取文本和视觉信息。
    优先使用Omniparser，如果失败或返回空则回退到Tesseract OCR。
    
    返回元组: (文本, 视觉元素JSON, 解析器类型)
    """
    global omniparser_request_count, tesseract_request_count, omniparser_consecutive_failures, omniparser_temporary_disabled
    
    logging.info(f"🔍 开始解析图像: {image_path}")
    
    try:
        # 优先使用Omniparser（如果可用且未被临时禁用）
        if USE_OMNIPARSER and not omniparser_temporary_disabled:
            logging.info(f"🚀 尝试使用Omniparser解析...")
            text, visual_elements = extract_with_omniparser(image_path)
            if text:
                omniparser_request_count += 1
                omniparser_consecutive_failures = 0  # 重置失败计数
                logging.info(f"✅ Omniparser成功解析 (第{omniparser_request_count}次请求)")
                return text, visual_elements, "omniparser"
            # 如果Omniparser返回空，回退到Tesseract
            logging.warning("⚠️  Omniparser返回空结果，回退到Tesseract OCR")
        elif omniparser_temporary_disabled:
            logging.info(f"⏸️  Omniparser服务临时禁用中({omniparser_consecutive_failures}次连续失败)，直接使用Tesseract OCR")
        else:
            logging.info(f"⚙️  Omniparser已禁用，直接使用Tesseract OCR")
        
        # 使用Tesseract OCR
        logging.info(f"🔤 开始使用Tesseract OCR解析...")
        tesseract_request_count += 1
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        word_count = len(text.split()) if text else 0
        char_count = len(text) if text else 0
        logging.info(f"✅ Tesseract解析完成 (第{tesseract_request_count}次): {word_count}个单词, {char_count}个字符")
        if text:
            logging.info(f"📄 Tesseract提取文本预览: '{text[:100]}{'...' if len(text) > 100 else ''}'")
        else:
            logging.warning(f"⚠️  Tesseract未提取到任何文本内容")
        return text, "", "tesseract"
    except Exception as e:
        logging.error(f"❌ 从图像提取文本失败 ({image_path}): {e}")
        return "", "", "failed"

def extract_with_omniparser(image_path):
    """
    使用Omniparser API从图像中提取结构化信息。
    返回元组: (合并后的文本描述, 原始结构化数据JSON字符串)
    """
    try:
        # 读取图像并转换为base64
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        # 准备请求数据
        payload = {"image_base64": image_data}
        
        # 记录开始调用服务端的日志
        logging.info(f"🚀 开始调用Omniparser服务: {OMNIPARSER_API_URL}")
        logging.info(f"📤 发送请求数据: 图像文件={image_path}, Base64数据长度={len(image_data)}字符")
        
        # 发送请求到Omniparser API
        response = requests.post(OMNIPARSER_API_URL, json=payload, timeout=30)
        
        # 记录服务端响应状态
        logging.info(f"📥 Omniparser服务响应: 状态码={response.status_code}, 响应时间={response.elapsed.total_seconds():.2f}秒")
        
        # 检查响应状态
        if response.status_code != 200:
            logging.error(f"❌ Omniparser API返回错误状态码: {response.status_code}")
            try:
                error_detail = response.text[:500]  # 限制错误信息长度
                logging.error(f"📄 API错误详情: {error_detail}")
            except:
                pass
            return "", ""
        
        # 记录原始响应内容（截断显示）
        response_preview = response.text[:300] if len(response.text) > 300 else response.text
        logging.info(f"📋 服务端返回原始数据预览: {response_preview}...")
        logging.info(f"📊 完整响应数据长度: {len(response.text)}字符")
        
        # 解析响应
        try:
            parsed_data = response.json()
            logging.info(f"✅ JSON解析成功, 数据类型: {type(parsed_data)}")
            if isinstance(parsed_data, list):
                logging.info(f"📝 解析结果: 列表类型，包含{len(parsed_data)}个元素")
            elif isinstance(parsed_data, dict):
                logging.info(f"📝 解析结果: 字典类型，包含键: {list(parsed_data.keys())}")
        except ValueError as e:
            logging.error(f"❌ Omniparser API返回无效JSON: {e}")
            logging.error(f"📄 响应内容: {response.text[:500]}")
            return "", ""
        
        # 检查返回数据是否有效
        if not parsed_data:
            logging.warning("⚠️  Omniparser API返回空数据")
            return "", ""
        
        # 提取并合并所有文本内容
        all_text = []
        
        # 记录数据处理过程
        logging.info(f"🔍 开始处理解析数据...")
        
        # 处理结构化数据，提取所有文本内容
        if isinstance(parsed_data, list):
            logging.info(f"📋 处理列表格式数据，共{len(parsed_data)}个项目")
            for i, item in enumerate(parsed_data):
                # 提取文本内容
                if isinstance(item, dict):
                    logging.debug(f"  项目{i+1}: {item}")
                    # 优先使用text字段
                    if "text" in item and item["text"]:
                        text_content = str(item["text"]).strip()
                        if text_content and text_content != "图像已处理，但未检测到文本内容":
                            all_text.append(text_content)
                            logging.info(f"  ✅ 项目{i+1}提取text: '{text_content[:50]}{'...' if len(text_content) > 50 else ''}'")
                    # 添加图标描述（避免重复）
                    elif "caption" in item and item["caption"]:
                        caption_text = str(item["caption"]).strip()
                        all_text.append(caption_text)
                        logging.info(f"  ✅ 项目{i+1}提取caption: '{caption_text[:50]}{'...' if len(caption_text) > 50 else ''}'")
                    # 添加其他可能的描述字段
                    elif "description" in item and item["description"]:
                        desc_text = str(item["description"]).strip()
                        all_text.append(desc_text)
                        logging.info(f"  ✅ 项目{i+1}提取description: '{desc_text[:50]}{'...' if len(desc_text) > 50 else ''}'")
                    else:
                        logging.info(f"  ⚠️  项目{i+1}无有效文本内容")
                elif isinstance(item, str) and item.strip():
                    all_text.append(item.strip())
                    logging.info(f"  ✅ 项目{i+1}直接字符串: '{item.strip()[:50]}{'...' if len(item.strip()) > 50 else ''}'")
        elif isinstance(parsed_data, dict):
            logging.info(f"📋 处理字典格式数据")
            # 兼容旧的字典格式 - 直接处理字典内容
            if "text" in parsed_data and parsed_data["text"]:
                text_content = str(parsed_data["text"]).strip()
                all_text.append(text_content)
                logging.info(f"  ✅ 提取text: '{text_content[:50]}{'...' if len(text_content) > 50 else ''}'")
            if "caption" in parsed_data and parsed_data["caption"]:
                caption_text = str(parsed_data["caption"]).strip()
                all_text.append(caption_text)
                logging.info(f"  ✅ 提取caption: '{caption_text[:50]}{'...' if len(caption_text) > 50 else ''}'")
            if "description" in parsed_data and parsed_data["description"]:
                desc_text = str(parsed_data["description"]).strip()
                all_text.append(desc_text)
                logging.info(f"  ✅ 提取description: '{desc_text[:50]}{'...' if len(desc_text) > 50 else ''}'")
        
        # 过滤空字符串并合并所有文本
        all_text = [text for text in all_text if text]
        combined_text = " ".join(all_text)
        
        logging.info(f"📝 文本提取完成: 共提取{len(all_text)}个文本片段，合并后总长度{len(combined_text)}字符")
        
        # 将原始结构化数据转换为JSON字符串
        try:
            structured_data_json = json.dumps(parsed_data, ensure_ascii=False)
            logging.info(f"✅ 结构化数据JSON序列化成功，长度: {len(structured_data_json)}字符")
        except (TypeError, ValueError) as e:
            logging.error(f"❌ 无法序列化Omniparser返回数据为JSON: {e}")
            structured_data_json = ""
        
        if combined_text:
            logging.info(f"🎉 Omniparser成功解析图像，提取了 {len(all_text)} 个元素，总文本长度: {len(combined_text)}")
            logging.info(f"📄 最终合并文本预览: '{combined_text[:100]}{'...' if len(combined_text) > 100 else ''}'")
        else:
            logging.warning("⚠️  Omniparser解析成功但未提取到任何文本内容")
        
        return combined_text, structured_data_json
    
    except requests.exceptions.Timeout:
        handle_omniparser_failure()
        logging.error(f"⏰ Omniparser API请求超时 ({image_path})")
        logging.error(f"💡 建议检查网络连接或增加超时时间")
        return "", ""
    except requests.exceptions.ConnectionError:
        handle_omniparser_failure()
        logging.error(f"🔌 无法连接到Omniparser服务 ({OMNIPARSER_API_URL})")
        logging.error(f"💡 建议检查服务是否启动: docker ps | grep omniparser")
        return "", ""
    except requests.exceptions.RequestException as e:
        handle_omniparser_failure()
        logging.error(f"📡 Omniparser API请求失败 ({image_path}): {e}")
        return "", ""
    except FileNotFoundError:
        logging.error(f"📁 图像文件不存在: {image_path}")
        return "", ""
    except Exception as e:
        handle_omniparser_failure()
        logging.error(f"❌ 使用Omniparser解析图像失败 ({image_path}): {e}", exc_info=True)
        return "", ""

def extract_url_from_text(text):
    """
    从OCR文本中提取URL。
    使用正则表达式匹配常见的URL模式。
    返回找到的第一个URL，如果没有找到则返回None。
    """
    if not text:
        return None
    
    # URL正则表达式模式
    url_patterns = [
        # 完整URL（http/https开头）
        r'https?://[^\s<>"\']+',
        # 常见域名格式（www开头）
        r'www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s<>"\']*)?',
        # 简单域名格式
        r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s<>"\']*)?'
    ]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # 返回第一个匹配的URL
            url = matches[0]
            # 如果URL不以http开头，添加https前缀
            if not url.startswith(('http://', 'https://')):
                if url.startswith('www.'):
                    url = 'https://' + url
                else:
                    # 简单验证是否像URL（包含点和有效字符）
                    if '.' in url and len(url.split('.')) >= 2:
                        url = 'https://' + url
                    else:
                        continue  # 跳过这个匹配，尝试下一个
            
            logging.info(f"从OCR文本中提取到URL: {url}")
            return url
    
    logging.debug("未能从OCR文本中提取到有效的URL")
    return None

def get_url_from_browser(hwnd, app_name):
    """
    使用UI Automation尝试从浏览器窗口获取当前URL。
    此功能依赖 uiautomation 库，可能不稳定，且在不同浏览器/版本上表现不一。
    """
    if not UIAUTOMATION_AVAILABLE or not hwnd:
        return None

    url = None
    try:
        # 将搜索超时设置得较短，以避免在找不到控件时长时间阻塞。
        auto.SetGlobalSearchTimeout(1.0)
        
        window_control = auto.ControlFromHandle(hwnd)

        # 适用于大多数基于Chromium的浏览器 (Chrome, Edge, etc.)
        if app_name in ["Chrome", "Edge", "msedge", "Chromium", "Brave", "Opera", "Cursor"]:
            # 优先查找 Toolbar，地址栏通常在其中
            toolbar = window_control.ToolBarControl()
            if toolbar.Exists(0.1, 0.1):
                address_bar = toolbar.EditControl()
                if address_bar.Exists(0.1, 0.1):
                    url = address_bar.GetValuePattern().Value
            
            # 如果在工具栏中找不到，使用旧的名称查找方法作为回退
            if not url:
                logging.debug(f"在工具栏中未找到地址栏，回退到按名称搜索...")
                address_bar_by_name = window_control.EditControl(Name='Address and search bar')
                if not address_bar_by_name.Exists(0.1, 0.1):
                    address_bar_by_name = window_control.EditControl(Name='地址与搜索栏')
                
                if address_bar_by_name.Exists(0.1, 0.1):
                    url = address_bar_by_name.GetValuePattern().Value

        # 适用于Firefox
        elif app_name == "Firefox":
            doc_control = window_control.DocumentControl(searchDepth=16)
            if doc_control and doc_control.Exists(0.1, 0.1):
                try:
                    url = doc_control.GetValuePattern().Value
                except Exception:
                    pass

        if url:
            url = url.strip()
            # 简单的验证，确保它看起来像一个URL（不包含空格等）
            if ' ' in url or not (url.startswith('http') or '://' in url or '.' in url):
                logging.warning(f"获取到的值 '{url}' 不像一个有效的URL，已忽略。")
                url = None
            else:
                 logging.info(f"成功从 {app_name} 获取URL: {url}")
                 return url
        
        logging.warning(f"未能从 {app_name} (HWND: {hwnd}) 获取到URL。")

    except Exception as e:
        # 减少日志噪音，只在DEBUG模式下显示完整堆栈
        logging.error(f"从浏览器获取URL时发生未知错误: {e}", exc_info=logging.getLogger().level == logging.DEBUG)
    finally:
        # 恢复默认的全局超时设置
        auto.SetGlobalSearchTimeout(auto.TIME_OUT_SECOND)
        
    return None

def capture_screenshot(filename_prefix="screenshot", window_rect=None, app_name="Unknown"):
    """
    捕获屏幕截图。如果提供了window_rect，则捕获该区域。
    对于已知浏览器，会尝试裁剪掉顶部的UI元素（标签栏、地址栏等）。
    在多显示器环境下，智能识别窗口所在显示器，避免截取多个显示器内容。
    返回截图文件的路径。
    """
    try:
        with mss.mss() as sct:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.png"
            filepath = os.path.join(SCREENSHOT_DIR, filename)
            
            sct_img = None
            capture_details = "N/A"
            target_monitor = None  # 用于存储目标显示器信息

            # 如果有窗口矩形信息，先尝试智能确定目标显示器
            if window_rect:
                target_monitor = determine_window_monitor(sct, window_rect)
                logging.debug(f"根据窗口矩形 {window_rect} 确定目标显示器: {target_monitor}")

            if window_rect:
                left, top, right, bottom = window_rect

                # -- 浏览器UI裁剪启发式逻辑 --
                browser_apps = ["Chrome", "Firefox", "Edge", "msedge", "Chromium", "Brave", "Opera", "Cursor"]
                if app_name in browser_apps:
                    # 从顶部裁剪一个固定的像素值，以尝试移除标签栏、地址栏和书签栏。
                    # 这个值是一个估计值，可能需要根据屏幕分辨率或浏览器设置进行调整。
                    top_crop_pixels = 130 
                    if (bottom - (top + top_crop_pixels)) > 50: # 确保截图仍有足够的高度
                        top += top_crop_pixels
                        logging.info(f"检测到浏览器 '{app_name}'。自动从截图顶部裁剪 {top_crop_pixels}px。")
                # -- 裁剪逻辑结束 --

                width = right - left
                height = bottom - top
                
                # 确保捕获区域有实际大小 (mss可能会对0或负值报错)
                MIN_CAPTURE_DIMENSION = 1
                if width >= MIN_CAPTURE_DIMENSION and height >= MIN_CAPTURE_DIMENSION:
                    capture_region = {'top': top, 'left': left, 'width': width, 'height': height}
                    try:
                        logging.info(f"尝试截取指定窗口区域: {capture_region}")
                        sct_img = sct.grab(capture_region)
                        capture_details = f"窗口区域: {capture_region}"
                    except mss.exception.ScreenShotError as e_grab:
                        logging.warning(f"使用mss.grab()截取窗口区域 {capture_region} 失败: {e_grab}. 将回退到智能显示器截图。")
                        sct_img = None # 确保sct_img为None以触发回退
                    except Exception as e_grab_other:
                        logging.warning(f"截取窗口区域 {capture_region} 时发生意外错误: {e_grab_other}. 将回退到智能显示器截图。")
                        sct_img = None
                else:
                    logging.warning(f"提供的窗口矩形 {window_rect} 尺寸过小或无效 (宽:{width}, 高:{height})。将回退到智能显示器截图。")
            
            # 智能回退策略：截取窗口所在的显示器，而不是所有显示器
            if sct_img is None:
                if target_monitor:
                    # 如果已经确定了目标显示器，使用它
                    monitor_to_capture = target_monitor
                    logging.info(f"使用已确定的目标显示器进行截图: {monitor_to_capture}")
                else:
                    # 如果没有窗口信息，使用默认策略
                    monitor_to_capture = get_primary_monitor(sct)
                    logging.info(f"无窗口信息，使用主显示器进行截图: {monitor_to_capture}")

                if monitor_to_capture:
                    try:
                        sct_img = sct.grab(monitor_to_capture)
                        capture_details = f"显示器全屏: {monitor_to_capture}"
                    except Exception as e_monitor:
                        logging.error(f"截取显示器 {monitor_to_capture} 失败: {e_monitor}")
                        # 最后的回退：尝试主显示器
                        try:
                            fallback_monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                            sct_img = sct.grab(fallback_monitor)
                            capture_details = f"回退显示器: {fallback_monitor}"
                            logging.warning(f"使用回退显示器进行截图: {fallback_monitor}")
                        except Exception as e_fallback:
                            logging.error(f"回退显示器截图也失败: {e_fallback}")
                            return None
                else:
                    logging.error("无法确定任何可用的显示器，截图失败。")
                    return None

            if sct_img:
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img.save(filepath)
                logging.info(f"截图已保存到 {filepath} (截图方式: {capture_details})")
                return filepath
            else:
                logging.error("未能生成sct_img对象，截图失败。")
                return None

    except Exception as e:
        logging.error(f"截图过程中发生严重错误: {e}", exc_info=True)
        return None

def determine_window_monitor(sct, window_rect):
    """
    根据窗口矩形坐标，确定窗口主要位于哪个显示器上。
    返回对应的显示器信息字典，如果无法确定则返回None。
    """
    if not window_rect or len(window_rect) < 4:
        return None
    
    left, top, right, bottom = window_rect
    window_center_x = (left + right) // 2
    window_center_y = (top + bottom) // 2
    window_area = (right - left) * (bottom - top)
    
    best_monitor = None
    max_overlap_area = 0
    
    # 遍历所有显示器（跳过索引0，它通常是所有显示器的组合）
    for i, monitor in enumerate(sct.monitors[1:], 1):
        monitor_left = monitor['left']
        monitor_top = monitor['top'] 
        monitor_right = monitor_left + monitor['width']
        monitor_bottom = monitor_top + monitor['height']
        
        # 计算窗口与显示器的重叠区域
        overlap_left = max(left, monitor_left)
        overlap_top = max(top, monitor_top)
        overlap_right = min(right, monitor_right)
        overlap_bottom = min(bottom, monitor_bottom)
        
        # 如果有重叠
        if overlap_left < overlap_right and overlap_top < overlap_bottom:
            overlap_area = (overlap_right - overlap_left) * (overlap_bottom - overlap_top)
            
            # 如果这个显示器有更大的重叠面积，或者窗口中心在这个显示器内
            center_in_monitor = (monitor_left <= window_center_x <= monitor_right and 
                               monitor_top <= window_center_y <= monitor_bottom)
            
            if overlap_area > max_overlap_area or (center_in_monitor and overlap_area > 0):
                max_overlap_area = overlap_area
                best_monitor = monitor
                logging.debug(f"显示器 {i} 有更好的匹配: 重叠面积={overlap_area}, 中心在内={center_in_monitor}")
    
    if best_monitor:
        logging.info(f"窗口 {window_rect} 主要位于显示器: {best_monitor}")
    else:
        logging.warning(f"无法为窗口 {window_rect} 确定对应的显示器")
    
    return best_monitor

def get_primary_monitor(sct):
    """
    获取主显示器信息。
    在多显示器环境下，返回主显示器；单显示器环境下，返回唯一的显示器。
    """
    monitors = sct.monitors
    
    if len(monitors) > 1:
        # 多显示器：返回第一个真实显示器（索引1）
        primary_monitor = monitors[1]
        logging.debug(f"多显示器环境，选择主显示器: {primary_monitor}")
        return primary_monitor
    elif len(monitors) == 1:
        # 单显示器：返回唯一的显示器
        single_monitor = monitors[0]
        logging.debug(f"单显示器环境: {single_monitor}")
        return single_monitor
    else:
        logging.error("未检测到任何显示器")
        return None

def get_active_window_info():
    """
    获取当前活动窗口的信息。
    返回窗口标题, 进程名, 应用名, 页面标题 (如果是浏览器/IDE等), PID, 和窗口矩形。
    """
    window_title = "Unknown"
    process_name = "Unknown"
    app_name = "Unknown"
    page_title = None
    url = None # <--- 新增: 初始化url变量
    pid = None
    window_rect = None # 新增：用于存储窗口矩形 (left, top, right, bottom)

    try:
        active_window_hwnd = None
        if PYWIN32_AVAILABLE:
            active_window_hwnd = win32gui.GetForegroundWindow()
            if active_window_hwnd:
                window_title = win32gui.GetWindowText(active_window_hwnd) if win32gui.GetWindowText(active_window_hwnd) else "Untitled"
                _, pid = win32process.GetWindowThreadProcessId(active_window_hwnd)
                logging.debug(f"pywin32: HWND={active_window_hwnd}, PID={pid}, Window Title='{window_title}'")

                # 尝试获取窗口矩形
                try:
                    if win32gui.IsWindowVisible(active_window_hwnd) and not win32gui.IsIconic(active_window_hwnd):
                        rect = win32gui.GetWindowRect(active_window_hwnd)
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        
                        # 定义合理的最小窗口尺寸，降低限制以支持更多窗口类型
                        MIN_VALID_WINDOW_WIDTH = 100   # 从150降低到100
                        MIN_VALID_WINDOW_HEIGHT = 80   # 从100降低到80

                        if width >= MIN_VALID_WINDOW_WIDTH and height >= MIN_VALID_WINDOW_HEIGHT:
                            window_rect = rect
                            logging.debug(f"获取到活动窗口矩形: {window_rect} (宽度: {width}, 高度: {height})")
                        elif width > 0 and height > 0: # 窗口有效但较小
                            # 对于小窗口，也尝试记录，但添加警告
                            window_rect = rect
                            logging.info(f"活动窗口 HWND {active_window_hwnd} 尺寸较小 ({width}x{height})，仍用于截图但可能效果不佳。")
                        else: # 无效尺寸
                            logging.warning(f"活动窗口 HWND {active_window_hwnd} 尺寸无效 ({width}x{height})，不用于区域截图。")
                    elif not win32gui.IsWindowVisible(active_window_hwnd):
                        logging.info(f"活动窗口 HWND {active_window_hwnd} 不可见，不获取矩形。")
                    else: # IsIconic (最小化)
                        logging.info(f"活动窗口 HWND {active_window_hwnd} 已最小化，不获取矩形。")
                except Exception as e_rect:
                    logging.error(f"获取窗口 HWND {active_window_hwnd} 的矩形时出错: {e_rect}")
                    # 尝试使用另一种方法获取窗口信息作为回退
                    try:
                        # 使用 GetClientRect 作为回退方案
                        client_rect = win32gui.GetClientRect(active_window_hwnd)
                        if client_rect and len(client_rect) == 4:
                            # GetClientRect返回的是相对坐标，需要转换为屏幕坐标
                            left_top = win32gui.ClientToScreen(active_window_hwnd, (client_rect[0], client_rect[1]))
                            right_bottom = win32gui.ClientToScreen(active_window_hwnd, (client_rect[2], client_rect[3]))
                            fallback_rect = (left_top[0], left_top[1], right_bottom[0], right_bottom[1])
                            
                            fallback_width = fallback_rect[2] - fallback_rect[0]
                            fallback_height = fallback_rect[3] - fallback_rect[1]
                            
                            if fallback_width > 50 and fallback_height > 50:  # 更宽松的回退条件
                                window_rect = fallback_rect
                                logging.info(f"使用ClientRect回退方案获取窗口矩形: {window_rect} ({fallback_width}x{fallback_height})")
                    except Exception as e_fallback:
                        logging.debug(f"ClientRect回退方案也失败: {e_fallback}")
            else:
                logging.warning("win32gui.GetForegroundWindow() 未返回有效的窗口句柄。")
                window_title = "No Active Window (pywin32)"
                # 在这种情况下，无法获取窗口矩形，window_rect 将保持 None
                # return {"title": window_title, ..., "window_rect": None} # 早期返回
        else: # 回退到 pygetwindow
            active_window_gw = gw.getActiveWindow()
            if not active_window_gw:
                logging.warning("gw.getActiveWindow() 未返回活动窗口。")
                window_title = "No Active Window (pygetwindow)"
                # return {"title": window_title, ..., "window_rect": None} # 早期返回
            else:
                window_title = active_window_gw.title if active_window_gw.title else "Untitled"
                # pygetwindow 获取精确PID和可靠的窗口矩形较为困难，通常不直接支持
                logging.warning("pywin32不可用，使用pygetwindow回退。精确的窗口区域截图将不可用，将进行全屏截图。")


        # --- 进程名和应用名提取逻辑 (基本保持不变) ---
        if pid:
            try:
                p = psutil.Process(pid)
                process_name = p.name()
    
                if process_name and process_name != "Unknown":
                    base_name_original_case = process_name.split('.')[0]
                    base_name_lower = base_name_original_case.lower() 
                    
                    if "qq" in window_title.lower() or (process_name and "qq" in process_name.lower()):
                        logging.info(f"QQ_DETECTION_DEBUG: WindowTitle='{window_title}', OriginalProcessName='{process_name}', BaseNameOriginalCase='{base_name_original_case}', BaseNameLower='{base_name_lower}'")
                    
                    if base_name_lower in KNOWN_APP_CASINGS:
                        app_name = KNOWN_APP_CASINGS[base_name_lower]
                        if "qq" in window_title.lower() or (process_name and "qq" in process_name.lower()):
                            logging.info(f"QQ_DETECTION_DEBUG: Matched KNOWN_APP_CASINGS. AppName set to '{app_name}' from key '{base_name_lower}'.")
                    else:
                        app_name = base_name_original_case.capitalize()
                        if "qq" in window_title.lower() or (process_name and "qq" in process_name.lower()):
                            logging.info(f"QQ_DETECTION_DEBUG: No match in KNOWN_APP_CASINGS. AppName set to '{app_name}' by capitalizing '{base_name_original_case}'.")
                else:
                    app_name = "Unknown"
                logging.info(f"PSUTIL_APP_NAME_INFO: PID='{pid}', OriginalProcess='{process_name}', DeterminedAppName='{app_name}'")

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e_psutil:
                logging.warning(f"无法通过PID '{pid}' 获取进程信息 (窗口: '{window_title}'). 错误: {e_psutil}.")
            except Exception as e_psutil_other:
                logging.error(f"使用 psutil.Process(pid={pid}) 时发生意外错误 (窗口: '{window_title}'): {e_psutil_other}")
        elif PYWIN32_AVAILABLE and not pid and active_window_hwnd : # pywin32可用但未能从有效窗口获取pid
            logging.warning(f"pywin32可用，但未能从窗口 '{window_title}' (HWND: {active_window_hwnd}) 获取PID。")
        
        # --- 页面标题提取逻辑 (基本保持不变) ---
        if app_name not in ["Unknown", "System", "No Active Window (pywin32)", "No Active Window (pygetwindow)"]:
            apps_with_page_titles = ["Chrome", "Firefox", "Edge", "Safari", "Chromium", "Brave", "Opera",
                                     "Code", "PyCharm", "Sublime_text", "Notepad++", "Explorer", "msedge", "Cursor"]
            is_target_app_type = app_name in apps_with_page_titles
            if not is_target_app_type and process_name != "Unknown":
                for app_key in apps_with_page_titles:
                    if app_key.lower() in process_name.lower():
                        is_target_app_type = True
                        break
            if is_target_app_type:
                temp_page_title = window_title
                suffix1 = f" - {app_name}"
                if temp_page_title.endswith(suffix1):
                    temp_page_title = temp_page_title[:-len(suffix1)].strip()
                if process_name != "Unknown" and not process_name.lower().startswith(app_name.lower()):
                    process_base_name = process_name.split('.')[0].capitalize()
                    if process_base_name != app_name :
                        suffix2 = f" - {process_base_name}"
                        if temp_page_title.endswith(suffix2):
                             temp_page_title = temp_page_title[:-len(suffix2)].strip()
                if temp_page_title and temp_page_title != window_title and temp_page_title.lower() != app_name.lower():
                    page_title = temp_page_title
                elif temp_page_title and temp_page_title == window_title and app_name == "Explorer": 
                    page_title = window_title

        # --- 新增：URL提取逻辑 ---
        browser_apps = ["Chrome", "Firefox", "Edge", "Safari", "Chromium", "Brave", "Opera", "msedge", "Cursor"]
        if app_name in browser_apps and active_window_hwnd:
            url = get_url_from_browser(active_window_hwnd, app_name)

    except AttributeError as e_attr:
        logging.error(f"获取活动窗口信息时发生 AttributeError: {e_attr}", exc_info=True)
        # 错误不应覆盖已获取的数据。保留已有的 window_title (如果有的话)
    except Exception as e_top:
        logging.error(f"获取活动窗口信息时发生顶层异常: {e_top}", exc_info=True)
        # 同样，不在这里覆盖标题

    mouse_pos = get_mouse_position()
    
    return {
        "title": window_title,
        "process_name": process_name,
        "app_name": app_name,
        "page_title": page_title,
        "url": url, # <--- 新增：将URL添加到返回字典
        "pid": pid,
        "mouse_x": mouse_pos[0] if mouse_pos else None,
        "mouse_y": mouse_pos[1] if mouse_pos else None,
        "window_rect": window_rect # <--- 新增：将窗口矩形添加到返回字典
    }

def save_record(record_data):
    """
    将单条记录保存到SQLite数据库中。
    使用锁来确保线程安全。
    返回新插入记录的ID，如果失败则返回None。
    """
    global record_file_lock
    
    columns = [
        'timestamp', 'record_type', 'triggered_by', 'event_type', 
        'window_title', 'process_name', 'app_name', 'page_title', 'url', 'pid',
        'from_app', 'to_app', 'to_app_title', 
        'screenshot_path', 'ocr_text', 'visual_elements', 'parser_type',
        'mouse_x', 'mouse_y', 'button', 'pressed'
    ]
    
    data_tuple = (
        record_data.get('timestamp'),
        record_data.get('record_type'),
        record_data.get('triggered_by'),
        record_data.get('event_type'),
        record_data.get('window_title'),
        record_data.get('process_name'),
        record_data.get('app_name'),
        record_data.get('page_title'),
        record_data.get('url'),
        record_data.get('pid'),
        record_data.get('from_app'),
        record_data.get('to_app'),
        record_data.get('to_app_title'),
        record_data.get('screenshot_path'),
        record_data.get('ocr_text'),
        record_data.get('visual_elements'),  # 新增：视觉元素JSON
        record_data.get('parser_type'),      # 新增：解析器类型
        record_data.get('mouse_x'),
        record_data.get('mouse_y'),
        record_data.get('button'),
        1 if record_data.get('pressed') else 0
    )

    sql = f"INSERT INTO activity_log ({', '.join(columns)}) VALUES ({', '.join(['?'] * len(columns))})"
    record_id = None # 初始化 record_id

    try:
        with record_file_lock: 
            conn = create_connection(DATABASE_FILE)
            if conn is None:
                logging.error("保存记录失败：无法连接到数据库。")
                return None # 修改：返回 None
            
            cursor = conn.cursor()
            cursor.execute(sql, data_tuple)
            record_id = cursor.lastrowid # 获取自增ID
            conn.commit()
            logging.info(f"记录已保存到数据库 (ID: {record_id})")
            return record_id # 修改：返回 record_id
    except sqlite3.Error as e:
        logging.error(f"保存记录到数据库失败: {e}. SQL: {sql}, Data: {data_tuple}", exc_info=True)
        return None # 修改：返回 None
    except Exception as e_global: 
        logging.error(f"保存记录时发生意外错误: {e_global}. Data: {record_data}", exc_info=True)
        return None # 修改：返回 None
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def print_parser_stats():
    """定期打印解析器使用统计"""
    global last_stats_time, omniparser_request_count, tesseract_request_count
    
    current_time = time.time()
    # 每5分钟打印一次统计
    if current_time - last_stats_time > 300:  # 300秒 = 5分钟
        total_requests = omniparser_request_count + tesseract_request_count
        if total_requests > 0:
            omni_percentage = (omniparser_request_count / total_requests) * 100
            tesseract_percentage = (tesseract_request_count / total_requests) * 100
            
            logging.info(f"📊 解析器使用统计: Omniparser {omniparser_request_count}次({omni_percentage:.1f}%), "
                        f"Tesseract {tesseract_request_count}次({tesseract_percentage:.1f}%)")
        
        last_stats_time = current_time

def record_screen_activity(triggered_by="timer"):
    """
    捕获屏幕、提取文本、保存记录，并索引到向量数据库。
    """
    global last_active_app_name, last_window_title
    
    # 定期打印统计信息
    print_parser_stats() 
    timestamp = datetime.now().isoformat()
    window_info = get_active_window_info() 
    current_app_name = window_info.get("app_name", "Unknown")
    current_window_title = window_info.get("title", "Unknown")
    current_url = window_info.get("url") # 获取URL
    mouse_x = window_info.get("mouse_x")
    mouse_y = window_info.get("mouse_y")
    pid_from_window_info = window_info.get("pid")
    active_window_rect = window_info.get("window_rect") 

    app_changed = current_app_name != last_active_app_name and current_app_name != "Unknown"

    if app_changed:
        event_record = {
            "timestamp": timestamp,
            "event_type": "app_switch", 
            "record_type": "app_switch", 
            "from_app": last_active_app_name if last_active_app_name else "None",
            "to_app": current_app_name,
            "to_app_title": current_window_title, 
            "url": current_url,
            "mouse_x": mouse_x,
            "mouse_y": mouse_y,
            "pid": pid_from_window_info, 
            "ocr_text": f"Switched from {last_active_app_name if last_active_app_name else 'Unknown'} to {current_app_name} ({current_window_title})",
            "visual_elements": "",  # 应用切换事件没有视觉元素
            "parser_type": "none"   # 应用切换事件不需要解析器
        }
        logging.info(f"检测到应用切换: 从 {last_active_app_name} 到 {current_app_name} ({current_window_title})")
        
        saved_event_id = save_record(event_record) 
        if saved_event_id is not None:
            event_record['id'] = saved_event_id 
            logging.debug(f"DEBUG: Calling index_single_activity_record for event_record with ID: {event_record.get('id')}") 
            
            # 只有在启用向量索引时才尝试索引
            if ENABLE_VECTOR_INDEXING:
                try:
                    index_single_activity_record(event_record)
                    logging.info("应用切换事件已成功索引到向量数据库")
                except Exception as e:
                    logging.error(f"索引应用切换事件时出错: {e}")
                    logging.info("应用切换事件已保存到主数据库，向量索引将在下次重启时重建")
            else:
                logging.debug("向量索引已禁用，跳过应用切换事件的向量索引")
        else:
            logging.error("应用切换事件未能保存到主数据库")
        
        last_active_app_name = current_app_name
        last_window_title = current_window_title
    elif current_app_name != "Unknown" and last_active_app_name is None : 
        last_active_app_name = current_app_name
        last_window_title = current_window_title
    
    screenshot_path = capture_screenshot(
        filename_prefix="screenshot",
        window_rect=active_window_rect, 
        app_name=current_app_name
    )
    if not screenshot_path:
        logging.error("截图失败，跳过本次记录")
        return
    
    # 使用新的提取函数获取文本和视觉元素
    ocr_text, visual_elements, parser_type = extract_text_from_image(screenshot_path)

    # --- 从OCR文本中回退提取URL ---
    if not current_url and ocr_text:
        logging.info("UI自动化未能获取URL，尝试从OCR文本中提取...")
        current_url = extract_url_from_text(ocr_text)
    
    if not ocr_text and triggered_by == "timer": 
        logging.warning(f"图像解析 (定时器触发) 未识别到有效内容，跳过记录")
        return
    
    activity_content_record = {
        "timestamp": timestamp,
        "record_type": "screen_content", 
        "triggered_by": "app_switch" if app_changed else triggered_by, 
        "window_title": window_info.get("title", "Unknown"), 
        "process_name": window_info.get("process_name", "Unknown"),
        "app_name": window_info.get("app_name", "Unknown"),
        "page_title": window_info.get("page_title"), 
        "url": current_url,
        "pid": pid_from_window_info, 
        "screenshot_path": screenshot_path,
        "ocr_text": ocr_text, 
        "visual_elements": visual_elements,  # 新增：存储视觉元素JSON
        "parser_type": parser_type,          # 新增：标记使用的解析器类型
        "mouse_x": mouse_x,
        "mouse_y": mouse_y
    }
    
    if not ocr_text and app_changed:
        logging.warning(f"应用切换到 '{current_app_name}'，但初始屏幕解析为空。仍记录窗口信息。")
    elif not ocr_text : 
        pass

    saved_content_id = save_record(activity_content_record)
    if saved_content_id is not None:
        activity_content_record['id'] = saved_content_id
        logging.debug(f"DEBUG: Calling index_single_activity_record for activity_content_record with ID: {activity_content_record.get('id')}") 
        
        # 只有在启用向量索引时才尝试索引
        if ENABLE_VECTOR_INDEXING:
            try:
                logging.info(f"尝试将屏幕内容记录 ({activity_content_record['record_type']}) 索引到向量数据库...")
                index_result = index_single_activity_record(activity_content_record)
                if index_result:
                    logging.info(f"屏幕内容记录 ({activity_content_record['record_type']}) 已成功索引")
                else:
                    logging.warning(f"屏幕内容记录 ({activity_content_record['record_type']}) 未能成功索引，但已保存到主数据库")
            except Exception as e:
                logging.error(f"索引屏幕内容记录 ({activity_content_record['record_type']}) 时出错: {e}")
                logging.info("记录已保存到主数据库，向量索引将在下次重启时重建")
        else:
            logging.debug("向量索引已禁用，跳过屏幕内容记录的向量索引")
    else:
        logging.error(f"屏幕内容记录 ({activity_content_record['record_type']}) 未能保存到主数据库")

def process_click_task(task_data):
    """
    在工作线程中处理单个鼠标点击任务（截图, 解析, 保存, 索引）。
    """
    x = task_data["x"]
    y = task_data["y"]
    button_str = task_data["button"]
    timestamp_iso = task_data["timestamp"]

    logging.info(f"工作线程开始处理点击任务: ({x}, {y}), button: {button_str}")

    window_info = get_active_window_info() 
    current_app_name = window_info.get("app_name", "Unknown")
    current_url = window_info.get("url")
    active_window_rect = window_info.get("window_rect") 
    click_mouse_x = x 
    click_mouse_y = y
    pid_from_window_info = window_info.get("pid")

    screenshot_path = capture_screenshot(
        filename_prefix="mouse_click", 
        window_rect=active_window_rect,
        app_name=current_app_name
    )
    if not screenshot_path:
        logging.error("鼠标点击事件 (工作线程)：截图失败，跳过记录")
        return

    # 使用新的提取函数获取文本和视觉元素
    ocr_text, visual_elements, parser_type = extract_text_from_image(screenshot_path)

    # --- 从OCR文本中回退提取URL ---
    if not current_url and ocr_text:
        logging.info("UI自动化未能获取URL(点击事件)，尝试从OCR文本中提取...")
        current_url = extract_url_from_text(ocr_text)

    click_event_record = {
        "timestamp": timestamp_iso, 
        "record_type": "mouse_interaction",
        "triggered_by": "mouse_click",
        "window_title": window_info.get("title", "Unknown"),
        "process_name": window_info.get("process_name", "Unknown"),
        "app_name": window_info.get("app_name", "Unknown"),
        "page_title": window_info.get("page_title"),
        "url": current_url, # 使用可能已通过OCR更新的URL
        "pid": pid_from_window_info, 
        "screenshot_path": screenshot_path,
        "ocr_text": ocr_text if ocr_text else "",
        "visual_elements": visual_elements,  # 新增：存储视觉元素JSON
        "parser_type": parser_type,          # 新增：标记使用的解析器类型
        "mouse_x": click_mouse_x,
        "mouse_y": click_mouse_y,
        "button": button_str, 
        "pressed": True, 
    }

    saved_click_id = save_record(click_event_record) 
    if saved_click_id is not None:
        click_event_record['id'] = saved_click_id 
        logging.debug(f"DEBUG: Calling index_single_activity_record for click_event_record with ID: {click_event_record.get('id')}") 
        
        # 只有在启用向量索引时才尝试索引
        if ENABLE_VECTOR_INDEXING:
            try:
                logging.info("尝试将鼠标交互记录 (工作线程) 索引到向量数据库...")
                index_result = index_single_activity_record(click_event_record)
                if index_result:
                    logging.info("鼠标交互记录 (工作线程) 已成功索引")
                else:
                    logging.warning("鼠标交互记录 (工作线程) 未能成功索引，但已保存到主数据库")
            except Exception as e:
                logging.error(f"索引鼠标交互记录 (工作线程) 时出错: {e}")
                logging.info("记录已保存到主数据库，向量索引将在下次重启时重建")
        else:
            logging.debug("向量索引已禁用，跳过鼠标交互记录的向量索引")
    else:
        logging.error("鼠标交互记录 (工作线程) 未能保存到主数据库")

def click_processing_worker():
    """工作线程函数，从队列中获取并处理鼠标点击任务。"""
    logging.info("鼠标点击处理工作线程已启动。")
    while True:
        try:
            task_data = click_task_queue.get() # 阻塞直到获取任务
            if task_data is None: # 接收到终止信号
                logging.info("鼠标点击处理工作线程收到终止信号，正在退出。")
                click_task_queue.task_done()
                break
            
            process_click_task(task_data)
            click_task_queue.task_done() # 标记任务完成
        except Exception as e:
            logging.error(f"鼠标点击处理工作线程发生错误: {e}", exc_info=True)
            # 即使发生错误，也应标记任务完成，以避免队列阻塞
            if 'task_data' in locals() and task_data is not None: # 确保 task_done 被调用
                 click_task_queue.task_done()

def handle_mouse_click_activity(x, y, button, pressed):
    """处理鼠标点击事件，将任务放入队列。"""
    global last_mouse_click_screenshot_time
    if not pressed: # 只处理按下事件
        return

    current_time = time.time()
    if current_time - last_mouse_click_screenshot_time < MOUSE_CLICK_CAPTURE_INTERVAL_SECONDS:
        # logging.debug("鼠标点击过于频繁，跳过此次截图")
        return
    last_mouse_click_screenshot_time = current_time
    
    # 只记录信息并放入队列，不在此处执行耗时操作
    logging.info(f"鼠标点击事件已捕获: ({x}, {y}), button: {button}. 将任务放入队列。")
    
    task_data = {
        "x": x,
        "y": y,
        "button": str(button),
        "timestamp": datetime.now().isoformat() # 记录事件发生的时间
    }
    click_task_queue.put(task_data)

def start_mouse_listener():
    """启动pynput鼠标监听器。"""
    global mouse_controller
    
    if not PYNPUT_AVAILABLE:
        logging.error("pynput库不可用，无法启动鼠标监听器。鼠标点击触发的截图功能将被禁用。")
        return
    
    try:
        mouse_controller = mouse.Controller() # 初始化一次，供get_mouse_position使用
        logging.info("鼠标控制器初始化成功。")
    except Exception as e:
        logging.error(f"启动时初始化鼠标控制器失败 (可能是Wayland/无头环境): {e}")
        # 即使控制器初始化失败，监听器可能仍然可以工作（取决于环境）
        # 或者 get_mouse_position 将持续返回 None

    logging.info("启动鼠标点击监听器...")
    try:
        # 使用 with 语句确保监听器在线程结束时正确停止
        with mouse.Listener(on_click=handle_mouse_click_activity) as listener:
            listener.join()
    except Exception as e:
        # 特别处理在某些Linux环境下（如Wayland或无X服务器）pynput可能无法启动的问题
        if "DISPLAY environment variable not set" in str(e) or \
           "Wayland" in str(e) or \
           "Xlib" in str(e) or \
           "Failed to connect to X server" in str(e): # 常见错误信息
            logging.error(f"无法启动pynput鼠标监听器 (可能是Wayland或无X服务器环境): {e}")
            logging.error("鼠标点击触发的截图功能将不可用。")
        else:
            logging.error(f"鼠标监听器线程中发生未处理的异常: {e}", exc_info=True)

def capture_test_screenshot():
    """捕获一个用于测试Omniparser服务的屏幕截图"""
    try:
        import mss
        with mss.mss() as sct:
            # 获取主显示器
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            # 截取一个较小的区域以减少数据量，比如左上角300x200区域
            test_region = {
                'top': monitor['top'], 
                'left': monitor['left'], 
                'width': min(300, monitor['width']), 
                'height': min(200, monitor['height'])
            }
            
            sct_img = sct.grab(test_region)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            # 转换为base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            logging.info(f"捕获测试截图成功，尺寸: {img.size}")
            return image_data
            
    except Exception as e:
        logging.warning(f"捕获测试截图失败: {e}")
        return None

def create_fallback_test_image():
    """创建备用测试图像"""
    try:
        # 创建一个包含真实内容的测试图像
        test_img = Image.new('RGB', (200, 150), color='white')
        from PIL import ImageDraw
        draw = ImageDraw.Draw(test_img)
        
        # 绘制一些模拟界面元素
        draw.rectangle([10, 10, 190, 30], fill='lightblue', outline='blue')
        draw.text((15, 15), "Test Application", fill='black')
        draw.rectangle([10, 40, 190, 140], outline='gray')
        draw.text((15, 50), "This is a test content", fill='black')
        draw.text((15, 70), "for Omniparser service", fill='black')
        draw.text((15, 90), "validation.", fill='black')
        
        buffer = BytesIO()
        test_img.save(buffer, format="PNG")
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        logging.info("创建备用测试图像成功")
        return image_data
    except Exception as e:
        logging.error(f"创建备用测试图像失败: {e}")
        return None

def check_omniparser_availability():
    """检查Omniparser服务是否可用"""
    global USE_OMNIPARSER
    
    # 首先尝试健康检查端点（更快的方式）
    try:
        health_url = OMNIPARSER_API_URL.replace('/parse', '/health')
        health_response = requests.get(health_url, timeout=3)
        
        if health_response.status_code == 200:
            health_data = health_response.json()
            if health_data.get('status') == 'healthy':
                logging.info("Omniparser健康检查通过，进行功能验证...")
            else:
                logging.warning(f"Omniparser健康检查显示服务状态异常: {health_data}")
                USE_OMNIPARSER = False
                return False
        else:
            logging.info("健康检查端点不可用，直接进行功能测试...")
            
    except requests.exceptions.RequestException:
        logging.info("健康检查失败，直接进行功能测试...")
    
    # 进行实际的功能测试
    try:
        # 优先使用实时屏幕截图进行测试
        image_data = capture_test_screenshot()
        
        # 如果实时截图失败，使用备用测试图像
        if not image_data:
            logging.info("实时截图失败，使用备用测试图像")
            image_data = create_fallback_test_image()
        
        if not image_data:
            logging.error("无法生成测试图像，跳过Omniparser服务检测")
            USE_OMNIPARSER = False
            return False
        
        # 准备请求数据
        payload = {"image_base64": image_data}
        
        # 发送请求到Omniparser API
        response = requests.post(OMNIPARSER_API_URL, json=payload, timeout=30)
        
        # 检查响应状态
        if response.status_code == 200:
            try:
                result = response.json()
                # 验证返回的数据格式和内容
                if result:
                    if isinstance(result, list):
                        # 新的服务端返回列表格式
                        valid_items = [item for item in result if isinstance(item, dict) and 
                                     ('text' in item or 'caption' in item or 'description' in item)]
                        if valid_items:
                            logging.info(f"Omniparser服务可用，返回{len(valid_items)}个有效解析元素")
                            USE_OMNIPARSER = True
                            return True
                        else:
                            logging.info("Omniparser服务响应中无有效内容，但服务正常")
                            USE_OMNIPARSER = True  # 即使无内容也认为服务可用
                            return True
                    elif isinstance(result, dict):
                        # 兼容旧的服务端返回字典格式
                        logging.info("Omniparser服务可用，返回字典格式数据")
                        USE_OMNIPARSER = True
                        return True
                else:
                    logging.warning("Omniparser服务响应为空")
                    USE_OMNIPARSER = False
                    return False
            except ValueError as e:
                logging.warning(f"Omniparser服务返回无效JSON: {e}")
                USE_OMNIPARSER = False
                return False
        else:
            logging.warning(f"Omniparser服务返回错误状态码: {response.status_code}")
            if response.status_code == 400:
                try:
                    error_detail = response.json()
                    logging.warning(f"Omniparser服务错误详情: {error_detail}")
                except:
                    logging.warning(f"Omniparser服务错误响应: {response.text[:200]}")
            logging.info("将回退到传统OCR")
            USE_OMNIPARSER = False
            return False
            
    except requests.exceptions.Timeout:
        logging.warning(f"Omniparser服务连接超时 ({OMNIPARSER_API_URL})")
        logging.info("将使用传统的Tesseract OCR进行文本提取")
        USE_OMNIPARSER = False
        return False
    except requests.exceptions.ConnectionError:
        logging.warning(f"无法连接到Omniparser服务 ({OMNIPARSER_API_URL}) - 服务可能未启动")
        logging.info("将使用传统的Tesseract OCR进行文本提取")
        USE_OMNIPARSER = False
        return False
    except requests.exceptions.RequestException as e:
        logging.warning(f"Omniparser服务请求失败: {e}")
        logging.info("将使用传统的Tesseract OCR进行文本提取")
        USE_OMNIPARSER = False
        return False
    except Exception as e:
        logging.error(f"检查Omniparser服务时发生未知错误: {e}")
        USE_OMNIPARSER = False
        return False

def reset_vector_database():
    """重置损坏的向量数据库"""
    import shutil
    chroma_dirs = ["chroma_db_activity", "chroma_db"]
    
    for chroma_dir in chroma_dirs:
        if os.path.exists(chroma_dir):
            try:
                shutil.rmtree(chroma_dir)
                print(f"✅ 已删除损坏的向量数据库目录: {chroma_dir}")
            except Exception as e:
                print(f"❌ 删除向量数据库目录失败 ({chroma_dir}): {e}")

def check_vector_database_health():
    """
    检查向量数据库健康状态。
    执行一个简单的查询来验证数据库是否正常工作。
    """
    try:
        # 尝试导入 collection 对象并执行一个测试查询
        from activity_retriever import collection
        
        if collection is not None:
            # 执行一个宽泛的测试查询，这比 .get()更能检测出查询路径的问题
            logging.info("执行向量数据库健康检查查询...")
            # 使用一个几乎总为真的过滤器，如果集合非空
            # 如果集合为空，query可能会表现不同，但不会像`Error finding id`那样报错
            collection.query(
                query_texts=["health check"],
                n_results=1,
                where={"source_db_id": {"$gte": 0}}
            )
            logging.info("向量数据库健康检查查询成功。")
            return True
        else:
            logging.warning("健康检查失败: activity_retriever.collection 对象为 None。")
            return False
    except ImportError:
        logging.error("健康检查失败: 无法从 activity_retriever 导入 collection 对象。")
        return False
    except Exception as e:
        # 捕获特定的ChromaDB错误以及其他异常
        logging.error(f"向量数据库健康检查失败: {e}", exc_info=True)
        # 打印特定消息以帮助调试
        print(f"⚠️  向量数据库健康检查失败: {e}")
        return False

def main():
    """主函数：初始化数据库，启动屏幕捕获和鼠标监听线程"""
    global mouse_listener_thread
    
    print("=== AI Watch Dog 屏幕活动监控系统 ===")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 初始化数据库
    print("正在初始化数据库...")
    init_db()
    
    # 检查Omniparser服务可用性
    print("正在检查Omniparser服务...")
    omniparser_available = check_omniparser_availability()
    if omniparser_available:
        print("✅ Omniparser服务可用")
        print("📊 解析策略: 优先Omniparser，失败时回退到Tesseract OCR")
        print("🔄 优质解析模式，确保最佳识别效果")
    else:
        print("⚠️  Omniparser服务不可用，将使用传统的Tesseract OCR")
    
    # 检查向量数据库状态和健康度
    if ENABLE_VECTOR_INDEXING:
        print("正在检查向量数据库状态...")
        if os.path.exists("chroma_db_activity"):
            print("📁 向量数据库目录存在，正在检查健康状态...")
            if check_vector_database_health():
                print("✅ 向量数据库健康状态良好")
            else:
                print("❌ 向量数据库损坏，正在重置...")
                reset_vector_database()
                print("🔄 向量数据库已重置，将在运行时重新创建和索引")
        else:
            print("🔄 向量数据库不存在，将在运行时重新创建")
    else:
        print("⚠️  向量数据库索引已禁用（临时措施以避免ChromaDB问题）")
        print("💡 数据仍会保存到SQLite数据库，可通过Web界面查询")
    
    # 创建并启动鼠标点击处理线程
    print("正在启动鼠标点击处理线程...")
    worker = threading.Thread(target=click_processing_worker, daemon=True)
    worker.start()
    
    # 创建并启动鼠标监听线程（如果pynput可用）
    mouse_listener_thread = None
    if PYNPUT_AVAILABLE:
        try:
            print("正在启动鼠标监听线程...")
            mouse_listener = mouse.Listener(on_click=handle_mouse_click_activity)
            mouse_listener.start()
            mouse_listener_thread = mouse_listener
            print("✅ 鼠标监听线程已启动")
        except Exception as e:
            logging.error(f"启动鼠标监听线程失败: {e}")
            print(f"❌ 鼠标监听线程启动失败: {e}")
            mouse_listener_thread = None
    else:
        print("⚠️  pynput不可用，鼠标点击触发的截图功能已禁用")
    
    print("\n=== 系统已启动，开始监控屏幕活动 ===")
    print("📊 数据保存到SQLite数据库，向量索引到ChromaDB")
    print("🔍 可通过Web界面(http://localhost:5001)查询活动记录")
    print("⏰ 定时截图间隔: {}秒 | 🖱️ 鼠标点击截图间隔: {}秒".format(CAPTURE_INTERVAL_SECONDS, MOUSE_CLICK_CAPTURE_INTERVAL_SECONDS))
    print("按 Ctrl+C 停止系统\n")
    logging.info("屏幕活动记录已启动。按Ctrl+C停止。")
    
    try:
        while True:
            record_screen_activity(triggered_by="timer")
            time.sleep(CAPTURE_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\n\n=== 正在停止系统 ===")
        logging.info("屏幕活动记录已停止。正在通知工作线程退出...")
        
        print("正在停止鼠标点击处理线程...")
        click_task_queue.put(None) # 发送终止信号给工作线程
        worker.join(timeout=5) # 等待工作线程处理完剩余任务或超时
        
        if mouse_listener_thread:
            print("正在停止鼠标监听线程...")
            mouse_listener_thread.stop()  # 停止鼠标监听器
            mouse_listener_thread.join(timeout=1) # 等待鼠标监听线程退出
            
        print("✅ 所有线程已安全退出")
        print("=== AI Watch Dog 已停止 ===")
        logging.info("所有线程已退出。")
    except Exception as e:
        print(f"\n❌ 系统运行时发生错误: {e}")
        logging.error(f"屏幕活动记录过程中发生错误: {e}", exc_info=True)
        # 考虑在发生严重错误时也尝试优雅关闭工作线程
        print("正在尝试优雅关闭...")
        click_task_queue.put(None)
        worker.join(timeout=5)
        if mouse_listener_thread:
            mouse_listener_thread.stop()
            mouse_listener_thread.join(timeout=1)
        print("系统已停止")

if __name__ == "__main__":
    main()

    # 提示：请确保Tesseract OCR已正确安装并配置
    # 如果在Windows上，您可能需要取消 pytesseract.pytesseract.tesseract_cmd 的注释并设置为您的Tesseract路径
    # 同时，确保您已下载了 `chi_sim.traineddata` 和 `eng.traineddata` 并将其放入Tesseract的 `tessdata` 目录 
    # 同时，确保您已下载了 `chi_sim.traineddata` 和 `eng.traineddata` 并将其放入Tesseract的 `tessdata` 目录 

