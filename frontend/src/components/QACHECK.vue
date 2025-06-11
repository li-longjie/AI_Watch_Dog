<template>
  <div class="qa-panel-container">
    <div class="panel-title">
      <div class="status-indicator" :class="{ 'connected': isConnected }"></div>
      <span>AI智能体</span>
    </div>
    <div class="qa-content">
      <div class="chat-history" ref="chatHistoryRef">
        <div v-for="msg in filteredMessages" :key="msg.id" class="chat-message-container" :class="{ 'user-message': msg.sender === 'user' }">
          <div class="avatar" :class="msg.sender">
            <span class="avatar-icon">{{ getAvatarIcon(msg.sender) }}</span>
          </div>
          <div class="message-bubble" :class="`bubble-${msg.sender}`">
            <div v-if="msg.sender === 'ai'" class="message-text markdown-content" v-html="renderMarkdown(msg.text)"></div>
            <div v-else class="message-text">{{ msg.text }}</div>
            <div v-if="msg.sender === 'ai'" class="message-actions">
              <button @click="speakMessage(msg.text, msg.id)" class="action-button speak-button" :title="isSpeaking && currentSpeakingId === msg.id ? '停止朗读' : '朗读消息'">
                <span v-if="isSpeaking && currentSpeakingId === msg.id">🔊</span>
                <span v-else>🔈</span>
              </button>
            </div>
          </div>
        </div>
        
        <!-- 思考动画 -->
        <div v-if="isThinking" class="chat-message-container">
          <div class="avatar ai">
            <span class="avatar-icon">🤖</span>
          </div>
          <div class="message-bubble bubble-system thinking-bubble">
            <div class="message-text">
              正在思考<span class="thinking-dots-animated">{{ thinkingDots }}</span>
            </div>
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
      <button @click="toggleVoiceRecognition" class="voice-button" :class="{ 'recording': isRecording }" title="语音输入">
        <span v-if="isRecording">🎙️</span>
        <span v-else>🎤</span>
      </button>
      <button @click="sendMessage" class="send-button">发送</button>
    </div>
    <div v-if="isRecording" class="recording-indicator">
      <div class="recording-waves">
        <div class="wave"></div>
        <div class="wave"></div>
        <div class="wave"></div>
      </div>
      <div class="recording-text">正在聆听... {{ recognizedText }}</div>
      <button @click="stopVoiceRecognition" class="stop-recording-button">停止</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, computed, onUnmounted } from 'vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

const userInput = ref('');
const chatHistoryRef = ref(null);
const messages = ref([]);
const isConnected = ref(false);
const isRecording = ref(false);
const recognizedText = ref('');
const isSpeaking = ref(false);
const currentSpeakingId = ref(null);
const isThinking = ref(false);
const thinkingDots = ref("");

// 语音识别相关
const audioContext = ref(null);
const mediaRecorder = ref(null);
const audioChunks = ref([]);
const audioStream = ref(null);
const whisperWebSocket = ref(null);
const whisperConnected = ref(false);
const WHISPER_SERVER_URL = 'ws://localhost:8086/ws/';
const WHISPER_API_URL = 'http://localhost:8086/transcribe_chunk/';

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

// 初始化WebSocket连接到Whisper服务
const initWhisperWebSocket = () => {
  try {
    whisperWebSocket.value = new WebSocket(WHISPER_SERVER_URL);
    
    whisperWebSocket.value.onopen = () => {
      console.log('已连接到Whisper WebSocket服务');
      whisperConnected.value = true;
    };
    
    whisperWebSocket.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.transcription) {
          recognizedText.value = data.transcription;
        } else if (data.error) {
          console.error('Whisper错误:', data.error);
        }
      } catch (e) {
        console.error('解析Whisper响应错误:', e);
      }
    };
    
    whisperWebSocket.value.onerror = (error) => {
      console.error('Whisper WebSocket错误:', error);
      whisperConnected.value = false;
    };
    
    whisperWebSocket.value.onclose = () => {
      console.log('Whisper WebSocket连接已关闭');
      whisperConnected.value = false;
    };
  } catch (e) {
    console.error('创建Whisper WebSocket连接错误:', e);
  }
};

