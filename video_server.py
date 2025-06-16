import cv2 
import asyncio 
import json 
import argparse
from datetime import datetime 
from concurrent.futures import ThreadPoolExecutor 
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from collections import deque 
from typing import Optional, Dict, Any, List
import numpy as np 
import logging 
from multi_modal_analyzer import MultiModalAnalyzer
import time
import uvicorn 
from multiprocessing import set_start_method 
from config import VideoConfig, ServerConfig, VIDEO_SOURCE, LOG_CONFIG, ARCHIVE_DIR, update_config
import os
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from video_processor import VideoProcessor
import queue
from pydantic import BaseModel

# 配置日志记录
logging.basicConfig(
    level=LOG_CONFIG['level'],
    format=LOG_CONFIG['format'],
    handlers=[logging.FileHandler(LOG_CONFIG['handlers'][0]['filename'], encoding='utf-8'), logging.StreamHandler()]
)

# 解析命令行参数
def parse_args():
    parser = argparse.ArgumentParser(description='智能视频监控系统')
    parser.add_argument('--video_source', type=str, help='视频源路径')
    parser.add_argument('--video_interval', type=int, help='视频分段时长(秒)')
    parser.add_argument('--analysis_interval', type=int, help='分析间隔(秒)')
    parser.add_argument('--buffer_duration', type=int, help='滑窗分析时长')
    parser.add_argument('--ws_retry_interval', type=int, help='WebSocket重连间隔(秒)')
    parser.add_argument('--max_ws_queue', type=int, help='消息队列最大容量')
    parser.add_argument('--jpeg_quality', type=int, help='JPEG压缩质量')
    parser.add_argument('--host', type=str, help='服务器主机地址')
    parser.add_argument('--port', type=int, help='服务器端口')
    parser.add_argument('--reload', type=bool, help='是否启用热重载')
    parser.add_argument('--workers', type=int, help='工作进程数')
    
    args = parser.parse_args()
    return {k: v for k, v in vars(args).items() if v is not None}

# 更新配置
args = parse_args()
update_config(args)

# 初始化视频源
def get_video_source(source):
    """根据输入确定视频源类型"""
    if source is None:
        return VIDEO_SOURCE
    
    # 尝试将输入转换为整数（摄像头索引）
    try:
        cam_index = int(source)
        return cam_index
    except ValueError:
        # 如果不是整数，则视为文件路径
        return source

# 初始化视频源
video_source = get_video_source(args.get('video_source'))

# 创建视频处理器
try:
    video_processor = VideoProcessor(video_source)
except ValueError as e:
    print(f"错误: {e}")
    import sys
    sys.exit(1)

# 创建FastAPI应用
app = FastAPI(title="智能视频监控系统")

# 设置静态文件目录 - 仅保留video_warning用于预警图片/视频访问
app.mount("/video_warning", StaticFiles(directory="video_warning"), name="video_warning")

# 注意：前端现在使用独立的Vue.js开发服务器
# 如果需要生产环境部署，请先构建Vue项目：
# cd frontend && npm run build
# 然后可以添加：app.mount("/", StaticFiles(directory="frontend/dist"), name="frontend")

