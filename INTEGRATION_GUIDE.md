# 🎤 智能语音按钮集成指南

## 📋 快速集成步骤

### 1. 确保服务运行

首先确保语音RAG服务正在运行：

```bash
# 在项目根目录下运行
python voice_rag_service.py
```

你应该看到类似这样的输出：
```
🎤 语音RAG集成服务
==================================================
🌐 服务地址: http://0.0.0.0:8087
🤖 Whisper模型: base
💻 运行设备: cpu
INFO:     Uvicorn running on http://0.0.0.0:8087
```

### 2. 在QAPanel中集成智能语音按钮

#### 方法A：添加独立的智能语音按钮（推荐）

在你的 `QAPanel.vue` 文件中添加智能语音按钮：

```vue
<template>
  <div class="qa-panel-container">
    <!-- 现有内容保持不变 -->
    <div class="panel-title">
      <!-- 现有标题内容 -->
    </div>

    <div class="qa-content">
      <!-- 现有聊天内容 -->
    </div>

    <div class="chat-input-area">
      <input type="text" v-model="userInput" @keyup.enter="sendMessage" class="chat-input">

      <!-- 保留原有语音按钮 -->
      <button @click="toggleVoiceRecognition" class="voice-button" :class="{ 'recording': isRecording }">
        <span v-if="isRecording">🎙️</span>
        <span v-else>🎤</span>
      </button>

      <!-- 新增智能语音按钮 -->
      <SmartVoiceButton
        @transcription="handleTranscription"
        @response="handleSmartVoiceResponse"
        @error="handleSmartVoiceError"
      />

      <button @click="sendMessage" class="send-button">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import SmartVoiceButton from './SmartVoiceButton.vue'; // 引入智能语音按钮

// 现有的响应式数据保持不变
const userInput = ref('');
const messages = ref([]);
// ... 其他现有代码

// 处理智能语音转录结果
const handleTranscription = (transcription) => {
  console.log('📝 语音识别结果:', transcription);
  userInput.value = transcription; // 将识别结果填入输入框
};

// 处理智能语音回复
const handleSmartVoiceResponse = (result) => {
  console.log('🤖 智能语音回复:', result);

  // 添加用户消息
  messages.value.push({
    id: Date.now(),
    sender: 'user',
    text: result.transcription
  });

  // 添加AI回复
  messages.value.push({
    id: Date.now() + 1,
    sender: 'ai',
    text: result.response
  });

  console.log(`⚡ 处理时间: ${result.processingTime.toFixed(2)}s`);
};

// 处理智能语音错误
const handleSmartVoiceError = (error) => {
  console.error('❌ 智能语音错误:', error);

  // 显示错误消息
  messages.value.push({
    id: Date.now(),
    sender: 'system',
    text: `智能语音错误: ${error}`
  });
};

// 现有的其他函数保持不变
// ...
</script>
```

#### 方法B：简单的JavaScript集成（如果不想修改Vue文件）

在你的 `QAPanel.vue` 文件的 `<script setup>` 部分末尾添加：

```javascript
// 在现有代码末尾添加
onMounted(async () => {
  // 现有的onMounted代码...

  // 添加智能语音功能
  await initSmartVoice();
});

// 初始化智能语音功能
const initSmartVoice = async () => {
  // 检查服务状态
  try {
    const response = await fetch('http://localhost:8087/api/health');
    if (response.ok) {
      console.log('✅ 智能语音服务已连接');
      addSmartVoiceButton();
    } else {
      console.warn('⚠️ 智能语音服务不可用');
    }
  } catch (error) {
    console.error('❌ 智能语音服务连接失败:', error);
  }
};

// 添加智能语音按钮
const addSmartVoiceButton = () => {
  // 创建智能语音按钮
  const smartVoiceBtn = document.createElement('button');
  smartVoiceBtn.innerHTML = '🧠';
  smartVoiceBtn.className = 'smart-voice-btn';
  smartVoiceBtn.title = '智能语音对话';
  smartVoiceBtn.style.cssText = `
    padding: 8px 12px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    margin-left: 5px;
    font-size: 16px;
  `;

  // 添加点击事件
  smartVoiceBtn.addEventListener('click', handleSmartVoiceClick);

  // 插入到现有语音按钮旁边
  const voiceButton = document.querySelector('.voice-button');
  if (voiceButton && voiceButton.parentNode) {
    voiceButton.parentNode.insertBefore(smartVoiceBtn, voiceButton.nextSibling);
    console.log('✅ 智能语音按钮已添加');
  }
};

// 处理智能语音点击
const handleSmartVoiceClick = async () => {
  // 这里可以调用你创建的语音RAG服务
  console.log('🎤 智能语音功能待实现...');
  alert('智能语音功能正在开发中，请使用SmartVoiceButton.vue组件获得完整功能');
};
```

