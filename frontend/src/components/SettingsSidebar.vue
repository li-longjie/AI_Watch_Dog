<template>
  <div class="settings-container">
    <!-- 触发器 - 只在侧边栏隐藏时显示 -->
    <div 
      v-if="!showSidebar"
      class="settings-trigger" 
      @mouseenter="showSidebar = true"
      @click="showSidebar = true"
    >
      <div class="trigger-icon">
        <div class="gear-icon">⚙</div>
        <div class="trigger-text">设置</div>
      </div>
    </div>

    <!-- 侧边栏 -->
    <transition name="slide-right">
      <div 
        v-if="showSidebar" 
        class="settings-sidebar"
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
          <h3>⚙️ 系统设置</h3>
          <button @click="closeSidebar" class="close-btn">×</button>
        </div>

        <!-- 侧边栏内容 -->
        <div class="sidebar-content">
          <!-- 预警规则设置 -->
          <div class="settings-section">
            <h4>
              <span class="section-icon">⚠</span>
              预警规则配置
            </h4>
            
            <div class="rule-form">
              <div class="form-group">
                <label>规则名称</label>
                <input 
                  v-model="newRule.name" 
                  type="text" 
                  placeholder="例如：离开位置检测"
                  class="cyber-input"
                />
              </div>

              <div class="form-group">
                <label>触发条件描述</label>
                <textarea 
                  v-model="newRule.condition" 
                  placeholder="描述什么情况下触发预警，例如：当检测到人员离开座位超过5分钟时"
                  class="cyber-textarea"
                  rows="3"
                ></textarea>
              </div>

              <div class="form-group">
                <label>预警级别</label>
                <select v-model="newRule.level" class="cyber-select">
                  <option value="low">低 - 提示</option>
                  <option value="medium">中 - 警告</option>
                  <option value="high">高 - 紧急</option>
                </select>
              </div>

              <div class="form-group">
                <label>启用状态</label>
                <div class="toggle-switch">
                  <input 
                    type="checkbox" 
                    v-model="newRule.enabled" 
                    :id="'rule-enabled-new'"
                  />
                  <label for="rule-enabled-new" class="switch-label">
                    <span class="switch-button"></span>
                  </label>
                </div>
              </div>

              <button @click="addRule" class="cyber-btn primary">
                <span class="btn-icon">+</span>
                添加规则
              </button>
            </div>
          </div>

          <!-- 系统预设规则管理 -->
          <div class="settings-section">
            <div class="section-header" @click="toggleSection('systemRules')">
              <div class="section-icon">⚙️</div>
              <h3>系统预设规则 ({{ enabledSystemRules }}/{{ systemRules.length }})</h3>
              <div class="section-toggle" :class="{ expanded: expandedSections.systemRules }">
                <span class="toggle-icon">⌄</span>
              </div>
            </div>
            
            <div class="section-content" v-show="expandedSections.systemRules">
              <div class="rules-list">
                <div 
                  v-for="(rule, index) in systemRules" 
                  :key="`system-${rule.id}`" 
                  class="rule-item system-rule"
                  :class="{ 'disabled': !rule.enabled }"
                >
                  <div class="rule-header">
                    <span class="rule-name">
                      <span class="system-badge">系统</span>
                      {{ rule.name }}
                    </span>
                    <div class="rule-actions">
                      <button 
                        @click="toggleRule(rule, index)" 
                        class="action-btn"
                        :class="rule.enabled ? 'enabled' : 'disabled'"
                      >
                        {{ rule.enabled ? '启用' : '禁用' }}
                      </button>
                    </div>
                  </div>
                  <div class="rule-condition">{{ rule.condition }}</div>
                  <div class="rule-meta">
                    <span class="rule-level" :class="rule.level">{{ getLevelText(rule.level) }}</span>
                    <span class="rule-status">
                      状态: {{ rule.enabled ? '活跃' : '暂停' }}
                    </span>
                    <span class="rule-type">活动类型: {{ rule.activity_type }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 用户自定义规则管理 -->
          <div class="settings-section">
            <h4>
              <span class="section-icon">👤</span>
              用户自定义规则 ({{ customRules.length }})
            </h4>
            
            <div class="rules-list">
              <div 
                v-for="(rule, index) in customRules" 
                :key="`custom-${rule.id}`" 
                class="rule-item custom-rule"
                :class="{ 'disabled': !rule.enabled }"
              >
                <div class="rule-header">
                  <span class="rule-name">
                    <span class="custom-badge">自定义</span>
                    {{ rule.name }}
                  </span>
                  <div class="rule-actions">
                    <button 
                      @click="toggleRule(rule, index)" 
                      class="action-btn"
                      :class="rule.enabled ? 'enabled' : 'disabled'"
                    >
                      {{ rule.enabled ? '启用' : '禁用' }}
                    </button>
                    <button 
                      @click="editRule(rule)" 
                      class="action-btn edit"
                    >
                      编辑
                    </button>
                    <button 
                      @click="deleteRule(rule.id)" 
                      class="action-btn delete"
                    >
                      删除
                    </button>
                  </div>
                </div>
                <div class="rule-condition">{{ rule.condition }}</div>
                <div class="rule-meta">
                  <span class="rule-level" :class="rule.level">{{ getLevelText(rule.level) }}</span>
                  <span class="rule-status">
                    状态: {{ rule.enabled ? '活跃' : '暂停' }}
                  </span>
                </div>
              </div>
              
              <div v-if="customRules.length === 0" class="empty-rules">
                <div class="empty-icon">📝</div>
                <div class="empty-text">暂无自定义规则</div>
                <div class="empty-hint">在上方添加您的专属预警规则</div>
              </div>
            </div>
          </div>

          <!-- 摄像头管理 -->
          <div class="settings-section">
            <div class="section-header" @click="toggleSection('cameraManagement')">
              <div class="section-icon">📹</div>
              <h3>摄像头管理</h3>
              <div class="section-toggle" :class="{ expanded: expandedSections.cameraManagement }">
                <span class="toggle-icon">⌄</span>
              </div>
            </div>
            
            <div class="section-content" v-show="expandedSections.cameraManagement">
              <!-- 当前摄像头状态 -->
              <div class="camera-status">
                <div class="status-item">
                  <span class="status-label">当前摄像头:</span>
                  <span class="status-value">{{ currentCamera.name || '摄像头 ' + currentCamera.index }}</span>
                  <div class="camera-indicator" :class="{ active: currentCamera.connected }"></div>
                </div>
                <div class="status-item">
                  <span class="status-label">分辨率:</span>
                  <span class="status-value">{{ currentCamera.resolution }}</span>
                </div>
                <div class="status-item">
                  <span class="status-label">帧率:</span>
                  <span class="status-value">{{ currentCamera.fps }} FPS</span>
                </div>
              </div>

              <!-- 添加摄像头 -->
              <div class="camera-add-section">
                <h4>添加新摄像头</h4>
                <div class="form-group">
                  <label>摄像头类型:</label>
                  <select v-model="newCamera.type" class="form-select">
                    <option value="usb">USB摄像头</option>
                    <option value="ip">网络摄像头(IP)</option>
                    <option value="rtsp">RTSP流</option>
                    <option value="file">视频文件</option>
                  </select>
                </div>

                <!-- USB摄像头配置 -->
                <div v-if="newCamera.type === 'usb'" class="camera-config">
                  <div class="form-group">
                    <label>设备索引:</label>
                    <input v-model.number="newCamera.index" type="number" min="0" max="10" class="form-input" placeholder="0, 1, 2...">
                  </div>
                  <button @click="detectUSBCameras" class="btn btn-secondary">
                    <span class="btn-icon">🔍</span>
                    检测可用设备
                  </button>
                </div>

                <!-- IP摄像头配置 -->
                <div v-if="newCamera.type === 'ip'" class="camera-config">
                  <div class="form-group">
                    <label>IP地址:</label>
                    <input v-model="newCamera.ip" type="text" class="form-input" placeholder="192.168.1.100">
                  </div>
                  <div class="form-group">
                    <label>端口:</label>
                    <input v-model.number="newCamera.port" type="number" class="form-input" placeholder="8080">
                  </div>
                  <div class="form-group">
                    <label>用户名:</label>
                    <input v-model="newCamera.username" type="text" class="form-input" placeholder="admin">
                  </div>
                  <div class="form-group">
                    <label>密码:</label>
                    <input v-model="newCamera.password" type="password" class="form-input" placeholder="password">
                  </div>
                </div>

                <!-- RTSP流配置 -->
                <div v-if="newCamera.type === 'rtsp'" class="camera-config">
                  <div class="form-group">
                    <label>RTSP URL:</label>
                    <input v-model="newCamera.url" type="text" class="form-input" 
                      placeholder="rtsp://username:password@ip:port/stream">
                  </div>
                </div>

                <!-- 视频文件配置 -->
                <div v-if="newCamera.type === 'file'" class="camera-config">
                  <div class="form-group">
                    <label>文件路径:</label>
                    <input v-model="newCamera.filePath" type="text" class="form-input" placeholder="选择视频文件">
                    <button @click="selectVideoFile" class="btn btn-secondary">
                      <span class="btn-icon">📁</span>
                      浏览
                    </button>
                  </div>
                </div>

                <!-- 通用配置 -->
                <div class="camera-config">
                  <div class="form-group">
                    <label>摄像头名称:</label>
                    <input v-model="newCamera.name" type="text" class="form-input" placeholder="给摄像头起个名字">
                  </div>
                  <div class="form-row">
                    <div class="form-group">
                      <label>分辨率:</label>
                      <select v-model="newCamera.resolution" class="form-select">
                        <option value="640x480">640×480</option>
                        <option value="1280x720">1280×720 (HD)</option>
                        <option value="1920x1080">1920×1080 (FHD)</option>
                        <option value="3840x2160">3840×2160 (4K)</option>
                      </select>
                    </div>
                    <div class="form-group">
                      <label>帧率:</label>
                      <select v-model.number="newCamera.fps" class="form-select">
                        <option value="15">15 FPS</option>
                        <option value="30">30 FPS</option>
                        <option value="60">60 FPS</option>
                      </select>
                    </div>
                  </div>
                </div>

                <!-- 测试和保存按钮 -->
                <div class="camera-actions">
                  <button @click="testCamera" class="btn btn-primary" :disabled="testingCamera">
                    <span class="btn-icon">{{ testingCamera ? '⏳' : '🎥' }}</span>
                    {{ testingCamera ? '测试中...' : '测试摄像头' }}
                  </button>
                  <button @click="addCamera" class="btn btn-success" :disabled="!canAddCamera">
                    <span class="btn-icon">➕</span>
                    添加摄像头
                  </button>
                </div>
              </div>

              <!-- 摄像头预览 -->
              <div v-if="showCameraPreview" class="camera-preview">
                <h4>摄像头预览</h4>
                <div class="preview-container">
                  <video ref="previewVideo" autoplay muted class="preview-video"></video>
                  <div class="preview-controls">
                    <button @click="stopPreview" class="btn btn-secondary">
                      <span class="btn-icon">⏹</span>
                      停止预览
                    </button>
                  </div>
                </div>
              </div>

              <!-- 摄像头列表 -->
              <div class="camera-list">
                <h4>已配置摄像头</h4>
                <div v-if="cameraList.length === 0" class="empty-state">
                  <div class="empty-icon">📹</div>
                  <p>暂无配置的摄像头</p>
                  <p class="empty-hint">请添加您的第一个摄像头</p>
                </div>
                
                <div v-for="camera in cameraList" :key="camera.id" class="camera-item">
                  <div class="camera-info">
                    <div class="camera-name">{{ camera.name }}</div>
                    <div class="camera-details">
                      <span class="camera-type">{{ getCameraTypeLabel(camera.type) }}</span>
                      <span class="camera-resolution">{{ camera.resolution }}</span>
                      <span class="camera-fps">{{ camera.fps }}FPS</span>
                    </div>
                  </div>
                  <div class="camera-controls">
                    <button @click="switchToCamera(camera)" 
                      class="btn btn-sm" 
                      :class="{ 'btn-primary': camera.id === currentCamera.id, 'btn-secondary': camera.id !== currentCamera.id }">
                      {{ camera.id === currentCamera.id ? '当前' : '切换' }}
                    </button>
                    <button @click="editCamera(camera)" class="btn btn-sm btn-secondary">
                      <span class="btn-icon">✏️</span>
                    </button>
                    <button @click="deleteCamera(camera.id)" class="btn btn-sm btn-danger">
                      <span class="btn-icon">🗑️</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 数据导出 -->
          <div class="settings-section">
            <h4>
              <span class="section-icon">📊</span>
              数据导出
            </h4>
            
            <div class="export-options">
              <div class="form-group">
                <label>导出时间范围</label>
                <select v-model="exportTimeRange" class="cyber-select">
                  <option value="today">今天</option>
                  <option value="week">最近一周</option>
                  <option value="month">最近一月</option>
                  <option value="custom">自定义时间</option>
                </select>
              </div>
              
              <div v-if="exportTimeRange === 'custom'" class="date-range">
                <div class="form-group">
                  <label>开始日期</label>
                  <input v-model="customStartDate" type="date" class="cyber-input" />
                </div>
                <div class="form-group">
                  <label>结束日期</label>
                  <input v-model="customEndDate" type="date" class="cyber-input" />
                </div>
              </div>
              
              <div class="form-group">
                <label>导出格式</label>
                <select v-model="exportFormat" class="cyber-select">
                  <option value="csv">CSV 表格</option>
                  <option value="json">JSON 数据</option>
                  <option value="pdf">PDF 报告</option>
                </select>
              </div>
              
              <div class="export-buttons">
                <button @click="exportAlerts" class="cyber-btn secondary">
                  <span class="btn-icon">📊</span>
                  导出预警记录
                </button>
                <button @click="exportBehaviorData" class="cyber-btn secondary">
                  <span class="btn-icon">📈</span>
                  导出行为数据
                </button>
              </div>
            </div>
          </div>

          <!-- 系统状态 -->
          <div class="settings-section">
            <h4>
              <span class="section-icon">🔧</span>
              系统状态
            </h4>
            
            <div class="system-status">
              <div class="status-item">
                <span class="status-label">AI模型状态:</span>
                <span class="status-value" :class="systemStatus.aiModel">
                  {{ systemStatus.aiModel }}
                </span>
              </div>
              <div class="status-item">
                <span class="status-label">视频流状态:</span>
                <span class="status-value" :class="systemStatus.videoStream">
                  {{ systemStatus.videoStream }}
                </span>
              </div>
              <div class="status-item">
                <span class="status-label">数据库连接:</span>
                <span class="status-value" :class="systemStatus.database">
                  {{ systemStatus.database }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'

// 响应式数据
const showSidebar = ref(false)
const hideTimer = ref(null)
const isPinned = ref(false)

// 展开状态
const expandedSections = ref({
  cameraManagement: false,
  systemRules: false
})

// 新规则表单
const newRule = ref({
  name: '',
  condition: '',
  level: 'medium',
  enabled: true
})

// 预警规则列表
const alertRules = ref([])

// 系统预设规则和用户自定义规则分类
const systemRules = computed(() => alertRules.value.filter(rule => rule.is_system_rule))
const customRules = computed(() => alertRules.value.filter(rule => !rule.is_system_rule))
const enabledSystemRules = computed(() => systemRules.value.filter(rule => rule.enabled).length)

// 摄像头管理相关数据
const currentCamera = ref({
  id: 1,
  name: '默认摄像头',
  type: 'usb',
  index: 4,
  resolution: '1280x720',
  fps: 30,
  connected: true
})

const newCamera = ref({
  type: 'usb',
  index: 0,
  name: '',
  resolution: '1280x720',
  fps: 30,
  ip: '',
  port: 8080,
  username: '',
  password: '',
  url: '',
  filePath: ''
})

const cameraList = ref([
  {
    id: 1,
    name: '默认摄像头',
    type: 'usb',
    index: 4,
    resolution: '1280x720',
    fps: 30,
    connected: true
  }
])

const testingCamera = ref(false)
const showCameraPreview = ref(false)
const previewVideo = ref(null)

// 计算属性
const canAddCamera = computed(() => {
  return newCamera.value.name && (
    (newCamera.value.type === 'usb' && newCamera.value.index >= 0) ||
    (newCamera.value.type === 'ip' && newCamera.value.ip) ||
    (newCamera.value.type === 'rtsp' && newCamera.value.url) ||
    (newCamera.value.type === 'file' && newCamera.value.filePath)
  )
})

// 导出设置
const exportTimeRange = ref('today')
const exportFormat = ref('csv')
const customStartDate = ref('')
const customEndDate = ref('')

// 系统状态
const systemStatus = reactive({
  aiModel: 'online',
  videoStream: 'online',
  database: 'online'
})

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
  expandedSections.value[sectionName] = !expandedSections.value[sectionName]
}

// 预警规则相关方法
const loadAlertRules = async () => {
  try {
    const response = await fetch('/api/custom-alert-rules')
    if (response.ok) {
      const data = await response.json()
      alertRules.value = data.rules || []
      console.log(`加载了${alertRules.value.length}个预警规则`)
    } else {
      throw new Error('获取规则失败')
    }
  } catch (error) {
    console.error('加载预警规则失败:', error)
    alertRules.value = []
  }
}

const addRule = async () => {
  if (!newRule.value.name || !newRule.value.condition) {
    alert('请填写完整的规则信息')
    return
  }

  try {
    const response = await fetch('/api/custom-alert-rules', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ...newRule.value,
        is_system_rule: false
      })
    })

    if (response.ok) {
      await loadAlertRules()
      Object.assign(newRule.value, {
        name: '',
        condition: '',
        level: 'medium',
        enabled: true
      })
      alert('规则添加成功！')
    } else {
      throw new Error('添加规则失败')
    }
  } catch (error) {
    console.error('添加规则错误:', error)
    alert('添加规则失败，请稍后重试')
  }
}

