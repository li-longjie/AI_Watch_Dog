<template>
  <div class="monitoring-page">
    <AppHeader />

    <draggable 
      v-model="panelOrder" 
      class="container"
      item-key="id"
      :animation="200"
      handle=".panel-title"
      ghost-class="ghost-panel"
      chosen-class="chosen-panel"
      drag-class="drag-panel"
    >
      <template #item="{element}">
        <div v-if="element.id === 1" class="panel video-panel" :style="getPanelStyle(1)" ref="panel1">
          <VideoPanel :videoSrc="videoFeedUrl" />
          <div class="resize-handle resize-e" @mousedown="startResize($event, 1, 'e')"></div>
          <div class="resize-handle resize-s" @mousedown="startResize($event, 1, 's')"></div>
          <div class="resize-handle resize-se" @mousedown="startResize($event, 1, 'se')"></div>
        </div>
        <div v-else-if="element.id === 2" class="panel warning-panel" :style="getPanelStyle(2)" ref="panel2">
          <WarningPanel :alertToReplay="selectedAlert" />
          <div class="resize-handle resize-w" @mousedown="startResize($event, 2, 'w')"></div>
          <div class="resize-handle resize-s" @mousedown="startResize($event, 2, 's')"></div>
          <div class="resize-handle resize-sw" @mousedown="startResize($event, 2, 'sw')"></div>
        </div>
        <div v-else-if="element.id === 3" class="panel alerts-panel" :style="getPanelStyle(3)" ref="panel3">
          <AlertsPanel :alerts="alerts" @view-alert="handleViewAlert" />
          <div class="resize-handle resize-e" @mousedown="startResize($event, 3, 'e')"></div>
          <div class="resize-handle resize-n" @mousedown="startResize($event, 3, 'n')"></div>
          <div class="resize-handle resize-ne" @mousedown="startResize($event, 3, 'ne')"></div>
        </div>
        <div v-else-if="element.id === 4" class="panel qa-panel" :style="getPanelStyle(4)" ref="panel4">
          <QAPanel :messages="chatMessages" @send-message="sendChatMessage" />
          <div class="resize-handle resize-w" @mousedown="startResize($event, 4, 'w')"></div>
          <div class="resize-handle resize-n" @mousedown="startResize($event, 4, 'n')"></div>
          <div class="resize-handle resize-nw" @mousedown="startResize($event, 4, 'nw')"></div>
        </div>
      </template>
    </draggable>

    <AppFooter />
  </div>
</template>

<script setup>
// 这里将添加页面的逻辑，例如 WebSocket 连接、数据获取等
import { onMounted, onUnmounted, ref } from 'vue';
import AppHeader from '../components/AppHeader.vue'; // 导入 Header
import AppFooter from '../components/AppFooter.vue';
import VideoPanel from '../components/VideoPanel.vue';
import WarningPanel from '../components/WarningPanel.vue';
import AlertsPanel from '../components/AlertsPanel.vue';
import QAPanel from '../components/QAPanel.vue';
import draggable from 'vuedraggable';

const videoFeedUrl = ref(''); // 用于存储视频流 URL
let videoWs = null;
const alerts = ref([]); // 存储预警信息列表
let alertsWs = null;
const MAX_DISPLAY_ALERTS = 50; // 前端最多显示多少条预警
const selectedAlert = ref(null); // 用于存储当前选中的预警
const chatMessages = ref([]); // 存储聊天消息
let qaWs = null;

// 定义面板顺序
const panelOrder = ref([
  { id: 1 }, // 视频面板
  { id: 2 }, // 预警回放面板
  { id: 3 }, // 预警信息面板
  { id: 4 }  // 智能问答面板
]);

// 添加面板大小调整相关的状态
const panelSizes = ref({
  1: { width: '100%', height: '100%' },
  2: { width: '100%', height: '100%' },
  3: { width: '100%', height: '100%' },
  4: { width: '100%', height: '100%' }
});

const resizing = ref({
  active: false,
  panelId: null,
  direction: null,
  startX: 0,
  startY: 0,
  startWidth: 0,
  startHeight: 0
});

