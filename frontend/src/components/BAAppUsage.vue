<template>
  <div class="app-usage-panel-container">
    <div class="panel-header">
      <h3 class="panel-title">
        <i class="fas fa-chart-pie"></i> 屏幕使用时长
      </h3>
      <div class="period-selector">
        <button
          v-for="p in periods"
          :key="p.value"
          :class="{ active: p.value === selectedPeriod }"
          @click="changePeriod(p.value)"
        >
          {{ p.label }}
        </button>
      </div>
    </div>
    <div class="usage-content">
      <div v-if="loading" class="loading-state">
        <div class="cyber-spinner"></div>
        <p>加载数据中...</p>
      </div>
      <div v-if="error" class="error-state">
        <p>错误: {{ error }}</p>
        <button @click="fetchUsageData">重试</button>
      </div>
      <div v-if="!loading && !error && usageData" class="data-display">
        <!-- 总使用时长概览 -->
        <div class="total-usage-summary">
            <span class="total-label">总使用时长</span>
            <span class="total-value">{{ usageData.total_usage_str }}</span>
        </div>

        <!-- 应用使用时长列表 -->
        <div class="app-list-container">
          <div v-if="usageData.app_specific_usage.length > 0" class="app-list">
            <div
              v-for="app in usageData.app_specific_usage"
              :key="app.app_name"
              class="app-item"
              @click="showAppSummary(app)"
            >
              <div class="app-info">
                <span class="app-name">{{ app.app_name }}</span>
                <span class="app-duration">{{ app.duration_str }}</span>
              </div>
              <div class="usage-bar-container">
                <div
                  class="usage-bar"
                  :style="{ width: `${(app.duration_seconds / maxDuration) * 100}%` }"
                ></div>
              </div>
              <div class="click-hint">点击查看使用总结</div>
            </div>
          </div>
          <div v-else class="no-data-state">
            <p>该时段内无应用使用记录</p>
          </div>
        </div>
      </div>
    </div>
     <div class="resize-handle resize-s" @mousedown.stop="e => emit('start-resize', e, 's')"></div>
     <div class="resize-handle resize-n" @mousedown.stop="e => emit('start-resize', e, 'n')"></div>

    <!-- 应用使用总结模态框（Teleport 到 body，避免父容器裁剪） -->
    <teleport to="body">
      <div v-if="showModal" class="app-summary-modal" @mousedown.self="closeModal">
        <div class="modal-content">
         <div class="modal-header">
           <div class="modal-title">
             <i class="fas fa-chart-bar"></i>
             <span>{{ selectedApp?.app_name }} 使用总结</span>
           </div>
           <button class="close-button" @click="closeModal">
             <i class="fas fa-times"></i>
           </button>
         </div>

          <div class="modal-body" ref="modalBodyRef">
           <div v-if="summaryLoading" class="loading-summary">
             <div class="cyber-spinner"></div>
             <p>正在分析 {{ selectedApp?.app_name }} 的使用情况...</p>
             <div class="loading-steps">
               <div class="step" :class="{ active: currentStep >= 1 }">
                 <span class="step-icon">🔍</span>
                 <span>检索活动记录</span>
               </div>
               <div class="step" :class="{ active: currentStep >= 2 }">
                 <span class="step-icon">🧠</span>
                 <span>AI智能分析</span>
               </div>
               <div class="step" :class="{ active: currentStep >= 3 }">
                 <span class="step-icon">📊</span>
                 <span>生成使用总结</span>
               </div>
             </div>
           </div>

           <div v-if="summaryError" class="error-summary">
             <i class="fas fa-exclamation-triangle"></i>
             <p>{{ summaryError }}</p>
             <button @click="generateSummary" class="retry-button">重试</button>
           </div>

           <div v-if="!summaryLoading && !summaryError && summaryData" class="summary-content">
             <div class="summary-stats">
               <div class="stat-item">
                 <span class="stat-label">使用时长</span>
                 <span class="stat-value">{{ selectedApp?.duration_str }}</span>
               </div>
               <div class="stat-item">
                 <span class="stat-label">使用期间</span>
                 <span class="stat-value">{{ getPeriodLabel(selectedPeriod) }}</span>
               </div>
             </div>

             <div class="summary-text">
               <h4>🔍 使用分析</h4>
               <div class="summary-markdown" v-html="renderSummary(summaryData.summary)"></div>
             </div>

             <div v-if="summaryData.key_activities && summaryData.key_activities.length > 0" class="key-activities">
               <h4>📋 主要活动</h4>
               <div class="activity-list">
                 <div v-for="activity in summaryData.key_activities" :key="activity.id" class="activity-item">
                   <div class="activity-time">{{ formatTime(activity.timestamp) }}</div>
                   <div class="activity-desc">{{ activity.description }}</div>
                 </div>
               </div>
             </div>
           </div>
         </div>

         <div class="modal-footer">
           <button @click="closeModal" class="modal-button secondary">关闭</button>
           <button v-if="!summaryLoading && summaryData" @click="generateSummary" class="modal-button primary">
             <i class="fas fa-refresh"></i>
             重新分析
           </button>
         </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from 'vue';
