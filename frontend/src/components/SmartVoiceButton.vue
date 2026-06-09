<template>
  <div class="smart-voice-container">
    <!-- 智能语音按钮 -->
    <button
      @click="toggleSmartVoice"
      class="smart-voice-button"
      :class="{
        'recording': isRecording,
        'processing': isProcessing,
        'connected': isServiceConnected
      }"
      :title="getButtonTitle()"
      :disabled="isProcessing"
    >
      <span v-if="isRecording">🎙️</span>
      <span v-else-if="isProcessing">⏳</span>
      <span v-else>🧠</span>
    </button>

    <!-- 录音指示器 -->
    <div v-if="isRecording" class="smart-recording-indicator">
      <div class="recording-waves">
        <div class="wave"></div>
        <div class="wave"></div>
        <div class="wave"></div>
      </div>
      <div class="recording-text">🧠 智能语音识别中... {{ recordingDuration }}s</div>
      <button @click="stopSmartVoice" class="stop-recording-button">停止</button>
    </div>

    <!-- 处理指示器 -->
    <div v-if="isProcessing" class="processing-indicator">
      <div class="processing-spinner"></div>
      <div class="processing-text">🤖 AI正在思考...</div>
    </div>

    <!-- 状态指示器 -->
    <div class="service-status" :class="{ 'connected': isServiceConnected }">
      <span v-if="isServiceConnected">🟢</span>
      <span v-else>🔴</span>
      <span class="status-text">{{ isServiceConnected ? '智能语音已连接' : '智能语音未连接' }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

// 定义事件
const emit = defineEmits(['transcription', 'response', 'error']);

// 响应式数据
const isRecording = ref(false);
const isProcessing = ref(false);
const isServiceConnected = ref(false);
const recordingDuration = ref(0);
const mediaRecorder = ref(null);
const audioStream = ref(null);
const audioChunks = ref([]);
const recordingTimer = ref(null);

// 配置
const VOICE_RAG_SERVICE_URL = 'http://localhost:8087';
const MAX_RECORDING_TIME = 30; // 最大录音时间（秒）

// 检查服务状态
const checkServiceStatus = async () => {
  try {
    const response = await fetch(`${VOICE_RAG_SERVICE_URL}/api/health`, {
      method: 'GET',
      timeout: 3000
    });

    if (response.ok) {
      const data = await response.json();
      isServiceConnected.value = data.status === 'healthy';
      console.log('🟢 智能语音服务状态:', data);
    } else {
      isServiceConnected.value = false;
      console.warn('🟡 智能语音服务状态异常:', response.status);
    }
  } catch (error) {
    isServiceConnected.value = false;
    console.error('🔴 智能语音服务连接失败:', error);
  }
};

// 获取按钮提示文本
const getButtonTitle = () => {
  if (isProcessing.value) return 'AI正在处理中...';
  if (isRecording.value) return '点击停止录音';
  if (!isServiceConnected.value) return '智能语音服务未连接';
  return '点击开始智能语音对话';
};

// 开始录音
const startRecording = async () => {
  try {
    console.log('🎤 开始智能语音录音...');

    // 请求麦克风权限
    audioStream.value = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    // 创建MediaRecorder
    mediaRecorder.value = new MediaRecorder(audioStream.value, {
      mimeType: 'audio/webm;codecs=opus'
    });

    audioChunks.value = [];
    recordingDuration.value = 0;

    // 监听数据可用事件
    mediaRecorder.value.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.value.push(event.data);
      }
    };

    // 监听停止事件
    mediaRecorder.value.onstop = async () => {
      await processAudio();
    };

    // 开始录音
    mediaRecorder.value.start(100); // 每100ms收集一次数据
    isRecording.value = true;

    // 开始计时
    recordingTimer.value = setInterval(() => {
      recordingDuration.value++;
      if (recordingDuration.value >= MAX_RECORDING_TIME) {
        stopRecording();
      }
    }, 1000);

    console.log('✅ 录音已开始');

  } catch (error) {
    console.error('❌ 启动录音失败:', error);

    if (error.name === 'NotAllowedError') {
      emit('error', '请允许访问麦克风以使用智能语音功能');
    } else {
      emit('error', `启动录音失败: ${error.message}`);
    }
  }
};

// 停止录音
const stopRecording = () => {
  if (!isRecording.value) return;

  try {
    // 停止录音
    if (mediaRecorder.value && mediaRecorder.value.state === 'recording') {
      mediaRecorder.value.stop();
    }

    // 停止音频流
    if (audioStream.value) {
      audioStream.value.getTracks().forEach(track => track.stop());
    }

    // 清理定时器
    if (recordingTimer.value) {
      clearInterval(recordingTimer.value);
      recordingTimer.value = null;
    }

    isRecording.value = false;
    console.log('⏹️ 录音已停止');

  } catch (error) {
    console.error('❌ 停止录音失败:', error);
  }
};

