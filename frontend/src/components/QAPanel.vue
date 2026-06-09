<template>
  <div class="qa-panel-container">
    <div class="panel-title">
      <div class="status-indicator" :class="{ 'connected': isConnected }"></div>
      <span>{{ currentMode === 'rag' ? 'AI智能体' : '桌面活动助手' }}</span>
      <div class="mode-switch">
        <button @click="switchMode('rag')" :class="{ 'active': currentMode === 'rag' }" class="mode-btn">
          🤖 AI问答
        </button>
        <button @click="switchMode('activity')" :class="{ 'active': currentMode === 'activity' }" class="mode-btn">
          🖥️ 活动检索
        </button>
        <button @click="clearChat" class="mode-btn clear-btn" title="清除对话">
          🗑️ 清除
        </button>
      </div>
    </div>
    <div class="qa-content">
      <!-- 快速问题建议 -->
      <div v-if="shouldShowQuickQuestions" class="quick-questions">
        <div class="quick-questions-title">💡 试试这些问题：</div>
        <div class="question-buttons">
          <button @click="sendQuickQuestion('过去30分钟我浏览了什么网页？')" class="quick-question-btn">
            🌐 过去30分钟浏览的网页
          </button>
          <button @click="sendQuickQuestion('我昨天主要使用了哪些应用？')" class="quick-question-btn">
            📱 昨天使用的应用
          </button>
          <button @click="sendQuickQuestion('最近1小时我在做什么？')" class="quick-question-btn">
            ⏰ 最近1小时的活动
          </button>
          <button @click="sendQuickQuestion('我今天上午做了什么工作？')" class="quick-question-btn">
            💼 今天上午的工作
          </button>
          <button @click="sendQuickQuestion('过去10分钟我点击了什么？')" class="quick-question-btn">
            🖱️ 最近的点击操作
          </button>
          <button @click="sendQuickQuestion('我使用Chrome浏览器做了什么？')" class="quick-question-btn">
            🌏 Chrome浏览活动
          </button>
        </div>
      </div>

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
      <input type="text" v-model="userInput" @keyup.enter="sendMessage" :placeholder="currentMode === 'rag' ? '输入您的问题...' : '问我关于您的桌面活动，如：过去30分钟我浏览了什么网页？'" class="chat-input">
      <button @click="handleVoiceButtonClick" class="voice-button smart-voice-button" :class="{ 'recording': isRecording, 'speaking': isSpeaking }" :title="getVoiceButtonTitle()">
        <span v-if="isRecording">🎙️</span>
        <span v-else-if="isSpeaking">🔊</span>
        <span v-else>🔈</span>
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
import { ref, watch, nextTick, onMounted, onBeforeUnmount, computed, onUnmounted } from 'vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { WakeWordManager } from '../utils/wakeword_manager.js';

const userInput = ref('');
const chatHistoryRef = ref(null);
// 为不同模式创建独立的消息存储
const ragMessages = ref([]);      // AI问答模式的消息
const activityMessages = ref([]); // 活动检索模式的消息

// 当前激活的消息列表（根据模式动态切换）
const messages = computed(() => {
  return currentMode.value === 'rag' ? ragMessages.value : activityMessages.value;
});

// 获取当前模式的消息数组（用于添加/删除操作）
const getCurrentMessages = () => {
  return currentMode.value === 'rag' ? ragMessages : activityMessages;
};
const isConnected = ref(false);
const isRecording = ref(false);
const recognizedText = ref('');
const isSpeaking = ref(false);
const currentSpeakingId = ref(null);
const currentAudio = ref(null);  // 当前播放的音频对象
const isThinking = ref(false);
const thinkingDots = ref("");
const systemStats = ref(null);
const currentMode = ref('rag'); // 'rag' 或 'activity'
const ragConnected = ref(false);
const activityConnected = ref(false);

// 语音识别相关
const audioContext = ref(null);
const mediaRecorder = ref(null);
const audioChunks = ref([]);
const audioStream = ref(null);
const voiceRagConnected = ref(false);
// 唤醒词
const wakewordEnabled = ref(false);
let wakewordManager = null;

// 服务器地址
const VOICE_RAG_SERVICE_URL = 'http://localhost:8087';  // 新的语音RAG服务
const RAG_SERVER_URL = 'http://localhost:8085';  // RAG智能问答服务器
const ACTIVITY_SERVER_URL = 'http://localhost:5001';  // 活动检索服务器