const toggleRule = async (rule, index) => {
  try {
    rule.enabled = !rule.enabled
    
    const response = await fetch(`/api/custom-alert-rules/${rule.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ enabled: rule.enabled })
    })
    
    if (!response.ok) {
      rule.enabled = !rule.enabled
      throw new Error('更新规则状态失败')
    }
  } catch (error) {
    console.error('切换规则状态失败:', error)
    alert('更新规则状态失败')
  }
}

const editRule = (rule) => {
  const newName = prompt('请输入新的规则名称：', rule.name)
  if (newName && newName !== rule.name) {
    updateRule({ ...rule, name: newName })
  }
}

const deleteRule = async (ruleId) => {
  if (confirm('确定要删除这个规则吗？')) {
    try {
      const response = await fetch(`/api/custom-alert-rules/${ruleId}`, {
        method: 'DELETE'
      })
      
      if (response.ok) {
        await loadAlertRules()
        alert('规则删除成功')
      } else {
        throw new Error('删除规则失败')
      }
    } catch (error) {
      console.error('删除规则失败:', error)
      alert('删除规则失败')
    }
  }
}

const updateRule = async (rule) => {
  try {
    const response = await fetch(`/api/custom-alert-rules/${rule.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(rule)
    })
    
    if (response.ok) {
      await loadAlertRules()
    } else {
      throw new Error('更新规则失败')
    }
  } catch (error) {
    console.error('更新规则失败:', error)
    alert('更新规则失败')
  }
}

