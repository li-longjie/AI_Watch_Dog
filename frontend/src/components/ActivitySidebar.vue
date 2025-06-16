<template>
  <div class="activity-container">
    <!-- 触发器 - 只在侧边栏隐藏时显示 -->
    <div 
      v-if="!showSidebar"
      class="activity-trigger" 
      @mouseenter="showSidebar = true"
      @click="showSidebar = true"
    >
      <div class="trigger-icon">
        <div class="activity-icon">📊</div>
        <div class="trigger-text">活动</div>
      </div>
    </div>

    <!-- 侧边栏 -->
    <transition name="slide-left">
      <div 
        v-if="showSidebar" 
        class="activity-sidebar"
        @mouseleave="handleMouseLeave"
        @mouseenter="cancelHideTimer"
      >
        <!-- 固定按钮 -->
        <div class="pin-controls">
          <button 
            @click="togglePin" 
            class="pin-btn"
            :class="{ 'pinned': isPinned }"
            :title="isPinned ? '取消固定' : '固定面板'"
          >
            📌
          </button>
        </div>

        <!-- 侧边栏头部 -->
        <div class="sidebar-header">
          <h3>📊 桌面活动记录</h3>
          <button @click="closeSidebar" class="close-btn">×</button>
        </div>

        <!-- 侧边栏内容 -->
        <div class="sidebar-content">
          <!-- 统计概览 -->
          <div class="stats-section">
            <h4>
              <span class="section-icon">📈</span>
              实时统计
            </h4>
            <div class="stats-grid">
              <div class="stat-item">
                <div class="stat-label">总记录数</div>
                <div class="stat-value">{{ stats.total_records || 0 }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">最新活动</div>
                <div class="stat-value">{{ stats.latest_activity ? formatTime(stats.latest_activity.timestamp) : '--' }}</div>
              </div>
            </div>
          </div>

          <!-- 最活跃应用 -->
          <div class="apps-section" v-if="stats.top_apps && stats.top_apps.length > 0">
            <div class="section-header" @click="toggleSection('topApps')">
              <div class="section-icon">🔥</div>
              <h4>最活跃应用</h4>
              <div class="section-toggle" :class="{ expanded: expandedSections.topApps }">
                <span class="toggle-icon">⌄</span>
              </div>
            </div>
            
            <div class="section-content" v-show="expandedSections.topApps">
              <div class="app-list">
                <div 
                  v-for="[appName, count] in stats.top_apps" 
                  :key="appName"
                  class="app-item"
                >
                  <div class="app-name">{{ appName }}</div>
                  <div class="app-count">{{ count }}次</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 搜索功能 -->
          <div class="search-section">
            <h4>
              <span class="section-icon">🔍</span>
              活动搜索
            </h4>
            <div class="search-form">
              <div class="search-input-group">
                <input 
                  v-model="searchQuery" 
                  type="text" 
                  placeholder="搜索应用、窗口标题或内容..."
                  class="cyber-input"
                  @keyup.enter="performSearch"
                />
                <button @click="performSearch" class="search-btn" :disabled="!searchQuery.trim()">
                  🔍
                </button>
              </div>
            </div>
          </div>

          <!-- 实时活动列表 -->
          <div class="activities-section">
            <div class="section-header" @click="toggleSection('activities')">
              <div class="section-icon">⏰</div>
              <h4>实时活动 {{ searchMode ? `(搜索: ${searchQuery})` : '' }}</h4>
              <div class="section-actions">
                <button 
                  @click="refreshActivities" 
                  class="refresh-btn"
                  :class="{ 'loading': loading }"
                  title="刷新活动记录"
                >
                  🔄
                </button>
                <div class="section-toggle" :class="{ expanded: expandedSections.activities }">
                  <span class="toggle-icon">⌄</span>
                </div>
              </div>
            </div>
            
            <div class="section-content" v-show="expandedSections.activities">
              <!-- 自动刷新控制 -->
              <div class="auto-refresh-control">
                <label class="toggle-switch">
                  <input type="checkbox" v-model="autoRefresh" />
                  <span class="switch-label">
                    <span class="switch-button"></span>
                  </span>
                  <span class="switch-text">自动刷新 ({{ refreshInterval / 1000 }}s)</span>
                </label>
              </div>

              <!-- 活动列表 -->
              <div class="activity-list">
                <div 
                  v-for="activity in activities" 
                  :key="activity.id"
                  class="activity-item"
                  :class="getActivityTypeClass(activity.record_type)"
                  @click="showActivityDetail(activity)"
                >
                  <div class="activity-header">
                    <div class="activity-app">
                      <span class="app-icon">{{ getAppIcon(activity.app_name) }}</span>
                      <span class="app-name">{{ activity.app_name }}</span>
                    </div>
                    <div class="activity-time">{{ formatTime(activity.timestamp) }}</div>
                  </div>
                  
                  <div class="activity-content">
                    <div class="activity-type">{{ getActivityTypeName(activity.record_type) }}</div>
                    <div class="activity-title" v-if="activity.window_title">
                      {{ activity.window_title }}
                    </div>
                    <div class="activity-text" v-if="activity.ocr_text">
                      {{ activity.ocr_text }}
                    </div>
                    <div class="activity-url" v-if="activity.url">
                      <a :href="activity.url" target="_blank" @click.stop>{{ activity.url }}</a>
                    </div>
                  </div>
                  
                  <div class="activity-meta">
                    <span class="parser-type" v-if="activity.parser_type">
                      {{ activity.parser_type }}
                    </span>
                    <span class="mouse-pos" v-if="activity.mouse_x && activity.mouse_y">
                      ({{ activity.mouse_x }}, {{ activity.mouse_y }})
                    </span>
                  </div>
                </div>

                <!-- 加载状态 -->
                <div v-if="loading" class="loading-state">
                  <div class="loading-spinner"></div>
                  <div class="loading-text">加载中...</div>
                </div>

                <!-- 空状态 -->
                <div v-if="!loading && activities.length === 0" class="empty-state">
                  <div class="empty-icon">📝</div>
                  <div class="empty-text">{{ searchMode ? '未找到匹配的活动记录' : '暂无活动记录' }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 活动详情模态框 -->
          <div v-if="selectedActivity" class="activity-detail-modal" @click="closeActivityDetail">
            <div class="modal-content" @click.stop>
              <div class="modal-header">
                <h3>活动详情</h3>
                <button @click="closeActivityDetail" class="close-btn">×</button>
              </div>
              <div class="modal-body">
                <div class="detail-row">
                  <span class="detail-label">时间:</span>
                  <span class="detail-value">{{ formatFullTime(selectedActivity.timestamp) }}</span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">应用:</span>
                  <span class="detail-value">{{ selectedActivity.app_name }}</span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">类型:</span>
                  <span class="detail-value">{{ getActivityTypeName(selectedActivity.record_type) }}</span>
                </div>
                <div class="detail-row" v-if="selectedActivity.window_title">
                  <span class="detail-label">窗口标题:</span>
                  <span class="detail-value">{{ selectedActivity.window_title }}</span>
                </div>
                <div class="detail-row" v-if="selectedActivity.url">
                  <span class="detail-label">URL:</span>
                  <span class="detail-value">
                    <a :href="selectedActivity.url" target="_blank">{{ selectedActivity.url }}</a>
                  </span>
                </div>
                <div class="detail-row" v-if="selectedActivity.ocr_text">
                  <span class="detail-label">识别内容:</span>
                  <span class="detail-value full-text">{{ selectedActivity.ocr_text }}</span>
                </div>
                <div class="detail-row" v-if="selectedActivity.parser_type">
                  <span class="detail-label">解析器:</span>
                  <span class="detail-value">{{ selectedActivity.parser_type }}</span>
                </div>
                <div class="detail-row" v-if="selectedActivity.mouse_x && selectedActivity.mouse_y">
                  <span class="detail-label">鼠标位置:</span>
                  <span class="detail-value">({{ selectedActivity.mouse_x }}, {{ selectedActivity.mouse_y }})</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue'

// API基地址
const API_BASE_URL = 'http://localhost:5001'

// 响应式数据
const showSidebar = ref(false)
const isPinned = ref(false)
const hideTimer = ref(null)
const loading = ref(false)
const autoRefresh = ref(true)
const refreshInterval = ref(5000) // 5秒刷新一次

// 展开状态
const expandedSections = reactive({
  topApps: true,
  activities: true
})

// 统计数据
const stats = reactive({
  total_records: 0,
  top_apps: [],
  record_types: {},
  latest_activity: null
})

// 活动数据
const activities = ref([])
const selectedActivity = ref(null)

// 搜索相关
const searchQuery = ref('')
const searchFilter = ref('all')
const searchMode = ref(false)

// 自动刷新定时器
let refreshTimer = null

// 方法
const handleMouseLeave = () => {
  if (!isPinned.value) {
    hideTimer.value = setTimeout(() => {
      showSidebar.value = false
    }, 500)
  }
}

const cancelHideTimer = () => {
  if (hideTimer.value) {
    clearTimeout(hideTimer.value)
    hideTimer.value = null
  }
}

const togglePin = () => {
  isPinned.value = !isPinned.value
  if (isPinned.value) {
    cancelHideTimer()
  }
}

const closeSidebar = () => {
  isPinned.value = false
  showSidebar.value = false
  cancelHideTimer()
}

const toggleSection = (sectionName) => {
  expandedSections[sectionName] = !expandedSections[sectionName]
}

// 获取统计数据
const loadStats = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/activity_stats`)
    if (response.ok) {
      const data = await response.json()
      Object.assign(stats, data)
    }
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

// 获取实时活动
const loadActivities = async () => {
  if (loading.value) return
  
  loading.value = true
  try {
    const limit = 20
    const response = await fetch(`${API_BASE_URL}/api/real_time_activities?limit=${limit}`)
    if (response.ok) {
      const data = await response.json()
      activities.value = data.activities || []
    }
  } catch (error) {
    console.error('获取活动记录失败:', error)
  } finally {
    loading.value = false
  }
}

// 搜索活动
const performSearch = async () => {
  if (!searchQuery.value.trim()) {
    searchMode.value = false
    await loadActivities()
    return
  }

  loading.value = true
  searchMode.value = true
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/activity_search?query=${encodeURIComponent(searchQuery.value)}&limit=50`)
    if (response.ok) {
      const data = await response.json()
      activities.value = data.activities || []
    }
  } catch (error) {
    console.error('搜索活动失败:', error)
  } finally {
    loading.value = false
  }
}