// 获取面板样式
function getPanelStyle(panelId) {
  return {
    width: panelSizes.value[panelId].width,
    height: panelSizes.value[panelId].height,
    position: 'relative'
  };
}

// 开始调整大小
function startResize(event, panelId, direction) {
  event.preventDefault();
  event.stopPropagation();
  
  const panel = document.querySelector(`.panel:nth-child(${panelId})`);
  if (!panel) return;
  
  const rect = panel.getBoundingClientRect();
  
  resizing.value = {
    active: true,
    panelId,
    direction,
    startX: event.clientX,
    startY: event.clientY,
    startWidth: rect.width,
    startHeight: rect.height
  };
  
  document.addEventListener('mousemove', handleResize);
  document.addEventListener('mouseup', stopResize);
}

// 处理调整大小
function handleResize(event) {
  if (!resizing.value.active) return;
  
  const { panelId, direction, startX, startY, startWidth, startHeight } = resizing.value;
  
  let newWidth = startWidth;
  let newHeight = startHeight;
  
  // 根据拖动方向计算新尺寸
  if (direction.includes('e')) {
    newWidth = startWidth + (event.clientX - startX);
  } else if (direction.includes('w')) {
    newWidth = startWidth - (event.clientX - startX);
  }
  
  if (direction.includes('s')) {
    newHeight = startHeight + (event.clientY - startY);
  } else if (direction.includes('n')) {
    newHeight = startHeight - (event.clientY - startY);
  }
  
  // 设置最小尺寸
  newWidth = Math.max(200, newWidth);
  newHeight = Math.max(150, newHeight);
  
  // 更新面板尺寸
  panelSizes.value[panelId] = {
    width: `${newWidth}px`,
    height: `${newHeight}px`
  };
}

// 停止调整大小
function stopResize() {
  resizing.value.active = false;
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
}

// 初始化视频 WebSocket
const initVideoWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/video_feed`; // 使用相对路径，由 Vite 代理

  videoWs = new WebSocket(wsUrl);

  videoWs.onopen = () => {
    console.log('视频 WebSocket 已连接');
    // 可以在状态栏显示连接状态
  };

  videoWs.onmessage = (event) => {
    if (event.data instanceof Blob) {
      // 释放之前的 URL
      if (videoFeedUrl.value && videoFeedUrl.value.startsWith('blob:')) {
        URL.revokeObjectURL(videoFeedUrl.value);
      }
      // 创建新的 Blob URL
      videoFeedUrl.value = URL.createObjectURL(event.data);
    }
    // 可以处理其他类型的消息，例如行为识别结果
  };

  videoWs.onerror = (error) => {
    console.error('视频 WebSocket 错误:', error);
  };

  videoWs.onclose = () => {
    console.log('视频 WebSocket 已关闭');
    // 可以在状态栏显示断开状态
    // 尝试重连 (可以添加延迟和次数限制)
    // setTimeout(initVideoWebSocket, 5000);
  };
};

// 关闭视频 WebSocket
const closeVideoWebSocket = () => {
  if (videoWs) {
    videoWs.close();
    videoWs = null;
    // 释放最后的 URL
    if (videoFeedUrl.value && videoFeedUrl.value.startsWith('blob:')) {
      URL.revokeObjectURL(videoFeedUrl.value);
      videoFeedUrl.value = '';
    }
  }
};

// 初始化预警 WebSocket
const initAlertsWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/alerts`; // 预警 WebSocket 端点

  alertsWs = new WebSocket(wsUrl);

  alertsWs.onopen = () => {
    console.log('预警 WebSocket 已连接');
  };

  alertsWs.onmessage = (event) => {
    try {
      const alertData = JSON.parse(event.data);
      if (alertData.type === 'alert') {
        console.log('收到新预警:', alertData);
        // 将新预警添加到列表开头
        alerts.value.unshift(alertData);
        // 限制列表长度
        if (alerts.value.length > MAX_DISPLAY_ALERTS) {
          alerts.value.pop(); // 移除最旧的预警
        }
        // TODO: 可以在 WarningPanel 中显示最新预警的图片/视频
      }
    } catch (error) {
      console.error('处理预警消息失败:', error);
    }
  };

  alertsWs.onerror = (error) => {
    console.error('预警 WebSocket 错误:', error);
  };

  alertsWs.onclose = () => {
    console.log('预警 WebSocket 已关闭');
    // 尝试重连
    // setTimeout(initAlertsWebSocket, 5000);
  };
};

