<template>
  <div class="qa-panel-container">
    <div class="panel-title">
      <div class="status-indicator" :class="{ 'connected': isConnected }"></div>
      <span>智能问答</span>
    </div>
    <div class="qa-content">
      <div class="chat-history" ref="chatHistoryRef">
        <div v-for="msg in filteredMessages" :key="msg.id" class="chat-message-container" :class="{ 'user-message': msg.sender === 'user' }">
          <div class="avatar" :class="msg.sender">
            <span class="avatar-icon">{{ getAvatarIcon(msg.sender) }}</span>
          </div>
          <div class="message-bubble" :class="`bubble-${msg.sender}`">
            <div class="message-sender">{{ getSenderName(msg.sender) }}</div>
            <div class="message-text">{{ msg.text }}</div>
          </div>
        </div>
      </div>
      <div class="qa-decoration left-circuit"></div>
      <div class="qa-decoration right-circuit"></div>
      <div class="qa-glow"></div>
      <div class="qa-data-points">
        <div class="data-point"></div>
        <div class="data-point"></div>
        <div class="data-point"></div>
      </div>
      <div class="input-hint"></div>
    </div>
    <div class="chat-input-area">
      <input type="text" v-model="userInput" @keyup.enter="sendMessage" placeholder="输入您的问题..." class="chat-input">
      <button @click="sendMessage" class="send-button">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, computed } from 'vue';

const userInput = ref('');
const chatHistoryRef = ref(null);
const messages = ref([]);
const isConnected = ref(false);

// RAG服务器地址
const RAG_SERVER_URL = 'http://localhost:8085';

// 过滤掉系统连接消息
const filteredMessages = computed(() => {
  return messages.value.filter(msg => 
    !(msg.sender === 'system' && msg.text.includes('已连接到智能问答系统')));
});

// 获取头像图标
const getAvatarIcon = (sender) => {
  switch (sender) {
    case 'user': return '👤'; // 用户图标
    case 'ai': return '🤖'; // AI机器人图标
    case 'system': return '⚙️'; // 系统设置图标
    default: return '?';
  }
};

// 发送消息
const sendMessage = async () => {
  if (userInput.value.trim()) {
    // 添加用户消息到列表
    const userMessage = {
      id: Date.now(),
      sender: 'user',
      text: userInput.value.trim()
    };
    messages.value.push(userMessage);
    
    const query = userInput.value.trim();
    userInput.value = ''; // 清空输入框
    
    try {
      // 添加等待消息
      const waitingId = Date.now() + 1;
      messages.value.push({
        id: waitingId,
        sender: 'system',
        text: '正在思考...'
      });
      
      // 发送到RAG服务器
      const response = await fetch(`${RAG_SERVER_URL}/search/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: query,
          k: 3
        })
      });
      
      if (!response.ok) {
        throw new Error(`服务器返回错误: ${response.status}`);
      }
      
      const data = await response.json();
      
      // 移除等待消息
      messages.value = messages.value.filter(msg => msg.id !== waitingId);
      
      // 添加AI回复
      if (data && data.status === 'success') {
        messages.value.push({
          id: Date.now() + 2,
          sender: 'ai',
          text: data.answer
        });
      } else {
        throw new Error('服务器返回错误数据');
      }
    } catch (error) {
      console.error('发送消息错误:', error);
      // 移除等待消息
      messages.value = messages.value.filter(msg => msg.id !== messages.value.find(m => m.sender === 'system')?.id);
      
      messages.value.push({
        id: Date.now() + 3,
        sender: 'system',
        text: '无法发送消息，请检查连接。'
      });
    }
  }
};

// 检查RAG服务器连接
const checkConnection = async () => {
  try {
    // 尝试连接RAG服务器
    const response = await fetch(`${RAG_SERVER_URL}/search/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        query: "测试连接",
        k: 1
      })
    });
    
    if (response.ok) {
      isConnected.value = true;
      messages.value.push({
        id: Date.now(),
        sender: 'system',
        text: '已连接到智能问答系统，请输入您的问题。'
      });
    } else {
      throw new Error('服务器状态异常');
    }
  } catch (error) {
    console.error('连接RAG服务器失败:', error);
    isConnected.value = false;
    messages.value.push({
      id: Date.now(),
      sender: 'system',
      text: '无法连接到智能问答系统，请检查服务器状态。'
    });
  }
};

