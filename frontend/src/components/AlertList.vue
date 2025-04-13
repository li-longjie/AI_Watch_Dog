<template>
  <div class="alerts-panel">
    <div class="panel-title">预警信息</div>
    <div class="alerts-container" ref="alertsContainer">
      <div v-if="groupedAlerts.length === 0" class="no-alerts">
        暂无预警信息
      </div>
      <div v-else>
        <div v-for="(group, index) in groupedAlerts" :key="group.id" class="alert-group">
          <div
            class="alert-item"
            :class="{
              'alert-important': isImportantAlert(group.alerts[0]) && group.activity !== '专注工作学习',
              'alert-focus': group.activity === '专注工作学习'
            }"
            @click="replayAlert(group.alerts[0])"
            title="点击查看详情"
          >
            <div class="alert-icon" v-if="group.activity !== '专注工作学习'">
              <i class="fas fa-exclamation-triangle"></i>
            </div>
            <div class="alert-content" :class="{'focus-content': group.activity === '专注工作学习'}">
              <div class="alert-timestamp">{{ formatTime(group.timestamp) }}</div>
              <div class="alert-message">
                <template v-if="group.isComplete">
                  {{ group.activity }}：{{ formatDuration(group.duration_minutes) }}
                  <div class="alert-time-range">
                    {{ formatTime(group.start_time) }} - {{ formatTime(group.end_time) }}
                  </div>
                </template>
                <template v-else>
                  {{ group.activity }}
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';

const props = defineProps({
  alerts: {
    type: Array,
    required: true,
    default: () => []
  }
});

const emit = defineEmits(['replay-alert']);
const alertsContainer = ref(null);

// 按活动ID对预警进行分组
const groupedAlerts = computed(() => {
  const groups = {};

  // 首先对alerts按时间排序（最新的在前）
  const sortedAlerts = [...props.alerts].sort((a, b) =>
    new Date(b.timestamp) - new Date(a.timestamp)
  );

  // 按activity_id分组
  sortedAlerts.forEach(alert => {
     // 使用 activity_id 或生成一个基于行为和开始时间的 ID
    const activityId = alert.activity_id || `${alert.content}_${new Date(alert.start_time || alert.timestamp).getTime()}`;
    if (!groups[activityId]) {
      groups[activityId] = {
        id: activityId,
        alerts: [],
        startAlert: null,
        endAlert: null,
        isComplete: false,
        activity: '未知活动' // 初始化活动名称
      };
    }

    // 添加到组
    groups[activityId].alerts.push(alert);

    // 判断是开始还是结束预警，并提取活动名称
    if (alert.content?.includes('结束')) {
        groups[activityId].endAlert = alert;
        // 从结束信息中提取活动名
        groups[activityId].activity = alert.content.split('结束')[0];
    } else {
        // 假设非结束预警都是开始预警或单一预警
        groups[activityId].startAlert = groups[activityId].startAlert || alert; // 保留最早的开始预警
        groups[activityId].activity = alert.content; // 直接使用内容作为活动名
    }

    // 标记组是否完成
    groups[activityId].isComplete = groups[activityId].startAlert && groups[activityId].endAlert;
  });

  // 处理每个组的数据
  return Object.values(groups).map(group => {
    // 确定主要时间戳和级别
    const mainAlert = group.endAlert || group.startAlert; // 优先使用结束或开始预警
    const displayTimestamp = mainAlert?.timestamp || group.alerts[0]?.timestamp;
    const level = mainAlert?.level || group.alerts[0]?.level;

    return {
      id: group.id,
      alerts: group.alerts, // 保留原始预警列表
      timestamp: displayTimestamp, // 用于排序和显示的时间戳
      activity: group.activity, // 组的活动名称
      isComplete: group.isComplete, // 是否是完整活动（有开始有结束）
      start_time: group.startAlert?.start_time || group.startAlert?.timestamp, // 开始时间
      end_time: group.endAlert?.end_time || group.endAlert?.timestamp, // 结束时间
      duration_minutes: group.endAlert?.duration_minutes || 0, // 持续时间
      level: level // 预警级别
    };
  }).sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)); // 最新的在前
});


const isImportantAlert = (alert) => {
  // 如果 alert 不存在或 level 不存在，则认为不是 important
  if (!alert || !alert.level) {
      return false;
  }
  // "专注工作学习" 即使 level 是 important 也不标记为 alert-important
  if (alert.content === '专注工作学习') {
      return false;
  }
  return alert.level === 'important';
};


const formatTime = (timeString) => {
  if (!timeString) return '';
  try {
    const date = new Date(timeString);
    // 返回 HH:mm:ss 格式
    return date.toLocaleTimeString('zh-CN', { hour12: false });
  } catch (e) {
     console.error("时间格式化错误:", timeString, e);
     // 尝试提取时间部分
     const parts = String(timeString).split(' ');
     if (parts.length > 1) {
        // 检查第二部分是否是时间格式
        if (/\d{1,2}:\d{1,2}:\d{1,2}/.test(parts[1])) {
            return parts[1];
        }
     }
     return timeString; // 返回原始字符串作为后备
  }
};