const getLevelText = (level) => {
  const levelMap = {
    low: '低',
    medium: '中',
    high: '高'
  }
  return levelMap[level] || level
}

// 摄像头管理方法
const detectUSBCameras = async () => {
  try {
    const response = await fetch('/api/camera/detect-usb', {
      method: 'POST'
    })
    const result = await response.json()
    
    if (result.status === 'success') {
      console.log('检测到的USB摄像头:', result.cameras)
    }
  } catch (error) {
    console.error('检测USB摄像头失败:', error)
  }
}

const selectVideoFile = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'video/*'
  input.onchange = (e) => {
    const file = e.target.files[0]
    if (file) {
      newCamera.value.filePath = file.path || file.name
    }
  }
  input.click()
}

const testCamera = async () => {
  testingCamera.value = true
  try {
    const cameraConfig = {
      type: newCamera.value.type,
      ...newCamera.value
    }
    
    const response = await fetch('/api/camera/test', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(cameraConfig)
    })
    
    const result = await response.json()
    
    if (result.status === 'success') {
      showCameraPreview.value = true
      await startPreview(cameraConfig)
    } else {
      alert('摄像头测试失败: ' + result.message)
    }
  } catch (error) {
    console.error('测试摄像头失败:', error)
    alert('测试摄像头失败: ' + error.message)
  } finally {
    testingCamera.value = false
  }
}

