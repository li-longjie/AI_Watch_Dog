import os
import json
import asyncio
import re
import sqlite3
import threading
from datetime import datetime, timedelta, date
from collections import Counter
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import logging

from activity_retriever import query_recent_activity, load_and_index_activity_data, get_all_activity_records, get_application_usage_summary

# 数据库相关配置
SCREENSHOT_DIR = "screen_recordings"
DATABASE_FILE = os.path.join(SCREENSHOT_DIR, "activity_log.db")

def create_connection(db_file):
    """ 创建一个数据库连接到SQLite数据库 """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        logging.debug(f"成功连接到SQLite数据库: {db_file}")
    except sqlite3.Error as e:
        logging.error(f"连接SQLite数据库失败 ({db_file}): {e}")
    return conn

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 添加CORS支持，允许前端跨域访问
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"])

# 确保templates目录存在
os.makedirs('templates', exist_ok=True)

# 存储聊天历史
chat_history = []

# --- 应用启动时加载一次数据 ---
def initial_load_data():
    print("应用启动：正在后台加载和索引屏幕活动数据...")
    try:
        # 这里的导入需要放在函数内部，以确保在子线程中能正确初始化
        from activity_retriever import load_and_index_activity_data
        count = load_and_index_activity_data()
        print(f"应用启动：后台任务完成，加载了 {count} 条新记录。")
    except Exception as e:
        print(f"应用启动：后台加载数据时出错: {e}")

# -----------------------------

@app.route('/')
def index():
    """主页"""
    return render_template('activity_chat.html')