const formatDuration = (minutes) => {
  if (minutes === undefined || minutes === null || minutes < 0) return '未知时长';
  if (minutes < 1) {
    const seconds = Math.round(minutes * 60);
    return `${seconds}秒`;
  }
  return `${minutes.toFixed(1)}分钟`;
};

const replayAlert = (alert) => {
  emit('replay-alert', alert);
};

// 监听新预警，自动滚动到顶部
watch(() => props.alerts.length, () => {
  if (alertsContainer.value) {
    setTimeout(() => {
      // 仅在滚动条不在顶部时滚动
      if (alertsContainer.value.scrollTop > 10) {
          // 不滚动，让用户保持当前位置
      } else {
          alertsContainer.value.scrollTop = 0;
      }
    }, 100);
  }
}, { deep: true }); // 使用 deep watch 监听数组内部变化


onMounted(() => {
  if (alertsContainer.value) {
    alertsContainer.value.scrollTop = 0;
  }
});
</script>

<style scoped>
.alerts-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: none; /* 背景由父组件控制 */
  border-radius: 8px;
  overflow: hidden;
}

.panel-title {
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.2), transparent);
  color: #ef4444;
  padding: 10px 15px;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid rgba(239, 68, 68, 0.3);
  display: flex;
  align-items: center;
  flex-shrink: 0; /* 防止标题被压缩 */
}

.panel-title::before {
  content: "";
  display: inline-block;
  width: 10px;
  height: 10px;
  background-color: #ef4444;
  border-radius: 50%;
  margin-right: 10px;
}

.alerts-container {
  flex-grow: 1;
  overflow-y: auto;
  padding: 10px;
}

.alert-group {
  margin-bottom: 8px; /* Reduced margin */
}

.alert-item {
  display: flex;
  align-items: center; /* Vertically align icon and content */
  /* Glassmorphism base */
  background-color: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-left-width: 4px; /* Default left border */
  border-left-color: rgba(248, 113, 113, 0.7); /* Default alert color (light red) */
  border-radius: 6px;
  margin-bottom: 6px;
  overflow: hidden;
  transition: all 0.3s ease;
  cursor: pointer;
  padding: 8px 0px 8px 0px; /* Add padding for content */
}

.alert-item:hover {
  background-color: rgba(255, 255, 255, 0.12);
  transform: translateY(-2px) scale(1.01);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
  border-color: rgba(255, 255, 255, 0.2);
  /* Keep left border color consistent on hover unless specified */
}

.alert-important {
  border-left-color: #ef4444; /* Strong red for important */
  /* Optional: Add a subtle background tint for important alerts */
  /* background-color: rgba(239, 68, 68, 0.05); */
}
.alert-important:hover {
   border-left-color: #dc2626; /* Darker red on hover */
}

/* Style for '专注工作学习' */
.alert-focus {
  border-left-color: #10b981; /* Green border for focus */
  background-color: rgba(16, 185, 129, 0.08); /* Subtle green background */
}
.alert-focus:hover {
  border-left-color: #059669; /* Darker green on hover */
  background-color: rgba(16, 185, 129, 0.12);
}

.alert-icon {
  flex-shrink: 0; /* Prevent icon from shrinking */
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 12px; /* Adjust padding */
  font-size: 1.1em; /* Slightly larger icon */
  color: rgba(248, 113, 113, 0.8); /* Default icon color */
}

.alert-important .alert-icon {
  color: #ef4444; /* Important icon color */
}
/* Focus alert has no icon by default due to v-if */


.alert-content {
  flex-grow: 1;
  padding: 0 10px 0 0; /* Padding only on the right now */
  color: #e2e8f0;
}
/* Adjust content padding if icon is hidden */
.focus-content {
    padding-left: 12px; /* Add left padding when icon is hidden */
}

.alert-timestamp {
  font-size: 12px;
  color: #bdc3cf; /* Lighter secondary text */
  margin-bottom: 3px;
}

.alert-message {
  font-size: 14px;
}

.alert-time-range {
  font-size: 12px;
  color: #bdc3cf;
  margin-top: 3px;
}

.alert-actions {
  display: none;
}

.replay-btn {
  display: none;
}

.no-alerts {
  text-align: center;
  padding: 20px;
  color: #bdc3cf; /* Lighter placeholder text */
  font-style: italic;
}

/* 滚动条样式 */
.alerts-container::-webkit-scrollbar {
  width: 6px;
}

.alerts-container::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05); /* Match glass background */
  border-radius: 3px;
}

.alerts-container::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2); /* Lighter thumb */
  border-radius: 3px;
}

.alerts-container::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style> 