import mermaid from 'mermaid';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

const emit = defineEmits(['start-resize']);

const loading = ref(true);
const error = ref(null);
const usageData = ref(null);

// 模态框相关状态
const showModal = ref(false);
const selectedApp = ref(null);
const summaryLoading = ref(false);
const summaryError = ref(null);
const summaryData = ref(null);
const currentStep = ref(0);
const modalBodyRef = ref(null);

const selectedPeriod = ref('today');
const periods = [
  { label: '今天', value: 'today' },
  { label: '昨天', value: 'yesterday' },
  { label: '本周', value: 'this_week' },
  { label: '本月', value: 'this_month' },
];

const maxDuration = computed(() => {
  if (usageData.value?.app_specific_usage?.length > 0) {
    // The list is sorted descending by the backend, so the first item has the max duration.
    return usageData.value.app_specific_usage[0].duration_seconds;
  }
  return 1; // Return 1 instead of 0 to avoid division by zero errors
});

const getUsageBarWidth = (durationSeconds) => {
  if (maxDuration.value === 0) {
    return '0%';
  }
  const percentage = (durationSeconds / maxDuration.value) * 100;
  return `${percentage}%`;
};

const fetchUsageData = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(`http://localhost:5001/api/usage_stats?period=${selectedPeriod.value}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    usageData.value = data;
  } catch (e) {
    console.error("Failed to fetch usage data:", e);
    error.value = e.message;
  } finally {
    loading.value = false;
  }
};

const changePeriod = (period) => {
  selectedPeriod.value = period;
  fetchUsageData();
};

// 显示应用总结模态框
const showAppSummary = (app) => {
  selectedApp.value = app;
  showModal.value = true;
  summaryData.value = null;
  summaryError.value = null;
  generateSummary();
};

// 关闭模态框
const closeModal = () => {
  showModal.value = false;
  selectedApp.value = null;
  summaryData.value = null;
  summaryError.value = null;
  currentStep.value = 0;
};

// 生成应用使用总结
const generateSummary = async () => {
  if (!selectedApp.value) return;

  summaryLoading.value = true;
  summaryError.value = null;
  currentStep.value = 0;

  try {
    // 第一步：检索活动记录
    currentStep.value = 1;
    await new Promise(resolve => setTimeout(resolve, 800)); // 模拟步骤延迟

    // 第二步：AI智能分析
    currentStep.value = 2;
    await new Promise(resolve => setTimeout(resolve, 500));

    // 第三步：生成使用总结
    currentStep.value = 3;

    const response = await fetch('http://localhost:5001/api/app_usage_summary', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        app_name: selectedApp.value.app_name,
        period: selectedPeriod.value,
        duration_seconds: selectedApp.value.duration_seconds
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    summaryData.value = data;

  } catch (e) {
    console.error("Failed to generate app summary:", e);
    summaryError.value = e.message || '生成总结失败，请重试';
  } finally {
    summaryLoading.value = false;
  }
};

// 获取期间标签
const getPeriodLabel = (period) => {
  const periodMap = {
    'today': '今天',
    'yesterday': '昨天',
    'this_week': '本周',
    'this_month': '本月'
  };
  return periodMap[period] || period;
};

// 渲染Markdown总结（含mermaid预处理）
const renderSummary = (text) => {
  if (!text) return '';

  // 预清洗：去掉可能包裹整段内容的代码围栏，以及将长破折号当作项目符号处理
  let cleaned = String(text)
    // 将非围栏 mermaid 代码块规范化为围栏形式（直到空行或文本末尾）
    .replace(/(^|\n)\s*mermaid\s*\n([\s\S]+?)(?=\n{2,}|$)/g, (m, p1, code) => `${p1}\n\n\
\`\`\`mermaid\n${code.trim()}\n\`\`\``)
    // 去掉三引号代码块围栏，保留其中的文本
    // 注意：保留 mermaid 围栏
    .replace(/```(?!mermaid)[^\n]*\n([\s\S]*?)```/g, '$1')
    // 处理偶发的单行代码围栏
    .replace(/```([\s\S]*?)```/g, '$1')
    // 将中文/长破折号开头的列表项规范为 Markdown 列表
    .replace(/^[\u2013\u2014]\s+/gm, '- ')
    // 统一全角井号为半角
    .replace(/[＃]+/g, '#')
    // 统一换行为 \n
    .replace(/\r\n/g, '\n');

  // 如果整段是 <pre><code> 包裹的代码块，直接提取其中内容
  const preCodeWholeDoc = cleaned.match(/^\s*<pre[^>]*>\s*<code[^>]*>([\s\S]*?)<\/code>\s*<\/pre>\s*$/i);
  if (preCodeWholeDoc) {
    cleaned = preCodeWholeDoc[1];
  }
  // 如果存在单独的 <code class="language-markdown"> 包裹，也尝试解包
  const codeMarkdownWholeDoc = cleaned.match(/^\s*<code[^>]*language-markdown[^>]*>([\s\S]*?)<\/code>\s*$/i);
  if (codeMarkdownWholeDoc) {
    cleaned = codeMarkdownWholeDoc[1];
  }

  try {
    // 配置marked选项
    marked.setOptions({
      breaks: true,        // 支持GitHub风格的换行
      gfm: true,           // 启用GitHub风格的Markdown
      headerIds: false,    // 不生成header id
      mangle: false        // 不混淆邮箱地址
    });

    // 解析并清理HTML
    const parsedHtml = marked.parse(cleaned);
    return DOMPurify.sanitize(parsedHtml);
  } catch (e) {
    console.error('Markdown渲染错误:', e);
    // 回退：尽量用基本规则把Markdown转成HTML
    const fallback = cleaned
      .replace(/^#{1,6}\s+/gm, '')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
    return DOMPurify.sanitize(fallback);
  }
};

