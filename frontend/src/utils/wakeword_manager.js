/*
 * 简易唤醒词管理器（前端）
 * - 使用 Web Speech API (SpeechRecognition / webkitSpeechRecognition)
 * - 监听麦克风语音，检测包含指定唤醒词的片段后触发 onWake 回调
 * - 提供 start/stop/pause/resume 接口
 */

export class WakeWordManager {
  constructor(options = {}) {
    this.wakePhrase = (options.wakePhrase || '你好助手').toLowerCase();
    this.engine = options.engine || 'webspeech';
    this.lang = options.lang || 'zh-CN';
    this.cooldownMs = typeof options.cooldownMs === 'number' ? options.cooldownMs : 5000;
    this.onWake = typeof options.onWake === 'function' ? options.onWake : () => {};

    this.enabled = false;       // 是否启用（start后为true，stop后为false）
    this.isListening = false;   // 是否正在监听
    this._recognition = null;   // SpeechRecognition 实例
    this._lastWakeAt = 0;       // 上次触发唤醒的时间戳

    // 兼容性检测
    this._SR = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  async start() {
    if (this.enabled) return true;

    if (this.engine === 'webspeech') {
      if (!this._SR) {
        console.warn('WakeWordManager: 当前浏览器不支持 Web Speech API，自动降级为手动触发模式。');
        // 降级：仍标记为启用，但无法自动识别。可在页面上提供按钮/快捷键触发。
        this.enabled = true;
        return true;
      }

      try {
        // 初始化识别器
        this._recognition = new this._SR();
        this._recognition.lang = this.lang;
        this._recognition.continuous = true;
        this._recognition.interimResults = true;

        this._recognition.onresult = (event) => {
          try {
            const now = Date.now();
            for (let i = event.resultIndex; i < event.results.length; i++) {
              const res = event.results[i];
              // 终稿或中间稿都检查一次，提升唤醒成功率
              const transcript = (res[0]?.transcript || '').toLowerCase();
              if (!transcript) continue;

              if (this._containsWakePhrase(transcript)) {
                if (now - this._lastWakeAt >= this.cooldownMs) {
                  this._lastWakeAt = now;
                  // 触发回调
                  try { this.onWake(); } catch (_) {}
                }
              }
            }
          } catch (err) {
            console.warn('WakeWordManager onresult 处理异常:', err);
          }
        };

        this._recognition.onerror = (e) => {
          // 常见错误：no-speech, audio-capture, not-allowed（权限被拒绝）
          console.warn('WakeWordManager 识别错误:', e?.error || e);
        };

        this._recognition.onend = () => {
          // 若仍处于启用状态且非手动暂停，则自动重启，保持常驻监听
          if (this.enabled && this.isListening) {
            // 少许延迟避免快速重启导致崩溃
            setTimeout(() => {
              try { this._recognition?.start(); } catch (_) {}
            }, 250);
          }
        };

        // 开始监听
        this._startRecognitionSafe();

        this.enabled = true;
        return true;
      } catch (err) {
        console.error('WakeWordManager 启动失败:', err);
        this.enabled = false;
        return false;
      }
    }

    // 其它引擎暂不支持，直接标记为启用（无自动识别能力）
    console.warn(`WakeWordManager: 未知引擎 ${this.engine}，已启用但不进行自动识别。`);
    this.enabled = true;
    return true;
  }

  async stop() {
    this.enabled = false;
    this.isListening = false;
    try {
      this._recognition?.stop();
    } catch (_) {}
    this._recognition = null;
  }

  pause() {
    // 暂停仅停止当前监听，不改变 enabled 状态
    if (!this._recognition) return;
    this.isListening = false;
    try { this._recognition.stop(); } catch (_) {}
  }

  resume() {
    if (!this.enabled) return;
    if (!this._recognition) return;
    this._startRecognitionSafe();
  }

  setWakePhrase(phrase) {
    this.wakePhrase = String(phrase || '').toLowerCase();
  }

  setLang(lang) {
    this.lang = lang || 'zh-CN';
    if (this._recognition) {
      try { this._recognition.lang = this.lang; } catch (_) {}
    }
  }

  _containsWakePhrase(text) {
    if (!text) return false;
    const t = text.toLowerCase().trim();
    // 简单包含匹配，必要时可拓展为正则或模糊匹配
    return t.includes(this.wakePhrase);
  }

  _startRecognitionSafe() {
    if (!this._recognition) return;
    try {
      this._recognition.start();
      this.isListening = true;
    } catch (err) {
      // 调用 start() 可能在正在运行时抛错，做一次兜底重启
      try {
        this._recognition.stop();
      } catch (_) {}
      setTimeout(() => {
        try { this._recognition?.start(); this.isListening = true; } catch (_) {}
      }, 200);
    }
  }
}