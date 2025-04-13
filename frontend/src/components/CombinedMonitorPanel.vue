<template>
  <div class="combined-panel">
    <div class="panel-title">
      <div class="status-indicator" :class="{ 'connected': isConnected }"></div>
      <span>监控设备</span>
    </div>
    
    <div class="panel-content">
      <!-- 左侧设备列表 -->
      <div class="device-list-container">
        <div v-if="devices.length === 0" class="no-devices">
          暂无在线设备
        </div>
        <div v-else class="devices-wrapper">
          <div v-for="device in devices" :key="device.id" 
               class="device-item" 
               :class="{'device-active': device.isActive}"
               @click="selectDevice(device)">
            <div class="device-icon">
              <i :class="getDeviceIcon(device.type)"></i>
            </div>
            <div class="device-content">
              <div class="device-name">{{ device.name }}</div>
              <div class="device-status">
                <span class="status-dot" :class="{'status-online': device.online}"></span>
                {{ device.online ? '在线' : '离线' }}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 右侧视频显示 -->
      <div class="video-container">
        <img v-if="videoSrc" :src="videoSrc" alt="实时监控画面" id="video-feed">
        <p v-else>等待视频流...</p>
        <div class="video-timestamp">
          <span class="timestamp-blink">•</span>
        </div>
        <div class="data-flow"></div>
        <div class="corner-decoration top-left"></div>
        <div class="corner-decoration top-right"></div>
        <div class="corner-decoration bottom-left"></div>
        <div class="corner-decoration bottom-right"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';

// 组件属性
const props = defineProps({
  videoSrc: {
    type: String,
    default: ''
  },
  videoWs: {
    type: Object,
    default: null
  },
  deviceWs: {
    type: Object,
    default: null
  }
});

// 连接状态
const isConnected = computed(() => {
  return (props.videoWs && props.videoWs.readyState === WebSocket.OPEN) || 
         (props.deviceWs && props.deviceWs.readyState === WebSocket.OPEN);
});

// 模拟设备数据
const devices = ref([
  { id: 1, name: '实验室摄像头', type: 'camera', online: true, isActive: true },
  { id: 2, name: '后门监控摄像头', type: 'camera', online: true, isActive: false },
  { id: 3, name: '仓库监控摄像头', type: 'camera', online: false, isActive: false },
  { id: 4, name: '办公室监控摄像头', type: 'camera', online: true, isActive: false },
  { id: 5, name: '门禁系统', type: 'security', online: true, isActive: false }
]);

// 根据设备类型返回图标
const getDeviceIcon = (type) => {
  switch (type) {
    case 'camera':
      return 'fas fa-video';
    case 'security':
      return 'fas fa-shield-alt';
    default:
      return 'fas fa-desktop';
  }
};

// 选择设备
const selectDevice = (device) => {
  devices.value.forEach(d => {
    d.isActive = d.id === device.id;
  });
  
  // 这里可以发送事件或直接切换视频源
  console.log('已选择设备:', device.name);
};

// 设备和视频WebSocket连接状态监控可以根据需要添加
</script>

<style scoped>
.combined-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 15px;
  color: var(--primary, #4fd1c5);
  border-bottom: 1px solid rgba(79, 209, 197, 0.5);
  padding-bottom: 8px;
  display: flex;
  align-items: center;
  letter-spacing: 1px;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
  cursor: move;
  user-select: none;
}

.panel-title::before {
  content: "⋮⋮";
  margin-right: 8px;
  opacity: 0.5;
  font-size: 14px;
}

.panel-title:hover::before {
  opacity: 1;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 10px;
  background-color: #ff4d4d;
  box-shadow: 0 0 8px rgba(255, 77, 77, 0.7);
  animation: breathingLightRed 3s infinite ease-in-out;
}

.status-indicator.connected {
  background-color: #4fd1c5;
  box-shadow: 0 0 8px rgba(79, 209, 197, 0.7);
  animation: breathingLightGreen 3s infinite ease-in-out;
}

@keyframes breathingLightRed {
  0%, 100% { opacity: 0.5; box-shadow: 0 0 5px rgba(255, 77, 77, 0.5); }
  50% { opacity: 1; box-shadow: 0 0 12px rgba(255, 77, 77, 0.9); }
}

