<template>
  <div class="keyword-panel-container">
    <div class="panel-header">
      <h3 class="panel-title">
        <i class="fas fa-cloud"></i> 关键词云 (近{{ timeRange }}h)
      </h3>
      <div class="time-controls">
        <select v-model="timeRange" @change="fetchKeywords" class="time-select">
          <option value="6">6小时</option>
          <option value="12">12小时</option>
          <option value="24">24小时</option>
          <option value="48">48小时</option>
          <option value="168">7天</option>
        </select>
        <button @click="fetchKeywords" class="refresh-btn" :disabled="loading" title="手动刷新">
          <i class="fas fa-sync-alt" :class="{ 'fa-spin': loading }"></i>
        </button>
        <button @click="toggleAutoUpdate" class="auto-update-btn" :class="{ active: autoUpdate }" :title="autoUpdate ? '关闭自动更新' : '开启自动更新'">
          <i class="fas" :class="autoUpdate ? 'fa-pause' : 'fa-play'"></i>
        </button>
        <div class="zoom-controls">
          <button @click="zoomOut" class="zoom-btn" title="缩小" :disabled="zoomLevel <= 0.5">
            <i class="fas fa-search-minus"></i>
          </button>
          <span class="zoom-level">{{ Math.round(zoomLevel * 100) }}%</span>
          <button @click="zoomIn" class="zoom-btn" title="放大" :disabled="zoomLevel >= 3">
            <i class="fas fa-search-plus"></i>
          </button>
          <button @click="resetZoom" class="zoom-btn" title="重置缩放">
            <i class="fas fa-expand-arrows-alt"></i>
          </button>
        </div>
      </div>
    </div>
    <div class="keyword-content" ref="keywordContainer">
      <div class="keyword-cloud-wrapper" @wheel="handleWheel">
              <div 
        v-if="keywords && keywords.length > 0" 
        class="keyword-cloud"
        :style="{ 
          transform: `scale(${zoomLevel})`, 
          transformOrigin: 'center center',
          gap: `${Math.max(2, 6 * zoomLevel)}px`
        }"
        ref="keywordCloudContainer"
      >
          <div
            v-for="keyword in keywords"
            :key="keyword.text"
            class="keyword-item"
            :style="getKeywordStyle(keyword)"
            :title="`${keyword.text}\n出现次数: ${keyword.count}`"
            @click="searchKeyword(keyword.text)"
          >
            {{ keyword.text }}
          </div>
        </div>
        <div v-else-if="loading" class="loading">
          <i class="fas fa-spinner fa-spin"></i>
          正在加载关键词...
        </div>
        <div v-else class="no-data">
          暂无关键词数据
        </div>
      </div>
      <div v-if="keywordStats" class="keyword-stats">
        <span class="stat-item">数据源: {{ keywordStats.records_count }}条</span>
        <span class="stat-item">总词汇: {{ keywordStats.unique_words }}</span>
        <span class="stat-item">文本长度: {{ formatTextLength(keywordStats.total_text_length) }}</span>
        <span class="stat-item">缩放: {{ Math.round(zoomLevel * 100) }}%</span>
        <span class="stat-item">最后更新: {{ lastUpdateTime }}</span>
        <span v-if="autoUpdate" class="stat-item auto-update-indicator">
          <i class="fas fa-circle"></i> 自动更新中
        </span>
      </div>
    </div>
    <!-- Resize Handles -->
    <div
      class="resize-handle resize-e"
      @mousedown="$emit('start-resize', $event, 'e')"
    ></div>
    <div
      class="resize-handle resize-s"
      @mousedown="$emit('start-resize', $event, 's')"
    ></div>
    <div
      class="resize-handle resize-se"
      @mousedown="$emit('start-resize', $event, 'se')"
    ></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, defineEmits } from 'vue';

defineEmits(['start-resize']);

const keywords = ref([]);
const keywordStats = ref(null);
const loading = ref(true);
const timeRange = ref(24);
const keywordContainer = ref(null);
const autoUpdate = ref(false);
const lastUpdateTime = ref('');
const zoomLevel = ref(1);
const keywordCloudContainer = ref(null);
let autoUpdateInterval = null;

const API_BASE_URL = 'http://localhost:5001';

// 获取关键词数据
const fetchKeywords = async () => {
  loading.value = true;
  try {
    const response = await fetch(`${API_BASE_URL}/api/keywords?hours=${timeRange.value}&limit=1000`);
    const data = await response.json();
    
    if (data.error) {
      console.error('获取关键词失败:', data.error);
      keywords.value = [];
      keywordStats.value = null;
    } else {
      keywords.value = data.keywords || [];
      keywordStats.value = {
        unique_words: data.unique_words || 0,
        total_text_length: data.total_text_length || 0,
        records_count: data.records_count || 0
      };
      // 更新最后更新时间
      lastUpdateTime.value = new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    }
  } catch (error) {
    console.error('请求关键词数据失败:', error);
    keywords.value = [];
    keywordStats.value = null;
  } finally {
    loading.value = false;
  }
};