// 过滤掉系统连接消息
const filteredMessages = computed(() => {
  return messages.value.filter(msg =>
    !(msg.sender === 'system' && msg.text.includes('已连接到智能问答系统')));
});

// 计算是否应该显示快速问题建议
const shouldShowQuickQuestions = computed(() => {
  if (currentMode.value !== 'activity') return false;

  // 只有系统消息时显示快速问题
  const userMessages = messages.value.filter(msg => msg.sender === 'user');
  const aiMessages = messages.value.filter(msg => msg.sender === 'ai');

  return userMessages.length === 0 && aiMessages.length === 0;
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

// 检查语音RAG服务连接
const checkVoiceRagConnection = async () => {
  try {
    const response = await fetch(`${VOICE_RAG_SERVICE_URL}/api/health`);
    if (response.ok) {
      voiceRagConnected.value = true;
      console.log('语音RAG服务连接正常');
      return true;
    } else {
      voiceRagConnected.value = false;
      return false;
    }
  } catch (error) {
    console.error('语音RAG服务连接失败:', error);
    voiceRagConnected.value = false;
    return false;
  }
};

// 将Blob转换为Base64的辅助函数
const blobToBase64 = (blob) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result.split(',')[1]); // 去掉data:audio/webm;base64,前缀
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
};