// 通过API发送音频数据到Whisper服务
const sendAudioToWhisperAPI = async (audioBlob) => {
  try {
    // 将Blob转换为Base64
    const reader = new FileReader();
    reader.readAsDataURL(audioBlob);
    
    reader.onloadend = async () => {
      const base64Audio = reader.result;
      
      const response = await fetch(WHISPER_API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          audio_data: base64Audio
        })
      });
      
      if (!response.ok) {
        throw new Error(`API返回错误: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.transcription) {
        recognizedText.value = data.transcription;
      }
    };
  } catch (e) {
    console.error('发送音频到Whisper API错误:', e);
  }
};

// 启动音频录制
const startAudioRecording = async () => {
  try {
    // 请求麦克风权限
    audioStream.value = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // 创建AudioContext
    audioContext.value = new (window.AudioContext || window.webkitAudioContext)();
    
    // 创建MediaRecorder
    mediaRecorder.value = new MediaRecorder(audioStream.value);
    audioChunks.value = [];
    
    // 收集音频数据
    mediaRecorder.value.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.value.push(event.data);
      }
    };
    
    // 处理录制停止事件
    mediaRecorder.value.onstop = async () => {
      // 合并音频块
      const audioBlob = new Blob(audioChunks.value, { type: 'audio/wav' });
      
      // 发送到Whisper服务
      if (whisperConnected.value && whisperWebSocket.value) {
        // 将Blob转换为Base64
        const reader = new FileReader();
        reader.readAsDataURL(audioBlob);
        
        reader.onloadend = () => {
          const base64Audio = reader.result;
          whisperWebSocket.value.send(base64Audio);
        };
      } else {
        // 使用API替代WebSocket
        await sendAudioToWhisperAPI(audioBlob);
      }
      
      // 清理AudioStream资源
      if (audioStream.value) {
        audioStream.value.getTracks().forEach(track => track.stop());
      }
    };
    
    // 每5秒发送一次音频数据（实时转录）
    const sendInterval = 5000; // 5秒
    let timerId;
    
    const sendAudioChunk = () => {
      if (audioChunks.value.length > 0 && isRecording.value) {
        const audioBlob = new Blob(audioChunks.value, { type: 'audio/wav' });
        sendAudioToWhisperAPI(audioBlob);
        // 保留最新的一部分数据，确保连贯性
        audioChunks.value = audioChunks.value.slice(-5);
      }
    };
    
    timerId = setInterval(sendAudioChunk, sendInterval);
    
    // 开始录制
    mediaRecorder.value.start(100); // 每100ms收集数据
    isRecording.value = true;
    recognizedText.value = '';
    
    // 清理定时器
    mediaRecorder.value.onresume = () => {
      if (!timerId) {
        timerId = setInterval(sendAudioChunk, sendInterval);
      }
    };
    
    mediaRecorder.value.onpause = () => {
      if (timerId) {
        clearInterval(timerId);
        timerId = null;
      }
    };
    
  } catch (error) {
    console.error('启动音频录制错误:', error);
    isRecording.value = false;
    
    if (error.name === 'NotAllowedError') {
      alert('请允许访问麦克风以使用语音功能');
    } else {
      alert(`无法启动录音: ${error.message}`);
    }
  }
};

// 切换语音识别
const toggleVoiceRecognition = () => {
  if (isRecording.value) {
    stopVoiceRecognition();
  } else {
    startVoiceRecognition();
  }
};

// 开始语音识别
const startVoiceRecognition = () => {
  startAudioRecording();
};

// 停止语音识别
const stopVoiceRecognition = () => {
  if (mediaRecorder.value && isRecording.value) {
    mediaRecorder.value.stop();
    isRecording.value = false;
    
    if (recognizedText.value) {
      userInput.value = recognizedText.value;
    }
  }
};

// 语音合成
let speechSynthesis = window.speechSynthesis;
let speechUtterance = null;

// 朗读消息
const speakMessage = (text, msgId) => {
  if (isSpeaking.value) {
    // 如果正在朗读，则停止
    speechSynthesis.cancel();
    isSpeaking.value = false;
    currentSpeakingId.value = null;
    return;
  }

  // 创建语音合成实例
  speechUtterance = new SpeechSynthesisUtterance(text);
  speechUtterance.lang = 'zh-CN'; // 设置中文
  
  // 监听语音开始和结束事件
  speechUtterance.onstart = () => {
    isSpeaking.value = true;
    currentSpeakingId.value = msgId;
  };
  
  speechUtterance.onend = () => {
    isSpeaking.value = false;
    currentSpeakingId.value = null;
  };
  
  speechUtterance.onerror = (event) => {
    console.error('语音合成错误:', event);
    isSpeaking.value = false;
    currentSpeakingId.value = null;
  };
  
  // 开始朗读
  speechSynthesis.speak(speechUtterance);
};

// 发送消息
const sendMessage = async () => {
  if (userInput.value.trim()) {
    // 如果正在录音，先停止
    if (isRecording.value) {
      stopVoiceRecognition();
    }
    
    // 添加用户消息到列表
    const userMessage = {
      id: Date.now(),
      sender: 'user',
      text: userInput.value.trim()
    };
    messages.value.push(userMessage);
    
    const query = userInput.value.trim();
    userInput.value = ''; // 清空输入框
    
    // 开始显示思考动画
    startThinkingAnimation();
    
    try {
      // 不再添加等待消息，使用思考动画代替
      
      // 使用意图检测API替代原有的搜索API
      const response = await fetch(`${RAG_SERVER_URL}/detect_intent/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: query
        })
      });
      
      // 停止思考动画
      stopThinkingAnimation();
      
      if (!response.ok) {
        throw new Error(`服务器返回错误: ${response.status}`);
      }
      
      const data = await response.json();
      
      // 添加AI回复
      if (data && data.status === 'success') {
        const aiMsgId = Date.now() + 2;
        messages.value.push({
          id: aiMsgId,
          sender: 'ai',
          text: data.answer
        });
        
        // 自动朗读AI回复
        speakMessage(data.answer, aiMsgId);
      } else {
        throw new Error('服务器返回错误数据');
      }
    } catch (error) {
      // 停止思考动画
      stopThinkingAnimation();
      
      console.error('发送消息错误:', error);
      
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
  initWhisperWebSocket();
});

