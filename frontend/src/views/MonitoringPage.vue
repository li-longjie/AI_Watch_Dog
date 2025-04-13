<template>
  <div class="monitoring-page">
    <!-- <AppHeader /> -->

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
        <div v-if="element.id === 1" class="panel combined-monitor-panel" :style="getPanelStyle(1)" ref="panel1">
          <CombinedMonitorPanel :videoSrc="videoFeedUrl" :videoWs="videoWs" :deviceWs="deviceWs" />
          <div class="resize-handle resize-e" @mousedown="startResize($event, 1, 'e')"></div>
          <div class="resize-handle resize-s" @mousedown="startResize($event, 1, 's')"></div>
          <div class="resize-handle resize-se" @mousedown="startResize($event, 1, 'se')"></div>
        </div>
        <div v-else-if="element.id === 4" class="panel qa-panel" :style="getPanelStyle(4)" ref="panel4">
          <QAPanel />
          <div class="resize-handle resize-w" @mousedown="startResize($event, 4, 'w')"></div>
          <div class="resize-handle resize-n" @mousedown="startResize($event, 4, 'n')"></div>
          <div class="resize-handle resize-nw" @mousedown="startResize($event, 4, 'nw')"></div>
          <div class="resize-handle resize-s" @mousedown="startResize($event, 4, 's')"></div>
          <div class="resize-handle resize-e" @mousedown="startResize($event, 4, 'e')"></div>
          <div class="resize-handle resize-sw" @mousedown="startResize($event, 4, 'sw')"></div>
          <div class="resize-handle resize-se" @mousedown="startResize($event, 4, 'se')"></div>
          <div class="resize-handle resize-ne" @mousedown="startResize($event, 4, 'ne')"></div>
        </div>
        <div v-else-if="element.id === 5" class="panel alert-replay-panel" :style="getPanelStyle(5)" ref="panel5">
          <AlertReplayPanel :alerts="alerts" :wsConnection="alertsWs" />
          <div class="resize-handle resize-e" @mousedown="startResize($event, 5, 'e')"></div>
          <div class="resize-handle resize-n" @mousedown="startResize($event, 5, 'n')"></div>
          <div class="resize-handle resize-ne" @mousedown="startResize($event, 5, 'ne')"></div>
          <div class="resize-handle resize-w" @mousedown="startResize($event, 5, 'w')"></div>
          <div class="resize-handle resize-s" @mousedown="startResize($event, 5, 's')"></div>
          <div class="resize-handle resize-sw" @mousedown="startResize($event, 5, 'sw')"></div>
          <div class="resize-handle resize-nw" @mousedown="startResize($event, 5, 'nw')"></div>
          <div class="resize-handle resize-se" @mousedown="startResize($event, 5, 'se')"></div>
        </div>
      </template>
    </draggable>

    <!-- <StatusBar /> -->
  </div>
</template>

<script setup>
// 这里将添加页面的逻辑，例如 WebSocket 连接、数据获取等
import { onMounted, onUnmounted, ref } from 'vue';
// import AppHeader from '../components/AppHeader.vue'; // 移除 Header 导入
// import StatusBar from '../components/AppFooter.vue'; // 移除 StatusBar 导入

import CombinedMonitorPanel from '../components/CombinedMonitorPanel.vue'; // 新的组合面板
import QAPanel from '../components/QAPanel.vue';
import AlertReplayPanel from '../components/AlertReplayPanel.vue'; // *** 导入新组件 ***
import draggable from 'vuedraggable';

const videoFeedUrl = ref(''); // 用于存储视频流 URL
let videoWs = ref(null); // 使用 ref 使得子组件可以响应式地接收 WebSocket 对象
const alerts = ref([]); // 存储预警信息列表
let alertsWs = ref(null); // 使用 ref
let deviceWs = ref(null); // 设备列表的WebSocket连接
const MAX_DISPLAY_ALERTS = 50; // 前端最多显示多少条预警

// 定义面板顺序 - 移除独立的设备列表面板
const panelOrder = ref([
  { id: 1 }, // 合并的监控面板（视频+设备列表）
  { id: 5 }, // 预警面板
  { id: 4 }  // 智能问答面板
]);