const startPreview = async (cameraConfig) => {
  try {
    let stream
    if (cameraConfig.type === 'usb') {
      stream = await navigator.mediaDevices.getUserMedia({
        video: {
          deviceId: cameraConfig.index,
          width: { ideal: parseInt(cameraConfig.resolution.split('x')[0]) },
          height: { ideal: parseInt(cameraConfig.resolution.split('x')[1]) }
        }
      })
    } else {
      console.log('非USB摄像头预览需要后端支持')
      return
    }
    
    if (previewVideo.value && stream) {
      previewVideo.value.srcObject = stream
    }
  } catch (error) {
    console.error('启动预览失败:', error)
    alert('启动预览失败: ' + error.message)
  }
}

const stopPreview = () => {
  if (previewVideo.value && previewVideo.value.srcObject) {
    const tracks = previewVideo.value.srcObject.getTracks()
    tracks.forEach(track => track.stop())
    previewVideo.value.srcObject = null
  }
  showCameraPreview.value = false
}

const addCamera = async () => {
  try {
    if (!newCamera.value.name) {
      alert('请输入摄像头名称')
      return
    }
    
    const cameraData = {
      ...newCamera.value,
      id: Date.now()
    }
    
    const response = await fetch('/api/camera/add', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(cameraData)
    })
    
    const result = await response.json()
    
    if (result.status === 'success') {
      cameraList.value.push({
        ...cameraData,
        id: result.camera_id,
        connected: false
      })
      
      newCamera.value = {
        type: 'usb',
        index: 0,
        name: '',
        resolution: '1280x720',
        fps: 30,
        ip: '',
        port: 8080,
        username: '',
        password: '',
        url: '',
        filePath: ''
      }
      
      alert('摄像头添加成功!')
    } else {
      alert('添加摄像头失败: ' + result.message)
    }
  } catch (error) {
    console.error('添加摄像头失败:', error)
    alert('添加摄像头失败: ' + error.message)
  }
}

