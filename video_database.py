import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
import os

# 数据库文件路径
DATABASE_PATH = "video_activities.db"

class VideoDatabase:
    """视频活动数据库管理类"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 视频活动主表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    activity_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_minutes REAL DEFAULT 0,
                    confidence_score REAL DEFAULT 0,
                    image_path TEXT,
                    metadata_json TEXT,
                    source_type TEXT DEFAULT 'video_analysis',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 活动会话表 (用于聚合统计)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    activity_type TEXT NOT NULL,
                    session_start TEXT NOT NULL,
                    session_end TEXT NOT NULL,
                    total_duration REAL NOT NULL,
                    event_count INTEGER DEFAULT 1,
                    daily_date TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引以优化查询性能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_type ON video_activities(activity_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_start_time ON video_activities(start_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_type ON video_activities(source_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_date ON activity_sessions(daily_date)')
            
            conn.commit()
            logging.info("视频活动数据库初始化完成")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 支持字典式访问
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logging.error(f"数据库操作失败: {e}")
            raise
        finally:
            conn.close()
    
    def insert_activity(self, activity_data: Dict[str, Any]) -> int:
        """插入新的活动记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO video_activities 
                (activity_type, content, start_time, end_time, duration_minutes, 
                 confidence_score, image_path, metadata_json, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                activity_data.get('activity_type'),
                activity_data.get('content'),
                activity_data.get('start_time'),
                activity_data.get('end_time'),
                activity_data.get('duration_minutes', 0),
                activity_data.get('confidence_score', 0),
                activity_data.get('image_path'),
                json.dumps(activity_data.get('metadata', {})),
                activity_data.get('source_type', 'video_analysis')
            ))
            
            activity_id = cursor.lastrowid
            conn.commit()
            
            logging.info(f"插入活动记录: ID={activity_id}, 类型={activity_data.get('activity_type')}")
            return activity_id
    
    def update_activity_end_time(self, activity_id: int, end_time: str, duration_minutes: float):
        """更新活动的结束时间和持续时长"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE video_activities 
                SET end_time = ?, duration_minutes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (end_time, duration_minutes, activity_id))
            
            conn.commit()
            logging.info(f"更新活动记录: ID={activity_id}, 持续时长={duration_minutes}分钟")
    
    def get_activities_by_time_range(self, start_time: str, end_time: str, 
                                   activity_type: Optional[str] = None) -> List[Dict]:
        """按时间范围查询活动记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            sql = '''
                SELECT * FROM video_activities 
                WHERE start_time >= ? AND start_time <= ?
            '''
            params = [start_time, end_time]
            
            if activity_type:
                sql += ' AND activity_type = ?'
                params.append(activity_type)
            
            sql += ' ORDER BY start_time DESC'
            
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_activity_statistics(self, date_str: str, activity_type: Optional[str] = None) -> Dict:
        """获取指定日期的活动统计"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 构建日期范围
            start_date = f"{date_str} 00:00:00"
            end_date = f"{date_str} 23:59:59"
            
            sql = '''
                SELECT 
                    activity_type,
                    COUNT(*) as event_count,
                    SUM(duration_minutes) as total_duration,
                    AVG(duration_minutes) as avg_duration,
                    MIN(start_time) as first_occurrence,
                    MAX(COALESCE(end_time, start_time)) as last_occurrence
                FROM video_activities 
                WHERE start_time >= ? AND start_time <= ?
            '''
            params = [start_date, end_date]
            
            if activity_type:
                sql += ' AND activity_type = ?'
                params.append(activity_type)
                sql += ' GROUP BY activity_type'
            else:
                sql += ' GROUP BY activity_type'
            
            cursor.execute(sql, params)
            results = cursor.fetchall()
            
            statistics = {}
            for row in results:
                statistics[row['activity_type']] = {
                    'event_count': row['event_count'],
                    'total_duration': row['total_duration'] or 0,
                    'avg_duration': row['avg_duration'] or 0,
                    'first_occurrence': row['first_occurrence'],
                    'last_occurrence': row['last_occurrence']
                }
            
            return statistics
    
    def get_recent_activities(self, limit: int = 50) -> List[Dict]:
        """获取最近的活动记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM video_activities 
                ORDER BY start_time DESC 
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def create_activity_session(self, activity_type: str, session_start: str, 
                              session_end: str, total_duration: float, event_count: int):
        """创建活动会话记录(用于日常统计)"""
        daily_date = session_start.split()[0]  # 提取日期部分
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO activity_sessions 
                (activity_type, session_start, session_end, total_duration, event_count, daily_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (activity_type, session_start, session_end, total_duration, event_count, daily_date))
            
            conn.commit()
            logging.info(f"创建活动会话: {activity_type}, 持续{total_duration}分钟")
    
    def search_activities_by_content(self, keyword: str, limit: int = 20) -> List[Dict]:
        """基于内容关键词搜索活动"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM video_activities 
                WHERE content LIKE ? 
                ORDER BY start_time DESC 
                LIMIT ?
            ''', (f'%{keyword}%', limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_activity_by_id(self, activity_id: int) -> Optional[Dict]:
        """根据ID获取活动记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM video_activities WHERE id = ?', (activity_id,))
            row = cursor.fetchone()
            
            return dict(row) if row else None
    
    def delete_old_activities(self, days_to_keep: int = 30):
        """删除过期的活动记录"""
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d %H:%M:%S')
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM video_activities WHERE start_time < ?', (cutoff_date,))
            deleted_count = cursor.rowcount
            
            conn.commit()
            logging.info(f"删除了{deleted_count}条过期活动记录")
            return deleted_count

# 全局数据库实例
video_db = VideoDatabase() 