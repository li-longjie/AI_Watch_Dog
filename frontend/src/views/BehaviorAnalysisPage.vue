<template>
  <div class="behavior-analysis-page">
    <AppHeader />
    
    <div class="content-container">
      <div class="page-header">
        <h1>行为分析页面</h1>
      </div>
      
      <div class="loading-message" v-if="loading">
        <div class="cyber-spinner"></div>
        <p>加载行为数据中...</p>
      </div>
      
      <draggable 
        v-if="!loading"
        v-model="panelOrder" 
        class="analysis-container"
        item-key="id"
        :animation="200"
        handle=".panel-title"
        ghost-class="ghost-panel"
        chosen-class="chosen-panel"
        drag-class="drag-panel"
        tag="div"
      >
        <template #item="{element}">
          <div v-if="element.id === 1" class="panel behavior-stats-panel cyber-panel" :style="getPanelStyle(1)" ref="panel1" data-id="1">
            <div class="panel-title">
              <span class="panel-icon">📊</span>
              行为统计
              <div class="panel-decoration"></div>
            </div>
            <div class="stats-content">
              <div class="stat-item">
                <div class="stat-value cyber-value">{{ behaviorData.statistics?.total_behaviors || 0 }}</div>
                <div class="stat-label">总行为数</div>
              </div>
              <div class="stat-item">
                <div class="stat-value cyber-value">{{ behaviorData.statistics?.unique_behaviors || 0 }}</div>
                <div class="stat-label">行为类型</div>
              </div>
              <div class="stat-item">
                <div class="stat-value cyber-value highlight">{{ behaviorData.statistics?.most_frequent || '无' }}</div>
                <div class="stat-label">最频繁行为</div>
              </div>
            </div>
            <div class="resize-handle resize-e" @mousedown="startResize($event, 1, 'e')"></div>
            <div class="resize-handle resize-s" @mousedown="startResize($event, 1, 's')"></div>
            <div class="resize-handle resize-se" @mousedown="startResize($event, 1, 'se')"></div>
          </div>
          
          <div v-else-if="element.id === 2" class="panel behavior-list-panel cyber-panel" :style="getPanelStyle(2)" ref="panel2" data-id="2">
            <div class="panel-title">
              <span class="panel-icon">📝</span>
              行为记录
              <div class="panel-decoration"></div>
            </div>
            <div class="behavior-list">
              <div v-for="behavior in behaviorData.behaviors" :key="behavior.id" class="behavior-item cyber-list-item">
                <div class="behavior-time">{{ formatTime(behavior.timestamp) }}</div>
                <div class="behavior-type">{{ behavior.type }}</div>
                <div class="behavior-count">{{ behavior.count }}次</div>
              </div>
              <div v-if="!behaviorData.behaviors || behaviorData.behaviors.length === 0" class="no-data">
                暂无行为数据
              </div>
            </div>
            <div class="resize-handle resize-w" @mousedown="startResize($event, 2, 'w')"></div>
            <div class="resize-handle resize-s" @mousedown="startResize($event, 2, 's')"></div>
            <div class="resize-handle resize-sw" @mousedown="startResize($event, 2, 'sw')"></div>
          </div>
          
          <div v-else-if="element.id === 3" class="panel behavior-chart-panel cyber-panel" :style="getPanelStyle(3)" ref="panel3" data-id="3">
            <div class="panel-title">
              <span class="panel-icon">📈</span>
              行为趋势
              <div class="panel-decoration"></div>
            </div>
            <div class="chart-container">
              <!-- 这里可以添加图表组件，例如使用 Chart.js 或 ECharts -->
              <div class="cyber-chart">
                <div class="cyber-chart-bar" v-for="(behavior, index) in behaviorData.behaviors" :key="index"
                     :style="{ height: `${behavior.count * 20}px`, backgroundColor: getChartColor(behavior.type) }">
                  <div class="cyber-bar-label">{{ behavior.type }}</div>
                  <div class="cyber-bar-value">{{ behavior.count }}</div>
                </div>
              </div>
            </div>
            <div class="resize-handle resize-e" @mousedown="startResize($event, 3, 'e')"></div>
            <div class="resize-handle resize-n" @mousedown="startResize($event, 3, 'n')"></div>
            <div class="resize-handle resize-ne" @mousedown="startResize($event, 3, 'ne')"></div>
          </div>
          
          <div v-else-if="element.id === 4" class="panel behavior-analysis-panel cyber-panel" :style="getPanelStyle(4)" ref="panel4" data-id="4">
            <div class="panel-title">
              <span class="panel-icon">🔍</span>
              行为分析
              <div class="panel-decoration"></div>
            </div>
            <div class="analysis-content">
              <div class="analysis-summary">
                <h3 class="cyber-subtitle">分析摘要</h3>
                <p class="cyber-text">根据当前行为数据分析，用户主要表现为 <span class="cyber-highlight">{{ behaviorData.statistics?.most_frequent || '无' }}</span> 行为。</p>
                <p class="cyber-text">建议关注行为模式变化，特别是 <span class="cyber-highlight">专注工作</span> 与其他行为的转换频率。</p>
              </div>
              <div class="analysis-recommendations">
                <h3 class="cyber-subtitle">建议</h3>
                <ul class="cyber-list">
                  <li class="cyber-list-item">定期休息，避免长时间保持同一姿势</li>
                  <li class="cyber-list-item">注意坐姿，保持良好的工作习惯</li>
                  <li class="cyber-list-item">合理安排工作时间，提高效率</li>
                </ul>
              </div>
            </div>
            <div class="resize-handle resize-w" @mousedown="startResize($event, 4, 'w')"></div>
            <div class="resize-handle resize-n" @mousedown="startResize($event, 4, 'n')"></div>
            <div class="resize-handle resize-nw" @mousedown="startResize($event, 4, 'nw')"></div>
          </div>
        </template>
      </draggable>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import AppHeader from '../components/AppHeader.vue';