const switchToCamera = async (camera) => {
  try {
    const response = await fetch('/api/camera/switch', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ camera_id: camera.id })
    })
    
    const result = await response.json()
    
    if (result.status === 'success') {
      currentCamera.value = { ...camera }
      cameraList.value.forEach(cam => {
        cam.connected = cam.id === camera.id
      })
      alert('摄像头切换成功!')
    } else {
      alert('切换摄像头失败: ' + result.message)
    }
  } catch (error) {
    console.error('切换摄像头失败:', error)
    alert('切换摄像头失败')
  }
}

const editCamera = (camera) => {
  const newName = prompt('请输入新的摄像头名称：', camera.name)
  if (newName && newName !== camera.name) {
    camera.name = newName
  }
}

const deleteCamera = async (cameraId) => {
  if (confirm('确定要删除这个摄像头吗？')) {
    try {
      const response = await fetch(`/api/camera/delete/${cameraId}`, {
        method: 'DELETE'
      })
      
      if (response.ok) {
        const index = cameraList.value.findIndex(cam => cam.id === cameraId)
        if (index > -1) {
          cameraList.value.splice(index, 1)
        }
        alert('摄像头删除成功!')
      } else {
        alert('删除摄像头失败')
      }
    } catch (error) {
      console.error('删除摄像头失败:', error)
      alert('删除摄像头失败: ' + error.message)
    }
  }
}