// 关闭预警 WebSocket
const closeAlertsWebSocket = () => {
  if (alertsWs) {
    alertsWs.close();
    alertsWs = null;
  }
};

// 获取历史预警
const fetchHistoricalAlerts = async () => {
  try {
    // 注意：这里的路径是 /api/alerts，由 Vite 代理到后端
    const response = await fetch('/api/alerts');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    if (data.status === 'success' && Array.isArray(data.alerts)) {
      // 将历史预警添加到列表 (注意顺序，API 返回的是最近的)
      // 后端 recent_alerts 是 deque，append 在右边，所以最新的在后面
      // 为了和 WebSocket 接收到的新预警保持一致（最新的在前面），需要反转一下
      alerts.value = data.alerts.reverse();
      console.log('获取到历史预警:', alerts.value.length, '条');
    } else {
      console.error('获取历史预警失败:', data.message || '格式错误');
    }
  } catch (error) {
    console.error('请求历史预警失败:', error);
  }
};

// 初始化问答 WebSocket
const initQWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/qa`; // 问答 WebSocket 端点

  qaWs = new WebSocket(wsUrl);

  qaWs.onopen = () => {
    console.log('问答 WebSocket 已连接');
    // 可以发送一条欢迎消息或请求初始状态
    // qaWs.send(JSON.stringify({ type: 'status_request' }));
    // 添加一条系统消息到聊天记录
    chatMessages.value.push({ id: Date.now(), sender: 'system', text: '已连接到问答助手。' });
  };

  qaWs.onmessage = (event) => {
    try {
      const messageData = JSON.parse(event.data);
      console.log('收到问答消息:', messageData);
      // 假设后端返回的消息格式为 { sender: 'ai'/'system', text: '...' }
      chatMessages.value.push({ id: Date.now(), ...messageData });
      // TODO: 滚动聊天窗口到底部
    } catch (error) {
      console.error('处理问答消息失败:', error);
      chatMessages.value.push({ id: Date.now(), sender: 'system', text: '处理消息时出错。' });
    }
  };

  qaWs.onerror = (error) => {
    console.error('问答 WebSocket 错误:', error);
    chatMessages.value.push({ id: Date.now(), sender: 'system', text: '问答服务连接错误。' });
  };

  qaWs.onclose = () => {
    console.log('问答 WebSocket 已关闭');
    chatMessages.value.push({ id: Date.now(), sender: 'system', text: '问答服务已断开。' });
    // 尝试重连
    // setTimeout(initQWebSocket, 5000);
  };
};

// 关闭问答 WebSocket
const closeQWebSocket = () => {
  if (qaWs) {
    qaWs.close();
    qaWs = null;
  }
};

// 处理从 AlertsPanel 传来的事件
function handleViewAlert(alert) {
  console.log('选中预警进行回放:', alert);
  selectedAlert.value = alert;
}

// 发送聊天消息
function sendChatMessage(messageText) {
  if (qaWs && qaWs.readyState === WebSocket.OPEN && messageText.trim()) {
    const message = { type: 'question', content: messageText.trim() };
    qaWs.send(JSON.stringify(message));
    // 将用户消息添加到聊天记录
    chatMessages.value.push({ id: Date.now(), sender: 'user', text: messageText.trim() });
    // TODO: 滚动聊天窗口到底部
  } else {
    console.error('无法发送消息：WebSocket 未连接或消息为空');
    chatMessages.value.push({ id: Date.now(), sender: 'system', text: '无法发送消息，请检查连接。' });
  }
}

onMounted(() => {
  console.log('主监控页面已挂载');
  initVideoWebSocket(); // 页面加载时连接视频 WS
  initAlertsWebSocket(); // 页面加载时连接预警 WS
  fetchHistoricalAlerts(); // 页面加载时获取历史预警
  initQWebSocket(); // 页面加载时连接问答 WS
});

onUnmounted(() => {
  console.log('主监控页面已卸载');
  closeVideoWebSocket(); // 页面卸载时关闭视频 WS
  closeAlertsWebSocket(); // 页面卸载时关闭预警 WS
  closeQWebSocket(); // 页面卸载时关闭问答 WS
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
});
</script>

<style scoped>
.monitoring-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh; /* 确保至少占满整个视口高度 */
  background-color: var(--dark-bg);
  width: 100vw; /* 占满整个视口宽度 */
  overflow-x: hidden; /* 防止水平滚动条 */
}

.container {
  display: grid;
  grid-template-columns: repeat(2, 1fr); /* 2列布局 */
  grid-template-rows: repeat(2, calc(45vh - 60px)); /* 减小高度，留出更多间距 */
  gap: 50px; /* 进一步增加面板之间的间距 */
  padding: 40px 60px 60px 60px; /* 增加四周内边距 */
  flex: 1; /* 让容器占据剩余空间 */
  max-width: 100%; /* 移除最大宽度限制，占满整个宽度 */
  width: 100%; /* 占满可用宽度 */
  margin: 0; /* 移除外边距 */
  box-sizing: border-box; /* 确保内边距不会增加总宽度 */
  position: relative; /* 添加相对定位 */
  overflow: visible; /* 允许面板溢出 */
}

.panel {
  background-color: rgba(23, 42, 69, 0.7); /* 半透明背景 */
  backdrop-filter: blur(10px); /* 毛玻璃效果 */
  -webkit-backdrop-filter: blur(10px); /* Safari 支持 */
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(79, 209, 197, 0.2);
  padding: 15px;
  display: flex;
  flex-direction: column;
  position: relative; /* 为伪元素定位 */
  overflow: hidden; /* 隐藏溢出的内容 */
  height: 100%; /* 占满网格单元格高度 */
  max-height: calc(45vh - 60px); /* 调整最大高度限制 */
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  cursor: pointer;
  border: 1px solid rgba(79, 209, 197, 0.2); /* 添加细边框 */
  transform: scale(0.98); /* 默认稍微缩小，增加分离感 */
  min-width: 200px; /* 最小宽度 */
  min-height: 150px; /* 最小高度 */
  resize: both; /* 原生调整大小功能（可选） */
  overflow: auto; /* 内容溢出时显示滚动条 */
}

.panel:hover {
  transform: translateY(-8px) scale(1.02); /* 悬停时上移更多 */
  box-shadow: 0 15px 30px rgba(0, 0, 0, 0.4), 0 0 20px rgba(79, 209, 197, 0.4);
  border-color: rgba(79, 209, 197, 0.5);
  z-index: 10;
}

.panel:active {
  transform: translateY(-2px) scale(1.01);
  transition: transform 0.1s ease;
}

.panel-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 15px;
  color: var(--primary, #4fd1c5);
  border-bottom: 1px solid rgba(79, 209, 197, 0.5);
  padding-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  letter-spacing: 1px;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
  cursor: move;
  user-select: none; /* 防止文本选择干扰拖拽 */
}

/* 迁移 main.css 中的面板发光和角落装饰效果 */
.panel::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.7), transparent);
  opacity: 0.7;
  z-index: 3;
}

/* 为每个面板添加不同的顶部装饰线颜色 */
.video-panel::before {
  background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.7), transparent);
}

.warning-panel::before {
  background: linear-gradient(90deg, transparent, rgba(255, 76, 76, 0.7), transparent);
}

.alerts-panel::before {
  background: linear-gradient(90deg, transparent, rgba(255, 204, 0, 0.7), transparent);
}

.qa-panel::before {
  background: linear-gradient(90deg, transparent, rgba(128, 90, 213, 0.7), transparent);
}

/* 面板内容区域样式 */
.video-container, .warning-content, .alerts-list-container, .qa-content {
  max-height: calc(100% - 40px); /* 减去标题和内边距的高度 */
  overflow: auto; /* 内容过多时显示滚动条 */
  background-color: rgba(10, 25, 47, 0.3); /* 半透明背景 */
  border-radius: 6px;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

/* 视频面板特定样式 */
.video-panel .video-container {
  max-height: calc(100% - 40px); /* 减去标题和内边距的高度 */
  overflow: hidden; /* 视频面板不需要滚动 */
}

/* 预警回放面板特定样式 */
.warning-panel .warning-content {
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 预警信息面板特定样式 */
.alerts-panel .alerts-list-container {
  max-height: calc(100% - 40px); /* 减去标题和内边距的高度 */
}

/* 智能问答面板特定样式 */
.qa-panel .chat-history {
  max-height: calc(100% - 100px); /* 减去标题、输入框和内边距的高度 */
}

/* 为特定面板添加 grid span (可选，用于调整布局) */
.video-panel {
  grid-column: span 1;
  grid-row: span 1;
  border-top: 2px solid rgba(79, 209, 197, 0.7);
  border-left: 2px solid rgba(79, 209, 197, 0.7);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 15px rgba(79, 209, 197, 0.2);
}
.warning-panel {
  grid-column: span 1;
  grid-row: span 1;
  border-top: 2px solid rgba(255, 76, 76, 0.7);
  border-right: 2px solid rgba(255, 76, 76, 0.7);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 15px rgba(255, 76, 76, 0.2);
}
.alerts-panel {
  grid-column: span 1;
  grid-row: span 1;
  border-bottom: 2px solid rgba(255, 204, 0, 0.7);
  border-left: 2px solid rgba(255, 204, 0, 0.7);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 15px rgba(255, 204, 0, 0.2);
}
.qa-panel {
  grid-column: span 1;
  grid-row: span 1;
  border-bottom: 2px solid rgba(128, 90, 213, 0.7);
  border-right: 2px solid rgba(128, 90, 213, 0.7);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 0 15px rgba(128, 90, 213, 0.2);
}

/* 添加全局背景网格效果 */
.monitoring-page::before {
  content: "";
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: 
      linear-gradient(rgba(10, 25, 47, 0.8), rgba(10, 25, 47, 0.8)),
      repeating-linear-gradient(transparent, transparent 50px, rgba(79, 209, 197, 0.1) 50px, rgba(79, 209, 197, 0.1) 51px),
      repeating-linear-gradient(90deg, transparent, transparent 50px, rgba(79, 209, 197, 0.1) 50px, rgba(79, 209, 197, 0.1) 51px);
  z-index: -1;
  opacity: 0.6; /* 增强背景网格对比度 */
  pointer-events: none;
}

/* 赛博动态扫描线 */
.monitoring-page::after {
  content: "";
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, transparent, var(--cyber-neon), transparent);
  box-shadow: 0 0 15px 2px var(--cyber-neon);
  z-index: 999;
  animation: scanline 8s linear infinite;
  opacity: 0.6;
}

@keyframes scanline {
  0% { top: -10px; }
  100% { top: 100vh; }
}

/* 响应式调整 */
@media (max-width: 900px) {
  .container {
    grid-template-columns: 1fr; /* 小屏幕下单列 */
    grid-template-rows: auto; /* 自动调整行高 */
  }
  
  .video-panel, .warning-panel, .alerts-panel, .qa-panel {
    grid-column: span 1;
    grid-row: auto;
  }
}

/* 修改 App.vue 中的样式，确保内容可以铺满 */
:deep(#app-container) {
  max-width: 100%;
  padding: 0;
  margin: 0;
  width: 100vw;
}

:deep(main) {
  padding: 0;
  margin: 0;
  width: 100%;
}

/* 面板悬停时的内部元素效果 */
.panel:hover .panel-title {
  color: #fff;
  text-shadow: 0 0 8px rgba(79, 209, 197, 0.8);
}

/* 面板悬停时的装饰效果增强 */
.panel:hover::before {
  animation-duration: 3s; /* 加快动画速度 */
}

.panel:hover::after {
  opacity: 1;
  transform: scale(1.2);
}

/* 视频面板特殊效果 */
.video-panel:hover .corner-decoration {
  opacity: 1;
  border-color: #fff;
  box-shadow: 0 0 10px rgba(79, 209, 197, 0.5);
}

/* 预警回放面板特殊效果 */
.warning-panel:hover .tech-decoration {
  opacity: 0.8;
  border-width: 2px;
}

/* 预警信息面板特殊效果 */
.alerts-panel:hover .data-stream-decoration {
  opacity: 0.8;
  width: 3px;
}

/* 智能问答面板特殊效果 */
.qa-panel:hover .qa-glow {
  opacity: 0.9;
  filter: blur(3px);
}

/* 悬停时的阴影效果 */
.video-panel:hover {
  box-shadow: 0 15px 30px rgba(0, 0, 0, 0.4), 0 0 25px rgba(79, 209, 197, 0.4);
}

.warning-panel:hover {
  box-shadow: 0 15px 30px rgba(0, 0, 0, 0.4), 0 0 25px rgba(255, 76, 76, 0.4);
}

.alerts-panel:hover {
  box-shadow: 0 15px 30px rgba(0, 0, 0, 0.4), 0 0 25px rgba(255, 204, 0, 0.4);
}

.qa-panel:hover {
  box-shadow: 0 15px 30px rgba(0, 0, 0, 0.4), 0 0 25px rgba(128, 90, 213, 0.4);
}

/* 拖拽相关样式 */
.ghost-panel {
  opacity: 0.5;
  background: rgba(0, 0, 0, 0.2) !important;
}

.chosen-panel {
  box-shadow: 0 0 20px rgba(79, 209, 197, 0.6) !important;
  z-index: 20;
}

.drag-panel {
  transform: rotate(2deg) scale(1.05);
  z-index: 30;
}

/* 添加拖拽手柄样式 */
.panel-title {
  cursor: move;
  user-select: none; /* 防止文本选择干扰拖拽 */
}

/* 添加拖拽提示 */
.panel-title::before {
  content: "⋮⋮";
  margin-right: 8px;
  opacity: 0.5;
  font-size: 14px;
}

.panel-title:hover::before {
  opacity: 1;
}

/* 调整大小的控制点样式 */
.resize-handle {
  position: absolute;
  background-color: rgba(79, 209, 197, 0.2);
  z-index: 10;
}

.resize-handle:hover {
  background-color: rgba(79, 209, 197, 0.5);
}

/* 东西南北方向的控制点 */
.resize-e {
  top: 0;
  right: 0;
  width: 5px;
  height: 100%;
  cursor: e-resize;
}

.resize-w {
  top: 0;
  left: 0;
  width: 5px;
  height: 100%;
  cursor: w-resize;
}

.resize-s {
  bottom: 0;
  left: 0;
  width: 100%;
  height: 5px;
  cursor: s-resize;
}

.resize-n {
  top: 0;
  left: 0;
  width: 100%;
  height: 5px;
  cursor: n-resize;
}

/* 角落的控制点 */
.resize-se {
  bottom: 0;
  right: 0;
  width: 15px;
  height: 15px;
  cursor: se-resize;
  border-radius: 0 0 5px 0;
}

.resize-sw {
  bottom: 0;
  left: 0;
  width: 15px;
  height: 15px;
  cursor: sw-resize;
  border-radius: 0 0 0 5px;
}

.resize-ne {
  top: 0;
  right: 0;
  width: 15px;
  height: 15px;
  cursor: ne-resize;
  border-radius: 0 5px 0 0;
}

.resize-nw {
  top: 0;
  left: 0;
  width: 15px;
  height: 15px;
  cursor: nw-resize;
  border-radius: 5px 0 0 0;
}

/* 当正在调整大小时，禁用面板的过渡效果 */
.panel.resizing {
  transition: none !important;
}

/* 当正在调整大小时，显示辅助线 */
.panel.resizing::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 2px dashed rgba(79, 209, 197, 0.7);
  pointer-events: none;
  z-index: 5;
}
</style> 