// 发送音频到语音RAG服务 - 分阶段处理版本
const sendAudioToVoiceRagService = async (audioBlob) => {
  try {
    const base64Audio = await blobToBase64(audioBlob);

    console.log('🎤 开始分阶段语音处理...');

    // 第一阶段：仅进行语音转录，立即显示用户输入
    console.log('📝 第一阶段：语音转录...');
    const transcribeResponse = await fetch(`${VOICE_RAG_SERVICE_URL}/api/voice/transcribe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        audio_data: base64Audio,
        format: 'webm'
      })
    });

    if (!transcribeResponse.ok) {
      throw new Error(`语音转录服务返回错误: ${transcribeResponse.status}`);
    }

    const transcribeData = await transcribeResponse.json();
    console.log('📝 转录结果:', transcribeData);

    if (transcribeData.success && transcribeData.transcription) {
      // 立即显示用户输入
      recognizedText.value = transcribeData.transcription;

      const userMessage = {
        id: Date.now(),
        sender: 'user',
        text: transcribeData.transcription
      };
      getCurrentMessages().value.push(userMessage);
      console.log('✅ 第一阶段完成：用户输入已显示');

      // 第二阶段：显示AI思考状态，然后生成回答
      console.log('🤖 第二阶段：生成AI回答...');

      // 开始思考动画（使用原有的思考动画）
      startThinkingAnimation();

      // 预分配AI消息ID，但不立即添加消息
      const aiMessageId = Date.now() + 1;

      try {
        // 调用后端生成AI回答
        const queryResponse = await fetch(`${VOICE_RAG_SERVICE_URL}/api/query/process`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            text: transcribeData.transcription,
            mode: currentMode.value
          })
        });

        // 停止思考动画
        stopThinkingAnimation();

        if (!queryResponse.ok) {
          throw new Error(`AI查询服务返回错误: ${queryResponse.status}`);
        }

        const queryData = await queryResponse.json();
        console.log('🤖 AI回答结果:', queryData);

        if (queryData.success) {
          // 直接添加AI回答消息
          const aiMessage = {
            id: aiMessageId,
            sender: 'ai',
            text: queryData.response_text
          };
          getCurrentMessages().value.push(aiMessage);

          console.log('✅ 第二阶段完成：AI回答已显示');

          // 播放AI语音回复
          if (queryData.audio_url) {
            playAudioResponse(queryData.audio_url);
          } else {
            // 使用灵动语音自动朗读文本
            console.log('🔊 使用灵动语音自动朗读AI回答');
            setTimeout(() => {
              speakMessage(queryData.response_text, aiMessageId);
            }, 100);
          }

          return {
            success: true,
            transcription: transcribeData.transcription,
            response_text: queryData.response_text,
            audio_url: queryData.audio_url,
            transcribe_time: transcribeData.transcribe_time,
            processing_time: queryData.processing_time
          };
        } else {
          throw new Error(queryData.error || 'AI查询失败');
        }
      } catch (queryError) {
        // 停止思考动画
        stopThinkingAnimation();

        // 添加错误消息
        const errorMessage = {
          id: aiMessageId,
          sender: 'ai',
          text: `抱歉，处理您的问题时出现错误：${queryError.message}`
        };
        getCurrentMessages().value.push(errorMessage);
        throw queryError;
      }
    } else {
      throw new Error(transcribeData.error || '语音转录失败');
    }
  } catch (e) {
    console.error('分阶段语音处理错误:', e);
    throw e;
  }
};

// 播放AI音频回复 - 启用灵动语音自动播放
const playAudioResponse = (audioUrl) => {
  try {
    if (!audioUrl) {
      console.log('没有音频URL，跳过播放');
      return;
    }

    // 构建正确的音频URL
    let fullAudioUrl;
    if (audioUrl.startsWith('http')) {
      fullAudioUrl = audioUrl;
    } else {
      fullAudioUrl = `${VOICE_RAG_SERVICE_URL}/${audioUrl}`;
    }

    console.log('🔊 准备播放AI语音回复:', fullAudioUrl);

    const audio = new Audio(fullAudioUrl);

    // 添加事件监听器
    audio.onloadstart = () => console.log('🎵 开始加载音频...');
    audio.oncanplay = () => console.log('🎵 音频可以播放');
    audio.onplay = () => {
      console.log('🎵 开始播放音频');
      isSpeaking.value = true;  // 更新全局语音状态
      currentAudio.value = audio;  // 设置当前音频对象
    };
    audio.onended = () => {
      console.log('🎵 音频播放完成');
      isSpeaking.value = false;  // 重置全局语音状态
      currentAudio.value = null;
    };
    audio.onerror = (e) => {
      console.error('❌ 音频播放错误:', e);
      isSpeaking.value = false;  // 重置全局语音状态
      currentAudio.value = null;
    };

    // 播放音频
    audio.play().then(() => {
      console.log('✅ 音频播放启动成功');
    }).catch(e => {
      console.error('❌ 播放音频回复失败:', e);
      // 尝试备用播放方式
      setTimeout(() => {
        try {
          audio.play();
        } catch (retryError) {
          console.error('❌ 重试播放也失败:', retryError);
        }
      }, 100);
    });

  } catch (e) {
    console.error('❌ 创建音频对象失败:', e);
  }
};

// 获取语音按钮的提示文本
const getVoiceButtonTitle = () => {
  if (isRecording.value) {
    return '正在录音中... (点击停止)';
  } else if (isSpeaking.value) {
    return '点击停止语音播放';
  } else if (voiceRagConnected.value) {
    return '智能语音对话 (一键识别+回答)';
  } else {
    return '语音输入 (服务未连接)';
  }
};

// 处理语音按钮点击 - 集成语音录制和语音打断功能
const handleVoiceButtonClick = () => {
  console.log('🎙️ 语音按钮被点击');
  console.log('🔊 当前语音状态:', isSpeaking.value);
  console.log('🎤 当前录音状态:', isRecording.value);

  if (isSpeaking.value) {
    // 如果正在播放语音，则停止播放
    console.log('⏹️ 停止语音播放');
    toggleGlobalVoiceControl();
  } else if (isRecording.value) {
    // 如果正在录音，则停止录音
    console.log('⏹️ 停止录音');
    stopVoiceRecognition();
  } else {
    // 否则开始语音识别
    console.log('🎙️ 开始语音识别');
    toggleVoiceRecognition();
  }
};

// 全局语音控制函数
const toggleGlobalVoiceControl = () => {
  console.log('🎛️ 全局语音控制被触发');
  console.log('🔊 当前语音状态:', isSpeaking.value);

  if (isSpeaking.value) {
    // 停止所有语音播放
    console.log('⏹️ 停止所有语音播放');

    // 停止当前的灵动语音朗读
    if (currentAudio.value) {
      console.log('⏹️ 停止灵动语音播放');
      currentAudio.value.pause();
      currentAudio.value.currentTime = 0;
      currentAudio.value = null;
    }

    // 停止系统语音合成
    if (speechSynthesis.speaking) {
      console.log('⏹️ 停止系统语音合成');
      speechSynthesis.cancel();
    }

    // 重置状态
    isSpeaking.value = false;
    currentSpeakingId.value = null;

    console.log('✅ 所有语音已停止');
  } else {
    console.log('ℹ️ 当前没有语音在播放');
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
      const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' });

      try {
        // 发送到语音RAG服务进行一体化处理
        await sendAudioToVoiceRagService(audioBlob);
      } catch (error) {
        console.error('语音处理失败:', error);

        // 显示错误消息
        getCurrentMessages().value.push({
          id: Date.now(),
          sender: 'system',
          text: `🎤 语音处理失败: ${error.message}`
        });
      }

      // 清理AudioStream资源
      if (audioStream.value) {
        audioStream.value.getTracks().forEach(track => track.stop());
      }
    };

    // 开始录制
    mediaRecorder.value.start(100); // 每100ms收集数据
    isRecording.value = true;
    recognizedText.value = '';

    // 显示录音状态
    console.log('🎤 开始录音...');
  // 启动静音检测
  try {
    if (audioContext.value && audioStream.value) {
      const silenceEnergyThreshold = 0.02;
      let lastVoiceTimestamp = Date.now();
      const source = audioContext.value.createMediaStreamSource(audioStream.value);
      const processor = audioContext.value.createScriptProcessor(2048, 1, 1);
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        let sum = 0; for (let i = 0; i < input.length; i += 1) sum += input[i] * input[i];
        const rms = Math.sqrt(sum / input.length);
        if (rms > silenceEnergyThreshold) lastVoiceTimestamp = Date.now();
      };
      source.connect(processor);
      processor.connect(audioContext.value.destination);
      // 保存到全局以便停止时清理
      window.__qaSilenceCtx = { source, processor, get lastVoice(){return lastVoiceTimestamp;}, set lastVoice(v){lastVoiceTimestamp=v;} };
      if (window.__qaSilenceTimer) clearInterval(window.__qaSilenceTimer);
      window.__qaSilenceTimer = setInterval(() => {
        if (isRecording.value && Date.now() - window.__qaSilenceCtx.lastVoice > 5000) {
          console.log('⏱️ 静音超时，自动停止录音');
          stopVoiceRecognition();
        }
      }, 1000);
    }
  } catch (e) {
    console.warn('静音检测启动失败:', e);
  }

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
  // 暂停唤醒监听，避免录音期间误触
  if (wakewordManager && wakewordManager.enabled) {
    wakewordManager.pause();
  }
  startAudioRecording();
};

// 停止语音识别
const stopVoiceRecognition = () => {
  if (mediaRecorder.value && isRecording.value) {
    mediaRecorder.value.stop();
    isRecording.value = false;
    console.log('⏹️ 录音已停止');
    // 录音结束后恢复唤醒监听
    if (wakewordManager && wakewordEnabled.value) {
      wakewordManager.resume();
    }
    // 停止静音检测
    try {
      if (window.__qaSilenceTimer) { clearInterval(window.__qaSilenceTimer); window.__qaSilenceTimer = null; }
      if (window.__qaSilenceCtx) {
        window.__qaSilenceCtx.processor.disconnect();
        window.__qaSilenceCtx.processor.onaudioprocess = null;
        window.__qaSilenceCtx.source.disconnect();
        window.__qaSilenceCtx = null;
      }
    } catch (_) {}

    // 注意：不再自动填充到输入框，因为语音RAG服务会直接处理并回复
  }
};

// 语音合成
let speechSynthesis = window.speechSynthesis;
let speechUtterance = null;

// 文本清理函数 - 将HTML内容转换为纯文本
const cleanTextForSpeech = (text) => {
  let cleanText = text;

  // 如果文本包含HTML标签，使用DOM解析获取纯文本
  if (text.includes('<')) {
    try {
      // 创建临时DOM元素来解析HTML
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = text;
      cleanText = tempDiv.textContent || tempDiv.innerText || '';
    } catch (e) {
      // 如果DOM解析失败，使用正则表达式清理
      cleanText = text.replace(/<[^>]*>/g, '');
    }
  }

  // 进一步清理文本
  cleanText = cleanText
    .replace(/^\s*speak[,\s]*/, '')  // 移除开头的"speak,,,"
    .replace(/^\s*[,\s]+/, '')  // 移除开头的逗号和空格
    .replace(/^[,，\s]+/, '')  // 移除开头的中英文逗号和空格
    .replace(/\*\*/g, '')  // 移除markdown加粗标记
    .replace(/\*/g, '')  // 移除markdown斜体标记
    .replace(/#{1,6}\s+/g, '')  // 移除markdown标题标记
    .replace(/\n\n+/g, ' ')  // 将多个换行替换为空格
    .replace(/\s+/g, ' ')  // 合并多个空格为单个空格
    .trim();

  return cleanText;
};

// 朗读消息 - 使用灵动语音 XiaoxiaoNeural
const speakMessage = async (text, msgId) => {
  console.log('🎙️ speakMessage 被调用');
  console.log('📝 传入文本:', text);
  console.log('🆔 消息ID:', msgId);
  console.log('🔊 当前朗读状态:', isSpeaking.value);

  if (isSpeaking.value) {
    // 如果正在朗读，则停止
    console.log('⏹️ 停止当前朗读');
    if (currentAudio.value) {
      currentAudio.value.pause();
      currentAudio.value.currentTime = 0;
    }
    isSpeaking.value = false;
    currentSpeakingId.value = null;
    return;
  }

  try {
    // 使用专门的清理函数
    const cleanText = cleanTextForSpeech(text);

    if (!cleanText) {
      console.log('❌ 清理后的文本为空，跳过朗读');
      isSpeaking.value = false;
      currentSpeakingId.value = null;
      return;
    }

    // 设置朗读状态
    isSpeaking.value = true;
    currentSpeakingId.value = msgId;

    console.log('='.repeat(80));
    console.log('🔍 朗读调试信息:');
    console.log('📝 原始文本类型:', typeof text);
    console.log('📝 原始文本长度:', text.length);
    console.log('📝 原始文本内容:');
    console.log(text);
    console.log('-'.repeat(40));
    console.log('🧹 清理后文本类型:', typeof cleanText);
    console.log('🧹 清理后文本长度:', cleanText.length);
    console.log('🧹 清理后文本内容:');
    console.log(cleanText);
    console.log('-'.repeat(40));
    console.log('🔊 即将发送给TTS的文本:');
    console.log(JSON.stringify(cleanText));
    console.log('='.repeat(80));

    // 调用语音RAG服务生成语音
    const response = await fetch(`${VOICE_RAG_SERVICE_URL}/api/tts/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        text: cleanText,  // 使用清理后的文本
        voice: 'zh-CN-XiaoxiaoNeural'  // 使用灵动的晓晓语音
      })
    });

    if (!response.ok) {
      throw new Error(`语音生成失败: ${response.status}`);
    }

    const result = await response.json();

    if (result.success && result.audio_url) {
      // 播放生成的语音
      let audioUrl = result.audio_url;
      if (!audioUrl.startsWith('http')) {
        audioUrl = `${VOICE_RAG_SERVICE_URL}${audioUrl}`;
      }

      console.log('🎵 播放灵动语音:', audioUrl);

      const audio = new Audio(audioUrl);
      currentAudio.value = audio;

      // 监听语音播放事件
      audio.onplay = () => {
        console.log('✅ 开始播放灵动语音朗读');
      };

      audio.onended = () => {
        console.log('✅ 灵动语音朗读完成');
        isSpeaking.value = false;
        currentSpeakingId.value = null;
        currentAudio.value = null;
      };

      audio.onerror = (e) => {
        console.error('❌ 灵动语音播放失败:', e);
        isSpeaking.value = false;
        currentSpeakingId.value = null;
        currentAudio.value = null;
      };

      // 开始播放
      await audio.play();

    } else {
      throw new Error(result.error || '语音生成失败');
    }

  } catch (error) {
    console.error('❌ 朗读消息失败:', error);
    isSpeaking.value = false;
    currentSpeakingId.value = null;
    currentAudio.value = null;

    // 如果灵动语音失败，回退到系统语音
    console.log('🔄 回退到系统语音...');
    try {
      speechUtterance = new SpeechSynthesisUtterance(cleanText);  // 使用清理后的文本
      speechUtterance.lang = 'zh-CN';
      speechUtterance.onend = () => {
        isSpeaking.value = false;
        currentSpeakingId.value = null;
      };
      speechSynthesis.speak(speechUtterance);
    } catch (fallbackError) {
      console.error('❌ 系统语音也失败:', fallbackError);
      isSpeaking.value = false;
      currentSpeakingId.value = null;
    }
  }
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
    getCurrentMessages().value.push(userMessage);

    const query = userInput.value.trim();
    userInput.value = ''; // 清空输入框

    // 开始显示思考动画
    startThinkingAnimation();

    try {
      let response, data;

      if (currentMode.value === 'activity') {
        // 使用活动查询API
        response = await fetch(`${ACTIVITY_SERVER_URL}/api/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            message: query
          })
        });
      } else {
        // 使用RAG智能问答API（使用detect_intent接口）
        response = await fetch(`${RAG_SERVER_URL}/detect_intent/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            query: query,
            mode: currentMode.value
          })
        });
      }

      // 停止思考动画
      stopThinkingAnimation();

      if (!response.ok) {
        throw new Error(`服务器返回错误: ${response.status}`);
      }

      data = await response.json();

      // 根据模式处理不同的响应格式
      let responseText = '';
      if (currentMode.value === 'activity') {
        if (data && data.result) {
          responseText = data.result;
        } else {
          throw new Error('桌面活动服务器返回错误数据');
        }
      } else {
        if (data && data.status === 'success') {
          responseText = data.answer;
        } else {
          throw new Error('RAG服务器返回错误数据');
        }
      }

      // 添加AI回复
      const aiMsgId = Date.now() + 2;
      getCurrentMessages().value.push({
        id: aiMsgId,
        sender: 'ai',
        text: responseText
      });

      // 自动朗读AI回复
      console.log('🤖 准备自动朗读AI回复');
      console.log('📝 回复文本:', responseText);
      console.log('🆔 消息ID:', aiMsgId);

      // 延迟一下确保DOM更新完成
      setTimeout(() => {
        console.log('🔊 开始自动朗读AI回复');
        speakMessage(responseText, aiMsgId);
      }, 100);
    } catch (error) {
      // 停止思考动画
      stopThinkingAnimation();

      console.error('发送消息错误:', error);

      let errorMessage = '抱歉，无法处理您的请求。';

      if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
        errorMessage = '🔌 无法连接到桌面活动服务器，请确保：\n• activity_ui.py 正在运行\n• 服务器地址为 http://localhost:5001\n• 网络连接正常';
      } else if (error.message.includes('500')) {
        errorMessage = '⚠️ 服务器内部错误，可能原因：\n• 向量数据库未初始化\n• 活动数据尚未加载\n• 请稍后重试';
      } else if (error.message.includes('404')) {
        errorMessage = '❌ API端点不存在，请检查服务器版本是否正确';
      } else {
        errorMessage = `❌ 发生未知错误：${error.message}`;
      }

      getCurrentMessages().value.push({
        id: Date.now() + 3,
        sender: 'system',
        text: errorMessage
      });
    }
  }
};

