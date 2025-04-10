<template>
  <div>
    <div class="panel-title">智能问答</div>
    <div class="qa-content">
      <div class="chat-history" ref="chatHistoryRef">
        <div v-for="msg in messages" :key="msg.id" :class="['chat-message', `message-${msg.sender}`]">
          <span class="message-sender">{{ getSenderName(msg.sender) }}:</span>
          <span class="message-text">{{ msg.text }}</span>
        </div>
      </div>
      <div class="chat-input-area">
        <input type="text" v-model="userInput" @keyup.enter="sendMessage" placeholder="输入您的问题..." class="chat-input">
        <button @click="sendMessage" class="send-button">发送</button>
      </div>
      <div class="qa-decoration left-circuit"></div>
      <div class="qa-decoration right-circuit"></div>
      <div class="qa-glow"></div>
      <div class="qa-data-points">
        <div class="data-point"></div>
        <div class="data-point"></div>
        <div class="data-point"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, defineProps, defineEmits } from 'vue';

const props = defineProps({
  messages: {
    type: Array,
    required: true,
    default: () => []
  }
});

const emit = defineEmits(['send-message']);

const userInput = ref('');
const chatHistoryRef = ref(null); // 用于获取聊天记录 DOM 元素

// 发送消息
const sendMessage = () => {
  if (userInput.value.trim()) {
    emit('send-message', userInput.value);
    userInput.value = ''; // 清空输入框
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

// 监听消息变化，自动滚动到底部
watch(() => props.messages, async () => {
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

.chat-message {
  margin-bottom: 8px;
  line-height: 1.5;
  font-size: 0.95em;
}

.message-user {
  color: var(--primary, #4fd1c5); /* 用户消息颜色 */
  text-align: right; /* 用户消息靠右 */
}

.message-ai {
  color: var(--text-primary, #e6f1ff); /* AI 消息颜色 */
}

.message-system {
  color: var(--text-secondary, #8892b0); /* 系统消息颜色 */
  font-style: italic;
  font-size: 0.9em;
}

.message-sender {
  font-weight: 600;
  margin-right: 5px;
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
</style> 