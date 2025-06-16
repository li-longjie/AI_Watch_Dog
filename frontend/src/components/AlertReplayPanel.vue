<template>
  <div class="alert-replay-panel">
    <div class="panel-title">
      <div class="status-indicator" :class="{ 'connected': isConnected }"></div>
      <span>预警与回放</span>
    </div>
    <div class="panel-content">
      <!-- 回放区域 -->
      <div class="replay-section">
        <div v-if="selectedAlert" class="media-switch-buttons">
          <button
            :class="{'active': mediaType === 'image'}"
            @click="switchMedia('image')"
            title="查看照片">
            <i class="fas fa-camera"></i>
          </button>
          <button
            :class="{'active': mediaType === 'video'}"
            @click="switchMedia('video')"
            title="查看视频"
            :disabled="!selectedAlertHasVideo">
            <i class="fas fa-video"></i>
          </button>
        </div>

        <div v-if="selectedAlert && mediaType === 'image'" class="replay-media-container">
          <img :src="selectedAlert.image_url" :alt="`预警: ${selectedAlert.content}`" class="replay-media replay-image">
          <div class="replay-info">
            <span>{{ formatDisplayTime(selectedAlert.timestamp) }}</span>
            <span>{{ formatAlertContent(selectedAlert) }}</span>
          </div>
          <div class="warning-overlay"></div>
          <div class="warning-frame"></div>
        </div>

        <div v-else-if="selectedAlert && mediaType === 'video' && selectedAlertHasVideo" class="replay-media-container">
          <video ref="videoPlayer" class="replay-media replay-video" controls :src="currentVideoUrl">
            您的浏览器不支持视频播放。
          </video>
          <div class="replay-info">
            <span>{{ formatDisplayTime(selectedAlert.timestamp) }}</span>
            <span>{{ formatAlertContent(selectedAlert) }}</span>
          </div>
        </div>

         <div v-else-if="selectedAlert && mediaType === 'video' && !selectedAlertHasVideo" class="no-media">
           <p>此预警没有关联视频</p>
         </div>

        <div v-else class="no-selection">
          <p>请从下方列表选择预警进行查看</p>
        </div>

        <!-- 装饰元素 from WarningPanel -->
        <div class="tech-decoration left"></div>
        <div class="tech-decoration right"></div>
        <div class="pulse-dot top-right"></div>
        <div class="pulse-dot bottom-left"></div>
      </div>

      <!-- 预警列表区域 -->
      <div class="list-section">
        <AlertList :alerts="alerts" @replay-alert="handleReplayAlert" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import AlertList from './AlertList.vue'; // 引入预警列表组件

// --- Props ---
const props = defineProps({
  alerts: {
    type: Array,
    required: true,
    default: () => []
  },
  // 接收父组件传递的 ws 连接对象用于状态显示
  wsConnection: {
    type: Object,
    default: null
  }
});

// --- State ---
const selectedAlert = ref(null); // 当前选中的预警
const mediaType = ref('image'); // 'image' or 'video'
const videoPlayer = ref(null);
const isConnected = ref(false); // 连接状态

// --- Computed ---
// 检查选中的预警是否有视频
const selectedAlertHasVideo = computed(() => {
  return selectedAlert.value && selectedAlert.value.video_url;
});

// 计算当前视频 URL（添加时间戳避免缓存）
const currentVideoUrl = computed(() => {
  if (!selectedAlertHasVideo.value) {
    return '';
  }
  const videoUrl = selectedAlert.value.video_url;
  // 判断是否已经是完整URL或相对路径
  if (videoUrl.startsWith('http')) {
    return `${videoUrl}?t=${new Date().getTime()}`;
  } else {
    // 相对路径，需要拼接 (假设后端服务和前端在同一域或已配置代理)
    // 对于 /static/... 或类似路径，浏览器会自动处理
    // 如果是完全不同的域且未代理，需要完整 URL
    // 简单起见，直接添加时间戳
    return `${videoUrl}?t=${new Date().getTime()}`;
  }
});

// --- Methods ---
// 处理从 AlertList 组件传来的事件
function handleReplayAlert(alert) {
  console.log('选中预警:', alert);
  selectedAlert.value = alert;
  // 默认切换回图片视图，如果图片不存在则尝试视频
  mediaType.value = alert.image_url ? 'image' : (alert.video_url ? 'video' : 'image');
}

// 切换媒体类型
const switchMedia = (type) => {
  if (!selectedAlert.value) return;
  if (type === 'video' && !selectedAlertHasVideo.value) return; // 没有视频则不允许切换

  mediaType.value = type;

  // 如果切换到视频，尝试加载和播放
  if (type === 'video' && videoPlayer.value) {
    setTimeout(() => {
      if (videoPlayer.value) {
          videoPlayer.value.load(); // 确保重新加载
          videoPlayer.value.play().catch(err => {
            console.warn('视频自动播放失败:', err);
          });
      }
    }, 50); // 短暂延迟确保 DOM 更新和 src 生效
  }
};