// 检查RAG服务器连接
const checkRAGConnection = async () => {
  try {
    const response = await fetch(`${RAG_SERVER_URL}/detect_intent/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        query: "测试连接"
      })
    });

    if (response.ok) {
      ragConnected.value = true;
      return true;
    } else {
      ragConnected.value = false;
      return false;
    }
  } catch (error) {
    ragConnected.value = false;
    return false;
  }
};

// 检查活动检索服务器连接
const checkActivityConnection = async () => {
  try {
    const response = await fetch(`${ACTIVITY_SERVER_URL}/api/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: "测试连接"
      })
    });

    if (response.ok) {
      activityConnected.value = true;
      // 获取系统统计信息
      await getSystemStats();
      return true;
    } else {
      activityConnected.value = false;
      return false;
    }
  } catch (error) {
    activityConnected.value = false;
    return false;
  }
};

// 检查所有服务器连接
const checkConnection = async () => {
  const ragStatus = await checkRAGConnection();
  const activityStatus = await checkActivityConnection();
  const voiceRagStatus = await checkVoiceRagConnection();

  // 根据当前模式设置连接状态
  if (currentMode.value === 'rag') {
    isConnected.value = ragStatus;
  } else {
    isConnected.value = activityStatus;
  }

  // 构建简洁的系统状态显示
  const statusIcons = [
    ragStatus ? '✅ AI智能问答' : '❌ AI智能问答',
    activityStatus ? '✅ 桌面活动检索' : '❌ 桌面活动检索',
    voiceRagStatus ? '✅ 智能语音' : '❌ 智能语音'
  ];

  let welcomeMessage = `🔌 系统连接状态：${statusIcons.join('  •  ')}\n`;

  if (activityStatus && systemStats.value?.hasData) {
    welcomeMessage += `📊 最新记录时间：${new Date(systemStats.value.latestActivity).toLocaleString('zh-CN')}`;
  } else {
    welcomeMessage += '💡 使用上方按钮切换检索模式  •  🎤 点击语音按钮进行智能对话';
  }

  // 在两个模式下都添加欢迎消息
  const welcomeMsg = {
    id: Date.now(),
    sender: 'system',
    text: welcomeMessage
  };
  ragMessages.value.push({...welcomeMsg});
  activityMessages.value.push({...welcomeMsg, id: Date.now() + 1});
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

// 设置快速问题
const setQuickQuestion = (question) => {
  userInput.value = question;
};

// 发送快速问题
const sendQuickQuestion = async (question) => {
  userInput.value = question;
  await sendMessage();
};

// 获取系统统计信息
const getSystemStats = async () => {
  try {
    const response = await fetch(`${ACTIVITY_SERVER_URL}/api/activity_records?limit=1`);
    if (response.ok) {
      const data = await response.json();
      if (data && data.length > 0) {
        const latestRecord = data[0];
        systemStats.value = {
          hasData: true,
          latestActivity: latestRecord.timestamp,
          recordCount: 'N/A' // 如果后端支持，可以添加总记录数API
        };
      } else {
        systemStats.value = {
          hasData: false,
          message: '尚无活动记录'
        };
      }
    }
  } catch (error) {
    console.log('获取系统统计信息失败:', error);
  }
};

// 添加模式选择功能
const switchMode = (mode) => {
  currentMode.value = mode;

  // 更新连接状态指示器
  if (mode === 'rag') {
    isConnected.value = ragConnected.value;
  } else {
    isConnected.value = activityConnected.value;
  }

  // 添加模式切换提示
  const modeNames = {
    rag: 'AI智能问答',
    activity: '桌面活动检索'
  };

  getCurrentMessages().value.push({
    id: Date.now(),
    sender: 'system',
    text: `🔄 已切换到 ${modeNames[mode]} 模式`
  });
};

// 清除聊天记录 - 只清除当前模式的消息
const clearChat = () => {
  // 只保留系统连接消息
  const currentMessages = getCurrentMessages();
  currentMessages.value = currentMessages.value.filter(msg =>
    msg.sender === 'system' && (
      msg.text.includes('系统连接状态') ||
      msg.text.includes('已连接到桌面活动检索系统') ||
      msg.text.includes('已连接到智能问答系统')
    )
  );
};
onMounted(async () => {
  // 初始化唤醒词管理器（默认关闭，可后续在设置里提供开关）
  wakewordManager = new WakeWordManager({
    wakePhrase: '你好助手',
    engine: 'webspeech',
    lang: 'zh-CN',
    cooldownMs: 5000,
    onWake: () => {
      console.log('🟢 语音唤醒触发');
      if (!isRecording.value) {
        // 轻提示音（常驻AudioContext + 包络，提升播放成功率并避免过响）
        try {
          if (!window.__uiAudioCtx) window.__uiAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
          const ctx = window.__uiAudioCtx;
          if (ctx.state === 'suspended') { ctx.resume?.(); }
          const o = ctx.createOscillator();
          const g = ctx.createGain();
          o.type = 'sine';
          o.frequency.setValueAtTime(880, ctx.currentTime);
          g.gain.setValueAtTime(0.0001, ctx.currentTime);
          g.gain.exponentialRampToValueAtTime(0.05, ctx.currentTime + 0.02);
          g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.15);
          o.connect(g).connect(ctx.destination);
          o.start();
          o.stop(ctx.currentTime + 0.18);
        } catch (_) {}
        toggleVoiceRecognition();
      }
    }
  });
  // 默认启用唤醒词
  wakewordEnabled.value = true; await wakewordManager.start();
});

