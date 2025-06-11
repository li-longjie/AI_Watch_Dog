<template>
  <div class="panel panel-custom qa-panel grid-area-right" style="width: 100%; height: 100%; position: relative;">
    <div class="qa-panel-container">
      <div class="panel-title">
        <div class="status-indicator"></div>
        <span>智能语音</span>
      </div>
      <div class="qa-content">
        <div class="chat-history">
          <div v-for="(item, index) in conversationHistory" :key="index" 
               class="chat-message-container">
            <div :class="['avatar', item.type]">
              <span class="avatar-icon">
                {{ item.type === 'user' ? '👤' : item.type === 'ai' ? '🤖' : '⚙️' }}
              </span>
            </div>
            <div :class="['message-bubble', `bubble-${item.type}`]">
              <div class="message-text">{{ item.text }}</div>
              <div class="message-time">{{ item.time }}</div>
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
      <div class="voice-controls">
        <div class="recording-status-text">
          {{ isProcessing ? '正在处理语音...' : isRecording ? '正在聆听...' : '语音输入未激活' }}
        </div>
        <div class="voice-buttons-container">
          <button v-if="!isRecording && !isProcessing" @click="startRecording" class="voice-button">聆听</button>
          <button v-if="isRecording && !isProcessing" @click="stopRecording" class="control-button">停止</button>
          <button v-if="isProcessing" disabled class="control-button" style="opacity: 0.7; cursor: not-allowed;">处理中...</button>
        </div>
      </div>
      <div class="debug-info" v-if="debugMessage">
        <strong>调试信息:</strong> {{ debugMessage }}
      </div>
    </div>
    <!-- 移除了拖拽手柄，因为目前无法实现拖拽功能 -->
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import axios from 'axios';

const isRecording = ref(false);
let mediaRecorder = null;
let audioChunks = ref([]);
const conversationHistory = ref([
  { type: 'system', text: '欢迎使用智能语音助手！', time: '10:00 AM' },
  { type: 'user', text: '你好，请问你是谁？', time: '10:01 AM' },
  { type: 'ai', text: '我叫千问，是一个18岁的女大学生，性格活泼开朗，说话俏皮！很高兴认识你！', time: '10:01 AM' },
  { type: 'user', text: '太棒了！', time: '10:02 AM' }
]);
const isProcessing = ref(false);
const debugMessage = ref('等待麦克风初始化...');

// 初始化录音功能
const initRecording = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/wav' });
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.value.push(event.data);
        debugMessage.value = `收到音频块, 大小: ${event.data.size}, 总块数: ${audioChunks.value.length}`;
      }
    };

    mediaRecorder.onstop = async () => {
      debugMessage.value = `录音停止. 总音频块数: ${audioChunks.value.length}`;
      if (audioChunks.value.length > 0) {
        const audioBlob = new Blob(audioChunks.value, { type: 'audio/wav' });
        debugMessage.value += `, Blob 大小: ${audioBlob.size} 字节`;
        await processAudio(audioBlob);
        audioChunks.value = []; // 清空音频块以便下一次录音
      } else {
        debugMessage.value = '录音停止，但未收集到音频块。';
        addToHistory('system', '没有检测到语音输入。');
      }
    };

    addToHistory('system', '智能语音已启动，等待聆听...');
    debugMessage.value = '智能语音已启动，等待聆听...';

  } catch (error) {
    debugMessage.value = `无法访问麦克风: ${error.message}`; 
    addToHistory('system', '无法访问麦克风，请确保已授予权限。' + error.message);
    isRecording.value = false;
  }
};

// 开始录音
const startRecording = () => {
  if (mediaRecorder && mediaRecorder.state !== 'recording') {
    audioChunks.value = [];
    mediaRecorder.start();
    isRecording.value = true;
    addToHistory('system', '正在聆听...');
    debugMessage.value = '正在聆听...';
  }
};

// 停止录音
const stopRecording = () => {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    isRecording.value = false;
    addToHistory('system', '录音已停止，正在处理...');
    debugMessage.value = '录音已停止，正在处理...';
  }
};