import draggable from 'vuedraggable';

const loading = ref(true);
const behaviorData = ref({
  behaviors: [],
  statistics: {
    total_behaviors: 0,
    unique_behaviors: 0,
    most_frequent: ''
  }
});

// 定义面板顺序
const panelOrder = ref([
  { id: 1 }, // 行为统计面板
  { id: 2 }, // 行为记录面板
  { id: 3 }, // 行为趋势面板
  { id: 4 }  // 行为分析面板
]);

// 修改面板大小调整相关的状态，设置初始大小
const panelSizes = ref({
  1: { width: '48%', height: '48%' },
  2: { width: '48%', height: '48%' },
  3: { width: '48%', height: '48%' },
  4: { width: '48%', height: '48%' }
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
  
  // 更精确地选择面板元素
  const panel = document.querySelector(`[ref="panel${panelId}"]`) || 
                document.querySelector(`.panel[data-id="${panelId}"]`) ||
                document.querySelector(`.behavior-analysis-page .panel:nth-of-type(${panelId})`);
  
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
  
  panel.classList.add('resizing');
  
  document.addEventListener('mousemove', handleResize);
  document.addEventListener('mouseup', stopResize);
}

// 处理调整大小
function handleResize(event) {
  if (!resizing.value.active) return;
  
  const { panelId, direction, startX, startY, startWidth, startHeight } = resizing.value;
  
  let newWidth = startWidth;
  let newHeight = startHeight;
  
  // 根据方向计算新尺寸
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
  if (!resizing.value.active) return;
  
  const panel = document.querySelector(`.panel:nth-child(${resizing.value.panelId})`);
  if (panel) {
    panel.classList.remove('resizing');
  }
  
  resizing.value.active = false;
  
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
}

// 格式化时间
function formatTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp.replace(' ', 'T'));
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
}

// 获取图表颜色
function getChartColor(behaviorType) {
  const colorMap = {
    '专注工作': '#4fd1c5',
    '吃东西': '#fc8181',
    '其他': '#b794f4'
  };
  return colorMap[behaviorType] || '#718096';
}

// 获取行为数据
async function fetchBehaviorData() {
  try {
    loading.value = true;
    // 使用模拟数据代替API请求
    setTimeout(() => {
      // 模拟数据
      behaviorData.value = {
        behaviors: [
          {id: 1, type: "专注工作", count: 5, timestamp: "2025-03-28 20:10:00"},
          {id: 2, type: "吃东西", count: 3, timestamp: "2025-03-28 20:12:30"},
          {id: 3, type: "其他", count: 2, timestamp: "2025-03-28 20:15:45"}
        ],
        statistics: {
          total_behaviors: 10,
          unique_behaviors: 3,
          most_frequent: "专注工作"
        }
      };
      loading.value = false;
    }, 1000); // 模拟加载时间
  } catch (error) {
    console.error('获取行为数据出错:', error);
    // 即使出错也使用模拟数据
    setTimeout(() => {
      behaviorData.value = {
        behaviors: [
          {id: 1, type: "专注工作", count: 5, timestamp: "2025-03-28 20:10:00"},
          {id: 2, type: "吃东西", count: 3, timestamp: "2025-03-28 20:12:30"},
          {id: 3, type: "其他", count: 2, timestamp: "2025-03-28 20:15:45"}
        ],
        statistics: {
          total_behaviors: 10,
          unique_behaviors: 3,
          most_frequent: "专注工作"
        }
      };
      loading.value = false;
    }, 1000);
  }
}