// 切换自动更新
const toggleAutoUpdate = () => {
  autoUpdate.value = !autoUpdate.value;
  
  if (autoUpdate.value) {
    // 开启自动更新，每3分钟更新一次
    autoUpdateInterval = setInterval(fetchKeywords, 3 * 60 * 1000);
    console.log('关键词云自动更新已开启（每3分钟）');
  } else {
    // 关闭自动更新
    if (autoUpdateInterval) {
      clearInterval(autoUpdateInterval);
      autoUpdateInterval = null;
    }
    console.log('关键词云自动更新已关闭');
  }
};

// 生成关键词样式
const getKeywordStyle = (keyword) => {
  const colors = [
    '#4fd1c5', '#63b3ed', '#f687b3', '#68d391', '#fbb6ce',
    '#9f7aea', '#f6ad55', '#fc8181', '#4299e1', '#48bb78',
    '#ed8936', '#38b2ac', '#667eea', '#f56565', '#38a169'
  ];
  
  const color = colors[Math.abs(keyword.text.split('').reduce((a, b) => a + b.charCodeAt(0), 0)) % colors.length];
  
  // 基于词频计算字体大小，范围10-24px，更紧凑
  const fontSize = Math.max(10, Math.min(24, 10 + keyword.count * 0.8));
  
  // 减少随机旋转和位置偏移，让排列更紧密
  const rotation = (Math.random() - 0.5) * 8; // -4到4度，更小的旋转
  const xOffset = (Math.random() - 0.5) * 6; // 更小的位置偏移
  const yOffset = (Math.random() - 0.5) * 6;
  
  return {
    fontSize: `${fontSize}px`,
    color: color,
    textShadow: `0 0 8px ${color}40`,
    transform: `rotate(${rotation}deg) translate(${xOffset}px, ${yOffset}px)`,
    fontWeight: keyword.count > 5 ? 'bold' : 'normal',
    lineHeight: '1.2'
  };
};

// 搜索关键词
const searchKeyword = (keyword) => {
  // 这里可以集成搜索功能，暂时使用console.log
  console.log('搜索关键词:', keyword);
  // 可以发送事件到父组件进行搜索
};

// 格式化文本长度
const formatTextLength = (length) => {
  if (length < 1000) return `${length}字符`;
  if (length < 1000000) return `${(length / 1000).toFixed(1)}K字符`;
  return `${(length / 1000000).toFixed(1)}M字符`;
};

// 缩放功能
const zoomIn = () => {
  if (zoomLevel.value < 3) {
    zoomLevel.value = Math.min(3, zoomLevel.value + 0.2);
  }
};

const zoomOut = () => {
  if (zoomLevel.value > 0.5) {
    zoomLevel.value = Math.max(0.5, zoomLevel.value - 0.2);
  }
};

const resetZoom = () => {
  zoomLevel.value = 1;
};

// 鼠标滚轮缩放
const handleWheel = (event) => {
  event.preventDefault();
  
  const delta = event.deltaY > 0 ? -0.1 : 0.1;
  const newZoom = zoomLevel.value + delta;
  
  if (newZoom >= 0.5 && newZoom <= 3) {
    zoomLevel.value = newZoom;
  }
};

// 键盘快捷键处理
const handleKeydown = (event) => {
  if (event.ctrlKey || event.metaKey) {
    if (event.key === '=' || event.key === '+') {
      event.preventDefault();
      zoomIn();
    } else if (event.key === '-') {
      event.preventDefault();
      zoomOut();
    } else if (event.key === '0') {
      event.preventDefault();
      resetZoom();
    }
  }
};

onMounted(() => {
  fetchKeywords();
  // 添加键盘事件监听
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  // 清理定时器
  if (autoUpdateInterval) {
    clearInterval(autoUpdateInterval);
    autoUpdateInterval = null;
  }
  // 移除键盘事件监听
  document.removeEventListener('keydown', handleKeydown);
});
</script>

<style scoped>
.keyword-panel-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 15px 20px;
  box-sizing: border-box;
  position: relative;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  flex-shrink: 0;
}

.panel-title {
  font-size: 1.3rem;
  color: var(--cyber-neon);
  margin: 0;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.7);
  cursor: move;
  user-select: none;
}

.panel-title i {
  margin-right: 10px;
}

.time-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.time-select {
  background: rgba(13, 25, 42, 0.8);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 6px;
  color: var(--cyber-neon);
  padding: 4px 8px;
  font-size: 0.85rem;
  outline: none;
  cursor: pointer;
}

.time-select:hover {
  border-color: rgba(79, 209, 197, 0.6);
  box-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
}

.refresh-btn, .auto-update-btn {
  background: rgba(13, 25, 42, 0.8);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 6px;
  color: var(--cyber-neon);
  padding: 6px 8px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 30px;
}