const getCameraTypeLabel = (type) => {
  const labels = {
    'usb': 'USB摄像头',
    'ip': 'IP摄像头', 
    'rtsp': 'RTSP流',
    'file': '视频文件'
  }
  return labels[type] || type
}

// 导出方法
const exportAlerts = async () => {
  try {
    const params = new URLSearchParams({
      timeRange: exportTimeRange.value,
      format: exportFormat.value
    })
    
    if (exportTimeRange.value === 'custom') {
      params.append('startDate', customStartDate.value)
      params.append('endDate', customEndDate.value)
    }
    
    const response = await fetch(`/api/export/alerts?${params}`)
    
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = `alerts_${exportTimeRange.value}.${exportFormat.value}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
    } else {
      alert('导出失败')
    }
  } catch (error) {
    console.error('导出失败:', error)
    alert('导出失败')
  }
}

const exportBehaviorData = async () => {
  try {
    const params = new URLSearchParams({
      timeRange: exportTimeRange.value,
      format: exportFormat.value
    })
    
    if (exportTimeRange.value === 'custom') {
      params.append('startDate', customStartDate.value)
      params.append('endDate', customEndDate.value)
    }
    
    const response = await fetch(`/api/export/behavior?${params}`)
    
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = `behavior_${exportTimeRange.value}.${exportFormat.value}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
    } else {
      alert('导出失败')
    }
  } catch (error) {
    console.error('导出失败:', error)
    alert('导出失败')
  }
}

// 系统状态检查
const checkSystemStatus = async () => {
  try {
    const response = await fetch('/api/system/status')
    if (response.ok) {
      const status = await response.json()
      Object.assign(systemStatus, status)
    }
  } catch (error) {
    console.error('获取系统状态失败:', error)
  }
}

