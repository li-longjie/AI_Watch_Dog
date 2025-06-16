<template>
  <div class="alerts-panel">
    <div class="panel-title">预警信息</div>
    <div class="alerts-container" ref="alertsContainer">
      <div v-if="sortedAlerts.length === 0" class="no-alerts">
        暂无预警信息
      </div>
      <div v-else>
        <!-- 直接遍历排序后的预警，不再分组 -->
        <div v-for="alert in sortedAlerts" :key="alert.alert_key" class="alert-group">
          <div
            class="alert-item"
            :class="getAlertLevelClass(alert)"
            @click="replayAlert(alert)"
            title="点击查看详情"
          >
            <div class="alert-icon" v-if="shouldShowIcon(alert)">
              <i class="fas fa-exclamation-triangle"></i>
            </div>
            <div class="alert-content" :class="{'low-content': isLowAlert(alert)}">
              <div class="alert-timestamp">{{ formatTime(alert.timestamp) }}</div>
              <div class="alert-message">
                <!-- 判断是否是结束预警 -->
                <template v-if="alert.type && alert.type.includes('end')">
                  {{ alert.content.replace('结束', '') }}：{{ formatDuration(alert.duration_minutes) }}
                  <div class="alert-time-range">
                    {{ formatTime(alert.start_time) }} - {{ formatTime(alert.end_time) }}
                  </div>
                </template>
                <!-- 如果是开始预警或单次预警 -->
                <template v-else>
                  {{ alert.content }}
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

// 直接对传入的 alerts 数组进行排序，不再进行分组
const sortedAlerts = computed(() => {
  return [...props.alerts].sort((a, b) =>
    new Date(b.timestamp) - new Date(a.timestamp)
  );
});

// 根据预警级别获取对应的CSS类
const getAlertLevelClass = (alert) => {
  const level = alert.level;
  
  // 专注工作学习保持绿色样式
  if (alert.content.includes('专注工作学习')) {
    return 'alert-focus';
  }
  
  // 根据级别返回对应的样式类
  switch (level) {
    case 'low':
      return 'alert-low';
    case 'medium':
      return 'alert-medium';
    case 'high':
      return 'alert-high';
    default:
      return 'alert-medium'; // 默认中级
  }
};

// 判断是否为低级预警
const isLowAlert = (alert) => {
  return alert.level === 'low' || alert.content.includes('专注工作学习');
};

// 判断是否显示预警图标
const shouldShowIcon = (alert) => {
  // 低级预警（包括专注工作学习）不显示图标
  return alert.level !== 'low' && !alert.content.includes('专注工作学习');
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

/* 低级预警样式 - 绿色 */
.alert-low {
  border-left-color: #10b981; /* Green border */
  background-color: rgba(16, 185, 129, 0.08); /* Subtle green background */
}
.alert-low:hover {
  border-left-color: #059669; /* Darker green on hover */
  background-color: rgba(16, 185, 129, 0.12);
}

/* 中级预警样式 - 黄色 */
.alert-medium {
  border-left-color: #f59e0b; /* Amber/yellow border */
  background-color: rgba(245, 158, 11, 0.08); /* Subtle amber background */
}
.alert-medium:hover {
  border-left-color: #d97706; /* Darker amber on hover */
  background-color: rgba(245, 158, 11, 0.12);
}

/* 高级预警样式 - 红色 */
.alert-high {
  border-left-color: #ef4444; /* Red border */
  background-color: rgba(239, 68, 68, 0.08); /* Subtle red background */
}
.alert-high:hover {
  border-left-color: #dc2626; /* Darker red on hover */
  background-color: rgba(239, 68, 68, 0.12);
}

/* Style for '专注工作学习' - 保持原有绿色样式 */
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

/* 中级预警图标 - 黄色 */
.alert-medium .alert-icon {
  color: #f59e0b; /* Amber icon color */
}

/* 高级预警图标 - 红色 */
.alert-high .alert-icon {
  color: #ef4444; /* Red icon color */
}

/* 低级预警和专注工作学习不显示图标 */


.alert-content {
  flex-grow: 1;
  padding: 0 10px 0 0; /* Padding only on the right now */
  color: #e2e8f0;
}

/* 调整没有图标的预警内容padding */
.low-content {
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