### 3. 测试集成效果

1. **启动前端应用**：
   ```bash
   npm run serve
   # 或
   npm run dev
   ```

2. **打开浏览器控制台**（F12），查看日志输出

3. **点击智能语音按钮**：
   - 🧠 按钮应该显示绿色边框（表示服务已连接）
   - 点击后应该开始录音（显示录音指示器）
   - 说话后停止录音，等待AI回复

### 4. 预期的工作流程

```
用户点击🧠按钮
    ↓
开始录音（显示录音指示器）
    ↓
用户说话："我什么时候玩手机了？"
    ↓
停止录音，显示处理指示器
    ↓
语音RAG服务处理：
  - Whisper识别语音
  - 意图分类（活动查询）
  - 调用activity_ui.py API
  - 生成语音回复
    ↓
前端显示对话：
  - 用户消息："我什么时候玩手机了？"
  - AI回复："根据记录，你今天下午2点到3点玩了手机..."
    ↓
自动播放AI语音回复
```

## 🔧 故障排除

### 问题1：智能语音按钮显示红色状态

**原因**：语音RAG服务未启动或不可用

**解决**：
```bash
# 检查服务是否运行
python voice_rag_service.py

# 检查服务状态
curl http://localhost:8087/api/health
```

### 问题2：点击按钮没有反应

**原因**：可能是浏览器权限问题

**解决**：
1. 确保浏览器允许麦克风访问
2. 检查浏览器控制台是否有错误信息
3. 尝试在HTTPS环境下运行

### 问题3：语音识别不准确

**解决**：
1. 确保在安静的环境中说话
2. 说话清晰，语速适中
3. 可以在 `voice_rag_service.py` 中调整Whisper模型：
   ```python
   WHISPER_MODEL = "small"  # 更准确但稍慢
   ```

### 问题4：处理速度慢

**解决**：
1. 使用更小的Whisper模型：
   ```python
   WHISPER_MODEL = "tiny"  # 更快但准确率稍低
   ```
2. 如果有GPU，启用CUDA加速：
   ```python
   WHISPER_DEVICE = "cuda"
   ```

## 📊 功能对比

| 功能 | 原始语音按钮🎤 | 智能语音按钮🧠 |
|------|----------------|----------------|
| 语音识别 | Google API/Whisper | Whisper (本地) |
| 响应速度 | 慢 | 快 (3-5秒) |
| 智能理解 | 无 | 意图识别 |
| 自动回复 | 无 | AI自动回复 |
| 语音播放 | 无 | 自动播放 |
| 离线使用 | 否 | 是 |

## 🎯 支持的查询示例

- **时间活动查询**：
  - "我什么时候玩手机了？"
  - "今天我睡了多久？"
  - "昨天我都做了什么？"

- **活动统计查询**：
  - "我今天工作了多长时间？"
  - "最近我的作息规律如何？"
  - "我昨天喝水了几次？"

- **实时查询**：
  - "我现在在做什么？"
  - "帮我分析一下我的时间分配"

## 🚀 下一步优化

1. **添加更多语音命令**
2. **支持多语言识别**
3. **添加语音唤醒词**
4. **集成更多AI功能**

---

现在你可以选择上述任一方法来集成智能语音功能。推荐使用方法A（SmartVoiceButton.vue组件），因为它提供了完整的UI和功能。