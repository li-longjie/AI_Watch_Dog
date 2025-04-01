<template>
  <footer class="app-footer">
    <div class="footer-content">
      <div class="system-status">
        <span class="status-indicator">系统运行中</span>
        <span class="memory-usage">内存: {{ memoryUsage }}%</span>
        <span class="network-speed">网络: {{ networkSpeed }} Mbps</span>
        <span class="current-time">{{ currentTime }}</span>
      </div>
      <div class="footer-actions">
        <router-link to="/behavior-analysis" class="action-button analysis-btn">行为分析</router-link>
      </div>
    </div>
  </footer>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

// 模拟系统状态数据
const memoryUsage = ref(Math.floor(Math.random() * 40) + 30); // 30-70%
const networkSpeed = ref((Math.random() * 2 + 1).toFixed(1)); // 1.0-3.0 Mbps
const currentTime = ref(formatDateTime(new Date()));

// 格式化日期时间
function formatDateTime(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  
  return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`;
}

// 更新时间的定时器
let timeInterval;

onMounted(() => {
  // 每秒更新一次时间
  timeInterval = setInterval(() => {
    currentTime.value = formatDateTime(new Date());
    
    // 随机波动系统状态数据，使其看起来更真实
    memoryUsage.value = Math.max(30, Math.min(70, memoryUsage.value + (Math.random() * 6 - 3)));
    networkSpeed.value = Math.max(1, Math.min(3, parseFloat(networkSpeed.value) + (Math.random() * 0.4 - 0.2))).toFixed(1);
  }, 1000);
});

onUnmounted(() => {
  // 清除定时器
  clearInterval(timeInterval);
});
</script>

<style scoped>
.app-footer {
  background-color: rgba(10, 25, 47, 0.8);
  backdrop-filter: blur(10px);
  border-top: 1px solid rgba(79, 209, 197, 0.3);
  padding: 8px 20px;
  color: var(--text-secondary);
  font-size: 0.9rem;
  position: relative;
  z-index: 100;
}

.footer-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.system-status {
  display: flex;
  gap: 20px;
}

.status-indicator {
  color: var(--cyber-neon);
  display: flex;
  align-items: center;
}

.status-indicator::before {
  content: "";
  display: inline-block;
  width: 8px;
  height: 8px;
  background-color: var(--cyber-neon);
  border-radius: 50%;
  margin-right: 6px;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.memory-usage, .network-speed {
  color: var(--text-secondary);
}

.current-time {
  font-family: monospace;
  letter-spacing: 1px;
}

.footer-actions {
  display: flex;
  gap: 10px;
}

.action-button {
  background-color: rgba(79, 209, 197, 0.2);
  border: 1px solid var(--cyber-neon);
  color: var(--cyber-neon);
  padding: 5px 15px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  text-decoration: none;
  display: inline-block;
}

.action-button:hover {
  background-color: rgba(79, 209, 197, 0.3);
  box-shadow: 0 0 10px rgba(79, 209, 197, 0.5);
}

.analysis-btn {
  display: flex;
  align-items: center;
}

.analysis-btn::before {
  content: "⟩";
  margin-right: 5px;
}
</style> 