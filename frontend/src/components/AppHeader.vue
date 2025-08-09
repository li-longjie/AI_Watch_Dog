<template>
  <div class="header">
    <div class="circuit-bg"></div>
    <div class="header-decorations">
      <div class="scan-line"></div>
      <div class="scan-line"></div>
      <div class="data-point"></div>
      <div class="data-point"></div>
      <div class="data-point"></div>
      <div class="data-point"></div>
      <div class="header-left-decor">
        <div class="data-cube"></div>
        <div class="data-cube"></div>
        <div class="data-cube"></div>
        <div class="data-cube"></div>
      </div>
      <div class="header-right-decor">
        <div class="radar-circle"></div>
      </div>
      
      <div class="digital-counter">ID:<span class="counter-value" data-value="0127"></span></div>
      <div class="waveform">
        <div class="wave-line"></div>
        <div class="wave-line"></div>
        <div class="wave-line"></div>
        <div class="wave-line"></div>
        <div class="wave-line"></div>
        <div class="wave-line"></div>
        <div class="wave-line"></div>
      </div>
      <div class="tech-frame"></div>
      <div class="rotating-mark"></div>
      <div class="data-stream"></div>
    </div>
    <div class="header-bg-extensions">
      <div class="background-grid"></div>
      
      <div class="tech-panel-left">
        <div class="monitor-line"></div>
        <div class="monitor-line"></div>
        <div class="monitor-line"></div>
      </div>
      
      <div class="tech-panel-right">
        <div class="monitor-line"></div>
        <div class="monitor-line"></div>
        <div class="monitor-line"></div>
      </div>
      
      <div class="tech-dot dot-1"></div>
      <div class="tech-dot dot-2"></div>
      <div class="tech-dot dot-3"></div>
      <div class="tech-dot dot-4"></div>
      
      <div class="status-indicator status-left">系统在线</div>
      <div class="status-indicator status-right">安全监控</div>
      
      <div class="horizontal-scan scan-top"></div>
      <div class="horizontal-scan scan-bottom"></div>
    </div>
    <div class="header-arrow-left">&gt; &gt; &gt; &gt;</div>
    <h1>
      <div class="title-backdrop">
        <div class="title-line title-line-top"></div>
        <div class="title-line title-line-bottom"></div>
      </div>
      <span class="title-flicker">融合AI-Agent的多模态行为监控系统</span>
      <div class="circuit-decoration circuit-left"></div>
      <div class="circuit-decoration circuit-right"></div>
      <div class="title-badge badge-left">V1.0</div>
      <div class="title-badge badge-right">secure</div>
    </h1>
    <div class="header-arrow-right">&gt; &gt; &gt; &gt;</div>
  </div>
</template>

<script setup>
// Header 可能需要的逻辑，例如动画触发等，暂时为空
import { onMounted } from 'vue';

onMounted(() => {
  // 数字计数器动画
  const counterElements = document.querySelectorAll('.counter-value');
  counterElements.forEach(element => {
    const targetValue = element.getAttribute('data-value');
    let currentValue = 0;
    const duration = 2000; // 动画持续时间（毫秒）
    const interval = 50; // 更新间隔（毫秒）
    const steps = duration / interval;
    const increment = parseInt(targetValue) / steps;
    
    const counter = setInterval(() => {
      currentValue += increment;
      if (currentValue >= parseInt(targetValue)) {
        currentValue = parseInt(targetValue);
        clearInterval(counter);
      }
      element.textContent = Math.floor(currentValue).toString().padStart(4, '0');
    }, interval);
  });
});
</script>

<style scoped>
/* 从 static/css/main.css 复制所有 .header 及其子元素的样式 */
.header {
  position: relative;
  height: 80px;
  width: 100%;
  background-color: rgba(6, 18, 36, 0.9);
  border-bottom: 1px solid rgba(79, 209, 197, 0.3);
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  z-index: 100; /* 确保 header 在内容之上 */
}

.circuit-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: 
    linear-gradient(rgba(0, 0, 0, 0) 9px, rgba(79, 209, 197, 0.1) 10px),
    linear-gradient(90deg, rgba(0, 0, 0, 0) 9px, rgba(79, 209, 197, 0.1) 10px);
  background-size: 10px 10px;
  opacity: 0.4;
  pointer-events: none;
}

.header-decorations {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* 扫描线 */
.scan-line {
  position: absolute;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.7), transparent);
  animation: scanline 8s linear infinite;
  opacity: 0.7;
  width: 100%;
}

.scan-line:nth-child(1) {
  top: 20%;
  animation-delay: -2s;
}

.scan-line:nth-child(2) {
  top: 60%;
  animation-delay: -6s;
}

