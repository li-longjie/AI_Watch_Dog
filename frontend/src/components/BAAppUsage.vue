<template>
  <div class="app-usage-panel-container">
    <div class="panel-header">
      <h3 class="panel-title">
        <i class="fas fa-chart-pie"></i> 屏幕使用时长
      </h3>
      <div class="period-selector">
        <button
          v-for="p in periods"
          :key="p.value"
          :class="{ active: p.value === selectedPeriod }"
          @click="changePeriod(p.value)"
        >
          {{ p.label }}
        </button>
      </div>
    </div>
    <div class="usage-content">
      <div v-if="loading" class="loading-state">
        <div class="cyber-spinner"></div>
        <p>加载数据中...</p>
      </div>
      <div v-if="error" class="error-state">
        <p>错误: {{ error }}</p>
        <button @click="fetchUsageData">重试</button>
      </div>
      <div v-if="!loading && !error && usageData" class="data-display">
        <!-- 总使用时长概览 -->
        <div class="total-usage-summary">
            <span class="total-label">总使用时长</span>
            <span class="total-value">{{ usageData.total_usage_str }}</span>
        </div>

        <!-- 应用使用时长列表 -->
        <div class="app-list-container">
          <div v-if="usageData.app_specific_usage.length > 0" class="app-list">
            <div 
              v-for="app in usageData.app_specific_usage" 
              :key="app.app_name" 
              class="app-item"
            >
              <div class="app-info">
                <span class="app-name">{{ app.app_name }}</span>
                <span class="app-duration">{{ app.duration_str }}</span>
              </div>
              <div class="usage-bar-container">
                <div 
                  class="usage-bar" 
                  :style="{ width: `${(app.duration_seconds / maxDuration) * 100}%` }"
                ></div>
              </div>
            </div>
          </div>
          <div v-else class="no-data-state">
            <p>该时段内无应用使用记录</p>
          </div>
        </div>
      </div>
    </div>
     <div class="resize-handle resize-s" @mousedown.stop="e => emit('start-resize', e, 's')"></div>
     <div class="resize-handle resize-n" @mousedown.stop="e => emit('start-resize', e, 'n')"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';

const emit = defineEmits(['start-resize']);

const loading = ref(true);
const error = ref(null);
const usageData = ref(null);

const selectedPeriod = ref('today');
const periods = [
  { label: '今天', value: 'today' },
  { label: '昨天', value: 'yesterday' },
  { label: '本周', value: 'this_week' },
  { label: '本月', value: 'this_month' },
];

const maxDuration = computed(() => {
  if (usageData.value?.app_specific_usage?.length > 0) {
    // The list is sorted descending by the backend, so the first item has the max duration.
    return usageData.value.app_specific_usage[0].duration_seconds;
  }
  return 1; // Return 1 instead of 0 to avoid division by zero errors
});

const getUsageBarWidth = (durationSeconds) => {
  if (maxDuration.value === 0) {
    return '0%';
  }
  const percentage = (durationSeconds / maxDuration.value) * 100;
  return `${percentage}%`;
};