onMounted(() => {
  fetchBehaviorData();
  
  // 添加窗口调整大小事件监听器
  window.addEventListener('resize', () => {
    if (resizing.value.active) {
      stopResize();
    }
  });
});

// 在组件卸载时移除事件监听器
onUnmounted(() => {
  window.removeEventListener('resize', stopResize);
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
});
</script>

<style scoped>
.behavior-analysis-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--dark-bg);
  color: var(--text-primary);
  position: relative;
  overflow: hidden;
}

/* 添加赛博朋克风格的背景装饰 */
.behavior-analysis-page::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    linear-gradient(to bottom, rgba(10, 25, 47, 0.8) 0%, rgba(10, 25, 47, 0.9) 100%),
    repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(79, 209, 197, 0.05) 2px, rgba(79, 209, 197, 0.05) 4px);
  z-index: -1;
}

/* 添加网格线背景 */
.behavior-analysis-page::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    linear-gradient(rgba(79, 209, 197, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(79, 209, 197, 0.05) 1px, transparent 1px);
  background-size: 50px 50px;
  z-index: -1;
}

.content-container {
  flex: 1;
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

.page-header {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 30px;
  position: relative;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(79, 209, 197, 0.3);
}

/* 添加装饰线 */
.page-header::after {
  content: "";
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 100px;
  height: 3px;
  background-color: var(--cyber-neon);
  box-shadow: 0 0 10px var(--cyber-neon);
}

.page-header h1 {
  color: var(--cyber-neon);
  font-size: 2rem;
  text-shadow: 0 0 10px rgba(79, 209, 197, 0.5);
  position: relative;
  display: inline-block;
}

/* 添加标题装饰 */
.page-header h1::before {
  content: "// ";
  color: rgba(79, 209, 197, 0.7);
  font-weight: normal;
}

.page-header h1::after {
  content: "";
  position: absolute;
  bottom: -5px;
  left: 0;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, var(--cyber-neon), transparent);
}

.loading-message {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 300px;
  color: var(--text-secondary);
  font-size: 1.2rem;
}

/* 添加加载动画 */
.cyber-spinner {
  width: 50px;
  height: 50px;
  border: 3px solid rgba(79, 209, 197, 0.3);
  border-top: 3px solid var(--cyber-neon);
  border-radius: 50%;
  margin-bottom: 20px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.analysis-container {
  display: flex;
  flex-wrap: wrap;
  gap: 30px;
  justify-content: space-between;
  padding: 20px;
  min-height: calc(100vh - 180px);
}

.panel {
  background-color: rgba(10, 25, 47, 0.7);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 5px;
  box-shadow: 0 0 15px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s ease;
  margin-bottom: 30px;
  min-height: 300px;
}

.panel:hover {
  box-shadow: 0 0 20px rgba(79, 209, 197, 0.2);
  border-color: rgba(79, 209, 197, 0.5);
}

/* 修改面板标题样式，使其更明显作为拖动手柄 */
.panel-title {
  background-color: rgba(10, 25, 47, 0.9);
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
  user-select: none; /* 防止文本选择干扰拖拽 */
  position: relative;
  z-index: 5;
}

/* 添加拖动手柄提示 */
.panel-title::after {
  content: "⋮⋮";
  position: absolute;
  right: 10px;
  opacity: 0.5;
  font-size: 14px;
  transition: opacity 0.3s ease;
}

.panel-title:hover::after {
  opacity: 1;
}

/* 添加面板装饰 */
.cyber-panel::before {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  width: 30px;
  height: 30px;
  border-top: 2px solid var(--cyber-neon);
  border-right: 2px solid var(--cyber-neon);
  opacity: 0.7;
}

.cyber-panel::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 0;
  width: 30px;
  height: 30px;
  border-bottom: 2px solid var(--cyber-neon);
  border-left: 2px solid var(--cyber-neon);
  opacity: 0.7;
}

.stats-content {
  display: flex;
  justify-content: space-around;
  align-items: center;
  flex: 1;
}

.stat-item {
  text-align: center;
  padding: 15px;
  position: relative;
  z-index: 1;
}

/* 添加统计项装饰 */
.stat-item::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(79, 209, 197, 0.05);
  border-radius: 8px;
  z-index: -1;
  transform: scale(0.9);
  transition: all 0.3s ease;
}

.stat-item:hover::before {
  transform: scale(1);
  background: rgba(79, 209, 197, 0.1);
}

.stat-value {
  font-size: 2.5rem;
  font-weight: bold;
  color: var(--cyber-neon);
  margin-bottom: 5px;
  text-shadow: 0 0 10px rgba(79, 209, 197, 0.5);
}

/* 添加数值动画效果 */
.cyber-value {
  position: relative;
  display: inline-block;
}