// 组件卸载时清理资源
onUnmounted(() => {
  if (mediaRecorder.value && isRecording.value) {
    mediaRecorder.value.stop();
  }
  
  if (audioStream.value) {
    audioStream.value.getTracks().forEach(track => track.stop());
  }
  
  if (whisperWebSocket.value) {
    whisperWebSocket.value.close();
  }
  
  if (isSpeaking.value) {
    speechSynthesis.cancel();
  }
});

// 监听消息变化，自动滚动到底部
watch(messages, async () => {
  await nextTick(); // 等待 DOM 更新完成
  if (chatHistoryRef.value) {
    chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight;
  }
}, { deep: true }); // 深度监听数组内部变化

// Markdown渲染函数
const renderMarkdown = (text) => {
  try {
    // 使用marked解析markdown，然后用DOMPurify清理HTML以防XSS攻击
    return DOMPurify.sanitize(marked.parse(text));
  } catch (e) {
    console.error('Markdown渲染错误:', e);
    return text; // 如果解析出错，返回原始文本
  }
};

// 添加一个控制动态省略号的函数
function startThinkingAnimation() {
  isThinking.value = true;
  let dotsCount = 0;
  
  const animateDots = () => {
    if (!isThinking.value) return;
    
    dotsCount = (dotsCount % 3) + 1; // 1, 2, 3 循环
    thinkingDots.value = ".".repeat(dotsCount);
    
    setTimeout(animateDots, 500); // 每500毫秒更新一次
  };
  
  animateDots();
}