// 刷新活动
const refreshActivities = async () => {
  if (searchMode.value) {
    await performSearch()
  } else {
    await loadActivities()
  }
  await loadStats()
}

// 显示活动详情
const showActivityDetail = (activity) => {
  selectedActivity.value = activity
}

// 关闭活动详情
const closeActivityDetail = () => {
  selectedActivity.value = null
}

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return '--'
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

const formatFullTime = (timestamp) => {
  if (!timestamp) return '--'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN')
}

// 获取应用图标
const getAppIcon = (appName) => {
  const iconMap = {
    'Chrome': '🌐',
    'Firefox': '🦊',
    'Edge': '🌐',
    'VSCode': '💻',
    'Code': '💻',
    'QQ': '💬',
    'WeChat': '💬',
    'Explorer': '📁',
    'Unknown': '❓'
  }
  return iconMap[appName] || '📱'
}

// 获取活动类型名称
const getActivityTypeName = (type) => {
  const typeMap = {
    'screen_content': '屏幕内容',
    'app_switch': '应用切换',
    'mouse_interaction': '鼠标交互'
  }
  return typeMap[type] || type
}

// 获取活动类型样式
const getActivityTypeClass = (type) => {
  return `activity-type-${type}`
}

// 设置自动刷新
const setupAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  
  if (autoRefresh.value) {
    refreshTimer = setInterval(() => {
      if (showSidebar.value) {
        refreshActivities()
      }
    }, refreshInterval.value)
  }
}