.refresh-btn:hover, .auto-update-btn:hover {
  border-color: rgba(79, 209, 197, 0.6);
  box-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
  transform: translateY(-1px);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.auto-update-btn.active {
  background: rgba(79, 209, 197, 0.2);
  border-color: rgba(79, 209, 197, 0.8);
  box-shadow: 0 0 8px rgba(79, 209, 197, 0.4);
}

.auto-update-btn.active:hover {
  background: rgba(79, 209, 197, 0.3);
}

.zoom-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: 8px;
  border-left: 1px solid rgba(79, 209, 197, 0.3);
  padding-left: 8px;
}

.zoom-btn {
  background: rgba(13, 25, 42, 0.8);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 4px;
  color: var(--cyber-neon);
  padding: 4px 6px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
}

.zoom-btn:hover:not(:disabled) {
  border-color: rgba(79, 209, 197, 0.6);
  box-shadow: 0 0 3px rgba(79, 209, 197, 0.3);
  transform: translateY(-1px);
}

.zoom-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

.zoom-level {
  color: rgba(79, 209, 197, 0.8);
  font-size: 0.75rem;
  min-width: 35px;
  text-align: center;
  font-weight: bold;
}



.keyword-cloud {
  flex-grow: 1;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: flex-start;
  align-content: flex-start;
  gap: 6px;
  padding: 15px;
  transition: transform 0.3s ease;
  min-height: 100%;
  line-height: 1.2;
}

.keyword-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: transparent;
  border-radius: 0 0 12px 12px;
  position: relative;
}

.keyword-cloud-wrapper {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.keyword-cloud-wrapper:hover {
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(79, 209, 197, 0.5) transparent;
}

.keyword-cloud-wrapper:hover::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.keyword-cloud-wrapper:hover::-webkit-scrollbar-track {
  background: transparent;
}

.keyword-cloud-wrapper:hover::-webkit-scrollbar-thumb {
  background: rgba(79, 209, 197, 0.5);
  border-radius: 3px;
}

.keyword-cloud-wrapper:hover::-webkit-scrollbar-thumb:hover {
  background: rgba(79, 209, 197, 0.7);
}



.keyword-item {
  display: inline-block;
  padding: 3px 6px;
  margin: 1px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(79, 209, 197, 0.2);
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
  user-select: none;
  animation: fadeInUp 0.6s ease forwards;
  animation-delay: calc(var(--index, 0) * 0.05s);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.keyword-item:hover {
  transform: scale(1.1) !important;
  background: rgba(255, 255, 255, 0.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 10;
}

.loading {
  flex-grow: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: column;
  color: var(--text-secondary);
  font-size: 1.1rem;
}

.loading i {
  margin-bottom: 10px;
  font-size: 1.5rem;
  color: var(--cyber-neon);
}

.no-data {
  flex-grow: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  color: var(--text-secondary);
  font-style: italic;
  font-size: 1.1rem;
}

.keyword-stats {
  display: flex;
  justify-content: center;
  gap: 20px;
  padding: 10px 0;
  border-top: 1px solid rgba(79, 209, 197, 0.3);
  margin-top: 10px;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
  background: linear-gradient(135deg, rgba(13, 25, 42, 0.95), rgba(7, 15, 25, 0.95));
  backdrop-filter: blur(10px);
  border-radius: 0 0 12px 12px;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.3);
}

.stat-item {
  font-size: 0.8rem;
  color: rgba(79, 209, 197, 0.9);
  display: flex;
  align-items: center;
  text-shadow: 0 0 3px rgba(79, 209, 197, 0.5);
  font-weight: 500;
}

.auto-update-indicator {
  color: #4CAF50 !important;
  animation: pulse 2s infinite;
}

.auto-update-indicator i {
  font-size: 0.6rem;
  margin-right: 4px;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Resize handle styles */
.resize-handle {
  position: absolute;
  background-color: rgba(79, 209, 197, 0.2);
  z-index: 10;
}

.resize-handle:hover {
  background-color: rgba(79, 209, 197, 0.5);
}

.resize-e { 
  display: none; 
}

.resize-s {
  bottom: 0; 
  left: 0; 
  width: 100%; 
  height: 8px; 
  cursor: s-resize;
}

.resize-se {
  bottom: 0; 
  right: 0; 
  width: 15px; 
  height: 15px; 
  cursor: se-resize; 
  border-radius: 0 0 8px 0;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .keyword-cloud {
    gap: 3px;
    padding: 8px;
  }
  
  .keyword-item {
    font-size: 0.75rem !important;
    padding: 2px 4px;
    margin: 0.5px;
  }
  
  .keyword-stats {
    flex-direction: column;
    gap: 5px;
    padding: 8px 0;
  }
  
  .stat-item {
    font-size: 0.75rem;
  }
}

/* 缩放级别优化 */
.keyword-cloud[style*="scale(0.5)"] .keyword-item,
.keyword-cloud[style*="scale(0.6)"] .keyword-item,
.keyword-cloud[style*="scale(0.7)"] .keyword-item {
  margin: 0px;
  padding: 2px 4px;
}

.keyword-cloud[style*="scale(0.8)"] .keyword-item,
.keyword-cloud[style*="scale(0.9)"] .keyword-item {
  margin: 1px;
  padding: 2px 5px;
}
</style> 