// 更新面板大小状态 - 移除设备列表面板
const panelSizes = ref({
  1: { width: '100%', height: '339.13px' }, // 调整合并面板尺寸
  4: { width: '100%', height: '100%' },
  5: { width: '100%', height: '100%' }
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
    // 检查 panelSizes 中是否存在该 panelId
    if (!panelSizes.value[panelId]) {
        console.warn(`Panel size for ID ${panelId} not found. Using default.`);
        return { width: '100%', height: '100%', position: 'relative' };
    }
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
  
  // 添加一个 class 到 panel 以禁用过渡效果
  panel.classList.add('resizing');
}

// 处理调整大小
function handleResize(event) {
  if (!resizing.value.active) return;
  
  const { panelId, direction, startX, startY, startWidth, startHeight } = resizing.value;
  
  let newWidth = startWidth;
  let newHeight = startHeight;
  
  const deltaX = event.clientX - startX;
  const deltaY = event.clientY - startY;
  
  // 根据拖动方向计算新尺寸
  if (direction.includes('e')) {
    newWidth = startWidth + deltaX;
  } else if (direction.includes('w')) {
    newWidth = startWidth - deltaX;
    console.warn("Resizing 'w'/'n' might have positioning issues with current setup.");
  }
  
  if (direction.includes('s')) {
    newHeight = startHeight + deltaY;
  } else if (direction.includes('n')) {
    newHeight = startHeight - deltaY;
    console.warn("Resizing 'w'/'n' might have positioning issues with current setup.");
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
  if (!resizing.value.active) return; // 防止重复触发

  const panelId = resizing.value.panelId;
  // 找到对应的面板元素移除 resizing class
  // 依赖于 DOM 结构，如果结构变化需要调整选择器
  // 使用 ID 或更具体的 class 可能更好
  const panelElement = document.querySelector(`.panel[ref='panel${panelId}']`) || document.querySelector(`.panel.${panelId === 1 ? 'video-panel' : panelId === 4 ? 'qa-panel' : 'alert-replay-panel'}`); // 基于 ref 或 class 查找
  if (panelElement) {
      panelElement.classList.remove('resizing');
  } else {
      // 如果找不到，尝试遍历所有 panel
      document.querySelectorAll('.panel.resizing').forEach(el => el.classList.remove('resizing'));
  }

  resizing.value.active = false;
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
}

// 初始化视频 WebSocket
const initVideoWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/video_feed`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('视频 WebSocket 已连接');
    videoWs.value = ws; // 将实例赋给 ref
  };

  ws.onmessage = (event) => {
    if (event.data instanceof Blob) {
      if (videoFeedUrl.value && videoFeedUrl.value.startsWith('blob:')) {
        URL.revokeObjectURL(videoFeedUrl.value);
      }
      videoFeedUrl.value = URL.createObjectURL(event.data);
    }
  };

  ws.onerror = (error) => {
    console.error('视频 WebSocket 错误:', error);
    videoWs.value = null; // 连接错误时清空 ref
  };

  ws.onclose = () => {
    console.log('视频 WebSocket 已关闭');
    videoWs.value = null; // 关闭时清空 ref
    if (videoFeedUrl.value && videoFeedUrl.value.startsWith('blob:')) {
      URL.revokeObjectURL(videoFeedUrl.value);
      videoFeedUrl.value = '';
    }
    // 可以在这里添加重连逻辑
  };
};

// 关闭视频 WebSocket
const closeVideoWebSocket = () => {
  if (videoWs.value) {
    videoWs.value.close();
    videoWs.value = null;
  }
  if (videoFeedUrl.value && videoFeedUrl.value.startsWith('blob:')) {
    URL.revokeObjectURL(videoFeedUrl.value);
    videoFeedUrl.value = '';
  }
};

// 初始化预警 WebSocket
const initAlertsWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/alerts`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('预警 WebSocket 已连接');
    alertsWs.value = ws; // 将实例赋给 ref
  };

  ws.onmessage = (event) => {
    try {
      const alertData = JSON.parse(event.data);
      if (alertData.type === 'alert') {
        console.log('收到新预警:', alertData);
        alerts.value.unshift(alertData); // 最新的放前面
        if (alerts.value.length > MAX_DISPLAY_ALERTS) {
          alerts.value.pop();
        }
      } else if (alertData.type === 'recent_alerts') {
         // 处理首次连接时收到的历史预警
         console.log('收到历史预警:', alertData.data.length, '条');
         // 假设 data 是按时间顺序（旧->新）发送的，所以需要反转
         alerts.value = [...alertData.data.reverse(), ...alerts.value];
         // 去重和限制长度可以在这里做，或者信任后端的逻辑
         if (alerts.value.length > MAX_DISPLAY_ALERTS) {
             alerts.value = alerts.value.slice(0, MAX_DISPLAY_ALERTS);
         }
      }
    } catch (error) {
      console.error('处理预警消息失败:', error);
    }
  };

  ws.onerror = (error) => {
    console.error('预警 WebSocket 错误:', error);
    alertsWs.value = null; // 连接错误时清空 ref
  };

  ws.onclose = () => {
    console.log('预警 WebSocket 已关闭');
    alertsWs.value = null; // 关闭时清空 ref
    // 可以在这里添加重连逻辑
  };
};

