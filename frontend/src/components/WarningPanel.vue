<template>
  <div>
    <div class="panel-title">预警回放</div>
    <div class="warning-content">
      <div v-if="alertToReplay && alertToReplay.image_path" class="replay-image-container">
        <img :src="getImageUrl(alertToReplay.image_path)" :alt="`预警: ${alertToReplay.content}`" class="replay-image">
        <div class="replay-info">
          <span>{{ formatTimestamp(alertToReplay.timestamp) }}</span>
          <span>{{ alertToReplay.content }}</span>
        </div>
        <div class="warning-overlay"></div>
        <div class="warning-frame"></div>
      </div>
      <p v-else>点击右侧预警信息查看快照</p>
      <div class="tech-decoration left"></div>
      <div class="tech-decoration right"></div>
      <div class="pulse-dot top-right"></div>
      <div class="pulse-dot bottom-left"></div>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue';

const props = defineProps({
  alertToReplay: {
    type: Object,
    default: null
  }
});

const formatTimestamp = (isoString) => {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'medium', hour12: false });
  } catch (e) {
    return isoString;
  }
};

const getImageUrl = (imagePath) => {
  if (!imagePath) return '';
  return imagePath.startsWith('/') ? imagePath : `/${imagePath}`;
};
</script>

<style scoped>
/* 预警回放面板特定样式 */
.warning-content {
  flex-grow: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px; /* 增加最小高度以容纳图片 */
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
  position: relative; /* 为了信息叠加 */
  overflow: hidden; /* 隐藏可能的溢出 */
}
.warning-content p {
  color: var(--text-secondary);
}
/* 从 main.css 迁移 .warning-panel 相关样式 */

.replay-image-container {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
}

.replay-image {
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain; /* 保持图片比例 */
  border-radius: 4px;
  z-index: 2;
}

.replay-info {
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
  opacity: 0; /* 默认隐藏 */
  transition: opacity 0.3s ease;
  z-index: 3;
}

.replay-image-container:hover .replay-info {
  opacity: 1; /* 悬停时显示信息 */
}

/* 警告覆盖层 - 添加红色警告效果 */
.warning-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: radial-gradient(circle, transparent 60%, rgba(255, 0, 0, 0.2) 100%);
  pointer-events: none;
  z-index: 1;
  animation: pulseWarning 3s infinite;
}

@keyframes pulseWarning {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.6; }
}

/* 警告框架 - 添加闪烁边框 */
.warning-frame {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 2px solid rgba(255, 0, 0, 0.3);
  pointer-events: none;
  z-index: 1;
  animation: blinkFrame 2s infinite;
}

@keyframes blinkFrame {
  0%, 100% { border-color: rgba(255, 0, 0, 0.3); }
  50% { border-color: rgba(255, 0, 0, 0.7); }
}

/* 科技装饰 */
.tech-decoration {
  position: absolute;
  width: 30px;
  height: 60px;
  border-top: 1px solid var(--cyber-neon);
  border-bottom: 1px solid var(--cyber-neon);
  opacity: 0.5;
  pointer-events: none;
}

.tech-decoration.left {
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  border-left: 1px solid var(--cyber-neon);
}

.tech-decoration.right {
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  border-right: 1px solid var(--cyber-neon);
}

/* 脉冲点 */
.pulse-dot {
  position: absolute;
  width: 6px;
  height: 6px;
  background-color: var(--cyber-neon);
  border-radius: 50%;
  animation: pulseDot 2s infinite;
}

.pulse-dot.top-right {
  top: 10px;
  right: 10px;
  animation-delay: 0.5s;
}

.pulse-dot.bottom-left {
  bottom: 10px;
  left: 10px;
}

@keyframes pulseDot {
  0%, 100% { transform: scale(1); opacity: 0.7; }
  50% { transform: scale(1.5); opacity: 1; }
}
</style> 