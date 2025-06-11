<template>
  <div class="qa-panel-container">
    <div class="panel-title">
      <div class="status-indicator" :class="{ 'connected': isConnected }"></div>
      <span>桌面活动助手</span>
      <div class="mode-switch">
        <button @click="toggleMode('ai')" :class="{ 'active': currentMode === 'ai' }" class="mode-btn ai-btn">
          🤖 AI问答
        </button>
        <button @click="toggleMode('monitoring')" :class="{ 'active': currentMode === 'monitoring' }" class="mode-btn monitoring-btn">
          🖥️ 活动检索
        </button>
        <button @click="clearChat" class="mode-btn clear-btn" title="清除对话">
          🗑️ 清除
        </button>
      </div>
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
      <!-- 添加监控记录查询提示 -->
      <div class="monitoring-hint" @click="insertMonitoringQuery">
        <div class="hint-icon">💡</div>
        <div class="hint-text">提示: 使用"你好，请告诉我..."可查询监控记录</div>
      </div>
    </div>
    <div class="chat-input-area">
      <input type="text" v-model="userInput" @keyup.enter="sendMessage" :placeholder="currentMode === 'ai' ? '输入您的问题...' : '问我关于您的桌面活动，如：过去30分钟我做了什么？'" class="chat-input">
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
const currentMode = ref('ai'); // 默认AI问答模式

// 语音识别相关
const audioContext = ref(null);
const mediaRecorder = ref(null);
const audioChunks = ref([]);
const audioStream = ref(null);

// RAG服务器地址
const RAG_SERVER_URL = 'http://localhost:8085';
// 语音处理服务器地址
const VOICE_SERVER_URL = 'http://localhost:5000';

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

// 插入监控查询模板
const insertMonitoringQuery = () => {
  userInput.value = "你好千问，请告诉我我什么时候玩手机了";
  // 聚焦输入框并将光标移到末尾
  const inputElement = document.querySelector('.chat-input');
  if (inputElement) {
    inputElement.focus();
    inputElement.setSelectionRange(userInput.value.length, userInput.value.length);
  }
};

// 检查是否是监控记录查询
const isMonitoringQuery = (text) => {
  const possiblePrefixes = [
    "你好千问", "你好千万", "你好前问", "你好钱问", "你好千汶", 
    "你好前万", "你好乾问", "你好谦问", "你好浅问", "你好迁问",
    "你好欠问", "你好倩问", "你好千闻", "你好千文", "你好钱文",
    "你好千", "你好前", "你好钱", "你好欠", "你好浅"
  ];
  
  const tellPhrases = ["请告诉我", "请告诉", "告诉我", "告诉"];
  
  // 检查是否以任何可能的前缀开头
  const hasPrefix = possiblePrefixes.some(prefix => text.startsWith(prefix));
  
  // 检查是否包含任何请求短语
  const hasTellPhrase = tellPhrases.some(phrase => text.includes(phrase));
  
  return hasPrefix && hasTellPhrase;
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
    
    // 创建MediaRecorder，明确指定输出类型为 audio/webm;codecs=opus
    mediaRecorder.value = new MediaRecorder(audioStream.value, { mimeType: 'audio/webm;codecs=opus' });
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
      
      // 发送到后端处理
      await sendAudioMessage(audioBlob);
      
      // 清理AudioStream资源
      if (audioStream.value) {
        audioStream.value.getTracks().forEach(track => track.stop());
      }
    };
    
    // 开始录制
    mediaRecorder.value.start(); // 开始录制，不再按时间分块
    isRecording.value = true;
    recognizedText.value = '';
    
    // 清理定时器相关逻辑
    mediaRecorder.value.onresume = () => {};
    mediaRecorder.value.onpause = () => {};
    
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
    
    // 清空识别的文本和输入框，因为音频发送函数会处理显示
    recognizedText.value = '';
    userInput.value = '';
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

// 标准化显示的用户输入（将各种变体统一为标准形式）
const standardizeUserInput = (text) => {
  const possiblePrefixes = [
    "你好千万", "你好前问", "你好钱问", "你好千汶", 
    "你好前万", "你好乾问", "你好谦问", "你好浅问", "你好迁问",
    "你好欠问", "你好倩问", "你好千闻", "你好千文", "你好钱文",
    "你好千", "你好前", "你好钱", "你好欠", "你好浅"
  ];
  
  // 检查是否以任何可能的变体前缀开头
  for (const prefix of possiblePrefixes) {
    if (text.startsWith(prefix)) {
      // 替换为标准形式
      return text.replace(prefix, "你好千问");
    }
  }
  
  // 如果没有匹配到任何变体，返回原始文本
  return text;
};

