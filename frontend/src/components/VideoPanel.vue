<template>
  <div> <!-- class="panel video-panel" 会由父组件传递 -->
    <div class="panel-title">实时监控</div>
    <div class="video-container">
      <img v-if="videoSrc" :src="videoSrc" alt="实时监控画面" id="video-feed">
      <p v-else>等待视频流...</p>
      <div class="video-timestamp">
        <span class="timestamp-text">实时</span>
        <span class="timestamp-blink">•</span>
      </div>
      <div class="data-flow"></div> <!-- 保留装饰元素 -->
      <div class="corner-decoration top-left"></div>
      <div class="corner-decoration top-right"></div>
      <div class="corner-decoration bottom-left"></div>
      <div class="corner-decoration bottom-right"></div>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue';

// 定义组件接收的属性
const props = defineProps({
  videoSrc: {
    type: String,
    default: ''
  }
});
</script>

<style scoped>
/* 视频面板特定样式 */
.video-container {
  flex-grow: 1;
  background-color: #000;
  position: relative;
  min-height: 250px; /* 最小高度 */
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 4px;
  overflow: hidden; /* 隐藏可能的溢出 */
}

#video-feed {
  display: block;
  max-width: 100%;
  max-height: 100%;
  width: auto; /* 保持宽高比 */
  height: auto; /* 保持宽高比 */
  object-fit: contain; /* 适应容器 */
}

.video-container p {
    color: var(--text-secondary, #8892b0);
}

/* 视频时间戳 */
.video-timestamp {
  position: absolute;
  top: 10px;
  right: 10px;
  background-color: rgba(0, 0, 0, 0.6);
  color: var(--cyber-neon);
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 0.8em;
  display: flex;
  align-items: center;
  gap: 5px;
  z-index: 10;
}

.timestamp-blink {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 从 main.css 迁移 .data-flow 样式 */
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

/* 角落装饰 */
.corner-decoration {
  position: absolute;
  width: 15px;
  height: 15px;
  border-color: var(--cyber-neon);
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
</style> 