// 停止思考动画
function stopThinkingAnimation() {
  isThinking.value = false;
  thinkingDots.value = "";
}
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
  padding: 8px;
  margin-bottom: 8px;
  background-color: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  position: relative;
  z-index: 2;
}

.chat-message-container {
  display: flex;
  margin-bottom: 8px;
  align-items: flex-start;
}

.user-message {
  flex-direction: row-reverse;
  justify-content: flex-start;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  flex-shrink: 0;
  margin: 0 6px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 16px;
}

.avatar-icon {
  line-height: 1;
}

.avatar.user {
  background-color: rgba(79, 209, 197, 0.2);
  border: 1px solid var(--primary, #4fd1c5);
}

.avatar.ai {
  background-color: rgba(16, 45, 80, 0.7);
  border: 1px solid rgba(80, 120, 170, 0.4);
  color: #e6f1ff;
}

.avatar.system {
  background-color: rgba(255, 204, 0, 0.2);
  border: 1px solid var(--warning, #ffcc00);
}

.message-bubble {
  padding: 5px 8px;
  border-radius: 8px;
  position: relative;
  max-width: 90%;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  font-size: 0.9em;
}

.message-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 5px;
}

.action-button {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 5px;
  font-size: 16px;
  opacity: 0.6;
  transition: opacity 0.2s;
}

.action-button:hover {
  opacity: 1;
}

.speak-button {
  color: var(--cyber-purple, #805ad5);
}

.bubble-user {
  background-color: rgba(79, 209, 197, 0.15);
  border: 1px solid rgba(79, 209, 197, 0.3);
  border-top-right-radius: 2px;
  margin-right: 10px;
}

.bubble-ai {
  background-color: rgba(16, 45, 80, 0.7);
  border: 1px solid rgba(80, 120, 170, 0.4);
  color: #e6f1ff;
  border-top-left-radius: 2px;
  margin-left: 10px;
  text-align: left;
  margin-right: auto;
}

.bubble-system {
  background-color: rgba(255, 204, 0, 0.1);
  border: 1px solid rgba(255, 204, 0, 0.3);
  border-top-left-radius: 2px;
  margin-left: 10px;
}

.message-text {
  word-break: break-word;
  line-height: 1.3;
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

/* 语音按钮样式 */
.voice-button {
  padding: 8px 12px;
  background: rgba(128, 90, 213, 0.2);
  color: var(--cyber-purple, #805ad5);
  border: 1px solid rgba(128, 90, 213, 0.4);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.voice-button:hover {
  background: rgba(128, 90, 213, 0.3);
  border-color: rgba(128, 90, 213, 0.6);
}

.voice-button.recording {
  background: rgba(255, 77, 77, 0.3);
  border-color: rgba(255, 77, 77, 0.6);
  color: #ff4d4d;
  animation: recordingPulse 1.5s infinite;
}

@keyframes recordingPulse {
  0%, 100% { transform: scale(1); box-shadow: 0 0 0 rgba(255, 77, 77, 0.4); }
  50% { transform: scale(1.05); box-shadow: 0 0 10px rgba(255, 77, 77, 0.7); }
}

/* 录音指示器样式 */
.recording-indicator {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid rgba(255, 77, 77, 0.5);
  border-radius: 12px;
  padding: 15px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  z-index: 100;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
}

.recording-waves {
  display: flex;
  gap: 3px;
  margin-bottom: 5px;
}

.wave {
  width: 3px;
  height: 15px;
  background-color: rgba(255, 77, 77, 0.7);
  border-radius: 1px;
  animation: waveAnimation 1.2s infinite ease-in-out;
}

.wave:nth-child(2) {
  animation-delay: 0.2s;
}

.wave:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes waveAnimation {
  0%, 100% { height: 5px; }
  50% { height: 15px; }
}

.recording-text {
  color: white;
  font-size: 0.9em;
  max-width: 250px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stop-recording-button {
  background: rgba(255, 77, 77, 0.2);
  color: #ff4d4d;
  border: 1px solid rgba(255, 77, 77, 0.4);
  border-radius: 4px;
  padding: 5px 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 0.9em;
}

.stop-recording-button:hover {
  background: rgba(255, 77, 77, 0.3);
  border-color: rgba(255, 77, 77, 0.6);
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

/* Markdown内容样式 */
.markdown-content {
  line-height: 1.3;
  text-align: left;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  margin-top: 0.5em;
  margin-bottom: 0.3em;
  font-weight: 600;
  text-align: left;
}

.markdown-content :deep(h1) { font-size: 1.5em; }
.markdown-content :deep(h2) { font-size: 1.3em; }
.markdown-content :deep(h3) { font-size: 1.2em; }
.markdown-content :deep(h4) { font-size: 1.1em; }
.markdown-content :deep(h5) { font-size: 1em; }
.markdown-content :deep(h6) { font-size: 0.95em; }

.markdown-content :deep(p) {
  margin-bottom: 0.4em;
  margin-top: 0;
  text-align: left;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin-left: 1em;
  margin-bottom: 0.4em;
  padding-left: 0.5em;
}

.markdown-content :deep(li) {
  margin-bottom: 0.2em;
  line-height: 1.2;
}

.markdown-content :deep(code) {
  font-family: monospace;
  padding: 0.2em 0.4em;
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
}

.markdown-content :deep(pre) {
  padding: 0.5em;
  margin-bottom: 0.5em;
}

.markdown-content :deep(pre code) {
  background-color: transparent;
  padding: 0;
}

.markdown-content :deep(blockquote) {
  padding-left: 0.5em;
  margin-bottom: 0.5em;
}

.markdown-content :deep(a) {
  color: var(--cyber-blue, #0088ff);
  text-decoration: none;
  display: inline-block;
  text-align: left;
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1em;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid rgba(128, 90, 213, 0.3);
  padding: 0.3em;
  text-align: left;
}

.markdown-content :deep(th) {
  background-color: rgba(128, 90, 213, 0.15);
}

.thinking-status {
  padding: 8px 12px;
  margin: 10px 0;
  background-color: rgba(128, 90, 213, 0.1);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  font-style: italic;
}

.thinking-text {
  display: flex;
  align-items: center;
}

.thinking-dots {
  min-width: 20px;
  display: inline-block;
  text-align: left;
  font-weight: bold;
  color: rgba(128, 90, 213, 0.8);
}

/* 如果使用系统消息样式 */
.system-message .thinking-dots {
  color: #4fd1c5;
  font-weight: bold;
  margin-left: 4px;
}

/* 更新思考动画的CSS样式 */
.thinking-bubble {
  background-color: rgba(79, 209, 197, 0.15) !important;
  border: 1px solid rgba(79, 209, 197, 0.3) !important;
  position: relative;
  overflow: hidden;
  text-align: left;
  margin-right: auto;
}

.thinking-bubble::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.7), transparent);
  animation: thinking-line 1.5s infinite;
}

.thinking-dots-animated {
  display: inline-block;
  min-width: 20px;
  font-weight: bold;
  color: #4fd1c5;
  animation: pulse 1s infinite;
  margin-left: 3px;
}

@keyframes thinking-line {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

@keyframes pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

/* 调整消息的整体宽度，使其更宽 */
.message-bubble {
  padding: 5px 8px;
  max-width: 90%;
  font-size: 0.9em;
}

/* 调整消息容器排列，确保AI消息靠左 */
.chat-message-container:not(.user-message) {
  justify-content: flex-start;
}
</style> 