// 发送音频消息到后端
const sendAudioMessage = async (audioBlob) => {
  // 添加用户消息，显示"正在转录..."
  const userTranscribingMessageId = Date.now();
  messages.value.push({
    id: userTranscribingMessageId,
    sender: 'user',
    text: '正在转录语音...'
  });

  startThinkingAnimation(); // 开始思考动画

  try {
    console.log("准备发送音频到后端服务器");
    
    // 创建FormData对象
    const formData = new FormData();
    formData.append('audio', audioBlob);
    
    console.log("发送请求到:", `${VOICE_SERVER_URL}/api/voice/process`);
    
    // 发送音频数据到后端处理
    const response = await fetch(`${VOICE_SERVER_URL}/api/voice/process`, {
      method: 'POST',
      body: formData
    });

    console.log("收到响应状态:", response.status);
    
    if (!response.ok) {
      throw new Error(`服务器返回错误: ${response.status}`);
    }

    const data = await response.json();
    console.log("收到处理结果:", data);

    stopThinkingAnimation(); // 停止思考动画

    // 更新用户消息为识别的文本，并标准化显示
    if (data.userText) {
      // 标准化用户输入显示
      const standardizedText = standardizeUserInput(data.userText);
      
      messages.value = messages.value.map(msg => 
        msg.id === userTranscribingMessageId ? { ...msg, text: standardizedText } : msg
      );
      
      // 添加AI回复
      if (data.aiResponse) {
        const aiMsgId = Date.now() + 1;
        messages.value.push({
          id: aiMsgId,
          sender: 'ai',
          text: data.aiResponse
        });
        
        // 如果有音频URL，播放音频
        if (data.audioUrl) {
          const audio = new Audio(`${VOICE_SERVER_URL}${data.audioUrl}`);
          audio.play();
        }
      }
    } else {
      throw new Error('语音识别失败');
    }
  } catch (error) {
    stopThinkingAnimation(); // 停止思考动画
    console.error('发送音频消息错误:', error);
    messages.value.push({
      id: Date.now() + 3,
      sender: 'system',
      text: `语音处理失败: ${error.message}`
    });
  }
};