onMounted(() => {
  loadAlertRules()
  checkSystemStatus()
  setInterval(checkSystemStatus, 30000)
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

.settings-container {
  position: fixed;
  left: 0;
  top: 90px; /* 从header（80px高度）下方10px开始 */
  bottom: 60px; /* 距离底部状态栏（50px高度）留出10px间距 */
  z-index: 200;
  height: auto; /* 让高度自动计算 */
}

.settings-trigger {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 60px;
  background: linear-gradient(45deg, var(--primary), rgba(79, 209, 197, 0.3));
  border-radius: 0 8px 8px 0;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.settings-trigger:hover {
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

.settings-trigger:hover .trigger-icon {
  opacity: 1;
}

.gear-icon {
  font-size: 16px;
  line-height: 1;
}

.trigger-text {
  font-size: 10px;
  margin-top: 2px;
  white-space: nowrap;
}

.settings-sidebar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0; /* 使用bottom定位而不是设置固定高度 */
  width: 420px;
  background: linear-gradient(135deg, 
    rgba(10, 25, 47, 0.95) 0%, 
    rgba(15, 35, 65, 0.95) 50%,
    rgba(20, 45, 80, 0.95) 100%);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(79, 209, 197, 0.2);
  border-left: none;
  border-radius: 0 12px 12px 0;
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
  right: 60px;
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
  height: calc(100% - 60px); /* 减去header高度 */
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

.settings-section {
  margin-bottom: 0;
  border-bottom: 1px solid rgba(79, 209, 197, 0.1);
  padding: 20px;
}

.settings-section:last-child {
  border-bottom: none;
  padding-bottom: 40px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 15px 0;
  cursor: pointer;
  transition: all 0.3s ease;
  border-radius: 8px;
  padding: 15px;
  margin: -15px 0 15px 0;
}

.section-header:hover {
  background: rgba(79, 209, 197, 0.05);
}

.section-icon {
  font-size: 16px;
  margin-right: 8px;
}

.section-header h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 500;
  flex: 1;
  display: flex;
  align-items: center;
}

.section-toggle {
  transition: transform 0.3s ease;
}

.section-toggle.expanded {
  transform: rotate(180deg);
}

.toggle-icon {
  color: var(--text-secondary);
  font-size: 18px;
}

.section-content {
  overflow: hidden;
  transition: all 0.3s ease;
}

.settings-section h4 {
  margin: 0 0 20px 0;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 500;
  display: flex;
  align-items: center;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(79, 209, 197, 0.2);
}

.rule-form {
  margin-bottom: 30px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
}

.cyber-input, 
.cyber-textarea, 
.cyber-select,
.form-input,
.form-select {
  width: 100%;
  padding: 12px 16px;
  background: rgba(79, 209, 197, 0.1) !important;
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 8px;
  color: var(--text-primary) !important;
  font-size: 14px;
  transition: all 0.3s ease;
  box-sizing: border-box;
  max-width: 100%;
}

/* 修复下拉框选项样式 */
.form-select option {
  background: rgba(20, 45, 80, 0.95) !important;
  color: white !important;
  padding: 8px 12px;
}

.cyber-select option {
  background: rgba(20, 45, 80, 0.95) !important;
  color: white !important;
  padding: 8px 12px;
}

/* 为select元素添加更强制的样式 */
select.form-select,
select.cyber-select {
  -webkit-appearance: none;
  -moz-appearance: none;
  appearance: none;
  background-image: url("data:image/svg+xml;charset=utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 4 5'%3E%3Cpath fill='%234fd1c5' d='M2 0L0 2h4zm0 5L0 3h4z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  background-size: 12px;
  padding-right: 40px;
}

.cyber-input:focus, 
.cyber-textarea:focus, 
.cyber-select:focus,
.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(79, 209, 197, 0.2);
  background: rgba(79, 209, 197, 0.15);
}

.cyber-textarea {
  resize: vertical;
  min-height: 80px;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.toggle-switch {
  display: flex;
  align-items: center;
}

.toggle-switch input[type="checkbox"] {
  opacity: 0;
  width: 0;
  height: 0;
}

.switch-label {
  position: relative;
  display: inline-block;
  width: 50px;
  height: 24px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.switch-button {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  transition: all 0.3s ease;
}

.toggle-switch input[type="checkbox"]:checked + .switch-label {
  background: var(--primary);
}

.toggle-switch input[type="checkbox"]:checked + .switch-label .switch-button {
  transform: translateX(26px);
}

.cyber-btn, .btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  text-decoration: none;
  min-width: 120px;
  box-sizing: border-box;
}

.cyber-btn.primary, .btn-primary {
  background: linear-gradient(45deg, var(--primary), rgba(79, 209, 197, 0.8));
  color: white;
  box-shadow: 0 0 15px rgba(79, 209, 197, 0.3);
}

.cyber-btn.primary:hover, .btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 20px rgba(79, 209, 197, 0.4);
}

.cyber-btn.secondary, .btn-secondary {
  background: rgba(79, 209, 197, 0.1);
  color: var(--primary);
  border: 1px solid rgba(79, 209, 197, 0.3);
}

.cyber-btn.secondary:hover, .btn-secondary:hover {
  background: rgba(79, 209, 197, 0.2);
}

.btn-success {
  background: var(--success);
  color: white;
}

.btn-success:hover {
  background: #38a169;
}

.btn-danger {
  background: var(--error);
  color: white;
}

.btn-danger:hover {
  background: #e53e3e;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
  min-width: auto;
}

.cyber-btn:disabled, .btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.btn-icon {
  margin-right: 8px;
  font-size: 16px;
}

.rules-list {
  margin-top: 20px;
}

.rule-item {
  background: rgba(79, 209, 197, 0.05);
  border: 1px solid rgba(79, 209, 197, 0.2);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 15px;
  transition: all 0.3s ease;
}

.rule-item.disabled {
  opacity: 0.6;
  background: rgba(255, 255, 255, 0.02);
}

.rule-item.system-rule {
  border-color: rgba(72, 187, 120, 0.3);
  background: rgba(72, 187, 120, 0.05);
}

.rule-item.custom-rule {
  border-color: rgba(79, 209, 197, 0.3);
  background: rgba(79, 209, 197, 0.05);
}

.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.rule-name {
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  flex: 1;
}

.system-badge {
  background: var(--success);
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 10px;
  margin-right: 8px;
}

.custom-badge {
  background: var(--primary);
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 10px;
  margin-right: 8px;
}

.rule-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  color: white;
}

.action-btn.enabled {
  background: var(--success);
}

.action-btn.disabled {
  background: rgba(255, 255, 255, 0.2);
}

.action-btn.edit {
  background: var(--warning);
}

.action-btn.delete {
  background: var(--error);
}

.action-btn:hover {
  transform: translateY(-1px);
}

.rule-condition {
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 12px;
  line-height: 1.5;
}

.rule-meta {
  display: flex;
  gap: 15px;
  font-size: 12px;
}

.rule-level {
  padding: 4px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.rule-level.low {
  background: rgba(237, 137, 54, 0.2);
  color: #ed8936;
}

.rule-level.medium {
  background: rgba(79, 209, 197, 0.2);
  color: var(--primary);
}

.rule-level.high {
  background: rgba(245, 101, 101, 0.2);
  color: #f56565;
}

.rule-status, .rule-type {
  color: var(--text-secondary);
}

.empty-rules {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-text {
  font-size: 16px;
  margin-bottom: 8px;
  color: var(--text-primary);
}

.empty-hint {
  font-size: 14px;
  opacity: 0.7;
}

/* 摄像头管理样式 */
.camera-status {
  background: rgba(79, 209, 197, 0.1);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 20px;
}

.status-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.status-item:last-child {
  margin-bottom: 0;
}

.status-label {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9em;
}

.status-value {
  color: var(--primary);
  font-weight: 500;
}

.camera-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #ff4444;
  box-shadow: 0 0 8px rgba(255, 68, 68, 0.5);
}

.camera-indicator.active {
  background-color: var(--primary);
  box-shadow: 0 0 8px rgba(79, 209, 197, 0.5);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.camera-add-section {
  margin-bottom: 30px;
}

.camera-config {
  margin-top: 15px;
}

.form-row {
  display: flex;
  gap: 15px;
}

.form-row .form-group {
  flex: 1;
}

.camera-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.camera-preview {
  margin: 20px 0;
  padding: 15px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
}

.preview-container {
  text-align: center;
}

.preview-video {
  width: 100%;
  max-width: 300px;
  height: auto;
  border-radius: 8px;
  margin-bottom: 10px;
}

.preview-controls {
  margin-top: 10px;
}

.camera-list h4 {
  margin-bottom: 15px;
  color: var(--text-primary);
}

.empty-state {
  text-align: center;
  padding: 30px;
  color: var(--text-secondary);
}

.camera-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: rgba(79, 209, 197, 0.05);
  border: 1px solid rgba(79, 209, 197, 0.2);
  border-radius: 8px;
  margin-bottom: 10px;
}

.camera-info {
  flex: 1;
}

.camera-name {
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 5px;
}

.camera-details {
  display: flex;
  gap: 15px;
  font-size: 12px;
  color: var(--text-secondary);
}

.camera-controls {
  display: flex;
  gap: 5px;
}

/* 导出功能样式 */
.export-options {
  margin-top: 20px;
}

.date-range {
  display: flex;
  gap: 15px;
  margin: 15px 0;
}

.date-range .form-group {
  flex: 1;
}

.export-buttons {
  display: flex;
  gap: 15px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.export-buttons .cyber-btn {
  flex: 1;
  min-width: 150px;
}

/* 系统状态样式 */
.system-status {
  margin-top: 20px;
}

.system-status .status-value.online {
  color: var(--success);
}

.system-status .status-value.offline {
  color: var(--error);
}

.system-status .status-value.warning {
  color: var(--warning);
}

/* 动画效果 */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.3s ease;
}

.slide-right-enter-from {
  transform: translateX(-100%);
}

.slide-right-leave-to {
  transform: translateX(-100%);
}

/* 响应式调整 */
@media (max-width: 768px) {
  .settings-sidebar {
    width: 100vw;
    border-radius: 0;
  }
  
  .export-buttons {
    flex-direction: column;
  }
  
  .export-buttons .cyber-btn {
    width: 100%;
  }
}
</style> 