onBeforeUnmount(async () => {
  if (wakewordManager) {
    await wakewordManager.stop();
    wakewordManager = null;
  }
});

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

/* 智能语音按钮样式 */
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

.smart-voice-button {
  background: linear-gradient(135deg, rgba(79, 209, 197, 0.2), rgba(128, 90, 213, 0.2));
  color: var(--primary, #4fd1c5);
  border: 1px solid rgba(79, 209, 197, 0.4);
  position: relative;
  overflow: hidden;
}

.smart-voice-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(79, 209, 197, 0.3), transparent);
  transition: left 0.5s ease;
}

.smart-voice-button:hover::before {
  left: 100%;
}

.voice-button:hover {
  background: rgba(128, 90, 213, 0.3);
  border-color: rgba(128, 90, 213, 0.6);
}

.smart-voice-button:hover {
  background: linear-gradient(135deg, rgba(79, 209, 197, 0.3), rgba(128, 90, 213, 0.3));
  border-color: rgba(79, 209, 197, 0.6);
  box-shadow: 0 0 12px rgba(79, 209, 197, 0.4);
}

.voice-button.recording {
  background: rgba(255, 77, 77, 0.3);
  border-color: rgba(255, 77, 77, 0.6);
  color: #ff4d4d;
  animation: recordingPulse 1.5s infinite;
}