// 发送消息 (原有的文本发送逻辑，现在也可能由语音识别结果触发)
const sendMessage = async () => {
  if (userInput.value.trim()) {
    // 如果正在录音，先停止
    if (isRecording.value) {
      stopVoiceRecognition();
    }
    
    // 获取用户输入并标准化显示
    const originalInput = userInput.value.trim();
    const standardizedInput = standardizeUserInput(originalInput);
    
    // 添加用户消息到列表（使用标准化后的文本显示）
    const userMessage = {
      id: Date.now(),
      sender: 'user',
      text: standardizedInput
    };
    messages.value.push(userMessage);
    
    userInput.value = ''; // 清空输入框
    
    // 开始显示思考动画
    startThinkingAnimation();
    
    try {
      // 检查是否是监控记录查询
      if (isMonitoringQuery(originalInput)) {
        console.log("检测到监控记录查询:", originalInput);
        
        // 对于监控记录查询，直接发送到后端处理（使用原始输入，不使用标准化的文本）
        const response = await fetch(`${VOICE_SERVER_URL}/api/chat/text`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            query: originalInput
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
        
        return;
      }
      
      // 如果不是监控记录查询，则使用RAG服务器（使用原始输入，不使用标准化的文本）
      const response = await fetch(`${RAG_SERVER_URL}/search/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: originalInput,
          k: 3
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
      
      // 检查响应内容，看是否包含API错误信息
      try {
        const data = await response.json();
        if (data.answer && (data.answer.includes("API调用失败") || data.answer.includes("503错误"))) {
          messages.value.push({
            id: Date.now() + 1,
            sender: 'system',
            text: '警告：大语言模型API连接异常，系统将使用监控记录直接回答，可能影响回答质量。'
          });
        }
      } catch (e) {
        console.error('解析响应数据失败:', e);
      }
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
    
    // 添加更详细的错误信息
    console.error('详细错误:', error);
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

// 从预警面板同步数据到监控系统
const syncAlertDataToMonitoring = async () => {
  try {
    // 获取预警面板中的所有警报项
    const alertItems = document.querySelectorAll('.alert-item');
    if (!alertItems || alertItems.length === 0) {
      console.log("未找到预警面板数据");
      return;
    }
    
    const records = [];
    
    // 遍历所有警报项
    alertItems.forEach(item => {
      try {
        // 获取时间戳
        const timestampEl = item.querySelector('.alert-timestamp');
        const messageEl = item.querySelector('.alert-message');
        const timeRangeEl = item.querySelector('.alert-time-range');
        
        if (!timestampEl || !messageEl) return;
        
        const timestamp = timestampEl.textContent.trim();
        let message = messageEl.textContent.trim();
        
        // 解析活动类型和持续时间
        let activity = message;
        let duration = null;
        
        // 检查是否包含持续时间信息 (格式: "活动：时长")
        if (message.includes('：')) {
          const parts = message.split('：');
          activity = parts[0].trim();
          if (parts[1]) {
            const durationPart = parts[1].trim();
            // 提取持续时间，格式可能是 "1.6分钟" 或 "1.6分钟 其他文本"
            const durationMatch = durationPart.match(/^([\d\.]+分钟)/);
            if (durationMatch) {
              duration = durationMatch[1];
            }
          }
        }
        
        // 解析时间范围
        let startTime = timestamp;
        let endTime = null;
        
        if (timeRangeEl) {
          const timeRange = timeRangeEl.textContent.trim();
          // 匹配时间范围格式 "HH:MM:SS - HH:MM:SS" 或 "HH:MM - HH:MM"
          const rangeMatch = timeRange.match(/(\d{1,2}:\d{1,2}(?::\d{1,2})?)\s*[-—–]\s*(\d{1,2}:\d{1,2}(?::\d{1,2})?)/);
          if (rangeMatch) {
            startTime = rangeMatch[1];
            endTime = rangeMatch[2];
          }
        }
        
        // 创建记录
        records.push({
          activity: activity,
          start_time: startTime,
          end_time: endTime,
          duration: duration,
          date: new Date().toISOString().split('T')[0]
        });
        
      } catch (err) {
        console.error('解析警报项时出错:', err);
      }
    });
    
    if (records.length > 0) {
      console.log("从预警面板解析到的记录:", records);
      
      // 发送到后端
      const response = await fetch(`${VOICE_SERVER_URL}/api/monitoring/update`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          records: records
        })
      });
      
      if (!response.ok) {
        throw new Error(`服务器返回错误: ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.status === 'success') {
        console.log(`监控数据同步成功，更新了 ${result.count || records.length} 条记录`);
      } else {
        throw new Error(result.message || '同步监控数据失败');
      }
    }
  } catch (error) {
    console.error('同步预警数据到监控系统时出错:', error);
    // 不再显示错误消息，避免干扰用户
  }
};

// 自动同步定时器
let syncIntervalId = null;

// 开始自动同步
const startAutoSync = () => {
  // 先执行一次同步
  syncAlertDataToMonitoring();
  
  // 设置定时器，每30秒自动同步一次
  syncIntervalId = setInterval(() => {
    console.log("执行自动同步...");
    syncAlertDataToMonitoring();
  }, 30000); // 30秒
  
  console.log("自动同步已启动");
};

// 停止自动同步
const stopAutoSync = () => {
  if (syncIntervalId) {
    clearInterval(syncIntervalId);
    syncIntervalId = null;
    console.log("自动同步已停止");
  }
};

// 组件挂载时检查连接
onMounted(() => {
  checkConnection();
  
  // 启动自动同步
  setTimeout(() => {
    startAutoSync();
  }, 2000); // 延迟2秒，确保预警面板已加载
});

// 组件卸载时清理资源
onUnmounted(() => {
  if (mediaRecorder.value && isRecording.value) {
    mediaRecorder.value.stop();
  }
  
  if (audioStream.value) {
    audioStream.value.getTracks().forEach(track => track.stop());
  }
  
  if (isSpeaking.value) {
    speechSynthesis.cancel();
  }
  
  // 停止自动同步
  stopAutoSync();
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

// 添加到知识库
const addToKnowledgeBase = async (text) => {
  try {
    const response = await fetch(`${RAG_SERVER_URL}/add_text/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        docs: [text],
        table_name: 'user_added'
      })
    });

    if (!response.ok) {
      throw new Error('添加失败');
    }

    const result = await response.json();
    if (result.status === 'success') {
      messages.value.push({
        id: Date.now(),
        sender: 'system',
        text: '已成功添加到知识库'
      });
    } else {
      throw new Error(result.message || '添加失败');
    }
  } catch (error) {
    console.error('添加到知识库失败:', error);
    messages.value.push({
      id: Date.now(),
      sender: 'system',
      text: `添加到知识库失败: ${error.message}`
    });
  }
};

// 切换模式
const toggleMode = (mode) => {
  currentMode.value = mode;
};

// 清除聊天记录
const clearChat = () => {
  messages.value = [];
  userInput.value = '';
};
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
  gap: 8px;
  margin-top: 4px;
}

.action-button {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  font-size: 16px;
  opacity: 0.6;
  transition: opacity 0.3s;
}

.action-button:hover {
  opacity: 1;
}

.action-button.speaking {
  opacity: 1;
  color: var(--primary);
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

/* 添加监控记录查询提示样式 */
.monitoring-hint {
  position: absolute;
  bottom: 70px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(16, 45, 80, 0.7);
  border: 1px solid rgba(79, 209, 197, 0.5);
  border-radius: 8px;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  z-index: 5;
  max-width: 90%;
}

.monitoring-hint:hover {
  background: rgba(16, 45, 80, 0.9);
  border-color: rgba(79, 209, 197, 0.8);
  transform: translateX(-50%) translateY(-2px);
}

.hint-icon {
  font-size: 18px;
  color: var(--primary, #4fd1c5);
}

.hint-text {
  font-size: 0.85em;
  color: #e6f1ff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 当输入框获得焦点时隐藏提示 */
.chat-input:focus + .monitoring-hint {
  opacity: 0;
  pointer-events: none;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .monitoring-hint {
    bottom: 60px;
    padding: 6px 10px;
  }
  
  .hint-text {
    font-size: 0.75em;
  }
}

/* 监控面板样式 */

/* 模式切换按钮样式 */
.mode-switch {
  display: flex;
  gap: 5px;
  margin-left: auto;
}

.mode-btn {
  padding: 4px 8px;
  font-size: 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.ai-btn {
  background: rgba(128, 90, 213, 0.2);
  border: 1px solid rgba(128, 90, 213, 0.5);
  color: rgba(230, 241, 255, 0.9);
}

.ai-btn:hover {
  background: rgba(128, 90, 213, 0.3);
  box-shadow: 0 0 8px rgba(128, 90, 213, 0.3);
}

.ai-btn.active {
  background: linear-gradient(135deg, #6a5acd 0%, #9370db 100%);
  border-color: #6a5acd;
  color: white;
  font-weight: 500;
  box-shadow: 0 0 8px rgba(128, 90, 213, 0.5);
}

.monitoring-btn {
  background: rgba(79, 209, 197, 0.2);
  border: 1px solid rgba(79, 209, 197, 0.5);
  color: rgba(230, 241, 255, 0.9);
}

.monitoring-btn:hover {
  background: rgba(79, 209, 197, 0.3);
  box-shadow: 0 0 8px rgba(79, 209, 197, 0.3);
}

.monitoring-btn.active {
  background: linear-gradient(135deg, #4fd1c5 0%, #38b2ac 100%);
  border-color: #4fd1c5;
  color: white;
  font-weight: 500;
  box-shadow: 0 0 8px rgba(79, 209, 197, 0.5);
}

.mode-btn.clear-btn {
  background: rgba(255, 77, 77, 0.1);
  border: 1px solid rgba(255, 77, 77, 0.3);
  color: rgba(255, 77, 77, 0.8);
}

.mode-btn.clear-btn:hover {
  background: rgba(255, 77, 77, 0.2);
  border-color: rgba(255, 77, 77, 0.5);
  color: rgba(255, 77, 77, 1);
}

/* 面板标题布局调整 */
.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}
</style> 