@keyframes scanline {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* 数据点 */
.data-point {
  position: absolute;
  width: 4px;
  height: 4px;
  background-color: var(--cyber-neon);
  border-radius: 50%;
  animation: pulse 3s infinite;
}

.data-point:nth-child(3) { top: 15%; left: 10%; animation-delay: -0.5s; }
.data-point:nth-child(4) { top: 25%; left: 85%; animation-delay: -1.5s; }
.data-point:nth-child(5) { top: 65%; left: 20%; animation-delay: -2.5s; }
.data-point:nth-child(6) { top: 75%; left: 90%; animation-delay: -3.5s; }

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.5); opacity: 1; }
}

/* 左侧装饰 */
.header-left-decor {
  position: absolute;
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.data-cube {
  width: 8px;
  height: 8px;
  background-color: rgba(79, 209, 197, 0.3);
  border: 1px solid rgba(79, 209, 197, 0.5);
  animation: rotateCube 4s infinite linear;
}

.data-cube:nth-child(2) { animation-delay: -1s; }
.data-cube:nth-child(3) { animation-delay: -2s; }
.data-cube:nth-child(4) { animation-delay: -3s; }

@keyframes rotateCube {
  0% { transform: rotate(0deg) scale(1); }
  50% { transform: rotate(180deg) scale(1.2); }
  100% { transform: rotate(360deg) scale(1); }
}

/* 右侧装饰 */
.header-right-decor {
  position: absolute;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
}

.radar-circle {
  width: 30px;
  height: 30px;
  border: 1px solid rgba(79, 209, 197, 0.5);
  border-radius: 50%;
  position: relative;
  animation: radarPulse 3s infinite;
}

.radar-circle::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 50%;
  height: 1px;
  background-color: rgba(79, 209, 197, 0.7);
  transform-origin: left center;
  animation: radarScan 3s infinite linear;
}

@keyframes radarPulse {
  0%, 100% { transform: scale(1); opacity: 0.7; }
  50% { transform: scale(1.1); opacity: 1; }
}

@keyframes radarScan {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 数字计数器 */
.digital-counter {
  position: absolute;
  top: 10px;
  left: 10px;
  font-family: monospace;
  font-size: 12px;
  color: var(--cyber-neon);
  background-color: rgba(0, 0, 0, 0.3);
  padding: 2px 5px;
  border: 1px solid rgba(79, 209, 197, 0.3);
}

/* 波形图 */
.waveform {
  position: absolute;
  bottom: 10px;
  right: 10px;
  display: flex;
  align-items: flex-end;
  height: 15px;
  width: 50px;
  gap: 2px;
}

.wave-line {
  width: 2px;
  background-color: var(--cyber-neon);
  animation: waveAnim 1.5s infinite ease-in-out;
}

.wave-line:nth-child(1) { height: 30%; animation-delay: -0.2s; }
.wave-line:nth-child(2) { height: 50%; animation-delay: -0.4s; }
.wave-line:nth-child(3) { height: 70%; animation-delay: -0.6s; }
.wave-line:nth-child(4) { height: 100%; animation-delay: -0.8s; }
.wave-line:nth-child(5) { height: 70%; animation-delay: -1.0s; }
.wave-line:nth-child(6) { height: 50%; animation-delay: -1.2s; }
.wave-line:nth-child(7) { height: 30%; animation-delay: -1.4s; }

@keyframes waveAnim {
  0%, 100% { transform: scaleY(0.5); opacity: 0.5; }
  50% { transform: scaleY(1); opacity: 1; }
}

/* 技术框架 */
.tech-frame {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 300px;
  height: 40px;
  border: 1px solid rgba(79, 209, 197, 0.2);
  transform: translate(-50%, -50%);
  z-index: -1;
}

/* 旋转标记 */
.rotating-mark {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 40px;
  height: 40px;
  border: 1px dashed rgba(79, 209, 197, 0.3);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  animation: rotate 10s linear infinite;
  z-index: -1;
}

@keyframes rotate {
  0% { transform: translate(-50%, -50%) rotate(0deg); }
  100% { transform: translate(-50%, -50%) rotate(360deg); }
}

/* 数据流 */
.data-stream {
  position: absolute;
  width: 100px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--cyber-neon), transparent);
  animation: dataStream 3s linear infinite;
}

.data-stream:nth-child(13) {
  top: 30%;
  animation-delay: -1.5s;
}

.data-stream:nth-child(14) {
  bottom: 30%;
  animation-delay: -0.5s;
}

@keyframes dataStream {
  0% { transform: translateX(-100%); opacity: 0; }
  50% { opacity: 1; }
  100% { transform: translateX(100%); opacity: 0; }
}