.voice-button.speaking {
  background: rgba(40, 167, 69, 0.3);
  border-color: rgba(40, 167, 69, 0.6);
  color: #28a745;
  animation: speakingPulse 2s infinite;
}

@keyframes recordingPulse {
  0%, 100% { transform: scale(1); box-shadow: 0 0 0 rgba(255, 77, 77, 0.4); }
  50% { transform: scale(1.05); box-shadow: 0 0 10px rgba(255, 77, 77, 0.7); }
}

@keyframes speakingPulse {
  0%, 100% { transform: scale(1); box-shadow: 0 0 0 rgba(40, 167, 69, 0.4); }
  50% { transform: scale(1.03); box-shadow: 0 0 8px rgba(40, 167, 69, 0.7); }
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

/* 快速问题建议样式 */
.quick-questions {
  padding: 12px;
  margin: 5px 0 10px 0;
  background: linear-gradient(145deg, rgba(16, 45, 80, 0.3), rgba(79, 209, 197, 0.1));
  border: 1px solid rgba(79, 209, 197, 0.2);
  border-radius: 8px;
  position: relative;
  overflow: hidden;
}

.quick-questions::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--cyber-neon), transparent);
  animation: scanLine 3s infinite;
}

@keyframes scanLine {
  0% { left: -100%; }
  100% { left: 100%; }
}