// 关闭预警 WebSocket
const closeAlertsWebSocket = () => {
  if (alertsWs.value) {
    alertsWs.value.close();
    alertsWs.value = null;
  }
};

onMounted(() => {
  console.log('主监控页面已挂载');
  initVideoWebSocket();
  initAlertsWebSocket();
});

onUnmounted(() => {
  console.log('主监控页面已卸载');
  closeVideoWebSocket();
  closeAlertsWebSocket();
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
});
</script>

<style scoped>
.monitoring-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--dark-bg);
  width: 100vw;
  overflow-x: hidden;
  /* 移除垂直居中，让内容从顶部开始 */
  /* justify-content: center; */
  /* 确保没有边距和内边距导致的空白 */
  margin: 0;
  padding: 0;
}

.container {
  /* 恢复grid布局 */
  display: grid;
  /* 宽度缩减并居中 */
  width: 90%;
  max-width: 1600px;
  margin: 0 auto;
  /* 比例保持不变，但调整格式添加空列作为间距 */
  grid-template-columns: 2fr 40px 1fr;
  /* 调整高度，确保一屏内完全显示 */
  grid-template-rows: 40vh 40vh;
  gap: 20px;
  grid-template-areas:
    "monitor .     qa"
    "alert   .     qa";
  /* 内边距适当缩减 */
  padding: 10px 0;
  box-sizing: border-box;
}

/* 定义网格区域 */
.combined-monitor-panel { grid-area: monitor; }
.alert-replay-panel { grid-area: alert; }
.qa-panel { 
  grid-area: qa;
}

/* 响应式调整 */
@media (max-width: 900px) {
  .container {
    width: 95%;
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
    grid-template-areas:
      "monitor"
      "alert"
      "qa";
    gap: 15px;
  }
  
  .panel {
    max-height: 50vh;
  }
}

.panel {
  background-color: rgba(15, 23, 42, 0.75); /* Slightly less transparent */
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-radius: 6px; /* Slightly smaller radius */
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(79, 209, 197, 0.15);
  padding: 15px;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden; /* 保持隐藏，手柄使用 z-index */
  height: 100%; /* 默认占满单元格 */
  width: 100%; /* 默认占满单元格 */
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  border: 1px solid rgba(79, 209, 197, 0.1); /* Subtler border */
  min-width: 200px;
  min-height: 150px;
}

.panel:hover {
  transform: translateY(-5px) scale(1.01); /* Subtler hover effect */
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3), 0 0 15px rgba(79, 209, 197, 0.3);
  border-color: rgba(79, 209, 197, 0.4);
  z-index: 10; /* Bring panel to front on hover */
}

.panel-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin: -15px -15px 15px -15px; /* Extend to edges */
  padding: 10px 15px; /* Adjust padding */
  color: var(--primary, #4fd1c5);
  border-bottom: 1px solid rgba(79, 209, 197, 0.3); /* Lighter border */
  display: flex;
  align-items: center;
  letter-spacing: 1px;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
  cursor: move;
  user-select: none;
  background-color: rgba(10, 25, 47, 0.5); /* Add slight background to title */
  border-radius: 6px 6px 0 0; /* Match panel radius */
  flex-shrink: 0; /* Prevent shrinking */
}