@keyframes breathingLightGreen {
  0%, 100% { opacity: 0.5; box-shadow: 0 0 5px rgba(79, 209, 197, 0.5); }
  50% { opacity: 1; box-shadow: 0 0 12px rgba(79, 209, 197, 0.9); }
}

.panel-content {
  flex-grow: 1;
  display: flex;
  gap: 15px;
  overflow: hidden;
}

/* 设备列表样式 */
.device-list-container {
  flex-grow: 1;
  overflow-y: auto;
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
  padding: 10px;
}

.device-item {
  display: flex;
  align-items: center;
  background-color: rgba(30, 41, 59, 0.7);
  border-left: 3px solid var(--primary, #4fd1c5);
  border-radius: 0 4px 4px 0;
  margin-bottom: 8px;
  padding: 10px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.device-item:hover {
  background-color: rgba(51, 65, 85, 0.7);
  transform: translateX(3px);
}

.device-active {
  border-left-color: #10b981;
  background-color: rgba(16, 185, 129, 0.15);
}

.device-icon {
  margin-right: 12px;
  color: var(--primary, #4fd1c5);
}

.device-content {
  flex-grow: 1;
}

.device-name {
  font-size: 14px;
  margin-bottom: 4px;
  color: #e2e8f0;
}

.device-status {
  font-size: 12px;
  color: #94a3b8;
  display: flex;
  align-items: center;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 5px;
  background-color: #94a3b8;
}

.status-online {
  background-color: #10b981;
}

.no-devices {
  text-align: center;
  padding: 20px;
  color: var(--text-secondary, #94a3b8);
  font-style: italic;
}

/* 视频容器样式 */
.video-container {
  flex-grow: 0;
  width: auto;
  background-color: #000;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 4px;
  overflow: hidden;
}

#video-feed {
  max-width: 100%;
  max-height: 100%;
  display: block;
  object-fit: contain;
}

.video-container p {
  color: var(--text-secondary, #8892b0);
}

.video-timestamp {
  position: absolute;
  top: 5px;
  right: 10px;
  background-color: transparent;
  color: var(--cyber-neon, #4fd1c5);
  padding: 3px;
  border-radius: 3px;
  font-size: 0.8em;
  display: flex;
  align-items: center;
  gap: 5px;
  z-index: 10;
}

.timestamp-blink {
  animation: blink 1s infinite;
  font-size: 1.5em;
  color: #4fd1c5;
  text-shadow: none;
}

@keyframes blink {
  0%, 100% { opacity: 1; transform: scale(1.3); }
  50% { opacity: 0.2; transform: scale(0.8); }
}

.data-flow {
  position: absolute;
  bottom: 5px;
  right: 5px;
  width: 50px;
  height: 20px;
  background: linear-gradient(45deg, rgba(79, 209, 197, 0.1), rgba(79, 209, 197, 0.3));
  opacity: 0.6;
  pointer-events: none;
  animation: dataFlowAnim 2s linear infinite alternate;
}

@keyframes dataFlowAnim {
  from { transform: scaleX(0.5); }
  to { transform: scaleX(1); }
}

.corner-decoration {
  position: absolute;
  width: 15px;
  height: 15px;
  border-color: var(--cyber-neon, #4fd1c5);
  opacity: 0.7;
}

.top-left {
  top: 5px;
  left: 5px;
  border-top: 2px solid;
  border-left: 2px solid;
}

.top-right {
  top: 5px;
  right: 5px;
  border-top: 2px solid;
  border-right: 2px solid;
}

.bottom-left {
  bottom: 5px;
  left: 5px;
  border-bottom: 2px solid;
  border-left: 2px solid;
}

.bottom-right {
  bottom: 5px;
  right: 5px;
  border-bottom: 2px solid;
  border-right: 2px solid;
}

/* 滚动条样式 */
.device-list-container::-webkit-scrollbar {
  width: 5px;
}

.device-list-container::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.3);
}

.device-list-container::-webkit-scrollbar-thumb {
  background: rgba(79, 209, 197, 0.5);
  border-radius: 3px;
}

.device-list-container::-webkit-scrollbar-thumb:hover {
  background: rgba(79, 209, 197, 0.7);
}
</style> 