@app.route('/api/query', methods=['POST'])
async def query_activity():
    """处理活动查询API请求"""
    data = request.json
    user_message = data.get('message', '')
    
    # 将用户消息添加到历史
    chat_history.append({"role": "user", "content": user_message})
    
    # 创建自定义提示词，现在将用户完整消息作为主要输入，让后端判断时间
    # 后端将根据 query_text (即 user_message) 来解析时间，或者使用默认回退机制
    custom_prompt_for_llm = f"""请根据屏幕活动记录回答用户的问题: {user_message}
如果问题无法直接从活动记录中回答，请基于你的知识进行回答，并说明这不是从我的屏幕活动中得出的结论。
如果用户的问题中包含类似"昨天"、"今天上午"、"上周"等时间描述，请确保你的回答严格基于该时间段的活动记录。
"""
    
    # 查询活动
    result = await query_recent_activity(query_text=user_message, custom_prompt=custom_prompt_for_llm)
    
    # 将助手回复添加到历史
    chat_history.append({"role": "assistant", "content": result})
    
    # 限制历史记录长度，避免占用过多内存
    if len(chat_history) > 100:
        chat_history.pop(0)
        chat_history.pop(0)
    
    return jsonify({
        'result': result,
        'query_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'history': chat_history
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    """获取聊天历史"""
    return jsonify(chat_history)

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    """清除聊天历史"""
    global chat_history
    chat_history = []
    return jsonify({"success": True})

@app.route('/api/activity_records', methods=['GET'])
def activity_records():
    """获取活动记录"""
    limit = request.args.get('limit', 50, type=int)
    records = get_all_activity_records(limit)
    return jsonify(records)

@app.route('/api/activity_record/<record_id>', methods=['GET'])
def activity_record_detail(record_id):
    """获取单条活动记录详情"""
    records = get_all_activity_records(1000)  # 获取足够多的记录以找到指定ID
    for record in records:
        if record.get('id') == record_id:
            return jsonify(record)
    return jsonify({"error": "记录未找到"}), 404

@app.route('/api/usage_stats', methods=['GET'])
async def usage_stats():
    """获取应用使用时长统计数据"""
    period = request.args.get('period', 'today') # today, yesterday, this_week, this_month

    now = datetime.now()
    start_time_dt = None
    end_time_dt = None

    if period == 'today':
        start_time_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time_dt = now
    elif period == 'yesterday':
        yesterday_dt = now - timedelta(days=1)
        start_time_dt = yesterday_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time_dt = yesterday_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == 'this_week':
        start_of_week = now - timedelta(days=now.weekday()) # 周一为0, 周日为6
        start_time_dt = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time_dt = now
    elif period == 'this_month':
        start_time_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_time_dt = now
    else:
        # 默认或未知周期，返回今日数据
        start_time_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time_dt = now
        period = 'today' # 确保period有一个有效值

    summary_data = await get_application_usage_summary(start_time_dt, end_time_dt)

    if summary_data.get("error"):
        return jsonify({"error": summary_data.get("error"), "period_processed": period}), 500

    # 格式化使用时长数据，将timedelta对象转换为可序列化的格式
    usage_data = summary_data.get("usage", {})
    formatted_usage = []
    total_duration_all_apps = timedelta()

    for app_name, duration_timedelta in usage_data.items():
        if isinstance(duration_timedelta, timedelta):
            total_duration_all_apps += duration_timedelta
            duration_seconds = duration_timedelta.total_seconds()
            hours, remainder = divmod(duration_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            duration_str = f"{int(hours)}小时 {int(minutes)}分钟" if hours > 0 else f"{int(minutes)}分钟"

            formatted_usage.append({
                "app_name": app_name,
                "duration_seconds": duration_seconds,
                "duration_str": duration_str
            })

    # 按使用时长排序（降序）
    formatted_usage.sort(key=lambda x: x["duration_seconds"], reverse=True)

    total_all_seconds = total_duration_all_apps.total_seconds()
    total_hours, total_remainder = divmod(total_all_seconds, 3600)
    total_minutes, _ = divmod(total_remainder, 60)
    total_duration_str = f"{int(total_hours)}小时 {int(total_minutes)}分钟"

    return jsonify({
        "period_processed": period,
        "start_time": start_time_dt.isoformat(),
        "end_time": end_time_dt.isoformat(),
        "total_usage_str": total_duration_str,
        "total_usage_seconds": total_all_seconds,
        "app_specific_usage": formatted_usage,
    })

@app.route('/api/activity_stats', methods=['GET'])
def activity_stats():
    """获取活动统计信息"""
    try:
        records = get_all_activity_records(100)  # 获取最近100条记录
        
        # 统计信息
        total_records = len(records)
        app_counts = {}
        record_types = {}
        
        for record in records:
            app_name = record.get('app_name', 'Unknown')
            record_type = record.get('record_type', 'unknown')
            
            app_counts[app_name] = app_counts.get(app_name, 0) + 1
            record_types[record_type] = record_types.get(record_type, 0) + 1
        
        # 获取最活跃的应用
        top_apps = sorted(app_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return jsonify({
            'total_records': total_records,
            'top_apps': top_apps,
            'record_types': record_types,
            'latest_activity': records[0] if records else None
        })
    except Exception as e:
        logging.error(f"获取活动统计失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/real_time_activities', methods=['GET'])
def real_time_activities():
    """获取实时活动记录"""
    try:
        limit = request.args.get('limit', 20, type=int)
        records = get_all_activity_records(limit)
        
        # 格式化时间和内容
        formatted_records = []
        for record in records:
            formatted_record = {
                'id': record.get('id'),
                'timestamp': record.get('timestamp'),
                'app_name': record.get('app_name', 'Unknown'),
                'record_type': record.get('record_type'),
                'window_title': record.get('window_title', ''),
                'ocr_text': record.get('ocr_text', '')[:100] + '...' if record.get('ocr_text', '') and len(record.get('ocr_text', '')) > 100 else record.get('ocr_text', ''),
                'url': record.get('url'),
                'parser_type': record.get('parser_type'),
                'mouse_x': record.get('mouse_x'),
                'mouse_y': record.get('mouse_y')
            }
            formatted_records.append(formatted_record)
        
        return jsonify({
            'activities': formatted_records,
            'count': len(formatted_records)
        })
    except Exception as e:
        logging.error(f"获取实时活动记录失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/keywords', methods=['GET'])
def get_keywords():
    """获取关键词云数据"""
    try:
        # 获取时间范围参数
        hours = request.args.get('hours', 24, type=int)  # 默认24小时
        
        # 根据时间范围动态调整获取记录数量
        if hours <= 6:
            limit = 500   # 6小时内获取500条
        elif hours <= 12:
            limit = 1000  # 12小时内获取1000条
        elif hours <= 24:
            limit = 2000  # 24小时内获取2000条
        elif hours <= 48:
            limit = 3000  # 48小时内获取3000条
        else:
            limit = 5000  # 7天获取5000条
        
        # 计算时间范围
        import re
        from collections import Counter
        from datetime import datetime, timedelta
        import sqlite3
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        cutoff_time_iso = cutoff_time.isoformat()
        
        # 直接从数据库按时间范围获取记录
        conn = create_connection(DATABASE_FILE)
        if not conn:
            return jsonify({'error': '无法连接到数据库'}), 500
        
        records = []
        try:
            cursor = conn.cursor()
            # 查询指定时间范围内的记录，按时间戳降序排序
            query = """
                SELECT timestamp, app_name, window_title, page_title, ocr_text, url
                FROM activity_log 
                WHERE timestamp >= ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            cursor.execute(query, (cutoff_time_iso, limit))
            rows = cursor.fetchall()
            
            # 转换为字典格式
            columns = ['timestamp', 'app_name', 'window_title', 'page_title', 'ocr_text', 'url']
            for row in rows:
                record = {}
                for i, column in enumerate(columns):
                    record[column] = row[i]
                records.append(record)
                
            logging.info(f"从数据库获取了 {len(records)} 条记录 (时间范围: {hours}小时, 限制: {limit}条)")
        except sqlite3.Error as e:
            logging.error(f"查询数据库失败: {e}")
            return jsonify({'error': f'数据库查询失败: {e}'}), 500
        finally:
            conn.close()
        
        # 收集所有文本内容
        all_text = []
        for record in records:
            # 提取OCR文本
            ocr_text = record.get('ocr_text', '')
            if ocr_text:
                all_text.append(ocr_text)
            
            # 提取窗口标题
            window_title = record.get('window_title', '')
            if window_title and window_title not in ['Unknown', 'Untitled']:
                all_text.append(window_title)
            
            # 提取页面标题
            page_title = record.get('page_title', '')
            if page_title:
                all_text.append(page_title)
        
        if not all_text:
            return jsonify({
                'keywords': [],
                'total_text_length': 0,
                'hours': hours
            })
        
        # 合并所有文本
        combined_text = ' '.join(all_text)
        
        # 简单的关键词提取
        # 移除标点符号，转换为小写，分割单词
        import string
        
        # 清理文本
        cleaned_text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', combined_text.lower())
        words = cleaned_text.split()
        
        # 过滤条件
        stop_words = {
            # 英文停用词
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
            'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
            'my', 'your', 'his', 'her', 'its', 'our', 'their', 'mine', 'yours', 'hers', 'ours', 'theirs',
            'not', 'no', 'yes', 'all', 'any', 'some', 'each', 'every', 'both', 'either', 'neither',
            'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
            # 中文停用词
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很',
            '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '来', '而',
            '把', '学', '对', '从', '起', '还', '用', '过', '时', '后', '可以', '回', '什么', '没',
            # 常见无意义词
            'com', 'www', 'http', 'https', 'html', 'htm', 'php', 'asp', 'jsp',
            'chrome', 'firefox', 'edge', 'safari', 'browser',
            # 代码和技术相关的停用词
            'div', 'class', 'span', 'script', 'style', 'function', 'var', 'let', 'const', 'import', 'export',
            'component', 'props', 'data', 'method', 'computed', 'watch', 'mounted', 'created', 'beforemount',
            'template', 'vue', 'react', 'angular', 'js', 'css', 'scss', 'sass', 'less', 'webpack', 'vite',
            'npm', 'yarn', 'node', 'modules', 'package', 'json', 'config', 'build', 'dist', 'src',
            'assets', 'static', 'public', 'lib', 'libs', 'vendor', 'polyfill', 'babel', 'eslint',
            'prettier', 'typescript', 'tsx', 'jsx', 'ts', 'vue', 'svelte', 'next', 'nuxt',
            # 文件路径相关
            'users', 'jason', 'pycharmprojects', 'ai_watch_dog', 'frontend', 'backend', 'node_modules',
            'vscode', 'cursor', 'ide', 'editor', 'terminal', 'console', 'command', 'cmd', 'powershell',
            # 代码语法
            'if', 'else', 'for', 'while', 'switch', 'case', 'break', 'continue', 'return', 'try', 'catch',
            'finally', 'throw', 'async', 'await', 'promise', 'callback', 'then', 'resolve', 'reject',
            # 通用技术词汇
            'api', 'url', 'uri', 'get', 'post', 'put', 'delete', 'patch', 'head', 'options', 'cors',
            'http', 'https', 'ssl', 'tls', 'tcp', 'udp', 'ip', 'dns', 'cdn', 'cache', 'session', 'cookie',
            # HTML/CSS相关
            'html', 'head', 'body', 'meta', 'title', 'link', 'script', 'style', 'img', 'src', 'href',
            'alt', 'id', 'class', 'name', 'value', 'type', 'content', 'data', 'aria', 'role',
            # 版本控制
            'git', 'github', 'gitlab', 'commit', 'push', 'pull', 'merge', 'branch', 'master', 'main',
            # 常见缩写和技术术语
            'app', 'dev', 'prod', 'test', 'debug', 'log', 'info', 'warn', 'error', 'success', 'fail',
            'true', 'false', 'null', 'undefined', 'nan', 'infinity',
            # 数学和几何相关（来自SVG等）
            'm0', '0l9', '5z', 'svg', 'path', 'rect', 'circle', 'line', 'polygon', 'polyline',
            # 界面元素
            'button', 'input', 'form', 'select', 'option', 'textarea', 'label', 'fieldset', 'legend',
            'table', 'tr', 'td', 'th', 'thead', 'tbody', 'tfoot', 'caption',
            # 动作相关
            'click', 'hover', 'focus', 'blur', 'change', 'submit', 'reset', 'load', 'unload', 'resize',
            'scroll', 'keydown', 'keyup', 'keypress', 'mousedown', 'mouseup', 'mousemove',
        }
        
        # 过滤单词
        filtered_words = [
            word for word in words 
            if len(word) >= 2 and  # 至少2个字符
            word not in stop_words and  # 不在停用词中
            not word.isdigit() and  # 不是纯数字
            not re.match(r'^[a-z]$', word)  # 不是单个字母
        ]
        
        # 统计词频
        word_counts = Counter(filtered_words)
        
        # 分离中文和英文关键词
        chinese_words = []
        english_words = []
        
        for word, count in word_counts.items():
            if count >= 1:  # 至少出现1次
                # 检查是否包含中文字符
                if re.search(r'[\u4e00-\u9fff]', word):
                    chinese_words.append((word, count))
                else:
                    # 进一步过滤英文技术词汇
                    if (len(word) > 2 and  # 英文词至少3个字符
                        not re.match(r'^[a-z]+[0-9]+$', word) and  # 不是字母+数字组合
                        not word.endswith('js') and not word.endswith('ts') and  # 不是文件扩展名
                        not word.endswith('css') and not word.endswith('html') and
                        not word.startswith('ba') and  # 不是组件前缀
                        not word.startswith('on') and  # 不是事件前缀
                        not re.match(r'^[a-z]{1,3}$', word) and  # 不是1-3个字母的简短缩写
                        word not in ['item', 'icon', 'list', 'grid', 'card', 'tabs']):  # 保留一些有意义的词如menu, text, panel
                        english_words.append((word, count))
        
        # 按词频排序
        chinese_words.sort(key=lambda x: x[1], reverse=True)
        english_words.sort(key=lambda x: x[1], reverse=True)
        
        # 取前25个中文词和前25个英文词
        top_chinese = chinese_words[:25]
        top_english = english_words[:25]
        
        # 合并并格式化输出
        keywords = []
        
        # 添加中文关键词
        for word, count in top_chinese:
            keywords.append({
                'text': word,
                'count': count,
                'size': min(36, max(14, count * 1.5))  # 中文字体稍小一些
            })
        
        # 添加英文关键词
        for word, count in top_english:
            keywords.append({
                'text': word,
                'count': count,
                'size': min(32, max(12, count * 1.2))  # 英文字体更小一些
            })
        
        # 按词频重新排序
        keywords.sort(key=lambda x: x['count'], reverse=True)
        
        return jsonify({
            'keywords': keywords,
            'total_text_length': len(combined_text),
            'unique_words': len(word_counts),
            'records_count': len(records),
            'hours': hours
        })
        
    except Exception as e:
        logging.error(f"获取关键词数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/activity_search', methods=['GET'])
def activity_search():
    """搜索活动记录"""
    try:
        query = request.args.get('query', '')
        limit = request.args.get('limit', 50, type=int)
        
        if not query:
            return jsonify({'activities': [], 'count': 0})
        
        # 简单的关键词搜索
        all_records = get_all_activity_records(1000)  # 搜索更多记录
        filtered_records = []
        
        for record in all_records:
            # 搜索应用名、窗口标题、OCR文本
            searchable_text = ' '.join([
                record.get('app_name', ''),
                record.get('window_title', ''),
                record.get('ocr_text', ''),
                record.get('url', '')
            ]).lower()
            
            if query.lower() in searchable_text:
                formatted_record = {
                    'id': record.get('id'),
                    'timestamp': record.get('timestamp'),
                    'app_name': record.get('app_name', 'Unknown'),
                    'record_type': record.get('record_type'),
                    'window_title': record.get('window_title', ''),
                    'ocr_text': record.get('ocr_text', '')[:100] + '...' if record.get('ocr_text', '') and len(record.get('ocr_text', '')) > 100 else record.get('ocr_text', ''),
                    'url': record.get('url'),
                    'parser_type': record.get('parser_type')
                }
                filtered_records.append(formatted_record)
                
                if len(filtered_records) >= limit:
                    break
        
        return jsonify({
            'activities': filtered_records,
            'count': len(filtered_records),
            'query': query
        })
    except Exception as e:
        logging.error(f"搜索活动记录失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/db_status', methods=['GET'])
def debug_db_status():
    """调试端点：检查数据库状态"""
    try:
        conn = create_connection(DATABASE_FILE)
        if not conn:
            return jsonify({'error': '无法连接到数据库', 'db_file': DATABASE_FILE}), 500
        
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log';")
        table_exists = cursor.fetchone() is not None
        
        total_records = 0
        recent_records = 0
        
        if table_exists:
            # 获取总记录数
            cursor.execute("SELECT COUNT(*) FROM activity_log;")
            total_records = cursor.fetchone()[0]
            
            # 获取最近24小时的记录数
            cutoff_time = datetime.now() - timedelta(hours=24)
            cutoff_time_iso = cutoff_time.isoformat()
            cursor.execute("SELECT COUNT(*) FROM activity_log WHERE timestamp >= ?;", (cutoff_time_iso,))
            recent_records = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'db_file': DATABASE_FILE,
            'db_exists': os.path.exists(DATABASE_FILE),
            'table_exists': table_exists,
            'total_records': total_records,
            'recent_24h_records': recent_records,
            'status': 'success'
        })
    except Exception as e:
        logging.error(f"数据库状态检查失败: {e}")
        return jsonify({'error': str(e), 'db_file': DATABASE_FILE}), 500

if __name__ == "__main__":
    # 启动应用
    print("正在启动Flask应用...")
    
    # 在后台线程中启动初始数据加载
    print("正在后台启动初始数据加载... 这可能需要几分钟时间，请耐心等待。")
    load_thread = threading.Thread(target=initial_load_data, daemon=True)
    load_thread.start()

    print("Flask应用已准备好处理请求。")
    # 端口改回5001，与前端和用户日志保持一致
    app.run(debug=False, port=5001, host='0.0.0.0') 