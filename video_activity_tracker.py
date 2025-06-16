import logging
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
import time
from collections import defaultdict
from video_database import video_db
from video_vector_manager import video_vector_manager

class VideoActivityTracker:
    """视频活动持续时间智能跟踪器"""
    
    def __init__(self):
        self.db = video_db
        self.vector_manager = video_vector_manager
        
        # 当前活动状态跟踪
        self.current_activities: Dict[str, Dict] = {}
        
        # 活动延续阈值 (秒)
        self.activity_continuation_threshold = 180  # 3分钟内算同一活动
        
        # 最小持续时间 (分钟)
        self.min_duration_to_record = 0.5  # 30秒以上才记录持续时间
        
        # 活动类型配置
        self.activity_configs = {
            "睡觉": {
                "max_gap": 300,  # 5分钟间隔内算连续
                "min_duration": 10,  # 至少10分钟才算睡觉
                "merge_threshold": 180  # 3分钟内的分段合并
            },
            "专注工作学习": {
                "max_gap": 120,  # 2分钟间隔内算连续
                "min_duration": 5,   # 至少5分钟
                "merge_threshold": 120
            },
            "玩手机": {
                "max_gap": 60,   # 1分钟间隔内算连续
                "min_duration": 1,   # 至少1分钟
                "merge_threshold": 60
            },
            "吃东西": {
                "max_gap": 180,  # 3分钟间隔内算连续
                "min_duration": 2,   # 至少2分钟
                "merge_threshold": 120
            },
            "喝水": {
                "max_gap": 60,   # 1分钟间隔内算连续
                "min_duration": 0.5, # 30秒
                "merge_threshold": 60
            },
            "喝饮料": {
                "max_gap": 120,  # 2分钟间隔内算连续
                "min_duration": 1,   # 1分钟
                "merge_threshold": 90
            }
        }
        
        # 历史活动缓存 (用于智能合并)
        self.recent_activities_cache: Dict[str, List[Dict]] = defaultdict(list)
        self.cache_duration = 1800  # 30分钟缓存
    
    async def process_detection_result(self, detection_result: str, timestamp: str, 
                                     image_path: Optional[str] = None) -> Optional[int]:
        """处理检测结果并智能跟踪活动持续时间"""
        try:
            # 解析检测结果
            activity_info = self._parse_detection_result(detection_result, timestamp)
            if not activity_info:
                return None
            
            activity_type = activity_info['activity_type']
            current_time = activity_info['timestamp']
            content = activity_info['content']
            
            # 检查是否是现有活动的延续
            continuation_result = await self._check_activity_continuation(
                activity_type, current_time, content
            )
            
            if continuation_result['is_continuation']:
                # 更新现有活动
                activity_id = await self._update_existing_activity(
                    continuation_result['existing_activity_id'],
                    current_time, content
                )
                logging.info(f"更新活动持续时间: {activity_type}, ID={activity_id}")
                return activity_id
            else:
                # 创建新活动
                activity_id = await self._create_new_activity(
                    activity_type, current_time, content, image_path
                )
                
                # 检查是否需要与历史活动合并
                await self._check_and_merge_with_history(activity_id, activity_type, current_time)
                
                logging.info(f"创建新活动: {activity_type}, ID={activity_id}")
                return activity_id
                
        except Exception as e:
            logging.error(f"处理检测结果失败: {e}")
            return None
    
    def _parse_detection_result(self, detection_result: str, timestamp: str) -> Optional[Dict]:
        """解析检测结果"""
        try:
            # 检测结果格式: "2025-01-15 14:30:00 玩手机"
            parts = detection_result.strip().split(' ', 2)
            if len(parts) >= 3:
                date_part = parts[0]
                time_part = parts[1]
                activity_type = parts[2]
                
                # 重新组合时间戳
                parsed_timestamp = f"{date_part} {time_part}"
                
                return {
                    'activity_type': activity_type,
                    'timestamp': parsed_timestamp,
                    'content': detection_result,
                    'confidence': 1.0  # 默认置信度
                }
            else:
                logging.warning(f"检测结果格式不正确: {detection_result}")
                return None
                
        except Exception as e:
            logging.error(f"解析检测结果失败: {e}")
            return None
    
    async def _check_activity_continuation(self, activity_type: str, current_time: str, 
                                         content: str) -> Dict:
        """检查是否为现有活动的延续"""
        result = {
            'is_continuation': False,
            'existing_activity_id': None,
            'time_gap': None
        }
        
        try:
            # 获取当前活动状态
            if activity_type in self.current_activities:
                current_activity = self.current_activities[activity_type]
                last_time = current_activity['last_update']
                
                # 计算时间间隔
                current_dt = datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
                last_dt = datetime.strptime(last_time, '%Y-%m-%d %H:%M:%S')
                time_gap = (current_dt - last_dt).total_seconds()
                
                # 获取活动配置
                config = self.activity_configs.get(activity_type, {})
                max_gap = config.get('max_gap', self.activity_continuation_threshold)
                
                if time_gap <= max_gap:
                    result['is_continuation'] = True
                    result['existing_activity_id'] = current_activity['activity_id']
                    result['time_gap'] = time_gap
                else:
                    # 间隔太长，结束当前活动
                    await self._finalize_current_activity(activity_type)
            
            return result
            
        except Exception as e:
            logging.error(f"检查活动延续失败: {e}")
            return result
    
    async def _create_new_activity(self, activity_type: str, start_time: str, 
                                 content: str, image_path: Optional[str] = None) -> int:
        """创建新的活动记录"""
        activity_data = {
            'activity_type': activity_type,
            'content': content,
            'start_time': start_time,
            'end_time': None,  # 暂时为空，后续更新
            'duration_minutes': 0,
            'confidence_score': 1.0,
            'image_path': image_path,
            'metadata': {
                'created_by': 'video_activity_tracker',
                'is_ongoing': True
            },
            'source_type': 'video_analysis'
        }
        
        # 插入数据库
        activity_id = self.db.insert_activity(activity_data)
        
        # 更新当前活动状态
        self.current_activities[activity_type] = {
            'activity_id': activity_id,
            'start_time': start_time,
            'last_update': start_time,
            'content_list': [content]
        }
        
        # 添加到向量数据库
        activity_data['id'] = activity_id  # 添加ID用于向量化
        await self.vector_manager.add_activity_to_vector_db(activity_id, activity_data)
        
        return activity_id
    
    async def _update_existing_activity(self, activity_id: int, current_time: str, 
                                      content: str) -> int:
        """更新现有活动的结束时间和持续时长"""
        try:
            # 获取活动信息
            activity = self.db.get_activity_by_id(activity_id)
            if not activity:
                logging.error(f"活动不存在: ID={activity_id}")
                return activity_id
            
            activity_type = activity['activity_type']
            start_time = activity['start_time']
            
            # 计算持续时长
            start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            current_dt = datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
            duration_minutes = (current_dt - start_dt).total_seconds() / 60
            
            # 更新数据库
            self.db.update_activity_end_time(activity_id, current_time, duration_minutes)
            
            # 更新当前活动状态
            if activity_type in self.current_activities:
                self.current_activities[activity_type]['last_update'] = current_time
                self.current_activities[activity_type]['content_list'].append(content)
            
            # 更新向量数据库
            updated_activity_data = {
                'activity_type': activity_type,
                'content': f"{activity['content']} | {content}",  # 合并内容
                'start_time': start_time,
                'end_time': current_time,
                'duration_minutes': duration_minutes,
                'source_type': 'video_analysis'
            }
            await self.vector_manager.update_activity_in_vector_db(activity_id, updated_activity_data)
            
            return activity_id
            
        except Exception as e:
            logging.error(f"更新现有活动失败: {e}")
            return activity_id
    
    async def _finalize_current_activity(self, activity_type: str):
        """结束当前活动"""
        if activity_type not in self.current_activities:
            return
        
        try:
            current_activity = self.current_activities[activity_type]
            activity_id = current_activity['activity_id']
            last_time = current_activity['last_update']
            
            # 获取活动记录
            activity = self.db.get_activity_by_id(activity_id)
            if activity:
                start_time = activity['start_time']
                start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                end_dt = datetime.strptime(last_time, '%Y-%m-%d %H:%M:%S')
                duration_minutes = (end_dt - start_dt).total_seconds() / 60
                
                # 检查是否满足最小持续时间
                config = self.activity_configs.get(activity_type, {})
                min_duration = config.get('min_duration', self.min_duration_to_record)
                
                if duration_minutes >= min_duration:
                    # 更新结束时间
                    self.db.update_activity_end_time(activity_id, last_time, duration_minutes)
                    
                    # 添加到历史缓存
                    self._add_to_history_cache(activity_type, activity)
                    
                    logging.info(f"活动结束: {activity_type}, 持续{duration_minutes:.1f}分钟")
                else:
                    # 持续时间太短，可考虑删除记录
                    logging.info(f"活动持续时间太短，保持记录: {activity_type}, {duration_minutes:.1f}分钟")
            
            # 清除当前活动状态
            del self.current_activities[activity_type]
            
        except Exception as e:
            logging.error(f"结束当前活动失败: {e}")
    
    async def _check_and_merge_with_history(self, activity_id: int, activity_type: str, current_time: str):
        """检查是否需要与历史活动合并"""
        try:
            config = self.activity_configs.get(activity_type, {})
            merge_threshold = config.get('merge_threshold', 180)
            
            # 获取最近的同类型活动
            current_dt = datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
            search_start = current_dt - timedelta(seconds=merge_threshold * 2)
            
            recent_activities = self.db.get_activities_by_time_range(
                search_start.strftime('%Y-%m-%d %H:%M:%S'),
                current_time,
                activity_type
            )
            
            # 查找可合并的活动
            for recent_activity in recent_activities:
                if recent_activity['id'] == activity_id:
                    continue
                
                if recent_activity['end_time']:
                    end_dt = datetime.strptime(recent_activity['end_time'], '%Y-%m-%d %H:%M:%S')
                    time_gap = (current_dt - end_dt).total_seconds()
                    
                    if time_gap <= merge_threshold:
                        # 执行合并
                        await self._merge_activities(recent_activity['id'], activity_id, activity_type)
                        break
            
        except Exception as e:
            logging.error(f"检查历史活动合并失败: {e}")
    
    async def _merge_activities(self, base_activity_id: int, new_activity_id: int, activity_type: str):
        """合并两个活动记录"""
        try:
            base_activity = self.db.get_activity_by_id(base_activity_id)
            new_activity = self.db.get_activity_by_id(new_activity_id)
            
            if not base_activity or not new_activity:
                return
            
            # 计算合并后的时间范围
            start_time = base_activity['start_time']
            end_time = new_activity.get('end_time') or new_activity['start_time']
            
            start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            total_duration = (end_dt - start_dt).total_seconds() / 60
            
            # 合并内容
            merged_content = f"{base_activity['content']} | 合并: {new_activity['content']}"
            
            # 更新基础活动
            self.db.update_activity_end_time(base_activity_id, end_time, total_duration)
            
            # 更新向量数据库
            merged_activity_data = {
                'activity_type': activity_type,
                'content': merged_content,
                'start_time': start_time,
                'end_time': end_time,
                'duration_minutes': total_duration,
                'source_type': 'video_analysis'
            }
            await self.vector_manager.update_activity_in_vector_db(base_activity_id, merged_activity_data)
            
            # 删除新活动记录 (可选，或标记为已合并)
            # 这里我们保留记录，但可以添加合并标记
            
            logging.info(f"活动合并完成: {activity_type}, 基础ID={base_activity_id}, 新ID={new_activity_id}")
            
        except Exception as e:
            logging.error(f"合并活动失败: {e}")
    
    def _add_to_history_cache(self, activity_type: str, activity: Dict):
        """添加活动到历史缓存"""
        current_time = time.time()
        
        # 清理过期缓存
        self.recent_activities_cache[activity_type] = [
            item for item in self.recent_activities_cache[activity_type]
            if current_time - item['cached_at'] < self.cache_duration
        ]
        
        # 添加新记录
        self.recent_activities_cache[activity_type].append({
            'activity': activity,
            'cached_at': current_time
        })
    
    async def finalize_all_activities(self):
        """结束所有当前活动 (系统关闭时调用)"""
        for activity_type in list(self.current_activities.keys()):
            await self._finalize_current_activity(activity_type)
        
        logging.info("所有当前活动已结束")
    
    def get_current_activities_status(self) -> Dict[str, Dict]:
        """获取当前活动状态"""
        status = {}
        current_time = datetime.now()
        
        for activity_type, activity_info in self.current_activities.items():
            start_time = activity_info['start_time']
            start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            current_duration = (current_time - start_dt).total_seconds() / 60
            
            status[activity_type] = {
                'activity_id': activity_info['activity_id'],
                'start_time': start_time,
                'current_duration_minutes': current_duration,
                'content_count': len(activity_info['content_list'])
            }
        
        return status
    
    async def force_end_activity(self, activity_type: str) -> bool:
        """强制结束指定活动"""
        if activity_type in self.current_activities:
            await self._finalize_current_activity(activity_type)
            return True
        return False

# 全局活动跟踪器实例
video_activity_tracker = VideoActivityTracker() 