// 在模态渲染后把 mermaid 代码块转为图
function initMermaidInModal() {
  const root = modalBodyRef.value;
  if (!root) return;
  try {
    // 将 <pre><code class="language-mermaid">...</code></pre> 转换为 <div class="mermaid">...</div>
    const codeBlocks = root.querySelectorAll('pre code.language-mermaid, code.language-mermaid');
    codeBlocks.forEach(codeEl => {
      const code = codeEl.textContent || '';
      const container = document.createElement('div');
      container.className = 'mermaid';
      container.textContent = code;
      const pre = codeEl.closest('pre') || codeEl;
      pre.replaceWith(container);
    });
    mermaid.initialize({ startOnLoad: false, theme: 'dark' });
    mermaid.init(undefined, root.querySelectorAll('.mermaid'));
  } catch (e) {
    console.warn('Mermaid 渲染失败:', e);
  }
}

watch([summaryData, () => showModal.value], async ([data, visible]) => {
  if (visible && data) {
    await nextTick();
    initMermaidInModal();
  }
});

// 格式化时间
const formatTime = (timestamp) => {
  try {
    return new Date(timestamp).toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return timestamp;
  }
};

onMounted(() => {
  fetchUsageData();
});

// 键盘Esc关闭模态框
const handleKeydown = (e) => {
  if (e.key === 'Escape' && showModal.value) {
    closeModal();
  }
};

onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
});

</script>

<style scoped>
.app-usage-panel-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  color: var(--text-primary);
  padding: 15px 20px;
  overflow: visible; /* 允许可视元素浮出（模态使用 teleport 但保守起见仍放开） */
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
}
.panel-title i {
    margin-right: 10px;
}

.period-selector {
  display: flex;
  gap: 5px;
  background: rgba(0,0,0,0.2);
  padding: 4px;
  border-radius: 6px;
}