.panel-title::before {
  content: "⋮⋮";
  margin-right: 10px; /* More space */
  opacity: 0.6;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5); /* Make handle more visible */
}
.panel-title:hover::before {
  opacity: 1;
  color: rgba(255, 255, 255, 0.8);
}

/* Top glow effect */
.panel::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.6), transparent);
  opacity: 0.6; /* Slightly dimmer */
  z-index: 3;
}
/* Specific glow colors remain */
.combined-monitor-panel::before { background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.6), transparent); }
.qa-panel::before { background: linear-gradient(90deg, transparent, rgba(128, 90, 213, 0.6), transparent); }
/* New combined panel glow */
.alert-replay-panel::before { background: linear-gradient(90deg, transparent, rgba(255, 165, 0, 0.6), transparent); } /* Example: Orange glow */

/* Panel content areas */
.panel > div:not(.panel-title):not(.resize-handle) {
  flex-grow: 1; /* Allow content div to grow */
  overflow: hidden; /* Let children handle scroll */
  border-radius: 0 0 6px 6px; /* Radius for content area below title */
}

/* Adjust specific panel spans/borders if needed (grid-area handles layout) */
.combined-monitor-panel { border-color: rgba(79, 209, 197, 0.2); }
.alert-replay-panel { border-color: rgba(255, 165, 0, 0.2); } /* Orange border */
.qa-panel { border-color: rgba(128, 90, 213, 0.2); }

/* Background grid and scanline remain the same */
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
  opacity: 0.5;
  pointer-events: none;
}
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
  opacity: 0.5;
}

@keyframes scanline {
  0% { top: -10px; }
  100% { top: 100vh; }
}

/* Draggable styles remain the same */
.ghost-panel { opacity: 0.5; background: rgba(0, 0, 0, 0.2) !important; }
.chosen-panel { box-shadow: 0 0 20px rgba(79, 209, 197, 0.6) !important; z-index: 20; }
.drag-panel { transform: rotate(1deg) scale(1.03); z-index: 30; }

/* Resize Handle Styles */
.resize-handle {
  position: absolute;
  background-color: transparent; /* Make invisible by default */
  z-index: 15; /* Above panel content, below hover effects? */
  transition: background-color 0.2s ease;
}

.panel:hover .resize-handle {
   /* Show handles only on panel hover */
   /* background-color: rgba(79, 209, 197, 0.1); */ /* Very subtle */
}

.resize-handle:hover {
  background-color: rgba(79, 209, 197, 0.4); /* Highlight on handle hover */
}

/* Directions */
.resize-e { top: 0; right: -2px; width: 8px; height: 100%; cursor: e-resize; }
.resize-w { top: 0; left: -2px; width: 8px; height: 100%; cursor: w-resize; }
.resize-s { bottom: -2px; left: 0; width: 100%; height: 8px; cursor: s-resize; }
.resize-n { top: -2px; left: 0; width: 100%; height: 8px; cursor: n-resize; }

/* Corners */
.resize-se { bottom: -2px; right: -2px; width: 12px; height: 12px; cursor: se-resize; border-radius: 0 0 4px 0; }
.resize-sw { bottom: -2px; left: -2px; width: 12px; height: 12px; cursor: sw-resize; border-radius: 0 0 0 4px; }
.resize-ne { top: -2px; right: -2px; width: 12px; height: 12px; cursor: ne-resize; border-radius: 0 4px 0 0; }
.resize-nw { top: -2px; left: -2px; width: 12px; height: 12px; cursor: nw-resize; border-radius: 4px 0 0 0; }

/* Resizing state */
.panel.resizing {
  transition: none !important;
  user-select: none; /* Prevent text selection during resize */
  /* Optionally add a visual indicator */
  /* box-shadow: 0 0 0 2px rgba(79, 209, 197, 0.5) inset !important; */
}

/* Global disable pointer events on panel content during resize */
.panel.resizing > *:not(.panel-title):not(.resize-handle) {
    pointer-events: none;
}

/* 修改AppHeader组件相关样式，如果存在的话 */
:deep(.header) {
  margin: 0;
  padding: 0;
}
</style> 