// 获取发送者名称
const getSenderName = (sender) => {
  switch (sender) {
    case 'user': return '您';
    case 'ai': return '助手';
    case 'system': return '系统';
    default: return sender;
  }
};

// 组件挂载时检查连接
onMounted(() => {
  checkConnection();
});

// 监听消息变化，自动滚动到底部
watch(messages, async () => {
  await nextTick(); // 等待 DOM 更新完成
  if (chatHistoryRef.value) {
    chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight;
  }
}, { deep: true }); // 深度监听数组内部变化
</script>

<style scoped>
/* 智能问答面板特定样式 */
.qa-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column; /* 准备放置聊天记录和输入框 */
  overflow: hidden; /* 防止内容溢出面板 */
  position: relative;
}

.chat-history {
  flex-grow: 1; /* 占据大部分空间 */
  overflow-y: auto; /* 允许滚动 */
  padding: 10px;
  margin-bottom: 10px;
  background-color: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  position: relative;
  z-index: 2;
}

.chat-message-container {
  display: flex;
  margin-bottom: 16px;
  align-items: flex-start;
}

.user-message {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  flex-shrink: 0;
  margin: 0 8px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 18px;
}

.avatar-icon {
  line-height: 1;
}

.avatar.user {
  background-color: rgba(79, 209, 197, 0.2);
  border: 1px solid var(--primary, #4fd1c5);
}

.avatar.ai {
  background-color: rgba(128, 90, 213, 0.2);
  border: 1px solid var(--cyber-purple, #805ad5);
}

.avatar.system {
  background-color: rgba(255, 204, 0, 0.2);
  border: 1px solid var(--warning, #ffcc00);
}

.message-bubble {
  padding: 10px 12px;
  border-radius: 12px;
  position: relative;
  max-width: 80%;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.bubble-user {
  background-color: rgba(79, 209, 197, 0.15);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-top-right-radius: 2px;
  margin-right: 10px;
}

.bubble-ai {
  background-color: rgba(128, 90, 213, 0.15);
  border: 1px solid rgba(128, 90, 213, 0.3);
  border-top-left-radius: 2px;
  margin-left: 10px;
}

.bubble-system {
  background-color: rgba(255, 204, 0, 0.1);
  border: 1px solid rgba(255, 204, 0, 0.3);
  border-top-left-radius: 2px;
  margin-left: 10px;
}

.message-sender {
  font-size: 0.8em;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--text-secondary);
}

.message-text {
  word-break: break-word;
  line-height: 1.4;
}

.chat-input-area {
  display: flex;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--panel-border, #2d3748);
  position: relative;
  z-index: 2;
}

.chat-input {
  flex-grow: 1;
  padding: 8px 12px;
  border: 1px solid var(--panel-border, #2d3748);
  border-radius: 4px;
  background-color: rgba(0, 0, 0, 0.2);
  color: var(--text-primary, #e6f1ff);
  font-size: 0.95em;
}

.chat-input:focus {
  outline: none;
  border-color: var(--primary, #4fd1c5);
  box-shadow: 0 0 0 2px rgba(79, 209, 197, 0.3);
}

.send-button {
  padding: 8px 15px;
  background: linear-gradient(135deg, var(--primary, #4fd1c5) 0%, var(--cyber-blue, #0088ff) 100%);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s ease;
}

.send-button:hover {
  opacity: 0.9;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
}

.send-button:active {
  opacity: 1;
  transform: translateY(1px);
}

/* 滚动条美化 (可选) */
.chat-history::-webkit-scrollbar {
  width: 6px;
}
.chat-history::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}
.chat-history::-webkit-scrollbar-thumb {
  background-color: var(--primary, #4fd1c5);
  border-radius: 3px;
}

/* 问答面板装饰 */
.qa-decoration {
  position: absolute;
  pointer-events: none;
  z-index: 1;
}

.left-circuit {
  left: 0;
  top: 30%;
  width: 15px;
  height: 40%;
  border-left: 1px solid var(--cyber-neon);
  border-bottom: 1px solid var(--cyber-neon);
  opacity: 0.4;
}

.right-circuit {
  right: 0;
  top: 20%;
  width: 15px;
  height: 30%;
  border-right: 1px solid var(--cyber-purple);
  border-top: 1px solid var(--cyber-purple);
  opacity: 0.4;
}

/* 发光效果 */
.qa-glow {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 80%;
  height: 2px;
  background: linear-gradient(90deg, 
    transparent, 
    var(--cyber-neon), 
    var(--cyber-purple), 
    transparent);
  filter: blur(2px);
  opacity: 0.6;
  animation: qaGlowPulse 4s infinite;
  pointer-events: none;
  z-index: 1;
}

@keyframes qaGlowPulse {
  0%, 100% { opacity: 0.3; width: 70%; }
  50% { opacity: 0.6; width: 90%; }
}

/* 数据点 */
.qa-data-points {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  gap: 5px;
  pointer-events: none;
  z-index: 1;
}

.qa-data-points .data-point {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background-color: var(--cyber-neon);
  opacity: 0.7;
  animation: dataPointBlink 3s infinite;
}

.qa-data-points .data-point:nth-child(2) {
  animation-delay: 1s;
}

.qa-data-points .data-point:nth-child(3) {
  animation-delay: 2s;
}

@keyframes dataPointBlink {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}

/* 修改面板标题样式，使其与其他面板一致 */
.panel-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 15px;
  color: var(--primary, #4fd1c5);
  border-bottom: 1px solid rgba(79, 209, 197, 0.5);
  padding-bottom: 8px;
  display: flex;
  align-items: center;
  letter-spacing: 1px;
  text-shadow: 0 0 5px rgba(79, 209, 197, 0.3);
  cursor: move; /* 确保显示为可拖动状态 */
  user-select: none; /* 防止文本选择干扰拖拽 */
}

.panel-title::before {
  content: "⋮⋮";
  margin-right: 8px;
  opacity: 0.5;
  font-size: 14px;
}

.panel-title:hover::before {
  opacity: 1;
}

.header-content {
  display: flex;
  align-items: center;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 10px;
  background-color: #ff4d4d; /* 默认红色 */
  box-shadow: 0 0 8px rgba(255, 77, 77, 0.7);
  animation: breathingLightRed 3s infinite ease-in-out;
}

.status-indicator.connected {
  background-color: #4fd1c5; /* 连接时绿色 */
  box-shadow: 0 0 8px rgba(79, 209, 197, 0.7);
  animation: breathingLightGreen 3s infinite ease-in-out;
}

@keyframes breathingLightRed {
  0%, 100% {
    opacity: 0.5;
    box-shadow: 0 0 5px rgba(255, 77, 77, 0.5);
  }
  50% {
    opacity: 1;
    box-shadow: 0 0 12px rgba(255, 77, 77, 0.9);
  }
}

@keyframes breathingLightGreen {
  0%, 100% {
    opacity: 0.5;
    box-shadow: 0 0 5px rgba(79, 209, 197, 0.5);
  }
  50% {
    opacity: 1;
    box-shadow: 0 0 12px rgba(79, 209, 197, 0.9);
  }
}

/* 添加容器样式 */
.qa-panel-container {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 修改聊天内容区域样式，使其占据全部空间 */
.qa-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  height: calc(100% - 60px);
  padding-bottom: 15px;
}

/* 输入框区域样式 */
.chat-input-area {
  display: flex;
  gap: 10px;
  padding: 12px;
  background-color: rgba(10, 25, 47, 0.5);
  border-radius: 6px 6px 0 0;
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  transform: translateY(100%);
  transition: transform 0.3s ease;
  z-index: 10;
  box-shadow: 0 -5px 15px rgba(0, 0, 0, 0.3);
}

/* 输入提示动画 */
.input-hint {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 50px;
  height: 3px;
  background: linear-gradient(90deg, transparent, var(--cyber-neon), transparent);
  border-radius: 3px;
  opacity: 0.7;
  animation: hintPulse 2s infinite;
  pointer-events: none;
}

@keyframes hintPulse {
  0%, 100% { width: 30px; opacity: 0.5; }
  50% { width: 50px; opacity: 0.8; }
}

/* 当鼠标靠近底部时显示输入框 */
.qa-panel-container:hover .chat-input-area {
  transform: translateY(0);
}

/* 鼠标靠近底部时隐藏提示 */
.qa-panel-container:hover .input-hint {
  opacity: 0;
}

/* 滚动条美化 - 保持现有样式 */
</style> 