.period-selector button {
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.period-selector button.active,
.period-selector button:hover {
  background-color: var(--cyber-neon-bg);
  color: var(--cyber-neon);
  text-shadow: 0 0 3px var(--cyber-neon);
}

.usage-content {
  flex-grow: 1;
  overflow: hidden; /* 确保内容区本身可以滚动 */
  display: flex;
  flex-direction: column;
}

.loading-state, .error-state, .no-data-state {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: var(--text-secondary);
}

.data-display {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.total-usage-summary {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 10px 15px;
  background: rgba(79, 209, 197, 0.1);
  border-radius: 6px;
  margin-bottom: 15px;
  flex-shrink: 0;
}

.total-label {
  font-size: 1rem;
  color: var(--text-secondary);
}

.total-value {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--cyber-neon);
}


.app-list-container {
  flex-grow: 1;
  overflow-y: auto;
  padding-right: 5px;
}

.app-list-container::-webkit-scrollbar {
  width: 8px;
}
.app-list-container::-webkit-scrollbar-track {
  background: transparent; /* 隐藏轨道 */
}
.app-list-container::-webkit-scrollbar-thumb {
  background: rgba(79, 209, 197, 0.5);
  border-radius: 4px;
}

.app-list {
  display: flex;
  flex-direction: column;
  gap: 8px; /* 增加间距 */
}

.app-item {
  display: flex;
  flex-direction: column;
  gap: 8px; /* 内部间距 */
  padding: 12px 15px;
  /* 与总时长摘要样式对齐 */
  background: rgba(79, 209, 197, 0.1);
  border-radius: 6px;
  transition: all 0.3s ease;
  border: none; /* 移除之前的边框 */
  cursor: pointer; /* 添加点击光标 */
  position: relative;
}

.app-item:hover {
  background: rgba(79, 209, 197, 0.2); /* 调整hover效果 */
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(79, 209, 197, 0.1);
}

.app-item:hover .click-hint {
  opacity: 1;
  transform: translateY(0);
}

.click-hint {
  position: absolute;
  top: 50%;
  right: 15px;
  transform: translateY(-50%) translateY(5px);
  background: rgba(79, 209, 197, 0.9);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  opacity: 0;
  transition: all 0.3s ease;
  pointer-events: none;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(79, 209, 197, 0.3);
}

.app-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1rem;
}

.app-name {
  color: var(--text-primary);
  font-weight: 500;
  letter-spacing: 1px;
}

.app-duration {
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-family: 'orbitron', sans-serif; /* 使用科技感字体 */
}

.usage-bar-container {
  width: 100%;
  height: 12px; /* 增加高度以容纳更复杂的效果 */
  background-color: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  overflow: hidden;
  position: relative; /* 用于动画定位 */
  border: 1px solid rgba(79, 209, 197, 0.2);
  /* 添加网格背景 */
  background-image: repeating-linear-gradient(
    45deg,
    rgba(255, 255, 255, 0.05),
    rgba(255, 255, 255, 0.05) 2px,
    transparent 2px,
    transparent 6px
  );
}

.usage-bar {
  height: 100%;
  background:
    linear-gradient(90deg,
      rgba(34, 211, 167, 0.7) 0%,
      rgba(79, 209, 197, 1) 90%,
      #fff 100%
    );
  border-radius: 6px;
  transition: width 0.8s cubic-bezier(0.25, 1, 0.5, 1); /* 更平滑的动画 */
  box-shadow:
    0 0 10px rgba(79, 209, 197, 0.8),
    inset 0 0 4px rgba(34, 211, 167, 0.5); /* 辉光和内发光 */
  position: relative;
  overflow: hidden; /* 隐藏扫描动画的溢出部分 */
}

/* 扫描动画 */
.usage-bar::after {
  content: '';
  position: absolute;
  top: 0;
  left: -50%;
  width: 50%;
  height: 100%;
  background: linear-gradient(
    to right,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.3) 50%,
    rgba(255, 255, 255, 0) 100%
  );
  transform: skewX(-25deg);
  animation: scan 3s linear infinite;
}

@keyframes scan {
  0% {
    left: -50%;
  }
  100% {
    left: 120%;
  }
}

.resize-handle {
  position: absolute;
  opacity: 0;
  transition: opacity 0.3s;
}
.resize-handle:hover {
  opacity: 1;
}
.resize-s {
  bottom: 0;
  left: 0;
  width: 100%;
  height: 10px;
  cursor: ns-resize;
  background: linear-gradient(to top, rgba(79, 209, 197, 0.3), transparent);
}
.resize-n {
  top: 0;
  left: 0;
  width: 100%;
  height: 10px;
  cursor: ns-resize;
  background: linear-gradient(to bottom, rgba(79, 209, 197, 0.3), transparent);
}

/* 应用使用总结模态框样式 */
.app-summary-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(5px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  animation: modalFadeIn 0.3s ease;
}