const fetchUsageData = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(`http://localhost:5001/api/usage_stats?period=${selectedPeriod.value}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    usageData.value = data;
  } catch (e) {
    console.error("Failed to fetch usage data:", e);
    error.value = e.message;
  } finally {
    loading.value = false;
  }
};

const changePeriod = (period) => {
  selectedPeriod.value = period;
  fetchUsageData();
};

onMounted(() => {
  fetchUsageData();
});

</script>

<style scoped>
.app-usage-panel-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  color: var(--text-primary);
  padding: 15px 20px;
  overflow: hidden; /* 防止内容溢出 */
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  flex-shrink: 0;
}

.panel-title {
  font-size: 1.3rem;
  color: var(--cyber-neon);
  margin: 0;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.7);
}
.panel-title i {
    margin-right: 10px;
}

.period-selector {
  display: flex;
  gap: 5px;
  background: rgba(0,0,0,0.2);
  padding: 4px;
  border-radius: 6px;
}

.period-selector button {
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.period-selector button.active,
.period-selector button:hover {
  background-color: var(--cyber-neon-bg);
  color: var(--cyber-neon);
  text-shadow: 0 0 3px var(--cyber-neon);
}

.usage-content {
  flex-grow: 1;
  overflow: hidden; /* 确保内容区本身可以滚动 */
  display: flex;
  flex-direction: column;
}

.loading-state, .error-state, .no-data-state {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: var(--text-secondary);
}

.data-display {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.total-usage-summary {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 10px 15px;
  background: rgba(79, 209, 197, 0.1);
  border-radius: 6px;
  margin-bottom: 15px;
  flex-shrink: 0;
}

.total-label {
  font-size: 1rem;
  color: var(--text-secondary);
}

.total-value {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--cyber-neon);
}


.app-list-container {
  flex-grow: 1;
  overflow-y: auto;
  padding-right: 5px;
}

.app-list-container::-webkit-scrollbar {
  width: 8px;
}
.app-list-container::-webkit-scrollbar-track {
  background: transparent; /* 隐藏轨道 */
}
.app-list-container::-webkit-scrollbar-thumb {
  background: rgba(79, 209, 197, 0.5);
  border-radius: 4px;
}

.app-list {
  display: flex;
  flex-direction: column;
  gap: 8px; /* 增加间距 */
}

.app-item {
  display: flex;
  flex-direction: column;
  gap: 8px; /* 内部间距 */
  padding: 12px 15px;
  /* 与总时长摘要样式对齐 */
  background: rgba(79, 209, 197, 0.1);
  border-radius: 6px;
  transition: all 0.3s ease;
  border: none; /* 移除之前的边框 */
}

.app-item:hover {
  background: rgba(79, 209, 197, 0.2); /* 调整hover效果 */
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(79, 209, 197, 0.1);
}

.app-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1rem;
}

.app-name {
  color: var(--text-primary);
  font-weight: 500;
  letter-spacing: 1px;
}

.app-duration {
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-family: 'orbitron', sans-serif; /* 使用科技感字体 */
}

.usage-bar-container {
  width: 100%;
  height: 12px; /* 增加高度以容纳更复杂的效果 */
  background-color: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  overflow: hidden;
  position: relative; /* 用于动画定位 */
  border: 1px solid rgba(79, 209, 197, 0.2);
  /* 添加网格背景 */
  background-image: repeating-linear-gradient(
    45deg,
    rgba(255, 255, 255, 0.05),
    rgba(255, 255, 255, 0.05) 2px,
    transparent 2px,
    transparent 6px
  );
}

.usage-bar {
  height: 100%;
  background: 
    linear-gradient(90deg, 
      rgba(34, 211, 167, 0.7) 0%, 
      rgba(79, 209, 197, 1) 90%,
      #fff 100%
    );
  border-radius: 6px;
  transition: width 0.8s cubic-bezier(0.25, 1, 0.5, 1); /* 更平滑的动画 */
  box-shadow: 
    0 0 10px rgba(79, 209, 197, 0.8),
    inset 0 0 4px rgba(34, 211, 167, 0.5); /* 辉光和内发光 */
  position: relative;
  overflow: hidden; /* 隐藏扫描动画的溢出部分 */
}

/* 扫描动画 */
.usage-bar::after {
  content: '';
  position: absolute;
  top: 0;
  left: -50%;
  width: 50%;
  height: 100%;
  background: linear-gradient(
    to right, 
    rgba(255, 255, 255, 0) 0%, 
    rgba(255, 255, 255, 0.3) 50%, 
    rgba(255, 255, 255, 0) 100%
  );
  transform: skewX(-25deg);
  animation: scan 3s linear infinite;
}

@keyframes scan {
  0% {
    left: -50%;
  }
  100% {
    left: 120%;
  }
}

.resize-handle {
  position: absolute;
  opacity: 0;
  transition: opacity 0.3s;
}
.resize-handle:hover {
  opacity: 1;
}
.resize-s {
  bottom: 0;
  left: 0;
  width: 100%;
  height: 10px;
  cursor: ns-resize;
  background: linear-gradient(to top, rgba(79, 209, 197, 0.3), transparent);
}
.resize-n {
  top: 0;
  left: 0;
  width: 100%;
  height: 10px;
  cursor: ns-resize;
  background: linear-gradient(to bottom, rgba(79, 209, 197, 0.3), transparent);
}
</style> 