# 创建必要的目录
import os
os.makedirs("video_warning", exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# 全局变量
active_connections: List[WebSocket] = [] # 添加类型提示
MAX_ALERTS = 10
recent_alerts: deque = deque(maxlen=MAX_ALERTS) # 再使用 deque 并设置最大长度

# 添加自定义预警规则存储
custom_alert_rules = []

# 初始化系统预设规则（基于activity_configs）
def init_default_alert_rules():
    """初始化系统预设的活动检测规则"""
    default_rules = [
        {
            "id": 1,
            "name": "睡觉检测",
            "condition": "当检测到人员趴在桌子上睡觉或闭眼休息时立即触发预警",
            "level": "high",
            "enabled": True,
            "is_system_rule": True,
            "generated_prompt": "检测画面中是否有人趴在桌子上睡觉、闭眼休息、长时间闭眼、头靠在手臂上休息，如果检测到请返回：[时间] 睡觉",
            "activity_type": "睡觉",
            "max_gap": 999999,
            "min_duration": 0,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": 2,
            "name": "专注工作学习检测",
            "condition": "当检测到人员专注工作或学习状态时立即记录行为",
            "level": "low",
            "enabled": True,
            "is_system_rule": True,
            "generated_prompt": "检测画面中是否有人专注工作、学习、使用电脑、办公、看电脑屏幕、使用键盘鼠标、翻看书籍、写字记录，如果检测到请返回：[时间] 专注工作学习",
            "activity_type": "专注工作学习",
            "max_gap": 999999,
            "min_duration": 0,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": 3,
            "name": "玩手机检测",
            "condition": "当检测到人员使用手机或低头看手机时立即触发预警",
            "level": "high",
            "enabled": True,
            "is_system_rule": True,
            "generated_prompt": "检测画面中是否有人使用手机、看手机、操作手机、低头看屏幕、手指滑动屏幕，如果检测到请返回：[时间] 玩手机",
            "activity_type": "玩手机",
            "max_gap": 999999,
            "min_duration": 0,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": 4,
            "name": "吃东西检测",
            "condition": "当检测到人员进食或用餐时立即记录行为",
            "level": "high",
            "enabled": True,
            "is_system_rule": True,
            "generated_prompt": "检测画面中是否有人进食、用餐、咀嚼食物、拿着食物进食，如果检测到请返回：[时间] 吃东西",
            "activity_type": "吃东西",
            "max_gap": 999999,
            "min_duration": 0,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": 5,
            "name": "喝水检测",
            "condition": "当检测到人员喝水行为时立即记录",
            "level": "high",
            "enabled": True,
            "is_system_rule": True,
            "generated_prompt": "检测画面中是否有人饮水、使用水杯、喝白开水、补充水分，如果检测到请返回：[时间] 喝水",
            "activity_type": "喝水",
            "max_gap": 999999,
            "min_duration": 0,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": 6,
            "name": "喝饮料检测",
            "condition": "当检测到人员饮用饮料时立即记录行为",
            "level": "high",
            "enabled": True,
            "is_system_rule": True,
            "generated_prompt": "检测画面中是否有人饮用非水类饮品、喝汽水、咖啡、果汁等饮料，如果检测到请返回：[时间] 喝饮料",
            "activity_type": "喝饮料",
            "max_gap": 999999,
            "min_duration": 0,
            "created_at": datetime.now().isoformat()
        }
    ]
    
    # 添加到全局规则列表
    custom_alert_rules.extend(default_rules)
    logging.info(f"初始化了{len(default_rules)}个系统预设规则")

# 在应用启动时初始化预设规则
init_default_alert_rules()

# 添加请求模型
class AlertRuleRequest(BaseModel):
    name: str
    condition: str
    level: str = "medium"
    enabled: bool = True
    is_system_rule: bool = False

class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    condition: Optional[str] = None
    level: Optional[str] = None
    enabled: Optional[bool] = None

@app.on_event("startup") 
async def startup():
    """应用启动时的初始化"""
    print("🚀 正在初始化视频监控系统...")
    
    # [重构] 移除模型预加载逻辑。
    # 向量数据库模型现在由 rag_server.py 服务独立、中心化地进行加载。
    # video_server.py 不再需要关心向量模型的初始化。
    
    # 直接启动视频处理和警报处理
    print("📹 启动视频处理服务...")
    asyncio.create_task(video_processor.start_processing())
    asyncio.create_task(alert_handler())
    
    # 等待视频服务稳定启动
    await asyncio.sleep(1)
    print("✅ 视频处理服务启动完成")
    
    print("🎯 视频监控系统启动完成")

@app.on_event("shutdown")
async def shutdown_event():
    await video_processor.stop_processing()

@app.websocket("/video_feed")
async def video_feed(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    video_processor.start_push_queue = 1
    try:
        await video_processor.video_streamer(websocket)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        logging.error(f"Video feed error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)
    finally:
        video_processor.start_push_queue = 0

@app.websocket("/alerts")
async def alerts(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    # 为每个连接维护一个已发送预警ID集合
    connection_sent_alerts = set()
    
    try:
        # 发送已有的预警，但确保不重复
        if recent_alerts:
            for alert in recent_alerts:
                # 提取预警的唯一标识
                alert_key = alert.get("alert_key")
                if not alert_key:
                    # 如果没有alert_key，根据内容和时间戳生成一个更可靠的后备key
                    timestamp = alert.get("timestamp", "")
                    content = alert.get("content", "")
                    # 移除可能为空的 start/end time，避免它们引起不一致
                    alert_key = f"{content}_{timestamp}"
                
                if alert_key not in connection_sent_alerts:
                    await websocket.send_json(alert)
                    connection_sent_alerts.add(alert_key)
                    
                    # 限制sent_alerts大小
                    if len(connection_sent_alerts) > 100:
                        connection_sent_alerts = set(list(connection_sent_alerts)[-100:])
        
        # 保持连接
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception as e:
        logging.error(f"Alert WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


@app.get("/api/alerts")
async def get_alerts_api(): # 修改函数名以示区分
    # 注意：现在 recent_alerts 是 deque
    return {
        "status": "success",
        "alerts": list(recent_alerts) # 返回列表
    }

# @app.get("/test_alert")
# async def test_alert():
#     """测试预警系统 - 强制发送预警消息到所有客户端"""
#     # 注释掉测试预警接口，防止产生测试信息
#     pass

async def alert_handler():
    """处理警报消息"""
    # 用于跟踪已处理的预警
    processed_alerts = set()
    
    while True:
        try:
            alert_processed = False  # 标记本轮是否处理了预警
            
            # 检查预警队列
            if hasattr(video_processor, 'alert_queue') and not video_processor.alert_queue.empty():
                try:
                    alert = video_processor.alert_queue.get_nowait()
                    
                    # 提取预警的唯一标识
                    alert_key = alert.get("alert_key")
                    if not alert_key:
                        # 如果没有alert_key，根据内容和时间戳生成一个更可靠的后备key
                        timestamp = alert.get("timestamp", "")
                        content = alert.get("content", "")
                        # 移除可能为空的 start/end time，避免它们引起不一致
                        alert_key = f"{content}_{timestamp}"
                    
                    # 检查是否已经处理过这个预警
                    if alert_key in processed_alerts:
                        logging.info(f"预警已处理，跳过: {alert_key}")
                        continue  # 跳过已处理的预警
                    
                    # 标记此预警已处理
                    processed_alerts.add(alert_key)
                    
                    # 限制processed_alerts的大小，避免内存无限增长
                    if len(processed_alerts) > 100:  # 保留最近100个预警记录
                        processed_alerts = set(list(processed_alerts)[-100:])
                    
                    # 简化去重检查 - 只检查alert_key，避免遍历整个recent_alerts
                    duplicate = False
                    # 只检查最近的几个预警，提高效率
                    check_count = min(10, len(recent_alerts))
                    for i in range(check_count):
                        existing_alert = recent_alerts[-(i+1)]  # 从最新的开始检查
                        existing_key = existing_alert.get("alert_key")
                        if existing_key and existing_key == alert_key:
                            duplicate = True
                            break
                    
                    if not duplicate:
                        # 添加到最近预警 (deque 自动处理)
                        recent_alerts.append(alert)
                    
                    # 实时发送给所有连接
                    disconnected = []
                    sent_count = 0
                    
                    # 逐个发送，避免批量发送时的连接状态问题
                    for connection in list(active_connections):  # 使用列表副本防止迭代时修改
                        try:
                            # 更严格的连接状态检查
                            if (hasattr(connection, 'client_state') and 
                                connection.client_state == WebSocketState.CONNECTED):
                                await connection.send_json(alert)
                                sent_count += 1
                            else:
                                disconnected.append(connection)
                        except Exception as e:
                            logging.warning(f"发送预警到连接失败: {e}")
                            disconnected.append(connection)
                    
                    # 清理断开的连接
                    for conn in disconnected:
                        if conn in active_connections:
                            active_connections.remove(conn)
                            logging.info(f"移除了断开的连接，剩余连接数: {len(active_connections)}")
                    
                    if sent_count > 0:
                        alert_type = alert.get('type', 'standard')
                        is_custom = alert.get('is_custom', False)
                        logging.info(f"📤 预警已发送到 {sent_count} 个活跃连接: [{alert_type}] {alert.get('content', 'Unknown')}")
                        # 如果是自定义预警，添加额外的调试信息
                        if is_custom or 'custom' in alert_type:
                            logging.info(f"🔧 自定义预警详情: type={alert_type}, level={alert.get('level')}, is_custom={is_custom}")
                        print(f"📤 预警发送成功: {alert.get('content', 'Unknown')}, 类型: {alert_type}")
                    else:
                        alert_type = alert.get('type', 'standard')
                        logging.info(f"📥 预警已添加到队列，但无活跃连接: {alert.get('content', 'Unknown')}")
                        print(f"📥 预警无活跃连接: {alert.get('content', 'Unknown')}, 类型: {alert_type}")

                    alert_processed = True  # 标记已处理预警

                except queue.Empty:
                    pass # 队列为空，正常情况
                except Exception as e: # 捕获处理单个警报时的其他异常
                    logging.error(f"处理单个警报时出错: {e}")
            
        except Exception as e:
            logging.error(f"Alert handler 主循环错误: {e}")
        finally:
             # 只有在没有处理预警时才休眠，避免不必要的延迟
             if not alert_processed:
                 await asyncio.sleep(0.05)  # 减少空转时的休眠时间到50毫秒
             else:
                 # 如果处理了预警，只做极短暂的让出，让其他协程有机会运行
                 await asyncio.sleep(0.001)  # 1毫秒的极短暂让出



# 添加行为数据API端点
@app.get("/api/behavior-data")
async def get_behavior_data():
    """获取行为分析数据"""
    # 这里返回模拟的行为数据
    # 实际应用中应从视频处理器获取真实数据
    return {
        "status": "success",
        "data": {
            "behaviors": [
                {"id": 1, "type": "专注工作", "count": 5, "timestamp": "2025-03-28 20:10:00"},
                {"id": 2, "type": "吃东西", "count": 3, "timestamp": "2025-03-28 20:12:30"},
                {"id": 7, "type": "其他", "count": 2, "timestamp": "2025-03-28 20:15:45"}
            ],
            "statistics": {
                "total_behaviors": 10,
                "unique_behaviors": 3,
                "most_frequent": "专注工作"
            }
        }
    }

@app.post("/api/custom-alert-rules")
async def add_custom_alert_rule(request: AlertRuleRequest):
    """添加自定义预警规则"""
    try:
        # 基本验证
        if not request.name or not request.condition:
            return {"status": "error", "message": "规则名称和条件不能为空"}
        
        # 检查是否已存在同名规则
        for existing_rule in custom_alert_rules:
            if existing_rule.get('name') == request.name and not existing_rule.get('is_system_rule', False):
                return {"status": "error", "message": f"规则名称 '{request.name}' 已存在，请使用不同的名称"}
        
        # 使用LLM生成检测提示词
        from llm_service import chat_completion
        
        prompt = f"""
        基于用户描述的预警条件，生成一个用于视频分析的检测提示词。
        
        用户规则：
        名称：{request.name}
        条件：{request.condition}
        级别：{request.level}
        
        要求：
        1. 生成的提示词要全面考虑各种可能的情况
        2. 如果涉及"离开座位"类的规则，也要考虑"座位上无人"的状态
        3. 如果涉及位置相关的规则，要考虑"画面中无人"的情况
        4. 检测逻辑要灵活，能适应不同的视频描述方式
        
        请生成一个简洁有效的提示词，用于让AI模型检测视频中是否出现该条件描述的情况。
        返回格式要求：直接返回提示词，不要其他解释。
        
        示例输出格式：
        "检测画面中是否有以下情况：1.人员离开座位 2.座位上无人出现 3.视频中未见人物，如果检测到请返回：[时间] 离开位置检测"
        """
        
        generated_prompt = await chat_completion(prompt)
        
        # 智能ID分配：用户自定义规则从1000开始，避免与系统预设规则（1-999）冲突
        max_user_id = 999  # 系统规则使用1-999
        for rule in custom_alert_rules:
            if not rule.get('is_system_rule', False) and rule.get('id', 0) > max_user_id:
                max_user_id = rule['id']
        
        new_id = max_user_id + 1
        
        # 构建完整的规则对象
        rule = {
            "id": new_id,
            "name": request.name,
            "condition": request.condition,
            "level": request.level,
            "enabled": request.enabled,
            "is_system_rule": request.is_system_rule,
            "generated_prompt": generated_prompt,
            "created_at": datetime.now().isoformat()
        }
        
        custom_alert_rules.append(rule)
        
        logging.info(f"添加自定义预警规则: {rule['name']} (ID: {new_id})")
        
        return {
            "status": "success",
            "message": "规则添加成功",
            "rule": rule
        }
        
    except Exception as e:
        logging.error(f"添加自定义预警规则失败: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/custom-alert-rules")
async def get_custom_alert_rules():
    """获取所有自定义预警规则"""
    return {
        "status": "success",
        "rules": custom_alert_rules
    }

@app.put("/api/custom-alert-rules/{rule_id}")
async def update_custom_alert_rule(rule_id: int, request: AlertRuleUpdate):
    """更新自定义预警规则"""
    try:
        # 查找规则
        rule_index = None
        for i, rule in enumerate(custom_alert_rules):
            if rule["id"] == rule_id:
                rule_index = i
                break
        
        if rule_index is None:
            return {"status": "error", "message": "规则不存在"}
        
        # 更新规则
        update_data = request.dict(exclude_unset=True)
        custom_alert_rules[rule_index].update(update_data)
        custom_alert_rules[rule_index]["updated_at"] = datetime.now().isoformat()
        
        return {
            "status": "success",
            "message": "规则更新成功",
            "rule": custom_alert_rules[rule_index]
        }
        
    except Exception as e:
        logging.error(f"更新自定义预警规则失败: {e}")
        return {"status": "error", "message": str(e)}

@app.delete("/api/custom-alert-rules/{rule_id}")
async def delete_custom_alert_rule(rule_id: int):
    """删除自定义预警规则"""
    try:
        # 查找并删除规则
        for i, rule in enumerate(custom_alert_rules):
            if rule["id"] == rule_id:
                deleted_rule = custom_alert_rules.pop(i)
                logging.info(f"删除自定义预警规则: {deleted_rule['name']}")
                return {
                    "status": "success",
                    "message": "规则删除成功"
                }
        
        return {"status": "error", "message": "规则不存在"}
        
    except Exception as e:
        logging.error(f"删除自定义预警规则失败: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/custom-alert-rules/cleanup")
async def cleanup_duplicate_rules():
    """清理重复的自定义预警规则"""
    try:
        global custom_alert_rules
        
        # 按名称分组，保留最新的规则
        rules_by_name = {}
        system_rules = []
        
        for rule in custom_alert_rules:
            if rule.get('is_system_rule', False):
                system_rules.append(rule)
            else:
                rule_name = rule.get('name')
                if rule_name:
                    if rule_name not in rules_by_name:
                        rules_by_name[rule_name] = rule
                    else:
                        # 比较创建时间，保留较新的
                        current_time = rule.get('created_at', '')
                        existing_time = rules_by_name[rule_name].get('created_at', '')
                        if current_time > existing_time:
                            rules_by_name[rule_name] = rule
        
        # 重新构建规则列表
        cleaned_user_rules = list(rules_by_name.values())
        original_count = len(custom_alert_rules)
        
        custom_alert_rules = system_rules + cleaned_user_rules
        new_count = len(custom_alert_rules)
        
        removed_count = original_count - new_count
        
        logging.info(f"清理重复规则完成: 移除 {removed_count} 个重复规则")
        
        return {
            "status": "success",
            "message": f"清理完成，移除了 {removed_count} 个重复规则",
            "removed_count": removed_count,
            "total_rules": new_count
        }
        
    except Exception as e:
        logging.error(f"清理重复规则失败: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/export/alerts")
async def export_alerts(timeRange: str = "today", format: str = "csv", 
                       startDate: str = None, endDate: str = None):
    """导出预警记录"""
    try:
        from datetime import datetime, timedelta
        import csv
        import json
        from io import StringIO
        from fastapi.responses import StreamingResponse
        
        # 确定时间范围
        now = datetime.now()
        if timeRange == "today":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now
        elif timeRange == "week":
            start_time = now - timedelta(days=7)
            end_time = now
        elif timeRange == "month":
            start_time = now - timedelta(days=30)
            end_time = now
        elif timeRange == "custom" and startDate and endDate:
            start_time = datetime.fromisoformat(startDate)
            end_time = datetime.fromisoformat(endDate)
        else:
            start_time = now - timedelta(days=1)
            end_time = now
        
        # 获取预警数据（这里使用recent_alerts作为示例）
        alerts_data = []
        for alert in recent_alerts:
            alert_time = datetime.fromisoformat(alert.get("timestamp", ""))
            if start_time <= alert_time <= end_time:
                alerts_data.append({
                    "时间": alert.get("timestamp", ""),
                    "类型": alert.get("type", ""),
                    "内容": alert.get("content", ""),
                    "级别": alert.get("level", ""),
                    "详情": alert.get("details", "")
                })
        
        if format == "csv":
            output = StringIO()
            if alerts_data:
                fieldnames = alerts_data[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(alerts_data)
            
            response = StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=alerts_{timeRange}.csv"}
            )
        elif format == "json":
            json_data = json.dumps(alerts_data, ensure_ascii=False, indent=2)
            response = StreamingResponse(
                iter([json_data]),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=alerts_{timeRange}.json"}
            )
        else:
            return {"status": "error", "message": "不支持的导出格式"}
        
        return response
        
    except Exception as e:
        logging.error(f"导出预警记录失败: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/export/behavior")
async def export_behavior_data(timeRange: str = "today", format: str = "csv",
                              startDate: str = None, endDate: str = None):
    """导出行为数据"""
    try:
        from datetime import datetime, timedelta
        import csv
        import json
        from io import StringIO
        from fastapi.responses import StreamingResponse
        from video_database import video_db
        
        # 确定时间范围
        now = datetime.now()
        if timeRange == "today":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        elif timeRange == "week":
            start_time = (now - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        elif timeRange == "month":
            start_time = (now - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        elif timeRange == "custom" and startDate and endDate:
            start_time = f"{startDate} 00:00:00"
            end_time = f"{endDate} 23:59:59"
        else:
            start_time = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        
        # 从数据库获取行为数据
        activities = video_db.get_activities_by_time_range(start_time, end_time)
        
        behavior_data = []
        for activity in activities:
            behavior_data.append({
                "ID": activity.get("id", ""),
                "活动类型": activity.get("activity_type", ""),
                "内容描述": activity.get("content", ""),
                "开始时间": activity.get("start_time", ""),
                "结束时间": activity.get("end_time", ""),
                "持续时间(分钟)": activity.get("duration_minutes", 0),
                "置信度": activity.get("confidence_score", 0),
                "来源类型": activity.get("source_type", "")
            })
        
        if format == "csv":
            output = StringIO()
            if behavior_data:
                fieldnames = behavior_data[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(behavior_data)
            
            response = StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=behavior_{timeRange}.csv"}
            )
        elif format == "json":
            json_data = json.dumps(behavior_data, ensure_ascii=False, indent=2)
            response = StreamingResponse(
                iter([json_data]),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=behavior_{timeRange}.json"}
            )
        else:
            return {"status": "error", "message": "不支持的导出格式"}
        
        return response
        
    except Exception as e:
        logging.error(f"导出行为数据失败: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/system/status")
async def get_system_status():
    """获取系统状态"""
    try:
        # 检查各个组件状态
        status = {
            "aiModel": "online",
            "videoStream": "online", 
            "database": "online"
        }
        
        # 检查视频处理器状态
        if hasattr(video_processor, 'video_source'):
            try:
                # 简单检查视频源是否可用
                status["videoStream"] = "online"
            except:
                status["videoStream"] = "offline"
        else:
            status["videoStream"] = "offline"
        
        # 检查数据库连接
        try:
            from video_database import video_db
            video_db.get_recent_activities(1)  # 尝试查询
            status["database"] = "online"
        except:
            status["database"] = "offline"
        
        # 检查AI模型状态（简化检查）
        try:
            from llm_service import chat_completion
            status["aiModel"] = "online"
        except:
            status["aiModel"] = "offline"
        
        return status
        
    except Exception as e:
        logging.error(f"获取系统状态失败: {e}")
        return {
            "aiModel": "unknown",
            "videoStream": "unknown",
            "database": "unknown"
        }

if __name__ == "__main__":
    # 确保设置了正确的启动方法 (如果需要)
    # try:
    #     set_start_method("spawn")
    # except RuntimeError:
    #     pass
    print(f"启动视频服务器 http://{ServerConfig.HOST}:{ServerConfig.PORT}")
    uvicorn.run( 
        "video_server:app", # 使用字符串形式以支持热重载
        host=ServerConfig.HOST,
        port=ServerConfig.PORT,
        log_level="info",
        reload=False
        #reload=ServerConfig.RELOAD # 从配置读取是否热重载
    )
