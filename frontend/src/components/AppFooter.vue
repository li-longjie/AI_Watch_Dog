<template>
  <div class="status-bar">
    <div class="status-bar-left">
      <span class="status-indicator" id="status-text">
        <span class="status-dot"></span> {{ systemStatus }}
      </span>
    </div>
    <div class="status-bar-center">
      <span class="memory-usage" id="memory-usage">内存: {{ memoryUsage }}%</span>
      <span class="network-usage" id="network-usage">网络: {{ networkUsage }} Mbps</span>
      <span class="current-time" id="current-time">{{ currentTime }}</span>
    </div>
    <div class="status-bar-right">
      <!-- 使用 router-link 进行页面导航 -->
      <router-link v-if="$route.path !== '/behavior'" to="/behavior" class="status-bar-btn">行为分析</router-link>
      <router-link v-if="$route.path === '/behavior'" to="/" class="status-bar-btn">返回监控</router-link>
      <router-link to="/voice" class="status-bar-btn">智能语音</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useRoute } from 'vue-router'; // 导入 useRoute

const systemStatus = ref('系统初始化...'); // 系统状态
const memoryUsage = ref(0);
const networkUsage = ref('0.0');
const currentTime = ref('加载中...');
let timeInterval = null;
let statsInterval = null;
const route = useRoute(); // 获取当前路由信息

// 更新时间
const updateTime = () => {
  const now = new Date();
  currentTime.value = `${now.getFullYear()}/` +
                     `${(now.getMonth() + 1).toString().padStart(2, '0')}/` +
                     `${now.getDate().toString().padStart(2, '0')} ` +
                     `${now.getHours().toString().padStart(2, '0')}:` +
                     `${now.getMinutes().toString().padStart(2, '0')}:` +
                     `${now.getSeconds().toString().padStart(2, '0')}`;
};

// 更新系统状态 (暂时使用随机数据)
const updateSystemStats = () => {
  memoryUsage.value = Math.floor(Math.random() * 30) + 20; // 20-50%
  networkUsage.value = (Math.random() * 10 + 1).toFixed(1); // 1.0-11.0 Mbps
  // TODO: 从 WebSocket 或 API 获取真实状态
  systemStatus.value = '系统运行中'; // 示例状态
};

onMounted(() => {
  updateTime();
  updateSystemStats();
  timeInterval = setInterval(updateTime, 1000);
  statsInterval = setInterval(updateSystemStats, 1000); // 暂时每秒更新模拟状态
});

onUnmounted(() => {
  clearInterval(timeInterval);
  clearInterval(statsInterval);
});
</script>

<style scoped>
/* 从 static/css/main.css 或 bahavior.css 复制 .status-bar 相关样式 */
.status-bar {
  position: fixed; /* 固定在底部 */
  bottom: 0;
  left: 0;
  right: 0;
  background-color: rgba(10, 25, 47, 0.9); /* 使用 CSS 变量或直接颜色值 */
  padding: 8px 20px; /* 调整内边距 */
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid rgba(79, 209, 197, 0.3);
  font-size: 14px;
  color: #e6f1ff; /* 使用 CSS 变量或直接颜色值 */
  z-index: 1000;
  height: 40px; /* 固定高度 */
  box-sizing: border-box; /* 包含 padding 和 border */
}

.status-bar-left,
.status-bar-center,
.status-bar-right {
  display: flex;
  align-items: center;
  gap: 15px; /* 元素间距 */
}

.status-indicator {
  display: flex;
  align-items: center;
  font-weight: 500;
}

.status-dot {
  width: 8px;
  height: 8px;
  background-color: #4CAF50; /* 绿色 */
  border-radius: 50%;
  margin-right: 8px;
  animation: pulseDot 2s infinite;
}

@keyframes pulseDot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 状态栏按钮样式 (从 main.css 迁移) */
.status-bar-btn {
    background: linear-gradient(135deg, #4fd1c5 0%, #3182ce 100%);
    color: white;
    border: none;
    border-radius: 5px; /* 调整圆角 */
    padding: 6px 12px; /* 调整内边距 */
    font-size: 14px; /* 调整字体大小 */
    font-weight: 500; /* 调整字重 */
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
    text-decoration: none;
    height: 28px; /* 调整高度 */
    /* width: 100px; */ /* 可以不固定宽度 */
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
    position: relative; /* 为了伪元素定位 */
    overflow: hidden; /* 隐藏溢出的伪元素 */
}

.status-bar-btn:hover {
    background: linear-gradient(135deg, #3182ce 0%, #4fd1c5 100%);
    transform: translateY(-1px); /* 调整悬浮效果 */
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
}

.status-bar-btn:active {
    transform: translateY(0px);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

/* 可以暂时移除或调整复杂的伪元素装饰 */
/* .status-bar-btn::before { ... } */

</style> 