.cyber-value::after {
  content: "";
  position: absolute;
  bottom: -3px;
  left: 0;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--cyber-neon), transparent);
}

.stat-label {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.highlight {
  color: #fc8181;
  text-shadow: 0 0 10px rgba(252, 129, 129, 0.5);
}

/* 行为列表面板 */
.behavior-list-panel {
  grid-column: 1 / 2;
  grid-row: 2 / 3;
}

.behavior-list {
  overflow-y: auto;
  max-height: 300px;
  scrollbar-width: thin;
  scrollbar-color: var(--cyber-neon) rgba(13, 25, 42, 0.5);
}

/* 自定义滚动条 */
.behavior-list::-webkit-scrollbar {
  width: 6px;
}

.behavior-list::-webkit-scrollbar-track {
  background: rgba(13, 25, 42, 0.5);
}

.behavior-list::-webkit-scrollbar-thumb {
  background-color: var(--cyber-neon);
  border-radius: 3px;
}

.behavior-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  transition: background-color 0.2s ease;
}

.behavior-item:hover {
  background-color: rgba(79, 209, 197, 0.1);
}

/* 添加列表项样式 */
.cyber-list-item {
  position: relative;
  overflow: hidden;
}

.cyber-list-item::before {
  content: ">";
  position: absolute;
  left: 0;
  color: var(--cyber-neon);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.cyber-list-item:hover::before {
  opacity: 1;
}

.behavior-time {
  color: var(--text-secondary);
  font-family: monospace;
}

.behavior-type {
  font-weight: bold;
  color: var(--text-primary);
}

.behavior-count {
  color: var(--cyber-neon);
  background: rgba(79, 209, 197, 0.1);
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.9rem;
}

.no-data {
  text-align: center;
  padding: 30px;
  color: var(--text-secondary);
  font-style: italic;
}

/* 行为趋势图表面板 */
.behavior-chart-panel {
  grid-column: 2 / 3;
  grid-row: 1 / 2;
}

.chart-container {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  position: relative;
}

/* 添加图表网格线 */
.chart-container::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 20px 20px;
  z-index: 0;
}

.cyber-chart {
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  width: 100%;
  height: 200px;
  padding: 10px;
  position: relative;
  z-index: 1;
}

.cyber-chart-bar {
  width: 60px;
  min-height: 20px;
  border-radius: 4px 4px 0 0;
  position: relative;
  transition: height 0.5s ease;
  box-shadow: 0 0 15px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}

/* 添加图表条纹效果 */
.cyber-chart-bar::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.1) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255, 255, 255, 0.1) 50%,
    rgba(255, 255, 255, 0.1) 75%,
    transparent 75%
  );
  background-size: 10px 10px;
  z-index: 1;
}

.cyber-bar-label {
  position: absolute;
  bottom: -25px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.cyber-bar-value {
  position: absolute;
  bottom: -10px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 0.8rem;
  color: var(--cyber-neon);
  text-shadow: 0 0 5px var(--cyber-neon);
}

/* 行为分析面板 */
.behavior-analysis-panel {
  grid-column: 2 / 3;
  grid-row: 2 / 3;
}

.analysis-content {
  padding: 10px;
}

.analysis-summary h3,
.analysis-recommendations h3 {
  color: var(--cyber-neon);
  margin-bottom: 10px;
  font-size: 1.1rem;
}

/* 添加小标题样式 */
.cyber-subtitle {
  position: relative;
  display: inline-block;
  padding-left: 15px;
}

.cyber-subtitle::before {
  content: "//";
  position: absolute;
  left: 0;
  color: var(--cyber-neon);
  opacity: 0.7;
}

.analysis-summary p {
  margin-bottom: 15px;
  line-height: 1.6;
}

/* 添加文本样式 */
.cyber-text {
  position: relative;
  padding-left: 10px;
  border-left: 2px solid rgba(79, 209, 197, 0.3);
}

.cyber-highlight {
  color: #fc8181;
  font-weight: bold;
  text-shadow: 0 0 5px rgba(252, 129, 129, 0.5);
  position: relative;
}

.cyber-highlight::after {
  content: "";
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 100%;
  height: 1px;
  background-color: rgba(252, 129, 129, 0.5);
}

.analysis-recommendations ul {
  padding-left: 20px;
}

.analysis-recommendations li {
  margin-bottom: 8px;
  line-height: 1.6;
}

/* 添加列表样式 */
.cyber-list {
  list-style-type: none;
  padding-left: 5px;
}

.cyber-list .cyber-list-item {
  position: relative;
  padding-left: 20px;
  margin-bottom: 10px;
}

.cyber-list .cyber-list-item::before {
  content: ">";
  position: absolute;
  left: 0;
  color: var(--cyber-neon);
  opacity: 1;
}

/* 添加拖拽相关样式 */
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