.quick-questions-title {
  color: var(--primary, #4fd1c5);
  font-size: 0.85rem;
  font-weight: 500;
  margin-bottom: 8px;
  text-align: center;
  text-shadow: 0 0 3px rgba(79, 209, 197, 0.3);
}

.question-buttons {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 6px;
}

.quick-question-btn {
  padding: 6px 10px;
  background: linear-gradient(135deg,
    rgba(128, 90, 213, 0.1),
    rgba(79, 209, 197, 0.1));
  color: rgba(230, 241, 255, 0.9);
  border: 1px solid rgba(128, 90, 213, 0.3);
  border-radius: 5px;
  cursor: pointer;
  font-size: 0.75rem;
  text-align: left;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.quick-question-btn:hover {
  background: linear-gradient(135deg,
    rgba(128, 90, 213, 0.2),
    rgba(79, 209, 197, 0.2));
  border-color: rgba(79, 209, 197, 0.5);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 209, 197, 0.2);
}

.quick-question-btn:active {
  transform: translateY(0);
  box-shadow: 0 2px 6px rgba(79, 209, 197, 0.3);
}

.quick-question-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg,
    transparent,
    rgba(79, 209, 197, 0.1),
    transparent);
  transition: left 0.5s ease;
}

.quick-question-btn:hover::before {
  left: 100%;
}