// 格式化时间戳 (仅时间部分)
const formatDisplayTime = (isoString) => {
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

// 格式化预警内容，显示持续时间
const formatAlertContent = (alert) => {
  if (!alert) return '';
  
  let content = alert.content || '';
  
  // 如果有持续时间信息，添加到内容中
  if (alert.duration_minutes !== undefined && alert.duration_minutes > 0) {
    const duration = alert.duration_minutes;
    let durationText = '';
    
    if (duration >= 60) {
      const hours = Math.floor(duration / 60);
      const minutes = Math.round(duration % 60);
      durationText = hours > 0 ? `${hours}小时${minutes}分钟` : `${minutes}分钟`;
    } else if (duration >= 1) {
      durationText = `${Math.round(duration)}分钟`;
    } else {
      durationText = `${Math.round(duration * 60)}秒`;
    }
    
    // 如果是结束预警，显示持续时间
    if (content.includes('结束')) {
      content = `${content}: ${durationText}`;
    } else {
      // 对于开始预警，如果有结束时间，也可以显示持续时间
      if (alert.end_time && alert.start_time) {
        content = `${content} (持续${durationText})`;
      }
    }
  }
  
  // 如果有开始时间和结束时间，显示时间范围
  if (alert.start_time && alert.end_time && alert.start_time !== alert.end_time) {
    const startTime = formatDisplayTime(alert.start_time);
    const endTime = formatDisplayTime(alert.end_time);
    content += ` [${startTime} - ${endTime}]`;
  }
  
  return content;
};

// 检查连接状态 (基于传入的 wsConnection)
const checkConnection = () => {
  try {
    isConnected.value = props.wsConnection && props.wsConnection.readyState === WebSocket.OPEN;
  } catch (error) {
    console.error('检查连接状态失败:', error);
    isConnected.value = false;
  }
};

// --- Watchers ---
// 监听父组件传入的 ws 连接对象变化
watch(() => props.wsConnection, (newWs) => {
  if (newWs) {
    checkConnection(); // 初始检查

    // 添加事件监听器实时更新状态
    newWs.addEventListener('open', checkConnection);
    newWs.addEventListener('close', checkConnection);
    newWs.addEventListener('error', checkConnection);

    // TODO: 在组件卸载时移除监听器 (需要 onUnmounted)
  } else {
    isConnected.value = false;
  }
}, { immediate: true });

// 当选中的预警变化时，如果当前是视频模式但新预警无视频，则切回图片
watch(selectedAlert, (newAlert) => {
    if (mediaType.value === 'video' && (!newAlert || !newAlert.video_url)) {
        mediaType.value = 'image';
    }
    // 如果视频播放器存在且正在播放，暂停它
    if (videoPlayer.value && !videoPlayer.value.paused) {
      videoPlayer.value.pause();
    }
});

</script>

<style scoped>
.alert-replay-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* 防止内容溢出 */
}