@keyframes modalFadeIn {
  from {
    opacity: 0;
    backdrop-filter: blur(0px);
  }
  to {
    opacity: 1;
    backdrop-filter: blur(5px);
  }
}

.modal-content {
  background: linear-gradient(145deg,
    rgba(16, 45, 80, 0.95),
    rgba(24, 56, 102, 0.95));
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 12px;
  width: min(92vw, 800px); /* 更宽一点，且适配窗口宽度 */
  max-height: 90vh; /* 进一步增加容器可见高度 */
  overflow: hidden;
  box-shadow:
    0 20px 40px rgba(0, 0, 0, 0.5),
    0 0 30px rgba(79, 209, 197, 0.2);
  animation: modalSlideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
}

@keyframes modalSlideIn {
  from {
    opacity: 0;
    transform: translateY(-30px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.modal-content::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg,
    transparent,
    rgba(79, 209, 197, 0.8),
    transparent);
  animation: modalGlow 3s infinite;
}

@keyframes modalGlow {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 22px; /* 适度压缩头部内边距 */
  border-bottom: 1px solid rgba(79, 209, 197, 0.2);
  background: rgba(79, 209, 197, 0.05);
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.3rem;
  font-weight: 600;
  color: var(--cyber-neon);
  text-shadow: 0 0 8px rgba(79, 209, 197, 0.5);
}

.modal-title i {
  font-size: 1.2rem;
}

.close-button {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 1.2rem;
  cursor: pointer;
  padding: 5px;
  border-radius: 4px;
  transition: all 0.3s ease;
}

.close-button:hover {
  color: rgba(255, 77, 77, 0.8);
  background: rgba(255, 77, 77, 0.1);
}

.modal-body {
  padding: 18px 22px; /* 略微减小内边距，释放可视高度 */
  max-height: 65vh; /* 提升可视区高度 */
  overflow-y: auto;
  overflow-x: hidden; /* 禁用横向滚动条，避免遮挡 */
  text-align: left;
}

.modal-body::-webkit-scrollbar {
  width: 6px;
}

.modal-body::-webkit-scrollbar-track {
  background: transparent;
}

.modal-body::-webkit-scrollbar-thumb {
  background: rgba(79, 209, 197, 0.4);
  border-radius: 3px;
}

.loading-summary {
  text-align: center;
  padding: 40px 20px;
}

.cyber-spinner {
  width: 50px;
  height: 50px;
  border: 3px solid rgba(79, 209, 197, 0.2);
  border-top: 3px solid var(--cyber-neon);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-summary p {
  color: var(--text-secondary);
  margin-bottom: 25px;
  font-size: 1.1rem;
}

.loading-steps {
  display: flex;
  justify-content: center;
  gap: 30px;
  margin-top: 20px;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  opacity: 0.4;
  transition: all 0.5s ease;
}

.step.active {
  opacity: 1;
  transform: scale(1.1);
}

.step-icon {
  font-size: 1.5rem;
  margin-bottom: 5px;
}

.step span:last-child {
  font-size: 0.9rem;
  color: var(--text-secondary);
  text-align: center;
}

.error-summary {
  text-align: center;
  padding: 40px 20px;
  color: rgba(255, 77, 77, 0.9);
}

.error-summary i {
  font-size: 2rem;
  margin-bottom: 15px;
  display: block;
}

.error-summary p {
  text-align: left;
  margin: 0 auto;
  word-wrap: break-word;
}

.retry-button {
  background: linear-gradient(135deg,
    rgba(255, 77, 77, 0.2),
    rgba(255, 77, 77, 0.3));
  border: 1px solid rgba(255, 77, 77, 0.4);
  color: rgba(255, 77, 77, 0.9);
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  margin-top: 15px;
  transition: all 0.3s ease;
}

.retry-button:hover {
  background: linear-gradient(135deg,
    rgba(255, 77, 77, 0.3),
    rgba(255, 77, 77, 0.4));
  transform: translateY(-1px);
}

.summary-content {
  animation: contentFadeIn 0.5s ease;
}

@keyframes contentFadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.summary-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  margin: 0 0 18px 0; /* 减少与下文间距，避免上下遮挡 */
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: rgba(79, 209, 197, 0.1);
  border-radius: 8px;
  border: 1px solid rgba(79, 209, 197, 0.2);
}

.stat-label {
  font-size: 0.9rem;
  color: var(--text-secondary);
  text-align: left;
}

.stat-value {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--cyber-neon);
  text-align: left;
  word-wrap: break-word;
}

.summary-text {
  margin-bottom: 25px;
}

