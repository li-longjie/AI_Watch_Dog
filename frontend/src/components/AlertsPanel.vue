<template>
  <div>
    <div class="panel-title">预警信息</div>
    <div class="alerts-list-container">
      <ul v-if="alerts.length > 0" class="alerts-list">
        <li v-for="alert in alerts" :key="alert.timestamp" :class="['alert-item', `alert-${alert.level || 'info'}`]" @click="emit('view-alert', alert)" style="cursor: pointer;">
          <span class="alert-icon">⚠️</span> <!-- 可以根据 level 改变图标 -->
          <div class="alert-content">
            <span class="alert-timestamp">{{ formatTimestamp(alert.timestamp) }}</span>
            <span class="alert-message">{{ alert.content }}</span>
            <span v-if="alert.details" class="alert-details">{{ alert.details }}</span>
          </div>
          <!-- 可以添加按钮用于查看详情或回放 -->
          <!-- <button @click="showAlertDetails(alert)">查看</button> -->
        </li>
      </ul>
      <div v-else class="no-alerts">暂无预警信息</div>
      <div class="data-stream-decoration"></div>
    </div>
  </div>
</template>

<script setup>
// defineProps 是宏，通常无需显式导入，但写上更清晰
const emit = defineEmits(['view-alert']); // 定义要触发的事件

// 定义接收的 prop
const props = defineProps({
  alerts: {
    type: Array,
    required: true,
    default: () => [] // 提供默认值
  }
});

// 格式化时间戳 (可以提取为公共工具函数)
const formatTimestamp = (isoString) => {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    // 返回 HH:mm:ss 格式
    return date.toLocaleTimeString('zh-CN', { hour12: false });
  } catch (e) {
    console.error("无法格式化时间戳:", isoString, e);
    return isoString; // 返回原始字符串
  }
};

// 点击预警项的逻辑 (可选)
// const showAlertDetails = (alert) => {
//   console.log('查看预警详情:', alert);
//   // 现在直接在模板中使用 emit
// };
</script>

<style scoped>
/* 预警信息面板特定样式 */
.alerts-list-container {
  flex-grow: 1;
  overflow-y: auto;
  position: relative;
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
  padding: 10px;
}

.alerts-list {
  list-style: none;
  padding: 0;
  margin: 0;
  position: relative;
  z-index: 2;
}

.alert-item {
  padding: 10px;
  margin-bottom: 8px;
  background-color: rgba(0, 0, 0, 0.3);
  border-left: 3px solid var(--primary);
  border-radius: 0 4px 4px 0;
  display: flex;
  align-items: flex-start;
  transition: all 0.2s ease;
}

.alert-item:hover {
  background-color: rgba(0, 0, 0, 0.5);
  transform: translateX(3px);
}

.alert-icon {
  margin-right: 10px;
  font-size: 1.2em;
}

.alert-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.alert-timestamp {
  font-size: 0.8em;
  color: var(--text-secondary);
  margin-bottom: 3px;
}

.alert-message {
  word-break: break-word;
}

.alert-warning {
  border-left-color: var(--warning, #ffcc00);
}

.alert-danger {
  border-left-color: var(--danger, #ff4d4d);
}

.no-alerts {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100px;
  color: var(--text-secondary);
  font-style: italic;
  position: relative;
  z-index: 2;
}

/* 数据流装饰 */
.data-stream-decoration {
  position: absolute;
  top: 0;
  right: 0;
  width: 2px;
  height: 100%;
  background: linear-gradient(to bottom, 
    transparent, 
    var(--cyber-neon), 
    transparent);
  opacity: 0.5;
  animation: dataStreamFlow 3s infinite linear;
  pointer-events: none;
}

@keyframes dataStreamFlow {
  0% { transform: translateY(-100%); }
  100% { transform: translateY(100%); }
}
</style> 