/* 背景扩展 */
.header-bg-extensions {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* 背景网格 */
.background-grid {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: 
    linear-gradient(rgba(79, 209, 197, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(79, 209, 197, 0.05) 1px, transparent 1px);
  background-size: 20px 20px;
  opacity: 0.5;
}

/* 技术面板 */
.tech-panel-left, .tech-panel-right {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 30px;
  height: 60px;
  display: flex;
  flex-direction: column;
  justify-content: space-around;
}

.tech-panel-left { left: 50px; }
.tech-panel-right { right: 50px; }

.monitor-line {
  height: 2px;
  background-color: rgba(79, 209, 197, 0.3);
  animation: monitorPulse 2s infinite;
}

.tech-panel-left .monitor-line:nth-child(1) { animation-delay: -0.3s; }
.tech-panel-left .monitor-line:nth-child(2) { animation-delay: -0.6s; }
.tech-panel-left .monitor-line:nth-child(3) { animation-delay: -0.9s; }

.tech-panel-right .monitor-line:nth-child(1) { animation-delay: -1.2s; }
.tech-panel-right .monitor-line:nth-child(2) { animation-delay: -1.5s; }
.tech-panel-right .monitor-line:nth-child(3) { animation-delay: -1.8s; }

@keyframes monitorPulse {
  0%, 100% { transform: scaleX(0.3); opacity: 0.3; }
  50% { transform: scaleX(1); opacity: 1; }
}

/* 技术点 */
.tech-dot {
  position: absolute;
  width: 6px;
  height: 6px;
  background-color: var(--cyber-neon);
  border-radius: 50%;
  animation: techDotPulse 3s infinite;
}

.dot-1 { top: 20px; left: 20px; animation-delay: -0.5s; }
.dot-2 { top: 20px; right: 20px; animation-delay: -1.0s; }
.dot-3 { bottom: 20px; left: 20px; animation-delay: -1.5s; }
.dot-4 { bottom: 20px; right: 20px; animation-delay: -2.0s; }

@keyframes techDotPulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.5); opacity: 1; }
}

/* 状态指示器 */
.status-indicator {
  position: absolute;
  font-size: 10px;
  color: var(--cyber-neon);
  background-color: rgba(0, 0, 0, 0.3);
  padding: 2px 5px;
  border: 1px solid rgba(79, 209, 197, 0.3);
}

.status-left { left: 100px; top: 10px; }
.status-right { right: 100px; top: 10px; }

/* 水平扫描 */
.horizontal-scan {
  position: absolute;
  left: 0;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--cyber-neon), transparent);
  animation: horizontalScan 5s infinite linear;
}

.scan-top { top: 0; }
.scan-bottom { bottom: 0; }

@keyframes horizontalScan {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* 标题样式 */
.header-arrow-left, .header-arrow-right {
  font-family: monospace;
  color: var(--cyber-neon);
  font-size: 14px;
  margin: 0 15px;
  opacity: 0.7;
}

.header h1 {
  color: var(--text-primary);
  font-size: 24px;
  font-weight: 600;
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  letter-spacing: 1px;
}

.title-backdrop {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: -1;
}

.title-line {
  position: absolute;
  left: 0;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, 
    transparent, 
    rgba(79, 209, 197, 0.5), 
    transparent);
}

.title-line-top { top: -5px; }
.title-line-bottom { bottom: -5px; }

.title-flicker {
  animation: textFlicker 5s infinite;
}

@keyframes textFlicker {
  0%, 100% { opacity: 1; }
  92% { opacity: 1; }
  93% { opacity: 0.6; }
  94% { opacity: 1; }
  95% { opacity: 0.6; }
  96% { opacity: 1; }
  97% { opacity: 0.6; }
  98% { opacity: 1; }
}

.circuit-decoration {
  position: absolute;
  width: 30px;
  height: 20px;
  border-top: 1px solid var(--cyber-neon);
  opacity: 0.5;
}

.circuit-left {
  left: -40px;
  border-left: 1px solid var(--cyber-neon);
}

.circuit-right {
  right: -40px;
  border-right: 1px solid var(--cyber-neon);
}

.title-badge {
  position: absolute;
  font-size: 10px;
  text-transform: uppercase;
  background-color: rgba(0, 0, 0, 0.3);
  padding: 2px 5px;
  border: 1px solid rgba(79, 209, 197, 0.3);
}

.badge-left {
  left: -60px;
  bottom: -10px;
  color: var(--cyber-neon);
}

.badge-right {
  right: -60px;
  bottom: -10px;
  color: var(--cyber-purple);
}

/* ... */
</style> 