// 监听自动刷新设置变化
watch(autoRefresh, setupAutoRefresh)
watch(showSidebar, (newVal) => {
  if (newVal) {
    refreshActivities()
    setupAutoRefresh()
  }
})

// 清理搜索
watch(searchQuery, (newVal) => {
  if (!newVal.trim() && searchMode.value) {
    searchMode.value = false
    loadActivities()
  }
})

onMounted(() => {
  setupAutoRefresh()
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  if (hideTimer.value) {
    clearTimeout(hideTimer.value)
  }
})
</script>

<style scoped>
:root {
  --primary: #4fd1c5;
  --secondary: #2d3748;
  --background: #1a202c;
  --surface: #2d3748;
  --text-primary: #ffffff;
  --text-secondary: #a0aec0;
  --border: rgba(79, 209, 197, 0.3);
  --success: #48bb78;
  --warning: #ed8936;
  --error: #f56565;
}

.activity-container {
  position: fixed;
  right: 0;
  top: 90px; /* 从header下方10px开始 */
  bottom: 60px; /* 距离底部状态栏留出10px间距 */
  z-index: 200;
  height: auto;
}

.activity-trigger {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 60px;
  background: linear-gradient(45deg, var(--primary), rgba(79, 209, 197, 0.3));
  border-radius: 8px 0 0 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.activity-trigger:hover {
  width: 50px;
  background: linear-gradient(45deg, var(--primary), rgba(79, 209, 197, 0.8));
  box-shadow: 0 0 20px rgba(79, 209, 197, 0.5);
}

.trigger-icon {
  opacity: 0;
  transition: opacity 0.3s ease;
  text-align: center;
  color: white;
  font-size: 12px;
}

.activity-trigger:hover .trigger-icon {
  opacity: 1;
}

.activity-icon {
  font-size: 16px;
  line-height: 1;
}

.trigger-text {
  font-size: 10px;
  margin-top: 2px;
  white-space: nowrap;
}

.activity-sidebar {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 420px;
  background: linear-gradient(135deg, 
    rgba(10, 25, 47, 0.95) 0%, 
    rgba(15, 35, 65, 0.95) 50%,
    rgba(20, 45, 80, 0.95) 100%);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(79, 209, 197, 0.2);
  border-right: none;
  border-radius: 12px 0 0 12px;
  box-shadow: 
    0 10px 30px rgba(0, 0, 0, 0.3),
    0 0 20px rgba(79, 209, 197, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pin-controls {
  position: absolute;
  top: 10px;
  left: 60px;
  z-index: 10;
}

.pin-btn {
  background: rgba(79, 209, 197, 0.1);
  border: 1px solid rgba(79, 209, 197, 0.3);
  color: var(--text-secondary);
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s ease;
}

.pin-btn:hover {
  background: rgba(79, 209, 197, 0.2);
  color: var(--primary);
}

.pin-btn.pinned {
  background: var(--primary);
  color: white;
  box-shadow: 0 0 10px rgba(79, 209, 197, 0.5);
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid rgba(79, 209, 197, 0.2);
  background: linear-gradient(90deg, rgba(79, 209, 197, 0.1), transparent);
}

.sidebar-header h3 {
  margin: 0;
  color: var(--primary);
  font-size: 18px;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.3s ease;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.sidebar-content {
  padding: 0;
  height: calc(100% - 60px);
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: rgba(79, 209, 197, 0.3) transparent;
}

.sidebar-content::-webkit-scrollbar {
  width: 6px;
}

.sidebar-content::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-content::-webkit-scrollbar-thumb {
  background: rgba(79, 209, 197, 0.3);
  border-radius: 3px;
}

.sidebar-content::-webkit-scrollbar-thumb:hover {
  background: rgba(79, 209, 197, 0.5);
}

/* 各个板块样式 */
.stats-section, .apps-section, .search-section, .activities-section {
  margin: 20px;
  padding: 15px;
  background: rgba(79, 209, 197, 0.05);
  border: 1px solid rgba(79, 209, 197, 0.2);
  border-radius: 12px;
}

.stats-section h4, .search-section h4 {
  margin: 0 0 15px 0;
  color: var(--primary);
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  margin-bottom: 15px;
}

.section-header h4 {
  margin: 0;
  color: var(--primary);
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-toggle {
  transition: transform 0.3s ease;
}

.section-toggle.expanded {
  transform: rotate(180deg);
}

.toggle-icon {
  color: var(--text-secondary);
  font-size: 14px;
}

.refresh-btn {
  background: rgba(79, 209, 197, 0.1);
  border: 1px solid rgba(79, 209, 197, 0.3);
  color: var(--primary);
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s ease;
}

.refresh-btn:hover {
  background: rgba(79, 209, 197, 0.2);
}

.refresh-btn.loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}

.stat-item {
  text-align: center;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 5px;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--primary);
}

/* 应用列表 */
.app-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.app-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
}

.app-name {
  color: var(--text-primary);
  font-size: 14px;
}

.app-count {
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
}

/* 搜索表单 */
.search-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.search-input-group {
  display: flex;
  gap: 8px;
}

.cyber-input {
  flex: 1;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 6px;
  padding: 8px 12px;
  color: var(--text-primary);
  font-size: 14px;
}

.cyber-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 8px rgba(79, 209, 197, 0.3);
}

.search-btn {
  background: var(--primary);
  border: none;
  border-radius: 6px;
  padding: 8px 12px;
  color: white;
  cursor: pointer;
  transition: all 0.3s ease;
}

.search-btn:hover:not(:disabled) {
  background: rgba(79, 209, 197, 0.8);
}

.search-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cyber-select {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 6px;
  padding: 8px 12px;
  color: var(--text-primary);
  font-size: 14px;
}

/* 自动刷新控制 */
.auto-refresh-control {
  margin-bottom: 15px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
}

.toggle-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.toggle-switch input[type="checkbox"] {
  display: none;
}

.switch-label {
  position: relative;
  width: 44px;
  height: 24px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  transition: background 0.3s ease;
}

.switch-button {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  transition: transform 0.3s ease;
}

.toggle-switch input[type="checkbox"]:checked + .switch-label {
  background: var(--primary);
}

.toggle-switch input[type="checkbox"]:checked + .switch-label .switch-button {
  transform: translateX(20px);
}

.switch-text {
  color: var(--text-primary);
  font-size: 14px;
}

/* 活动列表 */
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 400px;
  overflow-y: auto;
}