// 处理音频数据
const processAudio = async (audioBlob) => {
  debugMessage.value = '开始处理音频...';
  isProcessing.value = true;
  const tempUserMessageIndex = addToHistory('user', '正在识别语音...');

  try {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.wav');

    const response = await axios.post('http://localhost:5000/api/voice/process', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });

    // 更新用户语音识别结果
    if (response.data.userText) {
      removeOrUpdateHistory(tempUserMessageIndex, response.data.userText, 'user');
      debugMessage.value = `ASR 结果: ${response.data.userText}`;
    } else {
      removeOrUpdateHistory(tempUserMessageIndex, '未能识别语音内容', 'system');
      debugMessage.value = '未能识别语音内容。';
    }

    // 添加AI响应
    if (response.data.aiResponse) {
      addToHistory('ai', response.data.aiResponse);
      debugMessage.value += `, AI 回答: ${response.data.aiResponse}`;
    }

    // 播放AI语音响应
    if (response.data.audioUrl) {
      const audio = new Audio(`http://localhost:5000${response.data.audioUrl}`);
      audio.play().catch(e => {
        console.error('音频播放失败:', e);
        debugMessage.value += ', 音频播放失败。';
      });
      debugMessage.value += ', 播放 AI 语音。';
    }
  } catch (error) {
    debugMessage.value = `处理音频时出错: ${error.message}`;
    removeOrUpdateHistory(tempUserMessageIndex, '处理语音时出错，请重试。' + error.message, 'system');
  } finally {
    isProcessing.value = false;
  }
};

// 添加消息到对话历史并返回索引
const addToHistory = (type, text) => {
  const now = new Date();
  const time = now.toLocaleTimeString();
  conversationHistory.value.push({
    type,
    text,
    time
  });
  return conversationHistory.value.length - 1; // 返回新添加消息的索引
};

// 移除或更新对话历史中的消息
const removeOrUpdateHistory = (index, newText, newType) => {
    if (index >= 0 && index < conversationHistory.value.length) {
        if (newText) {
            // 更新消息内容和类型
            conversationHistory.value[index].text = newText;
            conversationHistory.value[index].type = newType;
             // 更新时间戳
            const now = new Date();
            conversationHistory.value[index].time = now.toLocaleTimeString();
        } else {
            // 如果没有新文本，则移除消息 (可选，取决于交互设计)
            // conversationHistory.value.splice(index, 1);
        }
    }
};

// 组件挂载时自动开始录音功能初始化
onMounted(() => {
  initRecording();
});

// 组件卸载时清理资源
onUnmounted(() => {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }
  if (mediaRecorder && mediaRecorder.stream) {
    mediaRecorder.stream.getTracks().forEach(track => track.stop());
  }
});
</script>