.summary-text h4 {
  color: var(--cyber-neon);
  margin-bottom: 15px;
  font-size: 1.1rem;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
}

.summary-markdown {
  color: var(--text-primary);
  line-height: 1.6;
  font-size: 0.95rem;
  text-align: left;
  word-wrap: break-word;      /* 老浏览器兼容 */
  overflow-wrap: anywhere;    /* 优先 anywhere，避免出现水平滚动条 */
  word-break: break-word;     /* 防止长英文/URL撑破容器 */
}

/* Mermaid 图容器自适应 */
.summary-markdown :deep(.mermaid) {
  display: block;
  width: 100%;
  overflow: hidden;
}

.summary-markdown :deep(h1),
.summary-markdown :deep(h2),
.summary-markdown :deep(h3),
.summary-markdown :deep(h4),
.summary-markdown :deep(h5),
.summary-markdown :deep(h6) {
  color: var(--cyber-neon);
  margin: 12px 0 8px 0;
  text-align: left;
  font-weight: 600;
}

.summary-markdown :deep(h1) { font-size: 1.3em; }
.summary-markdown :deep(h2) { font-size: 1.2em; }
.summary-markdown :deep(h3) { font-size: 1.1em; }
.summary-markdown :deep(h4) { font-size: 1.05em; }
.summary-markdown :deep(h5) { font-size: 1em; }
.summary-markdown :deep(h6) { font-size: 0.95em; }

.summary-markdown :deep(p) {
  margin-bottom: 12px;
  text-align: left;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.summary-markdown :deep(ul),
.summary-markdown :deep(ol) {
  margin-left: 20px;
  margin-bottom: 12px;
  text-align: left;
}

.summary-markdown :deep(li) {
  margin-bottom: 6px;
  text-align: left;
  word-wrap: break-word;
}

.summary-markdown :deep(strong) {
  color: var(--cyber-neon);
  font-weight: 600;
}

.summary-markdown :deep(em) {
  color: rgba(230, 241, 255, 0.8);
  font-style: italic;
}

.summary-markdown :deep(code) {
  background: rgba(79, 209, 197, 0.1);
  color: var(--cyber-neon);
  padding: 2px 4px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 0.9em;
}

.summary-markdown :deep(pre) {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(79, 209, 197, 0.2);
  border-radius: 4px;
  padding: 12px;
  margin: 12px 0;
  overflow-x: hidden;  /* 禁用横向滚动条 */
  white-space: pre-wrap; /* 代码块也自动换行 */
  word-break: break-word;
}

/* 某些LLM会把markdown包裹为 <code class="language-markdown"> 整段返回，这里把它当普通文本处理 */
.summary-markdown :deep(code.language-markdown) {
  background: transparent;
  color: inherit;
  font-family: inherit;
  font-size: inherit;
  padding: 0;
  border: 0;
  white-space: pre-wrap;
}

.summary-markdown :deep(blockquote) {
  border-left: 3px solid var(--cyber-neon);
  margin: 12px 0;
  padding-left: 12px;
  color: rgba(230, 241, 255, 0.8);
  font-style: italic;
}

.key-activities {
  margin-bottom: 15px;
}

.key-activities h4 {
  color: var(--cyber-neon);
  margin-bottom: 15px;
  font-size: 1.1rem;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 240px; /* 略微提高列表高度 */
  overflow-y: auto;
}

.activity-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: rgba(128, 90, 213, 0.1);
  border-radius: 6px;
  border-left: 3px solid rgba(128, 90, 213, 0.5);
}

.activity-time {
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: nowrap;
  min-width: 80px;
}

.activity-desc {
  color: var(--text-primary);
  font-size: 0.9rem;
  line-height: 1.4;
  text-align: left;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 14px 22px; /* 压缩底部内边距 */
  border-top: 1px solid rgba(79, 209, 197, 0.2);
  background: rgba(0, 0, 0, 0.2);
}

.modal-button {
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s ease;
  border: 1px solid;
  display: flex;
  align-items: center;
  gap: 6px;
}

.modal-button.secondary {
  background: transparent;
  color: var(--text-secondary);
  border-color: rgba(255, 255, 255, 0.2);
}

.modal-button.secondary:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
}

.modal-button.primary {
  background: linear-gradient(135deg, var(--cyber-neon), var(--cyber-blue));
  color: white;
  border-color: var(--cyber-neon);
}

.modal-button.primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 209, 197, 0.3);
}
</style>