.activity-item {
  padding: 12px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(79, 209, 197, 0.1);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.activity-item:hover {
  background: rgba(79, 209, 197, 0.1);
  border-color: rgba(79, 209, 197, 0.3);
}

.activity-item.activity-type-app_switch {
  border-left: 3px solid var(--warning);
}

.activity-item.activity-type-screen_content {
  border-left: 3px solid var(--primary);
}

.activity-item.activity-type-mouse_interaction {
  border-left: 3px solid var(--success);
}

.activity-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.activity-app {
  display: flex;
  align-items: center;
  gap: 6px;
}

.app-icon {
  font-size: 14px;
}

.app-name {
  color: var(--text-primary);
  font-weight: 500;
  font-size: 14px;
}

.activity-time {
  color: var(--text-secondary);
  font-size: 12px;
}

.activity-content {
  margin-bottom: 8px;
}

.activity-type {
  color: var(--primary);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.activity-title {
  color: var(--text-primary);
  font-size: 13px;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-text {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
  margin-bottom: 4px;
}

.activity-url {
  margin-bottom: 4px;
}

.activity-url a {
  color: var(--primary);
  font-size: 12px;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

.activity-url a:hover {
  text-decoration: underline;
}

.activity-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--text-secondary);
}

.parser-type {
  background: rgba(79, 209, 197, 0.2);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 10px;
}

/* 加载和空状态 */
.loading-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 30px;
  color: var(--text-secondary);
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(79, 209, 197, 0.3);
  border-top: 2px solid var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}

.empty-icon {
  font-size: 32px;
  margin-bottom: 10px;
}

.loading-text, .empty-text {
  font-size: 14px;
}

/* 活动详情模态框 */
.activity-detail-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--background);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 12px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid rgba(79, 209, 197, 0.2);
}

.modal-header h3 {
  margin: 0;
  color: var(--primary);
  font-size: 18px;
}

.modal-body {
  padding: 20px;
}

.detail-row {
  display: flex;
  margin-bottom: 15px;
  gap: 15px;
}

.detail-label {
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 80px;
  font-size: 14px;
}

.detail-value {
  color: var(--text-primary);
  flex: 1;
  font-size: 14px;
  word-break: break-all;
}

.detail-value.full-text {
  white-space: pre-wrap;
  line-height: 1.5;
}

.detail-value a {
  color: var(--primary);
  text-decoration: none;
}

.detail-value a:hover {
  text-decoration: underline;
}

/* 动画效果 */
.slide-left-enter-active,
.slide-left-leave-active {
  transition: transform 0.3s ease;
}

.slide-left-enter-from {
  transform: translateX(100%);
}

.slide-left-leave-to {
  transform: translateX(100%);
}

/* 响应式调整 */
@media (max-width: 768px) {
  .activity-sidebar {
    width: 100vw;
    border-radius: 0;
  }
  
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .search-input-group {
    flex-direction: column;
  }
}
</style> 