<template>
  <div>
    <div class="panel-title">
      <span class="panel-icon">📹</span> 实时监控
      <div class="panel-decoration"></div>
    </div>

    <div class="video-container">
      <img
        v-if="videoFeed"
        :src="videoFeed"
        alt="实时监控画面"
        id="video-feed"
      />
      <div v-else class="video-status">
        <span class="status-message">
          {{ wsConnected ? "等待视频数据..." : "视频连接失败，请检查服务状态" }}
        </span>
        <div v-if="wsConnected" class="loading-spinner"></div>
      </div>
      <div class="video-timestamp" v-if="videoFeed">
        <span class="timestamp-text">实时</span>
        <span class="timestamp-blink">•</span>
      </div>
      <div class="data-flow"></div>
      <div class="corner-decoration top-left"></div>
      <div class="corner-decoration top-right"></div>
      <div class="corner-decoration bottom-left"></div>
      <div class="corner-decoration bottom-right"></div>
    </div>

    <!-- Resize Handles -->
    <div
      class="resize-handle resize-w"
      @mousedown="$emit('start-resize', $event, 'w')"
    ></div>
    <div
      class="resize-handle resize-n"
      @mousedown="$emit('start-resize', $event, 'n')"
    ></div>
    <div
      class="resize-handle resize-nw"
      @mousedown="$emit('start-resize', $event, 'nw')"
    ></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, defineEmits } from "vue";

defineEmits(["start-resize"]);

// 视频相关状态
const videoFeed = ref("");
let ws = null;
const wsConnected = ref(false);

// WebSocket连接函数
function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/video_feed`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log("视频 WebSocket 已连接");
    wsConnected.value = true;
  };

  ws.onmessage = (event) => {
    if (event.data instanceof Blob) {
      if (videoFeed.value) {
        URL.revokeObjectURL(videoFeed.value);
      }
      videoFeed.value = URL.createObjectURL(event.data);
    } else {
      console.log("收到非 Blob 数据:", event.data);
    }
  };

  ws.onclose = () => {
    console.log("视频 WebSocket 已关闭，尝试重新连接...");
    wsConnected.value = false;
    videoFeed.value = ""; // 清空旧图像
    if (ws) {
      // 避免在组件卸载后仍然尝试重连
      setTimeout(connectWebSocket, 3000); // 增加重连延迟
    }
  };

  ws.onerror = (error) => {
    console.error("视频 WebSocket 错误:", error);
    wsConnected.value = false;
  };
}

onMounted(() => {
  connectWebSocket();
});

onUnmounted(() => {
  // 清理WebSocket连接
  if (ws) {
    ws.onclose = null; // 防止触发重连
    ws.onerror = null;
    ws.close();
    ws = null; // 显式设置为空
  }

  // 清理视频URL
  if (videoFeed.value) {
    URL.revokeObjectURL(videoFeed.value);
  }
});
</script>

<style scoped>
/* Styles extracted from BehaviorAnalysisPage.vue related to the video panel */

.panel-title {
  /* Styles for panel title are expected to be handled by the parent or globally */
  /* Basic structure provided */
  padding: 10px 15px;
  font-size: 1.1rem;
  color: var(--cyber-neon);
  border-bottom: 1px solid rgba(79, 209, 197, 0.3);
  display: flex;
  align-items: center;
  position: relative;
  letter-spacing: 1px;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
  cursor: move;
  user-select: none;
  z-index: 5;
}

.panel-icon {
  margin-right: 8px;
}

.panel-decoration {
  /* Optional: Add specific decoration if needed */
}

.video-container {
  position: relative;
  width: 100%;
  height: calc(100% - 45px); /* Adjusted for panel title */
  overflow: hidden;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 0 0 4px 4px; /* Adjust radius if title has border */
  flex-grow: 1; /* Ensure it fills space */
  display: flex;
  justify-content: center;
  align-items: center;
}

#video-feed {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-status {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: var(--text-primary);
}

.status-message {
  display: block;
  margin-bottom: 10px;
  font-size: 14px;
}

.loading-spinner {
  width: 30px;
  height: 30px;
  border: 3px solid rgba(79, 209, 197, 0.3);
  border-top: 3px solid var(--cyber-neon);
  border-radius: 50%;
  margin: 0 auto;
  animation: spin 1s linear infinite;
}

.video-timestamp {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.6);
  padding: 4px 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--text-primary);
  font-size: 12px;
  z-index: 3;
}

.timestamp-blink {
  color: #ff4444;
  animation: blink 1s infinite;
}

.corner-decoration {
  position: absolute;
  width: 20px;
  height: 20px;
  border: 2px solid var(--accent, var(--cyber-neon)); /* Fallback */
  opacity: 0.8;
  z-index: 2;
}

.top-left {
  top: 0;
  left: 0;
  border-right: none;
  border-bottom: none;
}

.top-right {
  top: 0;
  right: 0;
  border-left: none;
  border-bottom: none;
}

.bottom-left {
  bottom: 0;
  left: 0;
  border-right: none;
  border-top: none;
}

.bottom-right {
  bottom: 0;
  right: 0;
  border-left: none;
  border-top: none;
}

.data-flow {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(
    90deg,
    transparent,
    var(--accent, var(--cyber-neon)),
    transparent
  );
  animation: dataFlow 2s linear infinite;
  z-index: 2;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

@keyframes dataFlow {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

/* Resize handle styles (copied for encapsulation) */
.resize-handle {
  position: absolute;
  background-color: rgba(79, 209, 197, 0.2);
  z-index: 10;
}

.resize-handle:hover {
  background-color: rgba(79, 209, 197, 0.5);
}

.resize-w {
  top: 0;
  left: 0;
  width: 5px;
  height: 100%;
  cursor: w-resize;
}

.resize-n {
  top: 0;
  left: 0;
  width: 100%;
  height: 5px;
  cursor: n-resize;
}

.resize-nw {
  top: 0;
  left: 0;
  width: 15px;
  height: 15px;
  cursor: nw-resize;
  border-radius: 5px 0 0 0;
}
</style>