/* 模式切换按钮样式 */
.mode-switch {
  display: flex;
  gap: 5px;
  margin-left: auto;
}

.mode-btn {
  padding: 4px 8px;
  font-size: 0.75rem;
  border: 1px solid rgba(128, 90, 213, 0.3);
  background: rgba(128, 90, 213, 0.1);
  color: rgba(230, 241, 255, 0.7);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.mode-btn:hover {
  background: rgba(128, 90, 213, 0.2);
  border-color: rgba(128, 90, 213, 0.5);
  color: rgba(230, 241, 255, 0.9);
}

.mode-btn.active {
  background: linear-gradient(135deg, var(--primary, #4fd1c5) 0%, var(--cyber-blue, #0088ff) 100%);
  border-color: var(--primary, #4fd1c5);
  color: white;
  font-weight: 500;
  box-shadow: 0 0 8px rgba(79, 209, 197, 0.3);
}

.mode-btn.clear-btn {
  background: rgba(255, 77, 77, 0.1);
  border-color: rgba(255, 77, 77, 0.3);
  color: rgba(255, 77, 77, 0.8);
}

.mode-btn.clear-btn:hover {
  background: rgba(255, 77, 77, 0.2);
  border-color: rgba(255, 77, 77, 0.5);
  color: rgba(255, 77, 77, 1);
}

.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}


</style>