.panel-title {
  /* Styles from other panels (VideoPanel, QAPanel) */
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 15px;
  color: var(--primary, #4fd1c5); /* Use a neutral color or specific color */
  border-bottom: 1px solid rgba(79, 209, 197, 0.5);
  padding-bottom: 8px;
  display: flex;
  align-items: center;
  letter-spacing: 1px;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
  flex-shrink: 0; /* 防止标题被压缩 */
  cursor: move; /* Title is usually the drag handle */
  user-select: none;
}

.panel-title::before {
  content: "⋮⋮"; /* Drag handle indicator */
  margin-right: 8px;
  opacity: 0.5;
  font-size: 14px;
}

.panel-title:hover::before {
  opacity: 1;
}


.status-indicator {
  /* Styles from other panels */
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 10px;
  background-color: #ff4d4d; /* Default Red */
  box-shadow: 0 0 8px rgba(255, 77, 77, 0.7);
  animation: breathingLightRed 3s infinite ease-in-out;
}

.status-indicator.connected {
  background-color: #4fd1c5; /* Green when connected */
  box-shadow: 0 0 8px rgba(79, 209, 197, 0.7);
  animation: breathingLightGreen 3s infinite ease-in-out;
}

.panel-content {
  flex-grow: 1;
  display: flex;
  flex-direction: row; /* *** 改为左右布局 *** */
  overflow: hidden;
  gap: 10px;
}

.replay-section {
  /* 设置宽度，例如 50% 或使用 flex */
  width: 50%;
  /* height: 45%; */ /* 移除高度限制 */
  height: 100%; /* 高度占满父容器 */
  /* min-height: 150px; */ /* 移除或调整 */
  flex-shrink: 0;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
  overflow: hidden;
}

.list-section {
  /* 设置宽度，例如 50% 或使用 flex */
  width: 50%;
  /* flex-grow: 1; */ /* 移除 flex-grow 或调整 */
  height: 100%; /* 高度占满父容器 */
  overflow: hidden; /* AlertList 内部处理滚动 */
  border-radius: 4px;
}

.replay-media-container {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative; /* For replay-info positioning */
}

.replay-media {
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain; /* 保持比例 */
  border-radius: 4px;
  z-index: 2;
}

.replay-image {
  /* Specific styles for image if needed */
}

.replay-video {
  /* Specific styles for video if needed */
}


.replay-info {
  /* Styles from WarningPanel */
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 5px 10px;
  font-size: 0.85em;
  display: flex;
  justify-content: space-between;
  align-items: center;
  opacity: 0; /* Hidden by default */
  transition: opacity 0.3s ease;
  z-index: 3;
  pointer-events: none; /* Allow interaction with video controls */
}

.replay-media-container:hover .replay-info {
  opacity: 1; /* Show on hover */
}

.no-selection, .no-media {
  color: var(--text-secondary);
  font-style: italic;
}

/* Media Switch Buttons (from WarningPanel) */
.media-switch-buttons {
  position: absolute;
  top: 25px; /* 增大 top 值，将按钮向下移动 */
  right: 10px; /* 稍微增大 right 值，给右边留点空间 */
  z-index: 10;
  display: flex;
  gap: 6px;
}

.media-switch-buttons button {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(79, 209, 197, 0.4);
  color: #a0aec0;
  width: 15px;
  height: 15px;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.media-switch-buttons button:hover {
  background: rgba(30, 41, 59, 0.7);
  color: #e2e8f0;
  border-color: rgba(79, 209, 197, 0.7);
}

.media-switch-buttons button.active {
  background: rgba(79, 209, 197, 0.2);
  color: #4fd1c5;
  border-color: #4fd1c5;
  box-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
}

.media-switch-buttons button:disabled {
    background: rgba(51, 65, 85, 0.4);
    color: #718096;
    cursor: not-allowed;
    border-color: rgba(71, 85, 105, 0.5);
}


/* Decorations (from WarningPanel) */
.warning-overlay, .warning-frame, .tech-decoration, .pulse-dot {
  /* Copy relevant styles from WarningPanel.vue's <style scoped> */
  pointer-events: none;
}

.warning-overlay {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: radial-gradient(circle, transparent 60%, rgba(255, 0, 0, 0.15) 100%);
  z-index: 1;
  animation: pulseWarning 3s infinite;
}
.warning-frame {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  border: 1px solid rgba(255, 0, 0, 0.2);
  z-index: 1;
  animation: blinkFrame 2.5s infinite;
}
.tech-decoration {
  position: absolute; width: 20px; height: 40px;
  border-top: 1px solid var(--cyber-neon-dim, rgba(0, 255, 255, 0.3));
  border-bottom: 1px solid var(--cyber-neon-dim, rgba(0, 255, 255, 0.3));
  opacity: 0.4;
}
.tech-decoration.left { left: 10px; top: 50%; transform: translateY(-50%); border-left: 1px solid var(--cyber-neon-dim, rgba(0, 255, 255, 0.3)); }
.tech-decoration.right { right: 10px; top: 50%; transform: translateY(-50%); border-right: 1px solid var(--cyber-neon-dim, rgba(0, 255, 255, 0.3)); }
.pulse-dot {
  position: absolute; width: 5px; height: 5px;
  background-color: var(--cyber-neon-dim, rgba(0, 255, 255, 0.5));
  border-radius: 50%;
  animation: pulseDot 2.5s infinite;
}
.pulse-dot.top-right { top: 10px; right: 10px; animation-delay: 0.5s; }
.pulse-dot.bottom-left { bottom: 10px; left: 10px; }

@keyframes pulseWarning { 0%, 100% { opacity: 0.2; } 50% { opacity: 0.4; } }
@keyframes blinkFrame { 0%, 100% { border-color: rgba(255, 0, 0, 0.2); } 50% { border-color: rgba(255, 0, 0, 0.5); } }
@keyframes pulseDot { 0%, 100% { transform: scale(1); opacity: 0.5; } 50% { transform: scale(1.4); opacity: 0.8; } }

/* Breathing Light Animations (Copied from other panels) */
@keyframes breathingLightRed {
  0%, 100% { opacity: 0.5; box-shadow: 0 0 5px rgba(255, 77, 77, 0.5); }
  50% { opacity: 1; box-shadow: 0 0 12px rgba(255, 77, 77, 0.9); }
}
@keyframes breathingLightGreen {
  0%, 100% { opacity: 0.5; box-shadow: 0 0 5px rgba(79, 209, 197, 0.5); }
  50% { opacity: 1; box-shadow: 0 0 12px rgba(79, 209, 197, 0.9); }
}

/* 确保 AlertList 在新布局下正常工作 */
.list-section :deep(.alerts-panel) {
  height: 100%;
  background: none;
  box-shadow: none;
  padding: 0;
  border: none;
  display: flex; /* 确保其内部也是 flex 布局 */
  flex-direction: column; /* 保持 AlertList 内部的列方向 */
}

.list-section :deep(.alerts-container) {
  flex-grow: 1; /* 让列表容器填满剩余空间 */
  height: auto; /* 移除固定高度 */
  max-height: none; /* 移除最大高度 */
  padding: 0 5px 5px 5px; /* 可选调整 */
}

.list-section :deep(.panel-title) {
  display: none; /* 隐藏 AlertList 可能自带的标题 */
}

</style> 