<style scoped>
.panel, .panel-custom, .qa-panel, .grid-area-right {
  /* Basic panel styles from QAPanel */
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-radius: 8px;
  background-color: var(--panel-bg, #172a45);
  overflow: hidden;
  box-shadow: 0 0 20px rgba(79, 209, 197, 0.1);
}

.qa-panel-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.panel-title {
  padding: 15px 20px;
  background-color: var(--panel-bg, #172a45);
  border-bottom: 1px solid rgba(79, 209, 197, 0.3);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.1em;
  font-weight: 500;
  color: var(--primary, #4fd1c5);
  text-shadow: 0 0 10px rgba(79, 209, 197, 0.3);
}

.status-indicator {
  width: 8px;
  height: 8px;
  background-color: var(--primary, #4fd1c5);
  border-radius: 50%;
  animation: pulse 2s infinite;
}

.qa-content {
  flex: 1;
  padding: 20px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding-right: 10px;
}

.chat-message-container {
  display: flex;
  margin-bottom: 20px;
  align-items: flex-start;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  flex-shrink: 0;
}

.avatar.user {
  background: rgba(79, 209, 197, 0.2);
  border: 1px solid rgba(79, 209, 197, 0.4);
}

.avatar.ai {
  background: rgba(79, 209, 197, 0.1);
  border: 1px solid rgba(79, 209, 197, 0.3);
}

.avatar.system {
  background: rgba(255, 77, 77, 0.1);
  border: 1px solid rgba(255, 77, 77, 0.3);
}

.message-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 8px;
  position: relative;
}

.bubble-user {
  background: rgba(79, 209, 197, 0.1);
  border: 1px solid rgba(79, 209, 197, 0.3);
  margin-left: auto;
}

.bubble-ai {
  background: rgba(79, 209, 197, 0.05);
  border: 1px solid rgba(79, 209, 197, 0.2);
}

.bubble-system {
  background: rgba(255, 77, 77, 0.1);
  border: 1px solid rgba(255, 77, 77, 0.3);
  margin: 0 auto;
}

.message-text {
  margin-bottom: 5px;
  line-height: 1.4;
}

.message-time {
  font-size: 0.8em;
  color: rgba(230, 241, 255, 0.6);
  text-align: right;
}

.voice-controls {
  padding: 10px 20px;
  text-align: center;
  background-color: var(--panel-bg, #172a45);
  border-top: 1px solid rgba(79, 209, 197, 0.3);
  color: var(--primary, #4fd1c5);
  font-size: 1em;
}

.recording-status-text {
    /* Styles for the status text */
}

.voice-buttons-container {
  display: flex;
  justify-content: center;
  gap: 15px;
  margin-top: 15px; /* 按钮和状态文本之间留点空间 */
}

.voice-button, .control-button {
  padding: 12px 25px;
  border: none;
  border-radius: 25px;
  cursor: pointer;
  transition: background-color 0.3s ease, transform 0.2s ease;
  font-size: 1em;
  font-weight: bold;
  text-transform: uppercase;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
}

.voice-button {
  background-color: var(--primary, #4fd1c5);
  color: #000; /* 与背景色对比更明显 */
}

.voice-button:hover {
  background-color: #3aa89f;
  transform: translateY(-2px);
}

.control-button {
  background-color: #e74c3c; /* 停止按钮使用红色系 */
  color: #fff;
}

.control-button:hover {
  background-color: #c0392b;
  transform: translateY(-2px);
}

/* 装饰元素 */
.qa-decoration {
  position: absolute;
  width: 100px;
  height: 100px;
  pointer-events: none;
}

.left-circuit {
  top: 20px;
  left: 20px;
  border-left: 1px solid rgba(79, 209, 197, 0.2);
  border-top: 1px solid rgba(79, 209, 197, 0.2);
}

.right-circuit {
  bottom: 20px;
  right: 20px;
  border-right: 1px solid rgba(79, 209, 197, 0.2);
  border-bottom: 1px solid rgba(79, 209, 197, 0.2);
}

.qa-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(79, 209, 197, 0.1) 0%, transparent 70%);
  pointer-events: none;
}

.qa-data-points {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.data-point {
  position: absolute;
  width: 4px;
  height: 4px;
  background-color: var(--primary, #4fd1c5);
  border-radius: 50%;
  animation: float 3s infinite;
}

.data-point:nth-child(1) {
  top: 20%;
  left: 10%;
  animation-delay: 0s;
}

.data-point:nth-child(2) {
  top: 50%;
  right: 15%;
  animation-delay: 1s;
}

.data-point:nth-child(3) {
  bottom: 30%;
  left: 20%;
  animation-delay: 2s;
}

.input-hint {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--primary, #4fd1c5), transparent);
  opacity: 0.5;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

/* 滚动条样式 */
.chat-history::-webkit-scrollbar {
  width: 6px;
}

.chat-history::-webkit-scrollbar-track {
  background: rgba(79, 209, 197, 0.1);
  border-radius: 3px;
}

.chat-history::-webkit-scrollbar-thumb {
  background: rgba(79, 209, 197, 0.3);
  border-radius: 3px;
}

.chat-history::-webkit-scrollbar-thumb:hover {
  background: rgba(79, 209, 197, 0.5);
}

/* 麦克风和发送按钮容器，以及麦克风和停止按钮样式 */
.chat-input-area {
  display: none; 
}

.debug-info {
  margin-top: 20px;
  padding: 10px;
  background-color: rgba(255, 255, 0, 0.1); /* 柔和的黄色背景 */
  border: 1px solid rgba(255, 255, 0, 0.3);
  border-radius: 5px;
  color: #fff;
  font-size: 0.9em;
  word-wrap: break-word;
}
</style> 