// 处理音频
const processAudio = async () => {
  if (audioChunks.value.length === 0) {
    emit('error', '没有录制到音频数据');
    return;
  }

  isProcessing.value = true;

  try {
    console.log('🔄 开始处理音频...');

    // 合并音频块
    const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' });
    console.log(`📁 音频数据大小: ${(audioBlob.size / 1024).toFixed(2)} KB`);

    // 转换为Base64
    const base64Audio = await blobToBase64(audioBlob);

    // 发送到智能语音服务
    const response = await fetch(`${VOICE_RAG_SERVICE_URL}/api/voice/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        audio_data: base64Audio,
        format: 'webm'
      })
    });

    if (!response.ok) {
      throw new Error(`服务器返回错误: ${response.status}`);
    }

    const result = await response.json();
    console.log('📥 收到智能语音响应:', result);

    if (result.success) {
      // 发送转录结果
      if (result.transcription) {
        emit('transcription', result.transcription);
        console.log('📝 语音转录:', result.transcription);
      }

      // 发送AI回复
      if (result.response_text) {
        emit('response', {
          transcription: result.transcription,
          response: result.response_text,
          audioUrl: result.audio_url,
          processingTime: result.processing_time
        });
        console.log('🤖 AI回复:', result.response_text);

        // 自动播放语音回复
        if (result.audio_url) {
          playAudioResponse(result.audio_url);
        }
      }
    } else {
      throw new Error(result.error || '处理失败');
    }

  } catch (error) {
    console.error('❌ 音频处理失败:', error);
    emit('error', `处理失败: ${error.message}`);
  } finally {
    isProcessing.value = false;
  }
};

// Blob转Base64
const blobToBase64 = (blob) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
};

// 播放音频回复
const playAudioResponse = async (audioUrl) => {
  try {
    if (!audioUrl) return;

    const audio = new Audio(audioUrl);
    await audio.play();
    console.log('🔊 开始播放AI语音回复');

  } catch (error) {
    console.error('❌ 播放音频失败:', error);
  }
};

// 切换智能语音
const toggleSmartVoice = () => {
  if (!isServiceConnected.value) {
    emit('error', '智能语音服务未连接，请检查服务状态');
    return;
  }

  if (isProcessing.value) return;

  if (isRecording.value) {
    stopRecording();
  } else {
    startRecording();
  }
};

// 停止智能语音
const stopSmartVoice = () => {
  stopRecording();
};

// 清理资源
const cleanup = () => {
  if (isRecording.value) {
    stopRecording();
  }

  if (recordingTimer.value) {
    clearInterval(recordingTimer.value);
  }
};

// 生命周期
onMounted(async () => {
  console.log('🚀 智能语音按钮组件已挂载');
  await checkServiceStatus();

  // 定期检查服务状态
  setInterval(checkServiceStatus, 30000); // 每30秒检查一次
});

onUnmounted(() => {
  cleanup();
  console.log('🧹 智能语音按钮组件已卸载');
});
</script>

<style scoped>
.smart-voice-container {
  position: relative;
  display: inline-block;
}

/* 智能语音按钮 */
.smart-voice-button {
  padding: 8px 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.smart-voice-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.smart-voice-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.smart-voice-button.recording {
  background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
  animation: recordingPulse 1.5s infinite;
}

.smart-voice-button.processing {
  background: linear-gradient(135deg, #feca57 0%, #ff9ff3 100%);
  animation: processingPulse 2s infinite;
}

.smart-voice-button.connected {
  border: 2px solid #4fd1c5;
}

@keyframes recordingPulse {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 0 rgba(255, 107, 107, 0.4);
  }
  50% {
    transform: scale(1.05);
    box-shadow: 0 0 15px rgba(255, 107, 107, 0.7);
  }
}

@keyframes processingPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* 录音指示器 */
.smart-recording-indicator {
  position: absolute;
  bottom: 60px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  border: 1px solid #ff6b6b;
  border-radius: 12px;
  padding: 15px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  z-index: 100;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(5px);
  min-width: 200px;
}

.recording-waves {
  display: flex;
  gap: 3px;
}

.wave {
  width: 3px;
  height: 15px;
  background-color: #ff6b6b;
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
  text-align: center;
}

.stop-recording-button {
  background: rgba(255, 107, 107, 0.2);
  color: #ff6b6b;
  border: 1px solid rgba(255, 107, 107, 0.4);
  border-radius: 4px;
  padding: 5px 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 0.9em;
}

.stop-recording-button:hover {
  background: rgba(255, 107, 107, 0.3);
  border-color: rgba(255, 107, 107, 0.6);
}

/* 处理指示器 */
.processing-indicator {
  position: absolute;
  bottom: 60px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  border: 1px solid #feca57;
  border-radius: 12px;
  padding: 15px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  z-index: 100;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(5px);
  min-width: 200px;
}

.processing-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #feca57;
  border-top: 2px solid transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.processing-text {
  color: white;
  font-size: 0.9em;
  text-align: center;
}

/* 服务状态指示器 */
.service-status {
  position: absolute;
  top: -8px;
  right: -8px;
  background: rgba(0, 0, 0, 0.7);
  border-radius: 12px;
  padding: 2px 6px;
  font-size: 0.7em;
  color: white;
  display: flex;
  align-items: center;
  gap: 4px;
  z-index: 10;
}

.service-status.connected {
  background: rgba(79, 209, 197, 0.2);
  border: 1px solid rgba(79, 209, 197, 0.4);
}

.status-text {
  white-space: nowrap;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .smart-recording-indicator,
  .processing-indicator {
    min-width: 180px;
    padding: 12px 16px;
  }

  .service-status {
    display: none; /* 在小屏幕上隐藏状态文本 */
  }
}
</style>